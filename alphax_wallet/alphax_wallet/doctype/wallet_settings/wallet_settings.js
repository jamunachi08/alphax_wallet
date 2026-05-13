// AlphaX Wallet — Wallet Settings form
//
// Dropdown filters: every account field below restricts the user to ledger
// accounts only (is_group = 0) with the correct root_type / account_type, and
// scoped to the selected Default Company. The server-side validation in
// wallet_settings.py is the safety net; this is the UX layer.

frappe.ui.form.on("Wallet Settings", {
    refresh(frm) {
        frm.dashboard.add_comment(
            __("These settings power the entire AlphaX Wallet flow. Make sure all four GL accounts are set before going live."),
            "blue", true
        );

        frm.add_custom_button(__("Run Reconciliation Now"), () => {
            frappe.call({
                method: "alphax_wallet.alphax_wallet.tasks.reconcile_wallet_liability",
                callback: (r) => {
                    if (r.message) {
                        const msg = r.message.in_sync
                            ? __("✅ Wallet ledger and GL match perfectly.")
                            : __("⚠️ Drift detected: ledger {0}, GL {1}, diff {2}",
                                [r.message.ledger_total, r.message.gl_total, r.message.difference]);
                        frappe.msgprint({ title: __("Reconciliation"), message: msg });
                    }
                },
            });
        });

        // Diagnostics — surface every place that could cause currency or drift errors
        frm.add_custom_button(__("Run Diagnostics"), () => {
            run_diagnostics(frm);
        }, __("Tools"));

        // Quick way to create a Currency Exchange record
        frm.add_custom_button(__("Add Currency Exchange"), () => {
            show_currency_exchange_dialog(frm);
        }, __("Tools"));

        apply_account_filters(frm);
    },

    default_company(frm) {
        // Re-apply filters so each Link field re-queries with the new company,
        // and clear any selections that no longer belong to it.
        apply_account_filters(frm);
        clear_accounts_from_other_company(frm);
    },
});

// ---------------------------------------------------------------------------
// Filter definitions — one per account field
// ---------------------------------------------------------------------------
function apply_account_filters(frm) {
    // Wallet Liability — must be a Liability ledger account
    frm.set_query("wallet_liability_account", () => ({
        filters: {
            is_group: 0,
            root_type: "Liability",
            company: frm.doc.default_company,
        },
    }));

    // Default Bank Account — must be a Bank or Cash ledger account
    frm.set_query("default_bank_account", () => ({
        filters: {
            is_group: 0,
            account_type: ["in", ["Bank", "Cash"]],
            company: frm.doc.default_company,
        },
    }));

    // Deferred Revenue — Liability or Income ledger account
    frm.set_query("deferred_revenue_account", () => ({
        filters: {
            is_group: 0,
            root_type: ["in", ["Liability", "Income"]],
            company: frm.doc.default_company,
        },
    }));

    // Commission Expense — Expense ledger account
    frm.set_query("commission_expense_account", () => ({
        filters: {
            is_group: 0,
            root_type: "Expense",
            company: frm.doc.default_company,
        },
    }));
}

// If the company changes, blank out any account that belonged to the old
// company so the user is forced to pick a valid one for the new company.
function clear_accounts_from_other_company(frm) {
    const fields = [
        "wallet_liability_account",
        "default_bank_account",
        "deferred_revenue_account",
        "commission_expense_account",
    ];
    fields.forEach((fname) => {
        const value = frm.doc[fname];
        if (!value) return;
        frappe.db.get_value("Account", value, "company").then((r) => {
            if (r.message && r.message.company && r.message.company !== frm.doc.default_company) {
                frm.set_value(fname, null);
            }
        });
    });
}

// ---------------------------------------------------------------------------
// Diagnostics dialog
// ---------------------------------------------------------------------------
function run_diagnostics(frm) {
    frappe.call({
        method: "alphax_wallet.alphax_wallet.api_diagnostics.run_currency_audit",
        freeze: true,
        freeze_message: __("Running diagnostics..."),
        callback: (r) => {
            if (r.message) {
                render_diagnostics_dialog(r.message);
            }
        },
    });
}

function render_diagnostics_dialog(result) {
    const sev_colour = { error: "#DC2626", warning: "#D97706", info: "#7A2F87" };
    const sev_icon = { error: "✕", warning: "⚠", info: "ⓘ" };

    let body = `
        <div style="font-size:13px;color:#374151;">
            <div style="background:#F9FAFB;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:12.5px;">
                <b>${__("Company base currency:")}</b> ${result.company_base_currency || "—"}<br>
                <b>${__("Checked at:")}</b> ${result.checked_at}<br>
                <b>${__("Status:")}</b> ${
                    result.status === "clean"
                        ? `<span style="color:#7A2F87;">✓ ${__("Clean")}</span>`
                        : `<span style="color:#DC2626;">${__("Issues found")}</span>`
                }
            </div>
    `;

    if (result.status === "clean") {
        body += `<div style="text-align:center;padding:30px;color:#6B7280;">
            <div style="font-size:48px;margin-bottom:12px;">✓</div>
            <div>${result.summary}</div>
        </div>`;
    } else {
        result.findings.forEach((f) => {
            const colour = sev_colour[f.severity];
            const icon = sev_icon[f.severity];
            body += `
                <div style="border-left:4px solid ${colour};background:#FFFFFF;
                            border:1px solid #E5E7EB;border-radius:8px;
                            margin-bottom:14px;padding:14px 16px;">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                        <span style="color:${colour};font-weight:700;font-size:16px;">${icon}</span>
                        <b style="color:${colour};">${f.title}</b>
                        <span style="margin-left:auto;color:#9CA3AF;font-size:11px;">
                            ${__("count")}: ${f.count}
                        </span>
                    </div>
                    <div style="font-size:12.5px;color:#4B5563;margin-bottom:8px;">
                        ${f.explanation}
                    </div>
                    <div style="background:#F9F2FA;border-radius:6px;padding:8px 12px;
                                font-size:12px;color:#5A1F66;margin-bottom:10px;">
                        <b>${__("How to fix:")}</b> ${f.fix}
                    </div>
            `;

            // Render rows table
            if (f.rows && f.rows.length) {
                const cols = Object.keys(f.rows[0]);
                body += `<div style="overflow-x:auto;max-height:200px;overflow-y:auto;">
                    <table style="width:100%;font-size:11.5px;border-collapse:collapse;">
                        <thead><tr style="background:#F9FAFB;">`;
                cols.forEach(c => {
                    body += `<th style="padding:6px 8px;text-align:left;
                              border-bottom:1px solid #E5E7EB;color:#6B7280;
                              text-transform:uppercase;font-size:10px;letter-spacing:0.04em;">
                              ${c}</th>`;
                });
                body += `</tr></thead><tbody>`;
                f.rows.forEach(row => {
                    body += `<tr>`;
                    cols.forEach(c => {
                        let val = row[c];
                        if (val === null || val === undefined) val = "—";
                        body += `<td style="padding:6px 8px;border-bottom:1px solid #F3F4F6;">
                                 ${frappe.utils.escape_html(String(val))}</td>`;
                    });
                    body += `</tr>`;
                });
                body += `</tbody></table></div>`;
            }
            body += `</div>`;
        });
    }
    body += `</div>`;

    const d = new frappe.ui.Dialog({
        title: __("AlphaX Wallet — Diagnostics"),
        size: "extra-large",
        fields: [{ fieldtype: "HTML", fieldname: "body", options: body }],
        primary_action_label: __("Close"),
        primary_action() { d.hide(); },
    });
    d.show();
}

// ---------------------------------------------------------------------------
// Add Currency Exchange dialog
// ---------------------------------------------------------------------------
function show_currency_exchange_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Add Currency Exchange"),
        fields: [
            {
                fieldname: "info", fieldtype: "HTML",
                options: `<div class="alert alert-info" style="margin-bottom:12px;font-size:12.5px;">
                    ${__("Quick way to add a Currency Exchange record. Use this when you get 'Unable to find exchange rate' errors.")}
                </div>`,
            },
            { fieldname: "from_currency", label: __("From Currency"),
              fieldtype: "Link", options: "Currency", reqd: 1 },
            { fieldname: "to_currency", label: __("To Currency"),
              fieldtype: "Link", options: "Currency", reqd: 1 },
            { fieldname: "exchange_rate", label: __("Exchange Rate"),
              fieldtype: "Float", reqd: 1, precision: 6,
              description: __("How many [To] for one [From]. Example: 1 INR = 0.044 SAR → enter 0.044") },
            { fieldname: "date", label: __("Date"),
              fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            frappe.call({
                method: "alphax_wallet.alphax_wallet.api_diagnostics.create_currency_exchange",
                args: values,
                callback: (r) => {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Created Currency Exchange: {0}", [r.message]),
                            indicator: "green",
                        });
                        d.hide();
                    }
                },
            });
        },
    });
    d.show();
}
