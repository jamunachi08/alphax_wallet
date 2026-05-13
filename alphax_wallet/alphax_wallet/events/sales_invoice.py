"""
Sales Invoice hooks — capture the wallet hold placed by the source Sales Order.

If the invoice is created standalone (no SO) and 'use_wallet_payment' is ticked,
we deduct directly from the wallet via a Withdrawal.
"""

import frappe
from frappe import _


def capture_wallet_hold(doc, method=None):
    """on_submit hook on Sales Invoice."""
    if not getattr(doc, "use_wallet_payment", 0):
        return

    from alphax_wallet.alphax_wallet import wallet_engine

    # Find the upstream Sales Order(s) and their holds
    so_names = list({d.sales_order for d in (doc.items or []) if d.get("sales_order")})

    if so_names:
        for so in so_names:
            hold_txn = frappe.db.get_value("Sales Order", so, "wallet_hold_reference")
            if not hold_txn:
                continue
            wallet_engine.capture(
                hold_transaction=hold_txn,
                # Capture the proportionate amount for this SO
                amount=_amount_attributable_to_so(doc, so),
                reference_doctype="Sales Invoice",
                reference_name=doc.name,
                idempotency_key=f"SI-CAPTURE:{doc.name}:{so}",
                remarks=_("Capture from Sales Invoice {0}").format(doc.name),
            )
        return

    # No SO — direct wallet withdrawal at invoice time
    # (ad-hoc invoice paid from wallet)
    # Look up the customer's wallet without filtering by currency — same fix
    # as the engine, to avoid silently creating a parallel wallet when the
    # SI's currency differs from the existing wallet.
    wallet = frappe.db.get_value(
        "Customer Wallet",
        {"customer": doc.customer},
        "name",
    )
    if not wallet:
        frappe.throw(_("No wallet exists for {0}").format(doc.customer))

    # We can't 'capture' without a hold, so post a Hold + capture in one shot
    hold_txn = wallet_engine.hold(
        customer=doc.customer,
        amount=doc.grand_total,
        reference_doctype="Sales Invoice",
        reference_name=doc.name,
        idempotency_key=f"SI-HOLD:{doc.name}",
        remarks=_("Adhoc hold for Sales Invoice {0}").format(doc.name),
    )
    wallet_engine.capture(
        hold_transaction=hold_txn.name,
        reference_doctype="Sales Invoice",
        reference_name=doc.name,
        idempotency_key=f"SI-CAPTURE:{doc.name}",
        remarks=_("Capture from Sales Invoice {0}").format(doc.name),
    )


def reverse_wallet_capture(doc, method=None):
    """on_cancel hook on Sales Invoice — refund the captured amount back to the wallet."""
    if not getattr(doc, "use_wallet_payment", 0):
        return

    from alphax_wallet.alphax_wallet import wallet_engine

    wallet_engine.refund(
        customer=doc.customer,
        amount=doc.grand_total,
        reference_doctype="Sales Invoice",
        reference_name=doc.name,
        idempotency_key=f"SI-REFUND:{doc.name}",
        remarks=_("Refund because Sales Invoice {0} was cancelled").format(doc.name),
    )


def _amount_attributable_to_so(invoice, sales_order):
    """Sum of invoice item amounts that originated from the given Sales Order."""
    return sum(
        d.amount or 0 for d in (invoice.items or [])
        if d.get("sales_order") == sales_order
    ) or invoice.grand_total
