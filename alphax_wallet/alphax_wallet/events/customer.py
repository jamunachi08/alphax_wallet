"""Customer hooks: auto-create wallet on first save."""

import frappe


def auto_create_wallet(doc, method=None):
    """after_insert hook on Customer."""
    settings = frappe.get_single("Wallet Settings")
    if not settings.auto_create_wallet_on_customer:
        return

    # Resolve currency in order: Wallet Settings → company base → customer's own
    company_currency = None
    if settings.default_company:
        company_currency = frappe.db.get_value(
            "Company", settings.default_company, "default_currency"
        )

    currency = (
        settings.default_currency
        or company_currency
        # Customer.default_currency intentionally NOT used here — many imported
        # customers have it pre-set to a non-base currency (e.g., INR), which
        # would cause every wallet to be created in the wrong currency.
        # If you genuinely need per-customer currency, set it via the API
        # explicitly or create the wallet manually.
    )
    if not currency:
        # Don't block customer creation — just skip auto-wallet
        frappe.log_error(
            title="AlphaX Wallet: cannot auto-create wallet (no currency resolved)",
            message=f"Customer {doc.name} saved but no currency could be determined.",
        )
        return

    if frappe.db.exists("Customer Wallet", {"customer": doc.name, "currency": currency}):
        return

    wallet = frappe.get_doc({
        "doctype": "Customer Wallet",
        "customer": doc.name,
        "currency": currency,
        "status": "Active",
    })
    wallet.insert(ignore_permissions=True)
