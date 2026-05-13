// Surfaces the wallet top-up flag visibly on Payment Entry
frappe.ui.form.on("Payment Entry", {
    refresh(frm) {
        if (frm.doc.is_wallet_topup) {
            frm.dashboard.add_indicator(__("Wallet Top-up"), "green");
        }
        if (frm.doc.party_type === "Customer" && !frm.is_new() && frm.doc.docstatus === 1) {
            // Show resulting wallet balance after submit
            frappe.db.get_value(
                "Customer Wallet",
                { customer: frm.doc.party },
                ["current_balance", "currency"],
            ).then((r) => {
                if (r.message && r.message.current_balance !== undefined) {
                    frm.dashboard.add_indicator(
                        __("Wallet Balance: {0}", [
                            format_currency(r.message.current_balance, r.message.currency),
                        ]),
                        "blue",
                    );
                }
            });
        }
    },
    is_wallet_topup(frm) {
        if (frm.doc.is_wallet_topup) {
            frappe.show_alert({
                message: __("On submit, this Payment Entry will credit the customer wallet."),
                indicator: "blue",
            });
        }
    },
});
