"""
Wallet Transaction — the immutable wallet ledger.

Once inserted, a Wallet Transaction is effectively read-only. We allow
internal updates to `status` and `journal_entry` only, and block deletes
unless the user is System Manager.
"""

import frappe
from frappe import _
from frappe.model.document import Document


# Fields the wallet engine is allowed to update after insert
MUTABLE_FIELDS = {"status", "journal_entry"}


class WalletTransaction(Document):
    def validate(self):
        if self.is_new():
            self._validate_idempotency()
        else:
            self._enforce_immutability()

    def _validate_idempotency(self):
        if not self.idempotency_key:
            return
        existing = frappe.db.get_value(
            "Wallet Transaction",
            {
                "wallet": self.wallet,
                "idempotency_key": self.idempotency_key,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if existing:
            frappe.throw(
                _("A wallet transaction with this idempotency key already exists: {0}")
                .format(existing)
            )

    def _enforce_immutability(self):
        before = self.get_doc_before_save()
        if not before:
            return
        for field in self.meta.get("fields"):
            fname = field.fieldname
            if fname in MUTABLE_FIELDS:
                continue
            if (self.get(fname) or None) != (before.get(fname) or None):
                # Allow System Manager to override with a clear audit log
                if "System Manager" not in frappe.get_roles():
                    frappe.throw(
                        _("Wallet Transactions are immutable. Field '{0}' cannot be changed.")
                        .format(field.label or fname)
                    )

    def on_trash(self):
        if "System Manager" not in frappe.get_roles():
            frappe.throw(_("Wallet Transactions cannot be deleted. Reverse them instead."))
