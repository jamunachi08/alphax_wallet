"""
alphax_wallet.alphax_wallet.api_actions
=======================================

Whitelisted methods for UI buttons on the Wallet Transaction form:
  - reverse_transaction(transaction, reason): reverse a Deposit/Withdrawal/Refund
  - release_hold(transaction): release an Active Hold

Both delegate to wallet_engine so balance updates, GL postings, locking, and
idempotency stay consistent with the rest of the app.

Permissions: only Wallet Manager and System Manager can call these.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime


_ALLOWED_ROLES = {"Wallet Manager", "System Manager"}


def _check_permission():
    if not _ALLOWED_ROLES.intersection(frappe.get_roles()):
        frappe.throw(
            _("Only Wallet Manager or System Manager can perform this action."),
            frappe.PermissionError,
        )


@frappe.whitelist()
def reverse_transaction(transaction: str, reason: str) -> dict:
    """Reverse a Deposit/Withdrawal/Refund. Called from the form's button."""
    _check_permission()

    from alphax_wallet.alphax_wallet import wallet_engine

    reversal = wallet_engine.reverse(
        transaction_name=transaction,
        reason=reason,
    )
    return {
        "original": transaction,
        "reversal": reversal.name,
        "new_balance": flt(reversal.balance_after),
    }


@frappe.whitelist()
def release_hold(transaction: str) -> dict:
    """Release an Active Hold from the Wallet Transaction form button."""
    _check_permission()

    from alphax_wallet.alphax_wallet import wallet_engine

    release = wallet_engine.release(
        hold_transaction=transaction,
        idempotency_key=f"MANUAL-RELEASE:{transaction}",
        remarks=_("Manual release from form by {0} at {1}").format(
            frappe.session.user, now_datetime(),
        ),
    )
    return {"release": release.name}
