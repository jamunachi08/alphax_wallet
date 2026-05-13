// Sales Order — wallet payment + vendor procurement helpers
frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.doc.use_wallet_payment) {
            frm.dashboard.add_indicator(__("Pay using Wallet"), "blue");
        }
        if (frm.doc.wallet_hold_reference) {
            frm.add_custom_button(__("View Wallet Hold"), () => {
                frappe.set_route("Form", "Wallet Transaction", frm.doc.wallet_hold_reference);
            });
        }

        // Procurement status indicator
        if (frm.doc.alphax_procurement_status
                && frm.doc.alphax_procurement_status !== "Not Required") {
            const colour = {
                Pending: "orange",
                "PO Issued": "blue",
                Received: "cyan",
                "Vendor Paid": "green",
            }[frm.doc.alphax_procurement_status] || "gray";
            frm.dashboard.add_indicator(
                __("Procurement: {0}", [frm.doc.alphax_procurement_status]),
                colour,
            );
        }

        // Vendor-side action buttons — only for submitted SOs
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Create Vendor PO"), () => {
                create_vendor_po(frm);
            }, __("AlphaX Booking"));

            frm.add_custom_button(__("View Linked POs"), () => {
                frappe.set_route("List", "Purchase Order",
                    { alphax_against_customer_booking: frm.doc.name });
            }, __("AlphaX Booking"));

            frm.add_custom_button(__("View Linked PIs"), () => {
                frappe.set_route("List", "Purchase Invoice",
                    { alphax_against_customer_booking: frm.doc.name });
            }, __("AlphaX Booking"));

            frm.add_custom_button(__("Booking Flow"), () => {
                frappe.set_route("alphax-booking-flow", {
                    sales_order: frm.doc.name,
                });
            }, __("AlphaX Booking"));
        }
    },

    customer(frm) {
        if (!frm.doc.customer) return;
        frappe.db.get_value(
            "Customer Wallet",
            { customer: frm.doc.customer, currency: frm.doc.currency },
            ["current_balance", "held_amount"],
        ).then((r) => {
            if (!r.message) return;
            const avail = (r.message.current_balance || 0) - (r.message.held_amount || 0);
            frm.set_intro(
                __("Wallet available balance for this customer: {0}",
                    [format_currency(avail, frm.doc.currency)]),
                "blue",
            );
        });
    },

    use_wallet_payment(frm) {
        if (frm.doc.use_wallet_payment) {
            frappe.show_alert({
                message: __("On submit, the wallet will hold {0}",
                    [format_currency(frm.doc.grand_total, frm.doc.currency)]),
                indicator: "orange",
            });
        }
    },
});

// Create a new Purchase Order pre-linked to this Sales Order
function create_vendor_po(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Create Purchase Order for Vendor"),
        fields: [
            {
                fieldname: "supplier", label: __("Supplier"), reqd: 1,
                fieldtype: "Link", options: "Supplier",
            },
            {
                fieldname: "info_html", fieldtype: "HTML",
                options: `<div class="text-muted small" style="margin-top:8px;">
                    ${__("A new Purchase Order will be created, pre-linked to {0} (end customer: {1}). Items are copied from the Sales Order — you can edit them in the PO.",
                        [frm.doc.name, frm.doc.customer_name || frm.doc.customer])}
                </div>`,
            },
        ],
        primary_action_label: __("Create"),
        primary_action(values) {
            frappe.call({
                method: "alphax_wallet.alphax_wallet.api_vendor.create_po_from_so",
                args: {
                    sales_order: frm.doc.name,
                    supplier: values.supplier,
                },
                freeze: true,
                freeze_message: __("Creating Purchase Order..."),
                callback: (r) => {
                    if (r.message) {
                        d.hide();
                        frappe.set_route("Form", "Purchase Order", r.message);
                    }
                },
            });
        },
    });
    d.show();
}
