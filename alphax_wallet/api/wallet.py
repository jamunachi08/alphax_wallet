"""
AlphaX Wallet REST API
======================

All endpoints are exposed at /api/method/alphax_wallet.api.wallet.<func>
and require authentication (API key + secret in the Authorization header).

The website is expected to:
  1. Call get_balance() before showing 'Pay with Wallet' on the checkout page
  2. Call hold() during booking checkout
  3. Call capture() once the booking is confirmed (or release() on cancel)
  4. Call topup() from the payment gateway webhook

All write endpoints accept an idempotency_key argument. The same key with the
same wallet will return the existing transaction instead of double-posting.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


# ----------------------------------------------------------------------------
# Read endpoints
# ----------------------------------------------------------------------------

@frappe.whitelist()
def get_balance(customer: str, currency: str = None) -> dict:
    """
    GET /api/method/alphax_wallet.api.wallet.get_balance?customer=CUST-001

    Response:
        {
            "customer": "CUST-001",
            "currency": "<company base currency>",
            "current_balance": 5000.0,
            "held_amount": 1200.0,
            "available_balance": 3800.0,
            "status": "Active"
        }
    """
    _require_customer(customer)
    settings = frappe.get_single("Wallet Settings")
    currency = currency or settings.default_currency

    wallet_name = frappe.db.get_value(
        "Customer Wallet",
        {"customer": customer, "currency": currency},
        "name",
    )
    if not wallet_name:
        return {
            "customer": customer,
            "currency": currency,
            "current_balance": 0,
            "held_amount": 0,
            "available_balance": 0,
            "status": "Not Found",
        }

    w = frappe.get_doc("Customer Wallet", wallet_name)
    return {
        "customer": customer,
        "currency": currency,
        "current_balance": flt(w.current_balance),
        "held_amount": flt(w.held_amount),
        "available_balance": flt(w.current_balance) - flt(w.held_amount),
        "status": w.status,
    }


@frappe.whitelist()
def get_transactions(customer: str, limit: int = 50, offset: int = 0,
                     transaction_type: str = None):
    """
    Recent wallet transactions for a customer. Useful for "Wallet History" pages.
    """
    _require_customer(customer)
    filters = {"customer": customer}
    if transaction_type:
        filters["transaction_type"] = transaction_type

    return frappe.get_all(
        "Wallet Transaction",
        filters=filters,
        fields=["name", "transaction_type", "amount", "balance_after",
                "currency", "status", "reference_doctype", "reference_name",
                "posting_datetime", "remarks"],
        order_by="posting_datetime desc",
        limit_page_length=int(limit),
        limit_start=int(offset),
    )


# ----------------------------------------------------------------------------
# Write endpoints
# ----------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def topup(customer: str, amount, idempotency_key: str,
          currency: str = None, payment_reference: str = None,
          mode_of_payment: str = None, remarks: str = None):
    """
    Credit the wallet. Used by the website's payment-gateway webhook.

    Required: idempotency_key — the gateway's transaction id is a good choice.
    """
    _require_customer(customer)
    _require_idempotency(idempotency_key)

    from alphax_wallet.alphax_wallet import wallet_engine
    txn = wallet_engine.topup(
        customer=customer,
        amount=flt(amount),
        currency=currency,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Top-up via API; ref={0}").format(payment_reference or "n/a"),
    )
    return _txn_response(txn)


@frappe.whitelist(methods=["POST"])
def hold(customer: str, amount, reference_doctype: str, reference_name: str,
         idempotency_key: str, currency: str = None,
         expires_in_hours: int = None, remarks: str = None):
    """Reserve funds for a booking. Returns the hold transaction name."""
    _require_customer(customer)
    _require_idempotency(idempotency_key)

    from alphax_wallet.alphax_wallet import wallet_engine
    txn = wallet_engine.hold(
        customer=customer,
        amount=flt(amount),
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        currency=currency,
        idempotency_key=idempotency_key,
        expires_in_hours=int(expires_in_hours) if expires_in_hours else None,
        remarks=remarks,
    )
    return _txn_response(txn)


@frappe.whitelist(methods=["POST"])
def capture(hold_transaction: str, idempotency_key: str, amount=None,
            reference_doctype: str = None, reference_name: str = None,
            remarks: str = None):
    """Convert a hold into a withdrawal."""
    _require_idempotency(idempotency_key)

    from alphax_wallet.alphax_wallet import wallet_engine
    txn = wallet_engine.capture(
        hold_transaction=hold_transaction,
        amount=flt(amount) if amount else None,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        idempotency_key=idempotency_key,
        remarks=remarks,
    )
    return _txn_response(txn)


@frappe.whitelist(methods=["POST"])
def release(hold_transaction: str, idempotency_key: str, remarks: str = None):
    """Release a hold (booking cancelled before confirmation)."""
    _require_idempotency(idempotency_key)

    from alphax_wallet.alphax_wallet import wallet_engine
    txn = wallet_engine.release(
        hold_transaction=hold_transaction,
        idempotency_key=idempotency_key,
        remarks=remarks,
    )
    return _txn_response(txn)


@frappe.whitelist(methods=["POST"])
def refund(customer: str, amount, reference_doctype: str, reference_name: str,
           idempotency_key: str, currency: str = None, remarks: str = None):
    """Credit the wallet after a captured booking is cancelled/refunded."""
    _require_customer(customer)
    _require_idempotency(idempotency_key)

    from alphax_wallet.alphax_wallet import wallet_engine
    txn = wallet_engine.refund(
        customer=customer,
        amount=flt(amount),
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        currency=currency,
        idempotency_key=idempotency_key,
        remarks=remarks,
    )
    return _txn_response(txn)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _require_customer(customer):
    if not customer:
        frappe.throw(_("'customer' is required"), frappe.ValidationError)
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer not found: {0}").format(customer), frappe.DoesNotExistError)


def _require_idempotency(key):
    if not key:
        frappe.throw(
            _("'idempotency_key' is required for all write endpoints"),
            frappe.ValidationError,
        )


def _txn_response(txn):
    return {
        "name": txn.name,
        "wallet": txn.wallet,
        "customer": txn.customer,
        "transaction_type": txn.transaction_type,
        "amount": flt(txn.amount),
        "balance_after": flt(txn.balance_after),
        "held_after": flt(txn.held_after),
        "status": txn.status,
        "currency": txn.currency,
        "posting_datetime": str(txn.posting_datetime),
        "journal_entry": txn.journal_entry,
    }
