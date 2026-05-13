"""
Booking Commission — aggregates bookings into a per-employee, per-period
commission record and pushes the amount into ERPNext Payroll via Additional Salary.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class BookingCommission(Document):
    def validate(self):
        if getdate(self.period_to) < getdate(self.period_from):
            frappe.throw(_("Period To must be on or after Period From"))
        self._calculate_totals()

    def _calculate_totals(self):
        total_value = total_comm = 0
        for row in self.items:
            row.commission_amount = flt(row.booking_amount) * flt(row.commission_rate) / 100.0
            total_value += flt(row.booking_amount)
            total_comm += flt(row.commission_amount)
        self.total_booking_value = total_value
        self.total_commission = total_comm

    def on_submit(self):
        self.status = "Approved"
        self.db_set("status", "Approved")
        self._create_additional_salary()

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        if self.additional_salary:
            try:
                addl = frappe.get_doc("Additional Salary", self.additional_salary)
                if addl.docstatus == 1:
                    addl.cancel()
            except frappe.DoesNotExistError:
                pass

    def _create_additional_salary(self):
        """Create an Additional Salary so the next payroll picks up the commission."""
        if self.additional_salary:
            return
        if flt(self.total_commission) <= 0:
            return

        # Find a salary component named 'Booking Commission'; create on the fly if needed.
        component = self._ensure_commission_component()

        addl = frappe.get_doc({
            "doctype": "Additional Salary",
            "employee": self.employee,
            "salary_component": component,
            "amount": flt(self.total_commission),
            "payroll_date": today(),
            "company": frappe.db.get_value("Employee", self.employee, "company"),
            "ref_doctype": self.doctype,
            "ref_docname": self.name,
            "overwrite_salary_structure_amount": 0,
        })
        addl.insert(ignore_permissions=True)
        addl.submit()
        self.db_set("additional_salary", addl.name)

    def _ensure_commission_component(self):
        name = "Booking Commission"
        if frappe.db.exists("Salary Component", name):
            return name
        comp = frappe.get_doc({
            "doctype": "Salary Component",
            "salary_component": name,
            "salary_component_abbr": "BC",
            "type": "Earning",
            "is_tax_applicable": 1,
            "depends_on_payment_days": 0,
        })
        comp.insert(ignore_permissions=True)
        return name

    @frappe.whitelist()
    def auto_fetch_bookings(self):
        """
        Pull confirmed Sales Orders within the period where this employee was the sales person,
        and populate the items table.
        """
        rate = flt(frappe.db.get_value("Employee", self.employee, "commission_rate")) or 5.0

        rows = frappe.db.sql(
            """
            SELECT so.name, so.transaction_date, so.customer, so.grand_total, so.currency
            FROM `tabSales Order` so
            INNER JOIN `tabSales Team` st ON st.parent = so.name
            WHERE st.sales_person = %(emp)s
              AND so.transaction_date BETWEEN %(d1)s AND %(d2)s
              AND so.docstatus = 1
              AND so.name NOT IN (
                  SELECT bci.sales_order FROM `tabBooking Commission Item` bci
                  INNER JOIN `tabBooking Commission` bc ON bci.parent = bc.name
                  WHERE bc.docstatus != 2 AND bc.name != %(self)s
              )
            ORDER BY so.transaction_date
            """,
            {
                "emp": self.employee,
                "d1": self.period_from,
                "d2": self.period_to,
                "self": self.name or "",
            },
            as_dict=True,
        )

        self.items = []
        for r in rows:
            self.append("items", {
                "sales_order": r.name,
                "booking_date": r.transaction_date,
                "customer": r.customer,
                "booking_amount": r.grand_total,
                "commission_rate": rate,
            })
        self._calculate_totals()
        return len(rows)
