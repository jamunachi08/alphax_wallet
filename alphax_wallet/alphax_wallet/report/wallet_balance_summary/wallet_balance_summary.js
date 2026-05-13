// Filters for Wallet Balance Summary
frappe.query_reports["Wallet Balance Summary"] = {
    filters: [
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        { fieldname: "currency", label: __("Currency"), fieldtype: "Link", options: "Currency" },
        {
            fieldname: "status", label: __("Status"), fieldtype: "Select",
            options: "\nActive\nFrozen\nClosed",
        },
    ],
};
