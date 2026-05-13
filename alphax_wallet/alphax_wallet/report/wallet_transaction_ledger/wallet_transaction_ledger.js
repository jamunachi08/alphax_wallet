frappe.query_reports["Wallet Transaction Ledger"] = {
    filters: [
        {
            fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        },
        {
            fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            default: frappe.datetime.get_today(),
        },
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        { fieldname: "wallet", label: __("Wallet"), fieldtype: "Link", options: "Customer Wallet" },
        {
            fieldname: "transaction_type", label: __("Type"), fieldtype: "Select",
            options: "\nDeposit\nWithdrawal\nHold\nHold Release\nRefund",
        },
        {
            fieldname: "status", label: __("Status"), fieldtype: "Select",
            options: "\nActive\nReleased\nCaptured\nReversed\nExpired",
        },
    ],
};
