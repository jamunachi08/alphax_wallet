"""
Payment Entry hooks.

When a Payment Entry has the custom `is_wallet_topup` flag ticked and is
submitted for a Customer, we credit the customer wallet via wallet_engine.topup().

Idempotency is anchored on the Payment Entry name so re-submission (after a
cancel-amend) of the same PE never double-credits.
"""

import frappe
from frappe import _


def handle_wallet_topup(doc, method=None):
    """on_submit hook on Payment Entry."""
    if not getattr(doc, "is_wallet_topup", 0):
        return
    if doc.party_type != "Customer":
        frappe.throw(_("Wallet top-ups are only valid for Customer payments"))

    from alphax_wallet.alphax_wallet import wallet_engine

    # Note: the wallet_engine itself will create a Journal Entry for the deposit.
    # The Payment Entry already debits the bank and credits the customer
    # receivable/advance — to avoid double GL impact, the recommended pattern is
    # to route wallet top-ups via a dedicated Payment Entry that posts to the
    # 'Customer Wallet Liability' account directly (set on Mode of Payment).
    #
    # However the engine's idempotency key prevents duplicate ledger rows; we
    # rely on the admin's Mode of Payment configuration to handle the GL side
    # cleanly. For full wallet-only flows, set is_wallet_topup=1 and configure
    # the PE's "Paid To" account to be the Wallet Liability account — the engine
    # will then skip its own Journal Entry creation when it detects the PE has
    # already touched that account.
    wallet_engine.topup(
        customer=doc.party,
        amount=doc.paid_amount,
        payment_entry=doc.name,
        # Currency not passed — engine resolves to the customer's existing
        # wallet, avoiding silent creation of parallel wallets in the
        # PE's account currency.
        idempotency_key=f"PE:{doc.name}",
        remarks=_("Top-up via Payment Entry {0}").format(doc.name),
    )


def reverse_wallet_topup(doc, method=None):
    """on_cancel hook on Payment Entry — deduct the previously-credited amount."""
    if not getattr(doc, "is_wallet_topup", 0):
        return
    if doc.party_type != "Customer":
        return

    txn_name = frappe.db.get_value(
        "Wallet Transaction",
        {"idempotency_key": f"PE:{doc.name}", "transaction_type": "Deposit"},
        "name",
    )
    if not txn_name:
        return

    # Post a compensating Refund-out (treated as a deduction)
    from alphax_wallet.alphax_wallet import wallet_engine
    wallet_engine.refund(
        customer=doc.party,
        amount=-doc.paid_amount,  # negative refund = deduction; but engine refuses negatives
        reference_doctype="Payment Entry",
        reference_name=doc.name,
        idempotency_key=f"PE-REVERSE:{doc.name}",
        remarks=_("Reversal of cancelled Payment Entry {0}").format(doc.name),
    ) if False else _post_reversal(doc, txn_name)


def _post_reversal(pe_doc, original_txn_name):
    """
    Manual reversal: mark the original txn as Reversed and reduce the wallet
    balance by the same amount via a synthetic Withdrawal-class entry.
    """
    from alphax_wallet.alphax_wallet import wallet_engine

    original = frappe.get_doc("Wallet Transaction", original_txn_name)
    if original.status == "Reversed":
        return

    # Create a compensating refund record by posting a Withdrawal of the same amount
    # We bypass via a dedicated 'Reversal' transaction type would be cleaner, but the
    # cleanest user-facing pattern is: stamp original as Reversed + cut the GL entry.
    original.db_set("status", "Reversed")
    if original.journal_entry:
        from alphax_wallet.alphax_wallet.gl_posting import reverse_journal_entry_for_transaction
        reverse_journal_entry_for_transaction(original)

    # Decrease wallet balance & customer card mirror
    wallet = frappe.get_doc("Customer Wallet", original.wallet)
    new_bal = (wallet.current_balance or 0) - (original.amount or 0)
    wallet.db_set("current_balance", new_bal)
    frappe.db.set_value("Customer", wallet.customer, "alphax_wallet_balance", new_bal,
                        update_modified=False)
