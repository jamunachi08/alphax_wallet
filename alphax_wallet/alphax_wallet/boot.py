"""
boot_session hook — runs once per browser session.
Attaches the active Wallet Brand to frappe.boot so client JS can apply it
without a round-trip.

The brand is resolved by the user's current Company (frappe.defaults).
"""

import frappe

from alphax_wallet.alphax_wallet.doctype.wallet_brand.wallet_brand import (
    get_active_brand,
)


def boot_session(bootinfo):
    try:
        brand = get_active_brand()
        bootinfo["alphax_wallet_brand"] = brand
    except Exception:
        # Never block the bootstrap
        frappe.log_error(
            title="AlphaX Wallet: boot_session brand load failed",
            message=frappe.get_traceback(),
        )
        bootinfo["alphax_wallet_brand"] = None
