"""
alphax_wallet.alphax_wallet.gl_posting
======================================

Translates a Wallet Transaction into the appropriate ERPNext Journal Entry.

The mapping comes straight from the business requirement:

    Deposit:     Dr. Bank/Cash             Cr. Customer Wallet Liability
    Withdrawal:  Dr. Customer Wallet Liab  Cr. Deferred Revenue
    Refund:      Dr. Customer Wallet Liab  Cr. Bank/Cash   (or Sales Refund)

Holds and Hold Releases are NOT posted to the GL — they only restrict
spendable balance inside the wallet ledger.
"""

import frappe
from frappe import _
from frappe.utils import flt


def post_journal_entry_for_transaction(txn) -> str:
    """
    Create and submit a Journal Entry that mirrors the Wallet Transaction.
    Stores the JE name on the transaction for full bidirectional traceability.

    Returns the Journal Entry name.
    """
    settings = frappe.get_single("Wallet Settings")
    company = settings.default_company or _guess_company()

    if not company:
        frappe.throw(_("Set Default Company in Wallet Settings before posting wallet GL entries"))

    accounts = _accounts_for_transaction(txn, settings, company)
    if not accounts:
        return None  # transaction type doesn't post (Hold / Hold Release)

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": company,
        "posting_date": frappe.utils.getdate(txn.posting_datetime),
        "user_remark": _("AlphaX Wallet — {0} for {1} ({2})").format(
            txn.transaction_type, txn.customer, txn.name,
        ),
        "accounts": accounts,
    })
    je.insert(ignore_permissions=True)
    je.submit()

    txn.db_set("journal_entry", je.name, update_modified=False)
    return je.name


def reverse_journal_entry_for_transaction(txn):
    """Cancel the Journal Entry tied to a Wallet Transaction (used on reversals)."""
    if not txn.journal_entry:
        return
    je = frappe.get_doc("Journal Entry", txn.journal_entry)
    if je.docstatus == 1:
        je.cancel()


# ----------------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------------

def _accounts_for_transaction(txn, settings, company):
    """
    Build the JE 'accounts' child rows for a given Wallet Transaction.
    Returns a list of dicts or None if no GL posting is needed.

    Party tracking on the wallet-liability row is conditional:
      - If the account is Receivable/Payable type, ERPNext requires party_type.
      - If it's a plain Liability ledger account (the recommended setup),
        party_type MUST be omitted, otherwise ERPNext raises
        "Account ... and Party Type Customer have different account types".

    Per-customer override: if the Customer has `alphax_debit_account` set,
    we use that instead of the global Wallet Liability account. This is
    useful for B2B corporate clients who get their own ledger.
    """
    # Customer-level override wins, then the global Wallet Settings account
    customer_acct = frappe.db.get_value("Customer", txn.customer, "alphax_debit_account")
    wallet_acct = customer_acct or settings.wallet_liability_account

    bank_acct = settings.default_bank_account
    deferred_acct = settings.deferred_revenue_account

    # Decide once whether the wallet account supports party tracking
    wallet_party_kwargs = _party_kwargs_for_account(wallet_acct, "Customer", txn.customer)

    if txn.transaction_type == "Deposit":
        _require([wallet_acct, bank_acct],
                 "Wallet Liability Account and Default Bank Account")
        return [
            _row(bank_acct, debit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name),
            _row(wallet_acct, credit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name,
                 **wallet_party_kwargs),
        ]

    if txn.transaction_type == "Withdrawal":
        _require([wallet_acct, deferred_acct],
                 "Wallet Liability Account and Deferred Revenue Account")
        return [
            _row(wallet_acct, debit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name,
                 **wallet_party_kwargs),
            _row(deferred_acct, credit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name),
        ]

    if txn.transaction_type == "Refund":
        _require([wallet_acct, bank_acct],
                 "Wallet Liability Account and Default Bank Account")
        return [
            _row(wallet_acct, debit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name,
                 **wallet_party_kwargs),
            _row(bank_acct, credit=txn.amount,
                 reference_doctype=txn.reference_doctype, reference_name=txn.reference_name),
        ]

    return None


def _party_kwargs_for_account(account, party_type, party):
    """
    Return {'party_type': ..., 'party': ...} only if the account's account_type
    is one that ERPNext allows party tracking on. Otherwise return {}.

    Receivable accounts pair with party_type=Customer.
    Payable accounts pair with party_type=Supplier/Employee/Shareholder.
    Anything else (including plain Liability ledgers) must NOT have party_type.
    """
    if not account or not party:
        return {}

    account_type = frappe.db.get_value("Account", account, "account_type")

    valid_combinations = {
        "Receivable": {"Customer"},
        "Payable": {"Supplier", "Employee", "Shareholder"},
    }
    if account_type in valid_combinations and party_type in valid_combinations[account_type]:
        return {"party_type": party_type, "party": party}
    return {}


def _row(account, debit=0, credit=0, party_type=None, party=None,
         reference_doctype=None, reference_name=None):
    return {
        "account": account,
        "debit_in_account_currency": flt(debit),
        "credit_in_account_currency": flt(credit),
        "party_type": party_type,
        "party": party,
        "reference_type": reference_doctype,
        "reference_name": reference_name,
    }


def _require(values, label):
    if not all(values):
        frappe.throw(_("Configure {0} in Wallet Settings before posting wallet GL entries").format(label))


def _guess_company():
    return frappe.defaults.get_user_default("Company") \
        or frappe.db.get_single_value("Global Defaults", "default_company")
