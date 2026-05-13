frappe.query_reports["Supplier Settlement Statement"] = {
    filters: [
        {
            fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1,
        },
        {
            fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1,
        },
        { fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        {
            fieldname: "commission_rate", label: __("Commission %"), fieldtype: "Percent",
            default: 10, description: __("Commission deducted from gross when settling"),
        },
    ],
};
