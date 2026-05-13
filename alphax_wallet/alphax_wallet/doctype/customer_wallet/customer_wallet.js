// Customer Wallet form behaviour
frappe.ui.form.on("Customer Wallet", {
    refresh(frm) {
        // Show available balance prominently
        if (!frm.is_new()) {
            const available = (frm.doc.current_balance || 0) - (frm.doc.held_amount || 0);
            frm.dashboard.add_indicator(
                __("Available: {0}", [format_currency(available, frm.doc.currency)]),
                available > 0 ? "green" : "red"
            );
            if (frm.doc.held_amount > 0) {
                frm.dashboard.add_indicator(
                    __("Held: {0}", [format_currency(frm.doc.held_amount, frm.doc.currency)]),
                    "orange"
                );
            }
        }

        // Action buttons
        if (!frm.is_new() && frm.doc.status === "Active") {
            frm.add_custom_button(__("Top Up"), () => show_topup_dialog(frm), __("Actions"));
            frm.add_custom_button(__("View Ledger"), () => {
                frappe.set_route("List", "Wallet Transaction", { wallet: frm.doc.name });
            }, __("Actions"));

            // Reversal — Wallet Manager / System Manager only
            if (frappe.user.has_role("Wallet Manager") || frappe.user.has_role("System Manager")) {
                frm.add_custom_button(__("Reverse a Transaction..."), () => {
                    show_pick_reversal_dialog(frm);
                }, __("Actions"));
            }

            frm.add_custom_button(__("Freeze Wallet"), () => {
                frappe.confirm(__("Freeze this wallet? No new transactions will be allowed."),
                    () => frm.call("freeze").then(() => frm.reload_doc()));
            }, __("Actions"));
        }
        if (!frm.is_new() && frm.doc.status === "Frozen") {
            frm.add_custom_button(__("Unfreeze Wallet"), () => {
                frm.call("unfreeze").then(() => frm.reload_doc());
            }, __("Actions"));
        }

        // Set the page indicator colour
        const colour_map = { Active: "green", Frozen: "orange", Closed: "red" };
        frm.page.set_indicator(frm.doc.status, colour_map[frm.doc.status] || "gray");
    },
});

function show_topup_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Top Up Wallet"),
        fields: [
            { fieldname: "amount", label: __("Amount"), fieldtype: "Currency",
              options: frm.doc.currency, reqd: 1 },
            { fieldname: "remarks", label: __("Remarks"), fieldtype: "Small Text" },
        ],
        primary_action_label: __("Top Up"),
        primary_action(values) {
            frm.call("quick_topup", values).then((r) => {
                if (r.message) {
                    frappe.show_alert({
                        message: __("Top-up successful. New balance: {0}",
                            [format_currency(r.message.new_balance, frm.doc.currency)]),
                        indicator: "green",
                    });
                    d.hide();
                    frm.reload_doc();
                }
            });
        },
    });
    d.show();
}

// Reversal: pick a recent Active transaction and reverse it with a reason.
function show_pick_reversal_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reverse a Wallet Transaction"),
        size: "large",
        fields: [
            {
                fieldname: "transaction", label: __("Transaction to Reverse"),
                fieldtype: "Link", options: "Wallet Transaction", reqd: 1,
                get_query: () => ({
                    filters: {
                        wallet: frm.doc.name,
                        status: "Active",
                        transaction_type: ["in", ["Deposit", "Withdrawal", "Refund"]],
                    },
                }),
                description: __("Only Active Deposit/Withdrawal/Refund transactions can be reversed. To release a Hold, open the hold transaction directly."),
            },
            {
                fieldname: "reason", label: __("Reason"),
                fieldtype: "Small Text", reqd: 1,
                description: __("Recorded on the reversal for audit. Be specific."),
            },
        ],
        primary_action_label: __("Reverse"),
        primary_action(values) {
            frappe.confirm(
                __("Reverse {0}? This creates a compensating transaction and cancels the original Journal Entry.", [values.transaction]),
                () => {
                    frappe.call({
                        method: "alphax_wallet.alphax_wallet.api_actions.reverse_transaction",
                        args: values,
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
                }
            );
        },
    });
    d.show();
}
