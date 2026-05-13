"""
Wallet Brand — a per-Company brand profile.

One Wallet Brand per ERPNext Company. The active brand for a user is
resolved by looking up the Wallet Brand whose Company matches the user's
currently-active Company (frappe.defaults.get_user_default("Company")).

Behaviour:
- Exactly one Wallet Brand per Company can have is_active=1. Setting it
  on one record clears it on all others for the same Company.
- The palette can be auto-derived from an uploaded logo (the client-side
  Canvas extractor sends dominant hex values; the server derives the rest
  using HSL math in palette_utils).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from alphax_wallet.alphax_wallet import palette_utils


class WalletBrand(Document):
    def validate(self):
        # Ensure only one active brand per Company
        if self.is_active and self.company:
            others = frappe.db.sql_list("""
                SELECT name FROM `tabWallet Brand`
                WHERE company = %s AND is_active = 1 AND name != %s
            """, (self.company, self.name or ""))
            if others:
                # Don't fail — just deactivate the previous active brand
                frappe.db.sql(
                    "UPDATE `tabWallet Brand` SET is_active = 0 "
                    "WHERE company = %s AND is_active = 1 AND name != %s",
                    (self.company, self.name or ""),
                )

        # Fall back: brand_display_name defaults to brand_name if blank
        if not self.brand_display_name:
            self.brand_display_name = self.brand_name

    def after_insert(self):
        # If this is the first brand for the Company, make it active
        count = frappe.db.count("Wallet Brand", {"company": self.company})
        if count == 1 and not self.is_active:
            self.db_set("is_active", 1)

    @frappe.whitelist()
    def auto_generate(self, seed_colors):
        """Derive the full palette from a small seed dict (sent by client JS)."""
        if isinstance(seed_colors, str):
            import json as _json
            seed_colors = _json.loads(seed_colors)

        palette = palette_utils.derive_palette(seed_colors or {})
        for field, value in palette.items():
            if self.meta.has_field(field):
                self.set(field, value)
        self.save()
        return palette

    @frappe.whitelist()
    def activate(self):
        """One-click 'set as active brand for this Company'."""
        if not self.company:
            frappe.throw(_("Cannot activate: this brand has no Company assigned."))
        self.is_active = 1
        self.save()
        return {"activated": self.name, "company": self.company}

    def get_brand_dict(self) -> dict:
        """Return brand data as a flat dict (used by frontend + email templates)."""
        return {
            "name": self.name,
            "company": self.company,
            "brand_name": self.brand_name,
            "brand_display_name": self.brand_display_name or self.brand_name,
            "tagline": self.tagline,
            "support_email": self.support_email,
            "support_phone": self.support_phone,
            "logo": self.logo,
            "logo_on_dark": self.logo_on_dark or self.logo,
            "favicon": self.favicon,
            "footer_html": self.footer_html,
            "palette": self.get_palette_dict(),
        }

    def get_palette_dict(self) -> dict:
        return {
            "primary": self.primary,
            "primary_dark": self.primary_dark,
            "primary_light": self.primary_light,
            "primary_soft": self.primary_soft,
            "accent": self.accent,
            "accent_light": self.accent_light,
            "pink": self.pink,
            "pink_dark": self.pink_dark,
            "dark_base": self.dark_base,
            "dark_mid": self.dark_mid,
            "dark_elev": self.dark_elev,
            "text_on_dark": self.text_on_dark,
            "text_on_dark_muted": self.text_on_dark_muted,
            "text_on_dark_faint": self.text_on_dark_faint,
        }


# ============================================================================
# Module-level whitelisted helpers
# ============================================================================

@frappe.whitelist(allow_guest=False)
def get_active_brand(company: str = None) -> dict:
    """
    Resolve the active brand for the given Company (or the user's default
    Company if none provided).

    Resolution order:
      1. Active Wallet Brand for the specified/default Company
      2. Active Wallet Brand for ANY Company (so single-tenant benches Just Work)
      3. Hardcoded built-in default (Nozol palette + 'AlphaX Wallet' name)
    """
    company = company or frappe.defaults.get_user_default("Company") \
        or frappe.db.get_single_value("Global Defaults", "default_company")

    brand_name = None
    if company:
        brand_name = frappe.db.get_value(
            "Wallet Brand",
            {"company": company, "is_active": 1, "status": "Active"},
            "name",
        )

    if not brand_name:
        # Fall back to any active brand (covers single-tenant benches where
        # the user just set up one brand without worrying about Company)
        brand_name = frappe.db.get_value(
            "Wallet Brand",
            {"is_active": 1, "status": "Active"},
            "name",
        )

    if not brand_name:
        return _builtin_default_brand()

    brand = frappe.get_doc("Wallet Brand", brand_name)
    return brand.get_brand_dict()


@frappe.whitelist(allow_guest=True)
def get_active_brand_css(company: str = None) -> str:
    """Return raw CSS for the active brand. Public so the portal can use it."""
    brand = get_active_brand(company=company)
    return palette_utils.palette_to_css_variables(brand.get("palette") or {})


@frappe.whitelist(allow_guest=True)
def get_brand_for_customer(customer: str) -> dict:
    """Resolve a customer's effective brand by their Company link."""
    if not customer or not frappe.db.exists("Customer", customer):
        return _builtin_default_brand()

    # Customer.company is not standard but commonly added; fall back to default
    company = frappe.db.get_value("Customer", customer, "default_company") \
        or frappe.defaults.get_global_default("Company")
    return get_active_brand(company=company)


def _builtin_default_brand() -> dict:
    """Returned when no Wallet Brand is configured — keeps the app usable."""
    return {
        "name": "(built-in)",
        "company": None,
        "brand_name": "alphax-wallet",
        "brand_display_name": "AlphaX Wallet",
        "tagline": None,
        "support_email": None,
        "support_phone": None,
        "logo": "/assets/alphax_wallet/images/alphax-logo.svg",
        "logo_on_dark": "/assets/alphax_wallet/images/alphax-logo.svg",
        "favicon": None,
        "footer_html": None,
        "palette": {
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
        },
    }
