"""
Supplier Settlement Statement
=============================

For each supplier in a date range:
  - Gross booking amount (sum of Purchase Invoices)
  - Commission deducted (% from Supplier custom field, or filter)
  - Net payable
  - Amount actually paid (from Payment Entries)
  - Outstanding

Used both as a desk report and to feed the weekly settlement email.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, add_days


def execute(filters=None):
    filters = filters or {}
    if not filters.get("from_date"):
        filters["from_date"] = add_days(today(), -30)
    if not filters.get("to_date"):
        filters["to_date"] = today()

    columns = _columns()
    data = _data(filters)
    summary = _summary(data)
    chart = _chart(data)
    return columns, data, None, chart, summary


def _columns():
    return [
        {"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
        {"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 200},
        {"label": _("# Invoices"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 100},
        {"label": _("Gross Amount"), "fieldname": "gross_amount", "fieldtype": "Currency", "width": 140},
        {"label": _("Commission %"), "fieldname": "commission_rate", "fieldtype": "Percent", "width": 110},
        {"label": _("Commission"), "fieldname": "commission_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Net Payable"), "fieldname": "net_payable", "fieldtype": "Currency", "width": 140},
        {"label": _("Paid"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "width": 140},
    ]


def _data(filters):
    commission_rate = flt(filters.get("commission_rate")) or 10.0  # default 10%

    where = ["pi.docstatus = 1", "pi.posting_date BETWEEN %(d1)s AND %(d2)s"]
    params = {"d1": getdate(filters["from_date"]), "d2": getdate(filters["to_date"])}
    if filters.get("supplier"):
        where.append("pi.supplier = %(supplier)s")
        params["supplier"] = filters["supplier"]
    if filters.get("company"):
        where.append("pi.company = %(company)s")
        params["company"] = filters["company"]

    rows = frappe.db.sql(f"""
        SELECT
            pi.supplier,
            s.supplier_name,
            COUNT(pi.name) AS invoice_count,
            SUM(pi.grand_total) AS gross_amount,
            SUM(pi.grand_total - pi.outstanding_amount) AS paid_amount,
            SUM(pi.outstanding_amount) AS outstanding_pi
        FROM `tabPurchase Invoice` pi
        LEFT JOIN `tabSupplier` s ON s.name = pi.supplier
        WHERE {' AND '.join(where)}
        GROUP BY pi.supplier, s.supplier_name
        ORDER BY gross_amount DESC
    """, params, as_dict=True)

    for r in rows:
        r.commission_rate = commission_rate
        r.commission_amount = flt(r.gross_amount) * commission_rate / 100.0
        r.net_payable = flt(r.gross_amount) - r.commission_amount
        # outstanding here = net_payable - paid (whichever is greater of zero)
        r.outstanding = max(r.net_payable - flt(r.paid_amount), 0)
    return rows


def _summary(data):
    if not data:
        return []
    return [
        {"value": len(data), "label": _("Suppliers"), "datatype": "Int", "indicator": "Blue"},
        {"value": sum(flt(r.gross_amount) for r in data), "label": _("Gross"), "datatype": "Currency", "indicator": "Cyan"},
        {"value": sum(flt(r.commission_amount) for r in data), "label": _("Commission"), "datatype": "Currency", "indicator": "Green"},
        {"value": sum(flt(r.net_payable) for r in data), "label": _("Net Payable"), "datatype": "Currency", "indicator": "Orange"},
        {"value": sum(flt(r.outstanding) for r in data), "label": _("Outstanding"), "datatype": "Currency", "indicator": "Red"},
    ]


def _chart(data):
    if not data:
        return None
    top = sorted(data, key=lambda r: flt(r.gross_amount), reverse=True)[:8]
    return {
        "data": {
            "labels": [r.supplier_name or r.supplier for r in top],
            "datasets": [
                {"name": _("Gross"), "values": [flt(r.gross_amount) for r in top]},
                {"name": _("Net Payable"), "values": [flt(r.net_payable) for r in top]},
                {"name": _("Outstanding"), "values": [flt(r.outstanding) for r in top]},
            ],
        },
        "type": "bar",
        "colors": ["#7A2F87", "#D97A9E", "#D9A54A"],
    }
