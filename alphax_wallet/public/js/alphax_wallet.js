// AlphaX Wallet — global desk JS
// ================================
// Applies the active Wallet Brand on every page load. The brand resolves
// to the user's active Company; when the user switches Company via the
// navbar, we refetch and re-apply.

frappe.provide("alphax_wallet");

alphax_wallet.brand = null;

// ---------------------------------------------------------------------------
// Apply a brand payload — injects CSS variables and exposes brand data
// ---------------------------------------------------------------------------
alphax_wallet.apply_brand = function (brand) {
    if (!brand) return;
    alphax_wallet.brand = brand;

    // Inject palette as CSS variables
    let style_el = document.getElementById("alphax-brand-vars");
    if (!style_el) {
        style_el = document.createElement("style");
        style_el.id = "alphax-brand-vars";
        document.head.appendChild(style_el);
    }
    const mapping = {
        primary: "--ax-primary",
        primary_dark: "--ax-primary-dark",
        primary_light: "--ax-primary-light",
        primary_soft: "--ax-primary-soft",
        accent: "--ax-accent",
        accent_light: "--ax-accent-light",
        pink: "--ax-pink",
        pink_dark: "--ax-pink-dark",
        dark_base: "--ax-dark-base",
        dark_mid: "--ax-dark-mid",
        dark_elev: "--ax-dark-elev",
        text_on_dark: "--ax-text-on-dark",
        text_on_dark_muted: "--ax-text-on-dark-muted",
        text_on_dark_faint: "--ax-text-on-dark-faint",
    };
    const rules = [":root {"];
    const palette = brand.palette || {};
    Object.entries(mapping).forEach(([field, varname]) => {
        const val = palette[field];
        if (val) {
            rules.push(`  ${varname}: ${val};`);
            rules.push(`  ${varname.replace("--ax-", "--alphax-")}: ${val};`);
        }
    });
    rules.push("}");
    style_el.textContent = rules.join("\n");

    // Update the favicon (best-effort — some browsers cache aggressively)
    if (brand.favicon) {
        let link = document.querySelector('link[rel="icon"]');
        if (!link) {
            link = document.createElement("link");
            link.rel = "icon";
            document.head.appendChild(link);
        }
        link.href = brand.favicon;
    }
};

// Fetch the active brand from the server (used after Company switch)
alphax_wallet.fetch_brand = function (company) {
    return frappe.call({
        method: "alphax_wallet.alphax_wallet.doctype.wallet_brand.wallet_brand.get_active_brand",
        args: { company: company || null },
    }).then((r) => {
        if (r.message) {
            alphax_wallet.apply_brand(r.message);
            return r.message;
        }
    });
};

// Apply boot-time brand immediately
$(document).ready(function () {
    const boot = frappe.boot || {};
    if (boot.alphax_wallet_brand) {
        alphax_wallet.apply_brand(boot.alphax_wallet_brand);
    }
});

// Listen for the user switching Company via the navbar.
// Frappe fires `frappe.realtime` events for some things but Company changes
// don't have a built-in event — we poll the active Company once on each
// page-change which is cheap.
let _last_company = null;
$(document).on("page-change", function () {
    const current = frappe.defaults.get_user_default("Company");
    if (current && current !== _last_company) {
        _last_company = current;
        // Only re-fetch if we already had a brand applied (skip the first load)
        if (alphax_wallet.brand) {
            alphax_wallet.fetch_brand(current);
        }
    }

    // Preview-mode: dashboard with ?preview_brand=Name
    const route = frappe.get_route();
    if (route && route[0] === "alphax-wallet-dashboard") {
        const preview = frappe.utils.get_url_arg("preview_brand");
        if (preview) {
            frappe.db.get_doc("Wallet Brand", preview).then((doc) => {
                if (doc) {
                    alphax_wallet.apply_brand({
                        name: doc.name,
                        brand_display_name: doc.brand_display_name,
                        tagline: doc.tagline,
                        logo: doc.logo,
                        logo_on_dark: doc.logo_on_dark || doc.logo,
                        favicon: doc.favicon,
                        palette: {
                            primary: doc.primary, primary_dark: doc.primary_dark,
                            primary_light: doc.primary_light, primary_soft: doc.primary_soft,
                            accent: doc.accent, accent_light: doc.accent_light,
                            pink: doc.pink, pink_dark: doc.pink_dark,
                            dark_base: doc.dark_base, dark_mid: doc.dark_mid,
                            dark_elev: doc.dark_elev,
                            text_on_dark: doc.text_on_dark,
                            text_on_dark_muted: doc.text_on_dark_muted,
                            text_on_dark_faint: doc.text_on_dark_faint,
                        },
                    });
                }
            });
        }
    }
});

// ---------------------------------------------------------------------------
// Helper API
// ---------------------------------------------------------------------------
alphax_wallet.check_balance = function (customer, callback) {
    frappe.call({
        method: "alphax_wallet.api.wallet.get_balance",
        args: { customer: customer },
        callback: (r) => callback && callback(r.message),
    });
};
