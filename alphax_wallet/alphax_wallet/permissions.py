"""
Permission query and has_permission hooks.

A portal user (linked to a Customer) sees only their own wallet and
their own Wallet Transactions.

Desk users with Wallet Manager / Wallet User / Accounts Manager / System
Manager / Wallet Auditor see everything.
"""

import frappe


_PRIVILEGED_ROLES = {
    "System Manager", "Wallet Manager", "Wallet Auditor",
    "Accounts Manager", "Accounts User",
}


def _user_customer():
    """Return the Customer linked to the current portal user, if any."""
    return frappe.db.get_value(
        "Contact", {"user": frappe.session.user}, "customer"
    ) or frappe.db.get_value(
        "Customer", {"linked_user": frappe.session.user}, "name"
    )


def _is_privileged():
    return bool(_PRIVILEGED_ROLES.intersection(frappe.get_roles()))


# ----------------------------------------------------------------------------
# permission_query_conditions — filter list views & reports
# ----------------------------------------------------------------------------

def wallet_query(user=None):
    if _is_privileged():
        return ""
    customer = _user_customer()
    if not customer:
        return "1=0"
    return f"`tabCustomer Wallet`.customer = {frappe.db.escape(customer)}"


def transaction_query(user=None):
    if _is_privileged():
        return ""
    customer = _user_customer()
    if not customer:
        return "1=0"
    return f"`tabWallet Transaction`.customer = {frappe.db.escape(customer)}"


# ----------------------------------------------------------------------------
# has_permission — single doc access check
# ----------------------------------------------------------------------------

def has_wallet_permission(doc, user=None, permission_type=None):
    if _is_privileged():
        return True
    return doc.customer == _user_customer()


def has_transaction_permission(doc, user=None, permission_type=None):
    if _is_privileged():
        return True
    return doc.customer == _user_customer()
