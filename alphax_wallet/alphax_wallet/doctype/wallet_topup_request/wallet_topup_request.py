"""
Wallet Top-up Request — approval workflow for large top-ups.

Auto-approval threshold lives in Wallet Settings.topup_approval_threshold.
On approval, the request creates a Payment Entry that, when submitted,
flows through the Payment Entry hook into wallet_engine.topup().
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class WalletTopupRequest(Document):
    def validate(self):
        if self.amount <= 0:
            frappe.throw(_("Amount must be greater than zero"))

    def on_submit(self):
        if self.status not in ("Approved",):
            frappe.throw(_("Only Approved requests can be submitted. Click 'Approve' first."))
        self._materialise()

    def on_cancel(self):
        if self.status == "Processed":
            frappe.throw(_("This request has been processed. Cancel the linked Payment Entry first."))
        self.db_set("status", "Rejected")

    @frappe.whitelist()
    def approve(self):
        if self.status != "Pending":
            frappe.throw(_("Only Pending requests can be approved (current: {0})").format(self.status))
        self.db_set("status", "Approved")
        self.db_set("approved_by", frappe.session.user)
        self.db_set("approval_date", now_datetime())

    @frappe.whitelist()
    def reject(self, reason=None):
        if self.status != "Pending":
            frappe.throw(_("Only Pending requests can be rejected"))
        self.db_set("status", "Rejected")
        if reason:
            self.db_set("remarks", reason)

    def _materialise(self):
        """Create a Payment Entry that will trigger the wallet top-up hook."""
        from alphax_wallet.alphax_wallet import wallet_engine

        txn = wallet_engine.topup(
            customer=self.customer,
            amount=flt(self.amount),
            currency=self.currency,
            idempotency_key=f"WTR:{self.name}",
            remarks=_("Top-up via approved request {0}").format(self.name),
        )
        self.db_set("wallet_transaction", txn.name)
        self.db_set("status", "Processed")
