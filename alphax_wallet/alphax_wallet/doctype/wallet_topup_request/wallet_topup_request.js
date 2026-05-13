frappe.ui.form.on("Wallet Topup Request", {
    refresh(frm) {
        if (frm.doc.docstatus !== 0) return;

        if (frm.doc.status === "Pending" && frappe.user.has_role("Wallet Manager")) {
            frm.add_custom_button(__("Approve"), () => {
                frappe.confirm(__("Approve this top-up request?"), () => {
                    frm.call("approve").then(() => frm.reload_doc());
                });
            }).addClass("btn-primary");

            frm.add_custom_button(__("Reject"), () => {
                frappe.prompt(
                    [{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1 }],
                    (v) => frm.call("reject", { reason: v.reason }).then(() => frm.reload_doc()),
                    __("Reject Top-up Request"),
                );
            });
        }

        const colour = {
            Pending: "orange", Approved: "blue",
            Rejected: "red", Processed: "green",
        }[frm.doc.status] || "gray";
        frm.page.set_indicator(frm.doc.status, colour);
    },
});
