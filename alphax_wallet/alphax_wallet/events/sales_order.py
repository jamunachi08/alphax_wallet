"""
Sales Order hooks — place a wallet hold when 'Pay using Wallet' is checked.
The hold reserves the funds; on cancellation we release them. The actual
spend happens later, when the linked Sales Invoice is submitted (capture).
"""

import frappe
from frappe import _


def place_wallet_hold(doc, method=None):
    """on_submit hook on Sales Order."""
    if not getattr(doc, "use_wallet_payment", 0):
        return
    if doc.wallet_hold_reference:
        return  # already held, idempotent

    from alphax_wallet.alphax_wallet import wallet_engine

    txn = wallet_engine.hold(
        customer=doc.customer,
        amount=doc.grand_total,
        reference_doctype="Sales Order",
        reference_name=doc.name,
        # Currency intentionally not passed — the engine resolves to the
        # customer's existing wallet, which is the safer default than
        # silently auto-creating a parallel wallet in doc.currency.
        idempotency_key=f"SO-HOLD:{doc.name}",
        remarks=_("Hold for Sales Order {0}").format(doc.name),
    )
    doc.db_set("wallet_hold_reference", txn.name)
    frappe.msgprint(
        _("Wallet hold of {0} placed for Sales Order {1}")
        .format(frappe.utils.fmt_money(doc.grand_total, currency=doc.currency), doc.name),
        alert=True, indicator="green",
    )


def release_wallet_hold(doc, method=None):
    """on_cancel hook on Sales Order — release the previously-placed hold."""
    if not doc.wallet_hold_reference:
        return

    from alphax_wallet.alphax_wallet import wallet_engine
    wallet_engine.release(
        hold_transaction=doc.wallet_hold_reference,
        idempotency_key=f"SO-RELEASE:{doc.name}",
        remarks=_("Released because Sales Order {0} was cancelled").format(doc.name),
    )
