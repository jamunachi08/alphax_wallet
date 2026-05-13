from . import __version__ as app_version

app_name = "alphax_wallet"
app_title = "AlphaX Wallet"
app_publisher = "AlphaX"
app_description = "Customer wallet, booking integration, and multi-party settlement on top of ERPNext"
app_email = "support@alphax.io"
app_license = "MIT"
app_version = app_version
required_apps = ["frappe", "erpnext"]

# Branding / icon — these power the Installed Apps card AND the desktop icon
app_logo_url = "/assets/alphax_wallet/images/alphax-logo.svg"
app_icon = "octicon octicon-credit-card"
app_color = "#7A2F87"

# Brand assets used by the "Installed Apps" page in Setup.
# The path must be served as a static asset; the file lives in public/images/.
brand_html = (
    '<span style="display:inline-flex;align-items:center;gap:8px;">'
    '<img src="/assets/alphax_wallet/images/alphax-logo.svg" '
    'style="height:18px;width:18px;border-radius:4px;"/>'
    '<b style="color:#7A2F87;">AlphaX Wallet</b>'
    '</span>'
)

# ----------------------------------------------------------------------------
# Boot session — push the active theme to the browser on every page load
# ----------------------------------------------------------------------------
boot_session = "alphax_wallet.alphax_wallet.boot.boot_session"

# ----------------------------------------------------------------------------
# Includes in <head>
# ----------------------------------------------------------------------------
app_include_css = "/assets/alphax_wallet/css/alphax_wallet.css"
app_include_js = "/assets/alphax_wallet/js/alphax_wallet.js"

# ----------------------------------------------------------------------------
# DocType client scripts (form-level JS) — extends standard DocTypes
# ----------------------------------------------------------------------------
doctype_js = {
    "Customer": "public/js/customer.js",
    "Payment Entry": "public/js/payment_entry.js",
    "Sales Order": "public/js/sales_order.js",
    "Sales Invoice": "public/js/sales_invoice.js",
}

# ----------------------------------------------------------------------------
# Document events — server-side hooks into core DocTypes
# ----------------------------------------------------------------------------
doc_events = {
    "Customer": {
        "after_insert": "alphax_wallet.alphax_wallet.events.customer.auto_create_wallet",
    },
    "Payment Entry": {
        "on_submit": [
            "alphax_wallet.alphax_wallet.events.payment_entry.handle_wallet_topup",
            "alphax_wallet.alphax_wallet.events.purchase_documents.update_so_on_supplier_payment",
        ],
        "on_cancel": "alphax_wallet.alphax_wallet.events.payment_entry.reverse_wallet_topup",
    },
    "Sales Order": {
        "on_submit": [
            "alphax_wallet.alphax_wallet.events.sales_order.place_wallet_hold",
            "alphax_wallet.alphax_wallet.events.purchase_documents.init_procurement_status_on_so",
        ],
        "on_cancel": "alphax_wallet.alphax_wallet.events.sales_order.release_wallet_hold",
    },
    "Sales Invoice": {
        "on_submit": "alphax_wallet.alphax_wallet.events.sales_invoice.capture_wallet_hold",
        "on_cancel": "alphax_wallet.alphax_wallet.events.sales_invoice.reverse_wallet_capture",
    },
    "Delivery Note": {
        "on_submit": "alphax_wallet.alphax_wallet.events.delivery_note.recognise_revenue",
    },
    "Purchase Order": {
        "on_submit": "alphax_wallet.alphax_wallet.events.purchase_documents.update_so_on_po_submit",
        "on_cancel": "alphax_wallet.alphax_wallet.events.purchase_documents.update_so_on_po_cancel",
    },
    "Purchase Invoice": {
        "on_submit": "alphax_wallet.alphax_wallet.events.purchase_documents.update_so_on_pi_submit",
        "on_cancel": "alphax_wallet.alphax_wallet.events.purchase_documents.update_so_on_pi_cancel",
    },
}

# ----------------------------------------------------------------------------
# Scheduled jobs
# ----------------------------------------------------------------------------
scheduler_events = {
    "daily": [
        "alphax_wallet.alphax_wallet.tasks.reconcile_wallet_liability",
        "alphax_wallet.alphax_wallet.tasks.expire_stale_holds",
    ],
    "weekly": [
        "alphax_wallet.alphax_wallet.tasks.send_supplier_settlement_statements",
    ],
    "hourly": [
        "alphax_wallet.alphax_wallet.tasks.process_pending_topup_requests",
    ],
}

# ----------------------------------------------------------------------------
# Permissions — restrict wallet visibility per customer for portal users
# ----------------------------------------------------------------------------
permission_query_conditions = {
    "Customer Wallet": "alphax_wallet.alphax_wallet.permissions.wallet_query",
    "Wallet Transaction": "alphax_wallet.alphax_wallet.permissions.transaction_query",
}

has_permission = {
    "Customer Wallet": "alphax_wallet.alphax_wallet.permissions.has_wallet_permission",
    "Wallet Transaction": "alphax_wallet.alphax_wallet.permissions.has_transaction_permission",
}

# ----------------------------------------------------------------------------
# Fixtures — ship default Roles and Custom Fields with the app
# ----------------------------------------------------------------------------
fixtures = [
    {"dt": "Role", "filters": [["role_name", "in", [
        "Wallet Manager", "Wallet User", "Wallet Auditor"
    ]]]},
    {"dt": "Custom Field", "filters": [["fieldname", "in", [
        "alphax_wallet_section", "alphax_wallet_balance", "alphax_debit_account",
        "use_wallet_payment", "wallet_hold_reference",
        "alphax_vendor_section", "alphax_procurement_status",
        "alphax_against_customer_booking", "alphax_booking_customer",
        "is_wallet_topup",
        "alphax_commission_employee", "alphax_commission_rate",
    ]]]},
    {"dt": "Wallet Brand"},
]

# ----------------------------------------------------------------------------
# Website / Portal
# ----------------------------------------------------------------------------
website_route_rules = [
    {"from_route": "/wallet", "to_route": "wallet"},
]

# ----------------------------------------------------------------------------
# After install / migrate hooks — bootstrap defaults
# ----------------------------------------------------------------------------
after_install = "alphax_wallet.install.after_install"
after_migrate = ["alphax_wallet.install.after_migrate"]

# ----------------------------------------------------------------------------
# Override / Whitelisted methods — exposed via /api/method/*
# ----------------------------------------------------------------------------
# (kept implicit via @frappe.whitelist() decorators in api modules)
