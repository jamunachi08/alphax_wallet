frappe.ui.form.on("Booking Commission", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Auto-fetch Bookings"), () => {
                frm.call("auto_fetch_bookings").then((r) => {
                    if (r.message !== undefined) {
                        frappe.show_alert({
                            message: __("Loaded {0} booking(s)", [r.message]),
                            indicator: "green",
                        });
                        frm.refresh();
                    }
                });
            }, __("Actions"));
        }
        if (frm.doc.additional_salary) {
            frm.add_custom_button(__("Open Additional Salary"), () => {
                frappe.set_route("Form", "Additional Salary", frm.doc.additional_salary);
            });
        }
    },
});
