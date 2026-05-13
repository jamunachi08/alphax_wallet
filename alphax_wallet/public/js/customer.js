// AlphaX Wallet — Customer form integration
frappe.ui.form.on("Customer", {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__("Open Wallet"), () => {
            frappe.db.get_value(
                "Customer Wallet",
                { customer: frm.doc.name },
                "name",
            ).then((r) => {
                if (r.message && r.message.name) {
                    frappe.set_route("Form", "Customer Wallet", r.message.name);
                } else {
                    frappe.new_doc("Customer Wallet", { customer: frm.doc.name });
                }
            });
        }, __("AlphaX Wallet"));

        frm.add_custom_button(__("Wallet Transactions"), () => {
            frappe.set_route("List", "Wallet Transaction", { customer: frm.doc.name });
        }, __("AlphaX Wallet"));

        frm.add_custom_button(__("Top-up Request"), () => {
            frappe.new_doc("Wallet Topup Request", {
                customer: frm.doc.name,
                currency: frm.doc.default_currency,
            });
        }, __("AlphaX Wallet"));

        frm.add_custom_button(__("Booking Flow"), () => {
            frappe.set_route("alphax-booking-flow");
            // The page reads the customer filter from its own picker
        }, __("AlphaX Wallet"));

        // Restrict the Wallet Debit Account picker to non-group Liability accounts
        // belonging to the same company as Wallet Settings' default_company.
        apply_debit_account_filter(frm);
    },
});

function apply_debit_account_filter(frm) {
    frm.set_query("alphax_debit_account", () => {
        return {
            filters: {
                is_group: 0,
                root_type: "Liability",
            },
        };
    });
}
