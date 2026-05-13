"""
/wallet — customer-facing portal page.

Shows the logged-in customer their wallet balance, available balance, and
the last 20 transactions. Falls back to a friendly empty state if no wallet
is linked to the user.
"""

import frappe
from frappe import _
from frappe.utils import flt


no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/wallet"
        raise frappe.Redirect

    customer = _customer_for_user(frappe.session.user)
    context.no_cache = 1
    context.show_sidebar = True
    context.title = _("My Wallet")
    context.customer = customer

    if not customer:
        context.wallet = None
        context.transactions = []
        context.message = _(
            "No customer is linked to your user account. "
            "Please contact support."
        )
        return context

    wallet = frappe.db.get_value(
        "Customer Wallet",
        {"customer": customer},
        ["name", "currency", "current_balance", "held_amount", "status"],
        as_dict=True,
    )

    if not wallet:
        context.wallet = None
        context.transactions = []
        context.message = _("Your wallet hasn't been activated yet.")
        return context

    wallet["available"] = flt(wallet.current_balance) - flt(wallet.held_amount)
    context.wallet = wallet

    context.transactions = frappe.get_all(
        "Wallet Transaction",
        filters={"customer": customer, "wallet": wallet.name},
        fields=["name", "transaction_type", "amount", "balance_after",
                "status", "posting_datetime", "remarks", "reference_doctype",
                "reference_name", "currency"],
        order_by="posting_datetime DESC",
        limit_page_length=20,
    )

    # Inject the active brand for this customer's Company into the page
    try:
        from alphax_wallet.alphax_wallet.doctype.wallet_brand.wallet_brand import (
            get_brand_for_customer, get_active_brand_css,
        )
        context.brand = get_brand_for_customer(customer)
        context.theme_css = palette_to_css(context.brand)
    except Exception:
        context.brand = None
        context.theme_css = ""

    return context


def palette_to_css(brand: dict) -> str:
    """Inline CSS for the portal — converts brand palette to :root vars."""
    if not brand:
        return ""
    from alphax_wallet.alphax_wallet.palette_utils import palette_to_css_variables
    return palette_to_css_variables(brand.get("palette") or {})


def _customer_for_user(user):
    return frappe.db.get_value("Contact", {"user": user}, "customer") \
        or frappe.db.get_value("Customer", {"linked_user": user}, "name")
