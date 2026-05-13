"""
Scheduled jobs registered in hooks.py.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, add_days


# ----------------------------------------------------------------------------
# Daily — wallet liability reconciliation
# ----------------------------------------------------------------------------

@frappe.whitelist()
def reconcile_wallet_liability():
    """
    Compare:
      ledger_total = SUM(Customer Wallet.current_balance)
      gl_total     = balance of the Wallet Liability GL account

    They must be equal. If they're not, log a Reconciliation Drift error and
    email the configured recipients.

    Returns a dict for the UI button on Wallet Settings.
    """
    settings = frappe.get_single("Wallet Settings")

    ledger_total = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(current_balance), 0) FROM `tabCustomer Wallet` WHERE status != 'Closed'"
    )[0][0])

    gl_total = 0
    if settings.wallet_liability_account:
        # Liability account: net credit balance is the liability owed
        rows = frappe.db.sql("""
            SELECT
                COALESCE(SUM(credit_in_account_currency), 0) -
                COALESCE(SUM(debit_in_account_currency), 0) as bal
            FROM `tabGL Entry`
            WHERE account = %s AND is_cancelled = 0
        """, settings.wallet_liability_account)
        gl_total = flt(rows[0][0]) if rows else 0

    diff = round(ledger_total - gl_total, 2)
    in_sync = abs(diff) < 0.01

    result = {
        "ledger_total": ledger_total,
        "gl_total": gl_total,
        "difference": diff,
        "in_sync": in_sync,
        "checked_at": str(now_datetime()),
    }

    if not in_sync:
        _alert_reconciliation_drift(settings, result)

    return result


def _alert_reconciliation_drift(settings, result):
    frappe.log_error(
        title="AlphaX Wallet: reconciliation drift",
        message=frappe.as_json(result),
    )
    recipients = (settings.reconciliation_email_recipients or "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]
    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject="[AlphaX Wallet] Reconciliation drift detected",
            message=f"""
            <p>The wallet ledger and the Wallet Liability GL account do not match.</p>
            <ul>
                <li><b>Ledger total:</b> {result['ledger_total']}</li>
                <li><b>GL total:</b> {result['gl_total']}</li>
                <li><b>Difference:</b> {result['difference']}</li>
                <li><b>Checked at:</b> {result['checked_at']}</li>
            </ul>
            <p>Investigate immediately — this usually means a Journal Entry was
            posted manually against the wallet liability account, or a wallet
            transaction failed to post its JE.</p>
            """,
        )


# ----------------------------------------------------------------------------
# Daily — expire stale holds
# ----------------------------------------------------------------------------

def expire_stale_holds():
    """Auto-release any Active hold whose expires_at has passed."""
    expired = frappe.get_all(
        "Wallet Transaction",
        filters={
            "transaction_type": "Hold",
            "status": "Active",
            "expires_at": ("<", now_datetime()),
        },
        pluck="name",
    )
    if not expired:
        return

    from alphax_wallet.alphax_wallet import wallet_engine
    for txn_name in expired:
        try:
            wallet_engine.release(
                hold_transaction=txn_name,
                idempotency_key=f"AUTO-EXPIRE:{txn_name}",
                remarks=_("Auto-released by scheduler (hold expired)"),
            )
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet: auto-expire failed for {txn_name}",
                message=frappe.get_traceback(),
            )


# ----------------------------------------------------------------------------
# Hourly — process pending top-up requests below threshold
# ----------------------------------------------------------------------------

def process_pending_topup_requests():
    """
    Auto-approve top-up requests that are below the approval threshold.
    Gives small/recurring top-ups a frictionless path.
    """
    settings = frappe.get_single("Wallet Settings")
    threshold = flt(settings.topup_approval_threshold)
    if threshold <= 0:
        return

    pending = frappe.get_all(
        "Wallet Topup Request",
        filters={"status": "Pending", "docstatus": 0, "amount": ("<", threshold)},
        pluck="name",
    )
    for req_name in pending:
        try:
            req = frappe.get_doc("Wallet Topup Request", req_name)
            req.approve()
            req.submit()
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet: auto-approve failed for {req_name}",
                message=frappe.get_traceback(),
            )


# ----------------------------------------------------------------------------
# Weekly — supplier settlement statements
# ----------------------------------------------------------------------------

def send_supplier_settlement_statements():
    """
    Email every active supplier their settlement statement for the past week.
    Uses the standard Supplier email_id; silently skips suppliers without one.
    """
    end = now_datetime()
    start = add_days(end, -7)

    suppliers = frappe.get_all(
        "Supplier",
        filters={"disabled": 0},
        fields=["name", "supplier_name", "email_id"],
    )
    for s in suppliers:
        if not s.email_id:
            continue
        rows = frappe.db.sql("""
            SELECT pi.name, pi.posting_date, pi.grand_total, pi.status
            FROM `tabPurchase Invoice` pi
            WHERE pi.supplier = %s
              AND pi.posting_date BETWEEN %s AND %s
              AND pi.docstatus = 1
            ORDER BY pi.posting_date
        """, (s.name, start, end), as_dict=True)
        if not rows:
            continue

        body = "<h3>Settlement Statement</h3><table border=1 cellpadding=4><tr>"
        body += "<th>Invoice</th><th>Date</th><th>Amount</th><th>Status</th></tr>"
        for r in rows:
            body += f"<tr><td>{r.name}</td><td>{r.posting_date}</td><td>{r.grand_total}</td><td>{r.status}</td></tr>"
        body += "</table>"

        try:
            frappe.sendmail(
                recipients=[s.email_id],
                subject=f"Weekly Settlement Statement — {s.supplier_name}",
                message=body,
            )
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet: settlement email failed for {s.name}",
                message=frappe.get_traceback(),
            )
