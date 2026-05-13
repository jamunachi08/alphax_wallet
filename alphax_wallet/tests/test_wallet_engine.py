"""
Tests for the wallet engine.

Run with:
    bench --site your.site.local run-tests --app alphax_wallet
"""

import unittest

import frappe
from frappe.utils import flt

from alphax_wallet.alphax_wallet import wallet_engine


TEST_CUSTOMER = "_AX Test Customer"
TEST_CURRENCY = "INR"


class TestWalletEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Make sure the test customer exists
        if not frappe.db.exists("Customer", TEST_CUSTOMER):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": TEST_CUSTOMER,
                "customer_type": "Individual",
                "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
                "territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
            }).insert(ignore_permissions=True)

    def setUp(self):
        # Reset wallet state by deleting prior transactions for this customer
        frappe.db.delete("Wallet Transaction", {"customer": TEST_CUSTOMER})
        wallet_name = frappe.db.get_value(
            "Customer Wallet",
            {"customer": TEST_CUSTOMER, "currency": TEST_CURRENCY},
            "name",
        )
        if wallet_name:
            frappe.db.set_value("Customer Wallet", wallet_name,
                                {"current_balance": 0, "held_amount": 0})

    # --------------------------------------------------------------
    # Top-up
    # --------------------------------------------------------------
    def test_topup_increases_balance(self):
        wallet_engine.topup(TEST_CUSTOMER, 1000, currency=TEST_CURRENCY,
                            idempotency_key="t1", remarks="test")
        self.assertEqual(wallet_engine.get_balance(TEST_CUSTOMER, TEST_CURRENCY), 1000)

    def test_topup_idempotency(self):
        wallet_engine.topup(TEST_CUSTOMER, 500, currency=TEST_CURRENCY,
                            idempotency_key="t-idem", remarks="first")
        wallet_engine.topup(TEST_CUSTOMER, 500, currency=TEST_CURRENCY,
                            idempotency_key="t-idem", remarks="duplicate")
        self.assertEqual(wallet_engine.get_balance(TEST_CUSTOMER, TEST_CURRENCY), 500,
                         "Idempotency key must prevent double-credit")

    def test_topup_rejects_zero(self):
        with self.assertRaises(frappe.ValidationError):
            wallet_engine.topup(TEST_CUSTOMER, 0, currency=TEST_CURRENCY,
                                idempotency_key="t-zero")

    # --------------------------------------------------------------
    # Hold / Capture / Release
    # --------------------------------------------------------------
    def test_hold_capture_reduces_balance(self):
        wallet_engine.topup(TEST_CUSTOMER, 1000, currency=TEST_CURRENCY,
                            idempotency_key="seed1")
        h = wallet_engine.hold(TEST_CUSTOMER, 300,
                               reference_doctype="Sales Order", reference_name="SO-TEST-1",
                               currency=TEST_CURRENCY, idempotency_key="hold1")
        self.assertEqual(flt(h.held_after), 300)

        wallet_engine.capture(h.name, idempotency_key="cap1")
        self.assertEqual(wallet_engine.get_balance(TEST_CUSTOMER, TEST_CURRENCY), 700)

    def test_hold_release_restores_available(self):
        wallet_engine.topup(TEST_CUSTOMER, 1000, currency=TEST_CURRENCY,
                            idempotency_key="seed2")
        h = wallet_engine.hold(TEST_CUSTOMER, 400,
                               reference_doctype="Sales Order", reference_name="SO-TEST-2",
                               currency=TEST_CURRENCY, idempotency_key="hold2")
        wallet_engine.release(h.name, idempotency_key="rel2")

        wallet = frappe.get_doc("Customer Wallet",
                                {"customer": TEST_CUSTOMER, "currency": TEST_CURRENCY})
        self.assertEqual(flt(wallet.held_amount), 0)
        self.assertEqual(flt(wallet.current_balance), 1000)

    def test_hold_rejects_overdraw(self):
        wallet_engine.topup(TEST_CUSTOMER, 100, currency=TEST_CURRENCY,
                            idempotency_key="seed3")
        with self.assertRaises(frappe.ValidationError):
            wallet_engine.hold(TEST_CUSTOMER, 200,
                               reference_doctype="Sales Order", reference_name="SO-OD",
                               currency=TEST_CURRENCY, idempotency_key="hold-od")

    def test_partial_capture_releases_residue(self):
        wallet_engine.topup(TEST_CUSTOMER, 1000, currency=TEST_CURRENCY,
                            idempotency_key="seed4")
        h = wallet_engine.hold(TEST_CUSTOMER, 600,
                               reference_doctype="Sales Order", reference_name="SO-PART",
                               currency=TEST_CURRENCY, idempotency_key="hold-part")
        wallet_engine.capture(h.name, amount=400, idempotency_key="cap-part")

        wallet = frappe.get_doc("Customer Wallet",
                                {"customer": TEST_CUSTOMER, "currency": TEST_CURRENCY})
        # 1000 deposited, 400 captured = 600 balance, 0 held (residue 200 released)
        self.assertEqual(flt(wallet.current_balance), 600)
        self.assertEqual(flt(wallet.held_amount), 0)

    # --------------------------------------------------------------
    # Refund
    # --------------------------------------------------------------
    def test_refund_credits_wallet(self):
        wallet_engine.topup(TEST_CUSTOMER, 200, currency=TEST_CURRENCY,
                            idempotency_key="seed5")
        wallet_engine.refund(TEST_CUSTOMER, 50,
                             reference_doctype="Sales Invoice", reference_name="SI-TEST",
                             currency=TEST_CURRENCY, idempotency_key="ref5")
        self.assertEqual(wallet_engine.get_balance(TEST_CUSTOMER, TEST_CURRENCY), 250)
