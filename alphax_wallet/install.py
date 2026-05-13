"""
Bootstraps the AlphaX Wallet app on install and migrate.

- Creates the three Roles (Wallet Manager / User / Auditor) if missing
- Adds Custom Fields on Customer, Sales Order, Sales Invoice, Payment Entry
- Creates a default Wallet Settings single doc
- Best-effort: creates a default 'Customer Wallet Liability' GL account
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    """Called once when the app is first installed on a site."""
    _ensure_roles()
    _ensure_custom_fields()
    _ensure_wallet_settings()
    _ensure_default_accounts()
    _ensure_default_brand()
    frappe.db.commit()


def after_migrate():
    """Called on every `bench migrate` — must be idempotent."""
    _ensure_roles()
    _ensure_custom_fields()
    _ensure_wallet_settings()
    _ensure_default_brand()
    frappe.db.commit()


def _ensure_default_brand():
    """
    Seed a Wallet Brand for each Company that doesn't have one yet.
    Idempotent — safe to run on every migrate.
    """
    if not frappe.db.table_exists("Wallet Brand"):
        return  # doctype not yet installed

    companies = frappe.get_all("Company", fields=["name", "company_name"])
    for c in companies:
        existing = frappe.db.exists("Wallet Brand", {"company": c.name})
        if existing:
            continue
        brand_id = (c.name or "default").lower().replace(" ", "-")
        # Make sure the brand_id is unique
        suffix = 0
        while frappe.db.exists("Wallet Brand", brand_id):
            suffix += 1
            brand_id = f"{c.name.lower().replace(' ', '-')}-{suffix}"

        brand = frappe.get_doc({
            "doctype": "Wallet Brand",
            "brand_name": brand_id,
            "company": c.name,
            "brand_display_name": c.company_name or c.name,
            "status": "Active",
            "is_active": 1,
            "primary": "#7A2F87",
            "primary_dark": "#5A1F66",
            "primary_light": "#9A4BA7",
            "primary_soft": "#F3E5F5",
            "accent": "#D9A54A",
            "accent_light": "#F0C06A",
            "pink": "#D97A9E",
            "pink_dark": "#C56B87",
            "dark_base": "#18061F",
            "dark_mid": "#2B1038",
            "dark_elev": "#3C1745",
            "text_on_dark": "#F5EDEF",
            "text_on_dark_muted": "#E6D6BE",
            "text_on_dark_faint": "#B56CC0",
            "notes": "Auto-created on install/migrate. Customise the colours, logo, and identity fields to brand this Company.",
        })
        try:
            brand.insert(ignore_permissions=True, ignore_if_duplicate=True)
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet: failed to seed brand for {c.name}",
                message=frappe.get_traceback(),
            )


# ----------------------------------------------------------------------------
# Roles
# ----------------------------------------------------------------------------
ROLES = [
    {"role_name": "Wallet Manager", "desk_access": 1},
    {"role_name": "Wallet User", "desk_access": 1},
    {"role_name": "Wallet Auditor", "desk_access": 1},
]


def _ensure_roles():
    for r in ROLES:
        if not frappe.db.exists("Role", r["role_name"]):
            doc = frappe.get_doc({"doctype": "Role", **r})
            doc.insert(ignore_permissions=True)


# ----------------------------------------------------------------------------
# Custom Fields
# ----------------------------------------------------------------------------
CUSTOM_FIELDS = {
    "Customer": [
        {
            "fieldname": "alphax_wallet_section",
            "label": "AlphaX Wallet",
            "fieldtype": "Section Break",
            "insert_after": "default_currency",
            "collapsible": 1,
        },
        {
            "fieldname": "alphax_wallet_balance",
            "label": "Wallet Balance",
            "fieldtype": "Currency",
            "insert_after": "alphax_wallet_section",
            "read_only": 1,
            "options": "default_currency",
            "description": "Live balance from the Customer Wallet",
        },
        {
            "fieldname": "alphax_debit_account",
            "label": "Wallet Debit Account",
            "fieldtype": "Link",
            "options": "Account",
            "insert_after": "alphax_wallet_balance",
            "description": (
                "Optional: override the default Wallet Liability account "
                "for this specific customer (e.g., a sub-account for B2B "
                "corporate clients). Leave blank to use Wallet Settings default."
            ),
        },
    ],
    "Sales Order": [
        {
            "fieldname": "use_wallet_payment",
            "label": "Pay using Wallet",
            "fieldtype": "Check",
            "insert_after": "customer",
            "default": "0",
        },
        {
            "fieldname": "wallet_hold_reference",
            "label": "Wallet Hold Transaction",
            "fieldtype": "Link",
            "options": "Wallet Transaction",
            "insert_after": "use_wallet_payment",
            "read_only": 1,
            "depends_on": "eval:doc.use_wallet_payment",
        },
        {
            "fieldname": "alphax_vendor_section",
            "label": "Vendor Procurement",
            "fieldtype": "Section Break",
            "insert_after": "wallet_hold_reference",
            "collapsible": 1,
        },
        {
            "fieldname": "alphax_procurement_status",
            "label": "Procurement Status",
            "fieldtype": "Select",
            "options": "\nNot Required\nPending\nPO Issued\nReceived\nVendor Paid",
            "insert_after": "alphax_vendor_section",
            "default": "Not Required",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "read_only": 1,
            "description": "Auto-updated as the linked Purchase Order progresses",
        },
    ],
    "Sales Invoice": [
        {
            "fieldname": "use_wallet_payment",
            "label": "Pay using Wallet",
            "fieldtype": "Check",
            "insert_after": "customer",
            "default": "0",
        },
    ],
    "Payment Entry": [
        {
            "fieldname": "is_wallet_topup",
            "label": "Is Wallet Top-up",
            "fieldtype": "Check",
            "insert_after": "party",
            "default": "0",
            "description": "Tick this to credit the customer wallet on submit",
        },
        {
            "fieldname": "alphax_against_customer_booking",
            "label": "Against Customer Booking",
            "fieldtype": "Link",
            "options": "Sales Order",
            "insert_after": "is_wallet_topup",
            "description": (
                "For supplier payments: link this payout to the originating "
                "customer Sales Order so margin and settlement reports can "
                "match them up."
            ),
        },
    ],
    "Purchase Order": [
        {
            "fieldname": "alphax_vendor_section",
            "label": "AlphaX Booking",
            "fieldtype": "Section Break",
            "insert_after": "customer",
            "collapsible": 1,
        },
        {
            "fieldname": "alphax_against_customer_booking",
            "label": "Against Customer Booking",
            "fieldtype": "Link",
            "options": "Sales Order",
            "insert_after": "alphax_vendor_section",
            "in_standard_filter": 1,
            "description": (
                "Link to the originating customer Sales Order. "
                "Drives margin reporting and procurement status."
            ),
        },
        {
            "fieldname": "alphax_booking_customer",
            "label": "End Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "alphax_against_customer_booking",
            "read_only": 1,
            "fetch_from": "alphax_against_customer_booking.customer",
        },
    ],
    "Purchase Invoice": [
        {
            "fieldname": "alphax_vendor_section",
            "label": "AlphaX Booking",
            "fieldtype": "Section Break",
            "insert_after": "supplier",
            "collapsible": 1,
        },
        {
            "fieldname": "alphax_against_customer_booking",
            "label": "Against Customer Booking",
            "fieldtype": "Link",
            "options": "Sales Order",
            "insert_after": "alphax_vendor_section",
            "in_standard_filter": 1,
        },
        {
            "fieldname": "alphax_booking_customer",
            "label": "End Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "alphax_against_customer_booking",
            "read_only": 1,
            "fetch_from": "alphax_against_customer_booking.customer",
        },
    ],
}


def _ensure_custom_fields():
    create_custom_fields(CUSTOM_FIELDS, update=True)


# ----------------------------------------------------------------------------
# Wallet Settings — single doctype
# ----------------------------------------------------------------------------
def _ensure_wallet_settings():
    if not frappe.db.exists("Wallet Settings", "Wallet Settings"):
        # Pick the most sensible default currency:
        #   1. The system default (frappe.db.get_default("currency"))
        #   2. The default company's base currency
        #   3. None — admin must set it explicitly during onboarding
        default_currency = frappe.db.get_default("currency")
        if not default_currency:
            default_company = frappe.db.get_single_value(
                "Global Defaults", "default_company"
            )
            if default_company:
                default_currency = frappe.db.get_value(
                    "Company", default_company, "default_currency"
                )

        doc = frappe.get_doc({
            "doctype": "Wallet Settings",
            "auto_create_wallet_on_customer": 1,
            "default_currency": default_currency,
            "topup_approval_threshold": 100000,
            "hold_expiry_hours": 24,
            "reconciliation_email_recipients": "",
        })
        doc.insert(ignore_permissions=True)


# ----------------------------------------------------------------------------
# Default GL Accounts — best-effort, never fails install
# ----------------------------------------------------------------------------
def _ensure_default_accounts():
    """
    Try to create a 'Customer Wallet Liability' account under each Company.
    If the chart of accounts doesn't have a clean parent, we silently skip —
    the admin can pick an account in Wallet Settings instead.
    """
    try:
        for company in frappe.get_all("Company", pluck="name"):
            _create_account_for_company(company)
    except Exception:
        frappe.log_error(
            title="AlphaX Wallet: default account creation skipped",
            message=frappe.get_traceback(),
        )


def _create_account_for_company(company):
    abbr = frappe.db.get_value("Company", company, "abbr")
    account_name = f"Customer Wallet Liability - {abbr}"
    if frappe.db.exists("Account", account_name):
        return

    # Find a parent: prefer "Current Liabilities", fall back to any group
    # under root_type Liability.
    parent = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": "Current Liabilities", "is_group": 1},
        "name",
    ) or frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Liability", "is_group": 1},
        "name",
    )
    if not parent:
        return

    doc = frappe.get_doc({
        "doctype": "Account",
        "account_name": "Customer Wallet Liability",
        "parent_account": parent,
        "company": company,
        # No account_type — this is a plain liability ledger. Setting it to
        # Payable would force party_type tracking on every JE row, which
        # conflicts with party_type=Customer in the wallet GL postings.
        "root_type": "Liability",
        "is_group": 0,
    })
    doc.insert(ignore_permissions=True)
