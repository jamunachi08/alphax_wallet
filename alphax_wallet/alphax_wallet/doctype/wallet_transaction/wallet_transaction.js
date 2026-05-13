// AlphaX Wallet — Wallet Transaction form
frappe.ui.form.on("Wallet Transaction", {
    refresh(frm) {
        // Status indicator
        const colour_map = {
            Active: "green", Released: "gray", Captured: "blue",
            Reversed: "red", Expired: "orange",
        };
        if (frm.doc.status) {
            frm.page.set_indicator(frm.doc.status, colour_map[frm.doc.status] || "gray");
        }

        // Quick navigation
        if (frm.doc.journal_entry) {
            frm.add_custom_button(__("Open Journal Entry"), () => {
                frappe.set_route("Form", "Journal Entry", frm.doc.journal_entry);
            });
        }
        if (frm.doc.related_hold) {
            frm.add_custom_button(__("View Hold"), () => {
                frappe.set_route("Form", "Wallet Transaction", frm.doc.related_hold);
            });
        }
        if (frm.doc.reference_doctype && frm.doc.reference_name) {
            frm.add_custom_button(__("Open {0}", [frm.doc.reference_doctype]), () => {
                frappe.set_route("Form", frm.doc.reference_doctype, frm.doc.reference_name);
            });
        }

        // Reversal action — only for Wallet Manager / System Manager
        // and only on Active, GL-affecting transactions
        const can_reverse = (
            !frm.is_new()
            && frm.doc.status === "Active"
            && ["Deposit", "Withdrawal", "Refund"].includes(frm.doc.transaction_type)
            && (frappe.user.has_role("Wallet Manager") || frappe.user.has_role("System Manager"))
        );
        if (can_reverse) {
            frm.add_custom_button(__("Reverse Transaction"), () => show_reverse_dialog(frm),
                                  __("Actions")).addClass("btn-danger");
        }

        // Active hold? offer to release it
        const can_release = (
            !frm.is_new()
            && frm.doc.transaction_type === "Hold"
            && frm.doc.status === "Active"
            && (frappe.user.has_role("Wallet Manager") || frappe.user.has_role("System Manager"))
        );
        if (can_release) {
            frm.add_custom_button(__("Release Hold"), () => {
                frappe.confirm(
                    __("Release this hold? The reserved amount returns to the customer's available balance."),
                    () => {
                        frappe.call({
                            method: "alphax_wallet.alphax_wallet.api_actions.release_hold",
                            args: { transaction: frm.doc.name },
                            freeze: true,
                            freeze_message: __("Releasing hold..."),
                            callback: (r) => {
                                if (r.message) {
                                    frappe.show_alert({
                                        message: __("Hold released."),
                                        indicator: "green",
                                    });
                                    frm.reload_doc();
                                }
                            },
                        });
                    }
                );
            }, __("Actions"));
        }

        // Accurate informational banner — replaces the misleading old message
        if (!frm.is_new()) {
            const tip = frm.doc.status === "Active"
                ? __("Wallet Transactions are append-only. To reverse this transaction, use Actions → Reverse Transaction (Wallet Manager) or cancel its source document.")
                : __("Wallet Transactions are append-only. This transaction is no longer Active and cannot be reversed.");
            frm.dashboard.add_comment(tip, "yellow", true);
        }
    },
});

// ---------------------------------------------------------------------------
// Reverse dialog
// ---------------------------------------------------------------------------
function show_reverse_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reverse Wallet Transaction"),
        fields: [
            {
                fieldname: "summary_html", fieldtype: "HTML",
                options: `
                    <div class="alert alert-warning" style="margin-bottom:12px;">
                        <b>${__("You are about to reverse this transaction.")}</b><br>
                        <small>${__("A new compensating transaction will be created. The original will be marked Reversed. The linked Journal Entry will be cancelled.")}</small>
                    </div>
                    <table class="table table-bordered" style="margin-bottom:0;">
                        <tr><th style="width:35%;">${__("Transaction")}</th><td>${frm.doc.name}</td></tr>
                        <tr><th>${__("Type")}</th><td>${frm.doc.transaction_type}</td></tr>
                        <tr><th>${__("Amount")}</th><td>${format_currency(frm.doc.amount, frm.doc.currency)}</td></tr>
                        <tr><th>${__("Customer")}</th><td>${frm.doc.customer}</td></tr>
                    </table>
                `,
            },
            {
                fieldname: "reason", fieldtype: "Small Text",
                label: __("Reason for reversal"), reqd: 1,
                description: __("Recorded on the reversal transaction for audit. Be specific."),
            },
        ],
        primary_action_label: __("Confirm Reversal"),
        primary_action(values) {
            frappe.call({
                method: "alphax_wallet.alphax_wallet.api_actions.reverse_transaction",
                args: {
                    transaction: frm.doc.name,
                    reason: values.reason,
                },
                freeze: true,
                freeze_message: __("Reversing transaction..."),
                callback: (r) => {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("Reversed. New transaction: {0}", [r.message.reversal]),
                            indicator: "green",
                        });
                        d.hide();
                        frm.reload_doc();
                    }
                },
            });
        },
    });
    d.show();
}
