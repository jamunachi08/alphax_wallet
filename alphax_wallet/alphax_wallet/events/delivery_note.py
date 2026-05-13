"""
Delivery Note hook.

When the booking is actually delivered (e.g., the hotel night is consumed),
recognise the deferred revenue:

    Dr. Deferred Revenue
    Cr. Booking Revenue (net of commission)
    Cr. Tax Payable (separately, if applicable)

For complex setups, prefer ERPNext's built-in Deferred Revenue feature on the
Item master. This hook is the simpler manual fallback.
"""

import frappe
from frappe import _
from frappe.utils import flt


def recognise_revenue(doc, method=None):
    """on_submit hook on Delivery Note. Best-effort, never blocks delivery."""
    settings = frappe.get_single("Wallet Settings")
    if not settings.deferred_revenue_account:
        return  # not configured — skip

    # Only act on Delivery Notes that came from a wallet-paid Sales Order
    so_names = list({d.against_sales_order for d in (doc.items or []) if d.get("against_sales_order")})
    if not so_names:
        return

    wallet_paid_sos = frappe.get_all(
        "Sales Order",
        filters={"name": ("in", so_names), "use_wallet_payment": 1},
        pluck="name",
    )
    if not wallet_paid_sos:
        return

    try:
        _post_revenue_recognition(doc, wallet_paid_sos, settings)
    except Exception:
        frappe.log_error(
            title="AlphaX Wallet: revenue recognition failed",
            message=frappe.get_traceback(),
        )


def _post_revenue_recognition(delivery_note, sales_orders, settings):
    """
    Create one JE per Delivery Note that recognises the deferred revenue.
    Idempotent via custom remark check.
    """
    revenue_account = _get_default_income_account(delivery_note.company)
    if not revenue_account:
        return

    remark = f"AlphaX Wallet — Revenue recognition for DN {delivery_note.name}"

    if frappe.db.exists("Journal Entry", {"user_remark": remark, "docstatus": 1}):
        return

    amount_to_recognise = flt(delivery_note.grand_total)

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": delivery_note.company,
        "posting_date": delivery_note.posting_date,
        "user_remark": remark,
        "accounts": [
            {
                "account": settings.deferred_revenue_account,
                "debit_in_account_currency": amount_to_recognise,
                "reference_type": "Delivery Note",
                "reference_name": delivery_note.name,
            },
            {
                "account": revenue_account,
                "credit_in_account_currency": amount_to_recognise,
                "reference_type": "Delivery Note",
                "reference_name": delivery_note.name,
            },
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()


def _get_default_income_account(company):
    return frappe.db.get_value("Company", company, "default_income_account") \
        or frappe.db.get_value("Account", {
            "company": company,
            "root_type": "Income",
            "is_group": 0,
        }, "name")
