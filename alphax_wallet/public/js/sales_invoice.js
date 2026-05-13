frappe.ui.form.on("Sales Invoice", {
    refresh(frm) {
        if (frm.doc.use_wallet_payment) {
            frm.dashboard.add_indicator(__("Wallet Capture"), "blue");
        }
    },
});
