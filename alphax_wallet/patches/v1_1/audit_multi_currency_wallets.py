"""
v1.1 — Report any customer who has wallets in multiple currencies.

This is a side-effect of the v1.0 bug where Customer.default_currency could
cause an auto-created wallet to be in a non-base currency. The new code in
v1.1 prevents new parallel wallets, but this patch surfaces existing ones
so the admin can decide whether to merge or close them.

The patch DOES NOT modify any data — it only writes to Error Log so the
admin sees the issue.
"""

import frappe


def execute():
    rows = frappe.db.sql("""
        SELECT customer, COUNT(*) as n,
               GROUP_CONCAT(currency ORDER BY currency) as currencies
        FROM `tabCustomer Wallet`
        GROUP BY customer
        HAVING n > 1
    """, as_dict=True)

    if not rows:
        return

    settings = frappe.get_single("Wallet Settings")
    base = None
    if settings.default_company:
        base = frappe.db.get_value(
            "Company", settings.default_company, "default_currency"
        )

    message_lines = [
        f"Found {len(rows)} customer(s) with wallets in multiple currencies.",
        f"Company base currency: {base or 'unknown'}.",
        "",
        "Review each customer and decide whether to close the wallets in non-base currencies.",
        "Existing balances must be migrated manually via wallet_engine.reverse() before deletion.",
        "",
        "Customer | Currencies",
        "-" * 60,
    ]
    for r in rows:
        message_lines.append(f"{r.customer} | {r.currencies}")

    frappe.log_error(
        title="AlphaX Wallet v1.1: customers with multiple wallets",
        message="\n".join(message_lines),
    )
