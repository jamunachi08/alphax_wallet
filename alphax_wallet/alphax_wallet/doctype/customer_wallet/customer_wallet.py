"""Customer Wallet — one row per (customer, currency)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CustomerWallet(Document):
    def validate(self):
        # Enforce uniqueness — one wallet per (customer, currency)
        existing = frappe.db.get_value(
            "Customer Wallet",
            {
                "customer": self.customer,
                "currency": self.currency,
                "name": ("!=", self.name or ""),
            },
            "name",
        )
        if existing:
            frappe.throw(
                _("A wallet already exists for {0} in {1}: {2}").format(
                    self.customer, self.currency, existing
                )
            )

        # Populate the read-only computed fields so the saved doc has
        # consistent values. These are recomputed on every save and on form load.
        self._refresh_computed_fields()

    def onload(self):
        """Refresh computed fields when the form opens (read-only display)."""
        self._refresh_computed_fields()

    def _refresh_computed_fields(self):
        """Compute available_balance and lifetime totals from the ledger."""
        self.available_balance = flt(self.current_balance) - flt(self.held_amount)
        deposits, withdrawals = self.get_lifetime_totals()
        self.lifetime_deposits = deposits
        self.lifetime_withdrawals = withdrawals

    # ------------------------------------------------------------------
    # Computed values
    # ------------------------------------------------------------------
    def get_available_balance(self):
        return flt(self.current_balance) - flt(self.held_amount)

    def get_lifetime_totals(self):
        if not self.name or self.is_new():
            return 0, 0
        rows = frappe.db.sql(
            """
            SELECT transaction_type, SUM(amount) as total
            FROM `tabWallet Transaction`
            WHERE wallet = %s
            GROUP BY transaction_type
            """,
            self.name,
            as_dict=True,
        )
        deposits = sum(r.total for r in rows if r.transaction_type in ("Deposit", "Refund"))
        withdrawals = sum(r.total for r in rows if r.transaction_type == "Withdrawal")
        return flt(deposits), flt(withdrawals)

    # ------------------------------------------------------------------
    # Whitelisted methods (called from the form's button)
    # ------------------------------------------------------------------
    @frappe.whitelist()
    def quick_topup(self, amount, mode_of_payment=None, remarks=None):
        """One-click top-up from the wallet form. Used by the Action menu button."""
        from alphax_wallet.alphax_wallet import wallet_engine
        txn = wallet_engine.topup(
            customer=self.customer,
            amount=flt(amount),
            currency=self.currency,
            remarks=remarks or _("Manual top-up from wallet form"),
        )
        return {"transaction": txn.name, "new_balance": txn.balance_after}

    @frappe.whitelist()
    def freeze(self):
        if self.status == "Frozen":
            return
        self.db_set("status", "Frozen")
        frappe.msgprint(_("Wallet frozen. New transactions will be rejected."))

    @frappe.whitelist()
    def unfreeze(self):
        if self.status != "Frozen":
            return
        self.db_set("status", "Active")
        frappe.msgprint(_("Wallet unfrozen."))
