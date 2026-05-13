"""
alphax_wallet.alphax_wallet.wallet_engine
=========================================

The single, authoritative module for all wallet balance changes.

Every other piece of the app (DocType controllers, event hooks, REST API,
scheduled tasks) MUST go through these functions to mutate a wallet.
This is what guarantees:

  - One ledger row per balance change (immutable Wallet Transaction)
  - One Journal Entry per ledger row (perfectly mirrored GL posting)
  - Idempotency via (wallet, idempotency_key) unique constraint
  - Row-level locking so two concurrent bookings can't oversell the wallet

Public API
----------
    topup(customer, amount, payment_entry=None, idempotency_key=None, ...)
    hold(customer, amount, reference_doctype, reference_name, ...)
    capture(hold_transaction, amount=None, ...)
    release(hold_transaction, ...)
    refund(customer, amount, reference_doctype, reference_name, ...)
    get_balance(customer, currency=None)

All write operations return the resulting Wallet Transaction document.
All raise frappe.ValidationError on bad input — never silently corrupt state.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_datetime
from typing import Optional


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def get_balance(customer: str, currency: Optional[str] = None) -> float:
    """Live wallet balance for a customer. Creates wallet on demand if enabled."""
    wallet = _get_or_create_wallet(customer, currency)
    return flt(wallet.current_balance)


def topup(
    customer: str,
    amount: float,
    payment_entry: Optional[str] = None,
    currency: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    remarks: Optional[str] = None,
) -> "frappe.model.document.Document":
    """
    Credit the wallet. Used by:
      - Payment Entry on_submit hook (when is_wallet_topup is ticked)
      - REST API /topup called by the website's payment-gateway webhook
    """
    _validate_amount(amount, "Top-up amount")
    wallet = _get_or_create_wallet(customer, currency)
    return _post_transaction(
        wallet=wallet,
        transaction_type="Deposit",
        amount=amount,
        reference_doctype="Payment Entry" if payment_entry else None,
        reference_name=payment_entry,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Wallet top-up"),
    )


def hold(
    customer: str,
    amount: float,
    reference_doctype: str,
    reference_name: str,
    currency: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    expires_in_hours: Optional[int] = None,
    remarks: Optional[str] = None,
) -> "frappe.model.document.Document":
    """
    Reserve funds against the wallet without yet recognising them as revenue.
    Used when a Sales Order is submitted with `use_wallet_payment` ticked.
    The held amount cannot be used by another booking until released or captured.
    """
    _validate_amount(amount, "Hold amount")
    wallet = _get_or_create_wallet(customer, currency)

    # Lock the wallet row to serialise concurrent holds
    _lock_wallet(wallet.name)

    available = flt(wallet.current_balance) - flt(wallet.held_amount)
    if amount > available:
        frappe.throw(
            _("Insufficient available wallet balance for {0}: requested {1}, available {2}").format(
                customer, frappe.utils.fmt_money(amount), frappe.utils.fmt_money(available)
            ),
            frappe.ValidationError,
        )

    settings = frappe.get_single("Wallet Settings")
    expires_at = None
    hours = expires_in_hours or settings.hold_expiry_hours or 24
    if hours:
        from frappe.utils import add_to_date
        expires_at = add_to_date(now_datetime(), hours=hours)

    return _post_transaction(
        wallet=wallet,
        transaction_type="Hold",
        amount=amount,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Hold for {0} {1}").format(reference_doctype, reference_name),
        expires_at=expires_at,
    )


def capture(
    hold_transaction: str,
    amount: Optional[float] = None,
    reference_doctype: Optional[str] = None,
    reference_name: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    remarks: Optional[str] = None,
) -> "frappe.model.document.Document":
    """
    Convert a Hold into a Withdrawal — the funds are now spent.
    Called when the corresponding Sales Invoice is submitted.

    If `amount` is None or equals the held amount, the entire hold is captured.
    If `amount` is less, the remainder is auto-released back to spendable balance.
    """
    hold_doc = frappe.get_doc("Wallet Transaction", hold_transaction)
    if hold_doc.transaction_type != "Hold":
        frappe.throw(_("Transaction {0} is not a Hold").format(hold_transaction))
    if hold_doc.status != "Active":
        frappe.throw(_("Hold {0} is not active (status: {1})").format(
            hold_transaction, hold_doc.status))

    capture_amount = flt(amount) if amount else flt(hold_doc.amount)
    if capture_amount > flt(hold_doc.amount):
        frappe.throw(_("Capture amount cannot exceed hold amount"))

    wallet = frappe.get_doc("Customer Wallet", hold_doc.wallet)
    _lock_wallet(wallet.name)

    # 1. Mark hold as captured
    hold_doc.db_set("status", "Captured", update_modified=False)

    # 2. Post the actual withdrawal
    withdrawal = _post_transaction(
        wallet=wallet,
        transaction_type="Withdrawal",
        amount=capture_amount,
        reference_doctype=reference_doctype or hold_doc.reference_doctype,
        reference_name=reference_name or hold_doc.reference_name,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Capture of hold {0}").format(hold_transaction),
        related_hold=hold_transaction,
    )

    # 3. If partial capture, release the residue
    residue = flt(hold_doc.amount) - capture_amount
    if residue > 0:
        _post_transaction(
            wallet=wallet,
            transaction_type="Hold Release",
            amount=residue,
            reference_doctype=hold_doc.reference_doctype,
            reference_name=hold_doc.reference_name,
            remarks=_("Residue released after partial capture of {0}").format(hold_transaction),
            related_hold=hold_transaction,
        )

    return withdrawal


def release(
    hold_transaction: str,
    idempotency_key: Optional[str] = None,
    remarks: Optional[str] = None,
) -> "frappe.model.document.Document":
    """
    Release a previously-placed hold. Called on Sales Order cancellation or
    by the scheduled job that expires stale holds.
    """
    hold_doc = frappe.get_doc("Wallet Transaction", hold_transaction)
    if hold_doc.transaction_type != "Hold":
        frappe.throw(_("Transaction {0} is not a Hold").format(hold_transaction))
    if hold_doc.status != "Active":
        # Already released or captured — be idempotent
        return hold_doc

    wallet = frappe.get_doc("Customer Wallet", hold_doc.wallet)
    _lock_wallet(wallet.name)

    hold_doc.db_set("status", "Released", update_modified=False)

    return _post_transaction(
        wallet=wallet,
        transaction_type="Hold Release",
        amount=flt(hold_doc.amount),
        reference_doctype=hold_doc.reference_doctype,
        reference_name=hold_doc.reference_name,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Released hold {0}").format(hold_transaction),
        related_hold=hold_transaction,
    )


def refund(
    customer: str,
    amount: float,
    reference_doctype: str,
    reference_name: str,
    currency: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    remarks: Optional[str] = None,
) -> "frappe.model.document.Document":
    """Credit the wallet because a previously-captured booking was cancelled / refunded."""
    _validate_amount(amount, "Refund amount")
    wallet = _get_or_create_wallet(customer, currency)
    return _post_transaction(
        wallet=wallet,
        transaction_type="Refund",
        amount=amount,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        idempotency_key=idempotency_key,
        remarks=remarks or _("Refund to wallet"),
    )


def reverse(
    transaction_name: str,
    reason: str,
    idempotency_key: Optional[str] = None,
) -> "frappe.model.document.Document":
    """
    Reverse a previously-posted GL-affecting transaction (Deposit / Withdrawal / Refund).

    Strategy:
      1. Post a compensating Wallet Transaction with the OPPOSITE balance effect.
         No fresh Journal Entry is created (skip_gl=True) — instead we cancel the
         original's JE, which makes ERPNext post the reversing GL Entries natively.
      2. Mark the original as Reversed.
      3. Cancel the original's Journal Entry (best-effort; if the period is
         closed, the wallet ledger reversal still stands and the operator gets
         a warning).

    The reversal transaction is itself an immutable ledger row, so an audit
    can see both the original and its reversal pointing at each other via
    `reference_name`.
    """
    original = frappe.get_doc("Wallet Transaction", transaction_name)

    if original.status != "Active":
        frappe.throw(_("Only Active transactions can be reversed (current status: {0}).")
                     .format(original.status))
    if original.transaction_type not in ("Deposit", "Withdrawal", "Refund"):
        frappe.throw(_(
            "Cannot reverse a {0} transaction directly. "
            "For Holds, use Release. For Hold Releases, the parent Hold's lifecycle is the reversal path."
        ).format(original.transaction_type))
    if not reason or len(reason.strip()) < 5:
        frappe.throw(_("A reason of at least 5 characters is required for a reversal."))

    wallet = frappe.get_doc("Customer Wallet", original.wallet)
    _lock_wallet(wallet.name)

    idempotency_key = idempotency_key or f"REVERSE:{original.name}"
    remarks_text = _("Reversal of {0} — Reason: {1}").format(original.name, reason.strip())

    # Determine the compensating transaction type by inverting balance impact
    if original.transaction_type == "Deposit":
        compensating_type = "Withdrawal"   # debit the wallet
    elif original.transaction_type == "Refund":
        compensating_type = "Withdrawal"   # debit the wallet
    elif original.transaction_type == "Withdrawal":
        compensating_type = "Refund"       # credit the wallet
    else:
        frappe.throw(_("Unsupported reversal path"))

    # Pre-flight: a Withdrawal-style reversal needs sufficient available balance
    if compensating_type == "Withdrawal":
        available = flt(wallet.current_balance) - flt(wallet.held_amount)
        if flt(original.amount) > available:
            frappe.throw(_(
                "Cannot reverse {0}: customer's available balance ({1}) is less than "
                "the reversal amount ({2}). The customer must have spent the funds elsewhere — "
                "investigate before forcing a reversal."
            ).format(original.name, available, flt(original.amount)))

    reversal = _post_transaction(
        wallet=wallet,
        transaction_type=compensating_type,
        amount=flt(original.amount),
        reference_doctype="Wallet Transaction",
        reference_name=original.name,
        idempotency_key=idempotency_key,
        remarks=remarks_text,
        skip_gl=True,  # GL effect comes from JE cancellation, not a new JE
    )

    # Mark the original Reversed and cancel its JE
    original.db_set("status", "Reversed", update_modified=False)
    if original.journal_entry:
        try:
            from alphax_wallet.alphax_wallet.gl_posting import reverse_journal_entry_for_transaction
            reverse_journal_entry_for_transaction(original)
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet: JE cancel failed for {original.name}",
                message=frappe.get_traceback(),
            )
            frappe.msgprint(_(
                "Wallet ledger reversed, but the original Journal Entry "
                "could not be cancelled (likely because of a closed period). "
                "Please post a manual reversing JE."
            ), indicator="orange", alert=True)

    # Link the reversal back to the original on the original row for audit
    original.db_set("related_hold", reversal.name, update_modified=False) \
        if not original.related_hold else None

    return reversal


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------

def _validate_amount(amount, label):
    amount = flt(amount)
    if amount <= 0:
        frappe.throw(_("{0} must be greater than zero").format(label))


def _get_or_create_wallet(customer: str, currency: Optional[str] = None):
    """
    Return the Customer Wallet for `customer`, creating one if missing.

    Resolution strategy (new in v1.1):
      1. If the customer has exactly one wallet, USE THAT WALLET regardless of
         what currency was requested. Most customers have one wallet — using
         it avoids silently creating a parallel wallet in the wrong currency
         (the bug that caused INR/SAR errors).
      2. If the customer has multiple wallets, the explicit `currency` argument
         is required to disambiguate.
      3. If the customer has no wallets and auto-create is on, create one in:
         explicit arg → Wallet Settings default → Company base.
         Customer.default_currency is NO LONGER used (it was the source of
         INR contamination when imported customers had it set).
      4. Raise a clear error if a passed `currency` doesn't match the existing
         wallet — caller (Sales Order, etc.) should fix the document, not have
         a parallel wallet silently created.
    """
    if not frappe.db.exists("Customer", customer):
        frappe.throw(_("Customer {0} not found").format(customer))

    settings = frappe.get_single("Wallet Settings")

    # Look up all existing wallets for the customer
    existing = frappe.get_all(
        "Customer Wallet",
        filters={"customer": customer},
        fields=["name", "currency", "status"],
    )

    # Case A: exactly one existing wallet — use it
    if len(existing) == 1:
        w = existing[0]
        # If caller asked for a different currency, refuse rather than corrupt
        if currency and currency != w.currency:
            frappe.throw(
                _(
                    "Customer {0} already has a wallet in {1}, but this operation "
                    "is in {2}. Either change the document's currency to {1}, or "
                    "create a second wallet for {0} in {2} first."
                ).format(customer, w.currency, currency),
                frappe.ValidationError,
            )
        return frappe.get_doc("Customer Wallet", w.name)

    # Case B: multiple existing wallets — caller must specify
    if len(existing) > 1:
        if not currency:
            currencies = ", ".join(w.currency for w in existing)
            frappe.throw(
                _("Customer {0} has multiple wallets ({1}). Specify a currency.").format(
                    customer, currencies
                ),
                frappe.ValidationError,
            )
        match = next((w for w in existing if w.currency == currency), None)
        if not match:
            frappe.throw(_("No wallet in {0} for customer {1}.").format(currency, customer))
        return frappe.get_doc("Customer Wallet", match.name)

    # Case C: no existing wallet — create one. NEVER fall through to
    # Customer.default_currency, which is what caused the INR bug for
    # customers imported with that field pre-filled.
    company_currency = None
    if settings.default_company:
        company_currency = frappe.db.get_value(
            "Company", settings.default_company, "default_currency"
        )

    new_currency = currency or settings.default_currency or company_currency
    if not new_currency:
        frappe.throw(_(
            "Cannot determine wallet currency. Set Default Currency in Wallet Settings, "
            "or set Default Company so its base currency can be used."
        ))

    if not settings.auto_create_wallet_on_customer:
        frappe.throw(_("No wallet exists for {0}. Create one first.").format(customer))

    # Warn if creating a wallet that doesn't match company base
    if company_currency and new_currency != company_currency:
        frappe.msgprint(
            _(
                "Heads up: this wallet is being created in {0}, but your company "
                "base currency is {1}. Make sure a Currency Exchange ({0} → {1}) "
                "exists for the posting date, otherwise Journal Entries will fail."
            ).format(new_currency, company_currency),
            indicator="orange", alert=True,
        )

    wallet = frappe.get_doc({
        "doctype": "Customer Wallet",
        "customer": customer,
        "currency": new_currency,
        "status": "Active",
        "current_balance": 0,
        "held_amount": 0,
    })
    wallet.insert(ignore_permissions=True)
    return wallet


def _lock_wallet(wallet_name: str):
    """SELECT ... FOR UPDATE to serialise concurrent balance changes."""
    frappe.db.sql(
        "SELECT name FROM `tabCustomer Wallet` WHERE name = %s FOR UPDATE",
        wallet_name,
    )


def _check_idempotency(wallet_name: str, idempotency_key: Optional[str]):
    """If a transaction with this key already exists, return it instead of double-posting."""
    if not idempotency_key:
        return None
    existing = frappe.db.get_value(
        "Wallet Transaction",
        {"wallet": wallet_name, "idempotency_key": idempotency_key},
        "name",
    )
    if existing:
        return frappe.get_doc("Wallet Transaction", existing)
    return None


def _post_transaction(
    wallet,
    transaction_type: str,
    amount: float,
    reference_doctype: Optional[str] = None,
    reference_name: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    remarks: Optional[str] = None,
    related_hold: Optional[str] = None,
    expires_at=None,
    skip_gl: bool = False,
):
    """
    Create a Wallet Transaction, update the wallet snapshot fields, and post a
    matching Journal Entry. This is the only path that should ever change a
    wallet's current_balance or held_amount.

    skip_gl: if True, no Journal Entry is created. Used by reversal flows
    where the GL effect comes from cancelling the original's JE instead.
    """
    # Idempotency short-circuit
    existing = _check_idempotency(wallet.name, idempotency_key)
    if existing:
        return existing

    # Compute new balances based on transaction type
    new_balance = flt(wallet.current_balance)
    new_held = flt(wallet.held_amount)

    if transaction_type == "Deposit":
        new_balance += flt(amount)
    elif transaction_type == "Withdrawal":
        new_balance -= flt(amount)
        # Only release a corresponding hold if this withdrawal was actually
        # tied to one (normal Capture flow). Reversal-driven withdrawals have
        # no related hold and must NOT touch held_amount.
        if related_hold:
            new_held -= flt(amount)
    elif transaction_type == "Hold":
        new_held += flt(amount)
    elif transaction_type == "Hold Release":
        new_held -= flt(amount)
    elif transaction_type == "Refund":
        new_balance += flt(amount)
    else:
        frappe.throw(_("Unknown wallet transaction type: {0}").format(transaction_type))

    if new_balance < 0:
        frappe.throw(_("Wallet balance would become negative ({0}). Refused.").format(new_balance))
    if new_held < 0:
        # A defensive guard — shouldn't happen if engine is the only writer
        new_held = 0

    txn = frappe.get_doc({
        "doctype": "Wallet Transaction",
        "wallet": wallet.name,
        "customer": wallet.customer,
        "transaction_type": transaction_type,
        "amount": flt(amount),
        "balance_after": new_balance,
        "held_after": new_held,
        "currency": wallet.currency,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "related_hold": related_hold,
        "idempotency_key": idempotency_key,
        "remarks": remarks,
        "posting_datetime": now_datetime(),
        "status": "Active",
        "expires_at": expires_at,
    })
    txn.insert(ignore_permissions=True)

    # Snapshot fields on the wallet
    wallet.db_set("current_balance", new_balance, update_modified=False)
    wallet.db_set("held_amount", new_held, update_modified=False)
    wallet.db_set("available_balance", new_balance - new_held, update_modified=False)

    # Mirror the customer card field
    frappe.db.set_value(
        "Customer", wallet.customer, "alphax_wallet_balance", new_balance,
        update_modified=False,
    )

    # GL posting (skipped for pure Hold/Release — they don't move money,
    # only earmark it; capture/withdrawal does the GL posting).
    # Reversal flows pass skip_gl=True because they cancel the original JE
    # rather than posting a fresh one.
    if not skip_gl and transaction_type in ("Deposit", "Withdrawal", "Refund"):
        from alphax_wallet.alphax_wallet.gl_posting import post_journal_entry_for_transaction
        post_journal_entry_for_transaction(txn)

    txn.reload()
    return txn
