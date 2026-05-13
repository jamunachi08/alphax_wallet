"""
Wallet Transaction Ledger
=========================

Drill-down ledger of every Wallet Transaction with running balance and
running totals per (customer, currency).
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    data = _data(filters)
    summary = _summary(data)
    return columns, data, None, None, summary


def _columns():
    return [
        {"label": _("Date"), "fieldname": "posting_datetime", "fieldtype": "Datetime", "width": 160},
        {"label": _("Transaction"), "fieldname": "name", "fieldtype": "Link", "options": "Wallet Transaction", "width": 180},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("Type"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 110},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Balance After"), "fieldname": "balance_after", "fieldtype": "Currency", "options": "currency", "width": 140},
        {"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 180},
        {"label": _("Reference DocType"), "fieldname": "reference_doctype", "fieldtype": "Link", "options": "DocType", "width": 130, "hidden": 1},
        {"label": _("Journal Entry"), "fieldname": "journal_entry", "fieldtype": "Link", "options": "Journal Entry", "width": 150},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Small Text", "width": 240},
    ]


def _data(filters):
    where = ["1=1"]
    params = {}

    if filters.get("from_date"):
        where.append("posting_datetime >= %(from_date)s")
        params["from_date"] = getdate(filters["from_date"])
    if filters.get("to_date"):
        where.append("DATE(posting_datetime) <= %(to_date)s")
        params["to_date"] = getdate(filters["to_date"])
    if filters.get("customer"):
        where.append("customer = %(customer)s")
        params["customer"] = filters["customer"]
    if filters.get("wallet"):
        where.append("wallet = %(wallet)s")
        params["wallet"] = filters["wallet"]
    if filters.get("transaction_type"):
        where.append("transaction_type = %(transaction_type)s")
        params["transaction_type"] = filters["transaction_type"]
    if filters.get("status"):
        where.append("status = %(status)s")
        params["status"] = filters["status"]

    rows = frappe.db.sql(f"""
        SELECT
            name, posting_datetime, customer, wallet, transaction_type, status,
            amount, balance_after, reference_doctype, reference_name AS reference,
            journal_entry, currency, remarks
        FROM `tabWallet Transaction`
        WHERE {' AND '.join(where)}
        ORDER BY posting_datetime DESC, name DESC
    """, params, as_dict=True)
    return rows


def _summary(data):
    if not data:
        return []
    deposits = sum(flt(r.amount) for r in data if r.transaction_type in ("Deposit", "Refund"))
    withdrawals = sum(flt(r.amount) for r in data if r.transaction_type == "Withdrawal")
    holds = sum(flt(r.amount) for r in data if r.transaction_type == "Hold" and r.status == "Active")
    return [
        {"value": len(data), "label": _("Transactions"), "datatype": "Int", "indicator": "Blue"},
        {"value": deposits, "label": _("Deposits + Refunds"), "datatype": "Currency", "indicator": "Green"},
        {"value": withdrawals, "label": _("Withdrawals"), "datatype": "Currency", "indicator": "Red"},
        {"value": holds, "label": _("Active Holds"), "datatype": "Currency", "indicator": "Orange"},
    ]
