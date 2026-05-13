"""Singleton settings controller. Validates account choices."""

import frappe
from frappe import _
from frappe.model.document import Document


class WalletSettings(Document):
    def validate(self):
        self._validate_account("wallet_liability_account", expected_root_type="Liability")
        self._validate_account("deferred_revenue_account", expected_root_type=("Liability", "Income"))
        self._validate_account("commission_expense_account", expected_root_type="Expense")
        self._validate_account("default_bank_account", expected_account_type=("Bank", "Cash"))

    def _validate_account(self, fieldname, expected_root_type=None, expected_account_type=None):
        account = self.get(fieldname)
        if not account:
            return

        root_type, account_type, company, is_group = frappe.db.get_value(
            "Account", account, ["root_type", "account_type", "company", "is_group"]
        ) or (None, None, None, None)

        label = self.meta.get_label(fieldname)

        if is_group:
            frappe.throw(_("{0}: '{1}' is a group account. Choose a ledger account.").format(label, account))

        if self.default_company and company and company != self.default_company:
            frappe.throw(
                _("{0}: account '{1}' belongs to company '{2}', not the default company '{3}'")
                .format(label, account, company, self.default_company)
            )

        if expected_root_type:
            allowed = expected_root_type if isinstance(expected_root_type, tuple) else (expected_root_type,)
            if root_type not in allowed:
                frappe.throw(
                    _("{0}: account '{1}' has root type '{2}', expected one of {3}")
                    .format(label, account, root_type, ", ".join(allowed))
                )

        if expected_account_type:
            allowed = expected_account_type if isinstance(expected_account_type, tuple) else (expected_account_type,)
            if account_type not in allowed:
                frappe.throw(
                    _("{0}: account '{1}' has type '{2}', expected one of {3}")
                    .format(label, account, account_type, ", ".join(allowed))
                )
