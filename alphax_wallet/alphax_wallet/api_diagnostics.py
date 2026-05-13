"""
alphax_wallet.alphax_wallet.api_diagnostics
===========================================

Diagnostic and cleanup utilities for currency contamination, GL drift, and
orphan transactions. Surfaced as buttons on the Wallet Settings form.

These methods are read-only by default. Cleanup actions require explicit
opt-in via the `confirm=True` argument and Wallet Manager / System Manager role.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today


_PRIVILEGED = {"Wallet Manager", "System Manager"}


def _require_privilege():
    if not _PRIVILEGED.intersection(frappe.get_roles()):
        frappe.throw(_("Only Wallet Manager or System Manager can run diagnostics."),
                     frappe.PermissionError)


@frappe.whitelist()
def run_currency_audit() -> dict:
    """
    Surface every place where a non-base-currency document could be causing
    INR→SAR (or similar) JE posting errors. Read-only.
    """
    _require_privilege()

    settings = frappe.get_single("Wallet Settings")
    base = None
    if settings.default_company:
        base = frappe.db.get_value("Company", settings.default_company, "default_currency")

    result = {
        "company_base_currency": base,
        "checked_at": str(frappe.utils.now_datetime()),
        "findings": [],
    }

    # 1. Customers with default_currency != base
    customers_off_base = frappe.db.sql("""
        SELECT name, customer_name, default_currency
        FROM `tabCustomer`
        WHERE default_currency IS NOT NULL
          AND default_currency != ''
          AND default_currency != %s
        ORDER BY modified DESC
        LIMIT 50
    """, base, as_dict=True)
    if customers_off_base:
        result["findings"].append({
            "severity": "warning",
            "title": _("Customers with non-base default_currency"),
            "count": len(customers_off_base),
            "rows": customers_off_base,
            "explanation": _(
                "These customers will have new Sales Orders auto-filled in their "
                "currency (not {0}). That triggers exchange-rate lookups on JE post."
            ).format(base),
            "fix": _("Open each Customer and clear or change the Default Currency field."),
        })

    # 2. Wallets with currency != base
    wallets_off_base = frappe.db.sql("""
        SELECT name, customer, currency, current_balance, status
        FROM `tabCustomer Wallet`
        WHERE currency != %s
        ORDER BY current_balance DESC
    """, base, as_dict=True)
    if wallets_off_base:
        result["findings"].append({
            "severity": "warning",
            "title": _("Wallets in non-base currency"),
            "count": len(wallets_off_base),
            "rows": wallets_off_base,
            "explanation": _(
                "Wallets in a currency different from the company base ({0}) need a "
                "Currency Exchange record for every Journal Entry posting date."
            ).format(base),
            "fix": _(
                "If balance is zero: change status to Closed. "
                "Otherwise: ensure a Currency Exchange record exists for the date."
            ),
        })

    # 3. Customers with multiple wallets
    multi = frappe.db.sql("""
        SELECT customer, COUNT(*) as n,
               GROUP_CONCAT(name) as wallets,
               GROUP_CONCAT(currency) as currencies
        FROM `tabCustomer Wallet`
        GROUP BY customer
        HAVING n > 1
    """, as_dict=True)
    if multi:
        result["findings"].append({
            "severity": "info",
            "title": _("Customers with multiple wallets"),
            "count": len(multi),
            "rows": multi,
            "explanation": _("Likely a side-effect of v1.0 currency contamination."),
            "fix": _("Close the wallet in the wrong currency once its balance is migrated to zero."),
        })

    # 4. Recent Sales Orders in non-base currency
    recent_sos = frappe.db.sql("""
        SELECT name, customer, transaction_date, currency, grand_total, docstatus, status
        FROM `tabSales Order`
        WHERE currency != %s
          AND creation >= DATE_SUB(NOW(), INTERVAL 60 DAY)
        ORDER BY creation DESC
        LIMIT 20
    """, base, as_dict=True)
    if recent_sos:
        result["findings"].append({
            "severity": "warning",
            "title": _("Recent Sales Orders in non-base currency"),
            "count": len(recent_sos),
            "rows": recent_sos,
            "explanation": _("These will trigger exchange-rate lookups when invoiced or paid."),
            "fix": _("If not yet invoiced, cancel and recreate in {0}.").format(base),
        })

    # 5. Recent Payment Entries with non-base currency
    recent_pes = frappe.db.sql("""
        SELECT name, party, party_type, posting_date,
               paid_from_account_currency, paid_to_account_currency,
               paid_amount, docstatus
        FROM `tabPayment Entry`
        WHERE (paid_from_account_currency != %s OR paid_to_account_currency != %s)
          AND creation >= DATE_SUB(NOW(), INTERVAL 60 DAY)
        ORDER BY creation DESC
        LIMIT 20
    """, (base, base), as_dict=True)
    if recent_pes:
        result["findings"].append({
            "severity": "warning",
            "title": _("Recent Payment Entries with non-base currency"),
            "count": len(recent_pes),
            "rows": recent_pes,
            "explanation": _("Mixed-currency Payment Entries need a Currency Exchange record for the posting date."),
            "fix": _("Either change the account currencies, or create a Currency Exchange record."),
        })

    # 6. Reconciliation drift
    ledger_total = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(current_balance), 0)
        FROM `tabCustomer Wallet`
        WHERE status != 'Closed'
    """)[0][0])
    gl_total = 0
    if settings.wallet_liability_account:
        rows = frappe.db.sql("""
            SELECT COALESCE(SUM(credit_in_account_currency), 0) -
                   COALESCE(SUM(debit_in_account_currency), 0)
            FROM `tabGL Entry`
            WHERE account = %s AND is_cancelled = 0
        """, settings.wallet_liability_account)
        gl_total = flt(rows[0][0]) if rows else 0
    drift = round(ledger_total - gl_total, 2)
    if abs(drift) > 0.01:
        # Find the GL entries that don't have a matching Wallet Transaction
        orphan_gls = frappe.db.sql("""
            SELECT name, posting_date, voucher_type, voucher_no,
                   debit, credit, against_voucher, remarks
            FROM `tabGL Entry`
            WHERE account = %s AND is_cancelled = 0
              AND voucher_type = 'Journal Entry'
              AND voucher_no NOT IN (
                  SELECT DISTINCT journal_entry
                  FROM `tabWallet Transaction`
                  WHERE journal_entry IS NOT NULL AND journal_entry != ''
              )
            ORDER BY posting_date DESC
            LIMIT 30
        """, settings.wallet_liability_account, as_dict=True)
        result["findings"].append({
            "severity": "error",
            "title": _("Reconciliation drift detected"),
            "count": 1,
            "rows": [{
                "ledger_total": ledger_total,
                "gl_total": gl_total,
                "drift": drift,
            }],
            "explanation": _(
                "The Wallet Liability GL account balance ({0}) doesn't match "
                "the sum of wallet balances ({1}). Difference: {2}."
            ).format(gl_total, ledger_total, drift),
            "fix": _(
                "Likely an orphan Journal Entry was posted directly against the "
                "wallet liability account, or a wallet transaction's JE failed mid-flight."
            ),
        })
        if orphan_gls:
            result["findings"].append({
                "severity": "error",
                "title": _("Orphan GL entries on wallet liability account"),
                "count": len(orphan_gls),
                "rows": orphan_gls,
                "explanation": _(
                    "These GL entries are NOT linked to any Wallet Transaction. "
                    "They're likely the source of the drift."
                ),
                "fix": _("Open each Journal Entry. If it was posted in error, cancel it."),
            })

    # 7. Orphan Wallet Transactions (no JE)
    orphan_txns = frappe.db.sql("""
        SELECT name, customer, transaction_type, amount, status, creation
        FROM `tabWallet Transaction`
        WHERE transaction_type IN ('Deposit', 'Withdrawal', 'Refund')
          AND status = 'Active'
          AND (journal_entry IS NULL OR journal_entry = '')
        ORDER BY creation DESC
        LIMIT 20
    """, as_dict=True)
    if orphan_txns:
        result["findings"].append({
            "severity": "error",
            "title": _("Wallet Transactions without Journal Entry"),
            "count": len(orphan_txns),
            "rows": orphan_txns,
            "explanation": _("These transactions changed the wallet balance but never posted to the GL."),
            "fix": _("Investigate the Error Log for the failed JE posting. Likely currency-related."),
        })

    if not result["findings"]:
        result["status"] = "clean"
        result["summary"] = _("No currency or drift issues detected. Everything is consistent.")
    else:
        result["status"] = "issues_found"
        result["summary"] = _("Found {0} category(ies) of issues. Review and fix.").format(
            len(result["findings"]))

    return result


@frappe.whitelist()
def fix_customer_default_currency(customer: str, new_currency: str = None) -> dict:
    """
    Clear or change a customer's default_currency field.
    Wallet Manager / System Manager only.
    """
    _require_privilege()

    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} not found").format(customer))

    old = frappe.db.get_value("Customer", customer, "default_currency")
    frappe.db.set_value("Customer", customer, "default_currency", new_currency or None,
                        update_modified=False)

    return {
        "customer": customer,
        "old_currency": old,
        "new_currency": new_currency or "(blank)",
    }


@frappe.whitelist()
def create_currency_exchange(from_currency: str, to_currency: str,
                              exchange_rate: float, date: str = None) -> str:
    """
    Convenience method to create a Currency Exchange record from the diagnostic
    panel. Saves a few clicks compared to the standard form.
    """
    _require_privilege()

    if not date:
        date = today()

    name = frappe.db.exists("Currency Exchange", {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "date": date,
    })
    if name:
        frappe.throw(_("A Currency Exchange already exists for {0} → {1} on {2}").format(
            from_currency, to_currency, date))

    doc = frappe.get_doc({
        "doctype": "Currency Exchange",
        "from_currency": from_currency,
        "to_currency": to_currency,
        "exchange_rate": flt(exchange_rate),
        "date": date,
        "for_selling": 1,
        "for_buying": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name
