"""
v1.5 migration: rename Wallet Theme → Wallet Brand and convert records.

For each existing Wallet Theme:
- Create a Wallet Brand record keyed to the user's default Company
- Copy all palette tokens
- Set the new brand as active for that Company if the old theme was default

Also:
- Drop the obsolete wallet_theme Custom Field on Customer
- Drop the obsolete theme_mode / default_theme fields from Wallet Settings
"""

import frappe


def execute():
    if frappe.db.table_exists("tabWallet Theme"):
        _migrate_themes_to_brands()

    _drop_obsolete_customer_field()
    _drop_obsolete_settings_fields()


def _migrate_themes_to_brands():
    default_company = (
        frappe.db.get_single_value("Wallet Settings", "default_company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not default_company:
        frappe.log_error(
            title="AlphaX Wallet v1.5: cannot migrate themes",
            message="No default Company found. Themes left in place; manually migrate them.",
        )
        return

    if not frappe.db.exists("DocType", "Wallet Brand"):
        # New doctype not yet installed — skip; will re-run on next migrate
        return

    themes = frappe.get_all(
        "Wallet Theme",
        fields=["name", "theme_name", "status", "is_default", "logo",
                "primary", "primary_dark", "primary_light", "primary_soft",
                "accent", "accent_light", "pink", "pink_dark",
                "dark_base", "dark_mid", "dark_elev",
                "text_on_dark", "text_on_dark_muted", "text_on_dark_faint",
                "notes"],
    )
    for t in themes:
        # Skip if already migrated
        new_name = (t.theme_name or t.name).lower().replace(" ", "-")
        if frappe.db.exists("Wallet Brand", new_name):
            continue

        brand = frappe.get_doc({
            "doctype": "Wallet Brand",
            "brand_name": new_name,
            "company": default_company,
            "brand_display_name": t.theme_name or "Migrated Brand",
            "status": t.status or "Active",
            "is_active": bool(t.is_default),
            "logo": t.logo,
            "primary": t.primary, "primary_dark": t.primary_dark,
            "primary_light": t.primary_light, "primary_soft": t.primary_soft,
            "accent": t.accent, "accent_light": t.accent_light,
            "pink": t.pink, "pink_dark": t.pink_dark,
            "dark_base": t.dark_base, "dark_mid": t.dark_mid,
            "dark_elev": t.dark_elev,
            "text_on_dark": t.text_on_dark,
            "text_on_dark_muted": t.text_on_dark_muted,
            "text_on_dark_faint": t.text_on_dark_faint,
            "notes": f"Migrated from Wallet Theme '{t.name}'. {t.notes or ''}",
        })
        try:
            brand.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            frappe.log_error(
                title=f"AlphaX Wallet v1.5: failed to migrate theme {t.name}",
                message=frappe.get_traceback(),
            )


def _drop_obsolete_customer_field():
    """Remove the wallet_theme Custom Field from Customer (no longer used)."""
    name = frappe.db.exists("Custom Field",
                             {"dt": "Customer", "fieldname": "wallet_theme"})
    if name:
        frappe.delete_doc("Custom Field", name, ignore_permissions=True)


def _drop_obsolete_settings_fields():
    """Wallet Settings no longer has theme_mode / default_theme.
    They're standard fields, so we just clear any stored value via SQL
    (the columns may already be dropped by the JSON schema sync)."""
    try:
        frappe.db.sql("""
            UPDATE `tabSingles` SET value = NULL
            WHERE doctype = 'Wallet Settings'
              AND field IN ('theme_mode', 'default_theme')
        """)
    except Exception:
        pass  # column doesn't exist anymore — fine
