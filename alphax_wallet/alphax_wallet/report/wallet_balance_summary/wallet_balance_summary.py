"""
Wallet Balance Summary
======================

Lists every wallet with its current balance, held amount, and available balance.
Total row at the bottom reconciles against the GL Wallet Liability account.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = _columns()
    data = _data(filters)
    summary = _summary(data)
    chart = _chart(data)
    return columns, data, None, chart, summary


def _columns():
    return [
        {"label": _("Wallet"), "fieldname": "name", "fieldtype": "Link", "options": "Customer Wallet", "width": 220},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
        {"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 200},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 80},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("Current Balance"), "fieldname": "current_balance", "fieldtype": "Currency", "options": "currency", "width": 140},
        {"label": _("Held"), "fieldname": "held_amount", "fieldtype": "Currency", "options": "currency", "width": 120},
        {"label": _("Available"), "fieldname": "available", "fieldtype": "Currency", "options": "currency", "width": 140},
        {"label": _("Last Transaction"), "fieldname": "last_transaction_at", "fieldtype": "Datetime", "width": 160},
    ]


def _data(filters):
    where = ["1=1"]
    params = {}
    if filters.get("customer"):
        where.append("customer = %(customer)s")
        params["customer"] = filters["customer"]
    if filters.get("currency"):
        where.append("currency = %(currency)s")
        params["currency"] = filters["currency"]
    if filters.get("status"):
        where.append("status = %(status)s")
        params["status"] = filters["status"]
    else:
        where.append("status != 'Closed'")

    rows = frappe.db.sql(f"""
        SELECT
            name, customer, customer_name, currency, status,
            current_balance, held_amount, last_transaction_at,
            (current_balance - held_amount) AS available
        FROM `tabCustomer Wallet`
        WHERE {' AND '.join(where)}
        ORDER BY current_balance DESC
    """, params, as_dict=True)
    return rows


def _summary(data):
    if not data:
        return []
    total_balance = sum(flt(r.current_balance) for r in data)
    total_held = sum(flt(r.held_amount) for r in data)
    total_avail = total_balance - total_held
    return [
        {"value": len(data), "label": _("Active Wallets"), "datatype": "Int", "indicator": "Blue"},
        {"value": total_balance, "label": _("Total Balance"), "datatype": "Currency", "indicator": "Green"},
        {"value": total_held, "label": _("Total Held"), "datatype": "Currency", "indicator": "Orange"},
        {"value": total_avail, "label": _("Total Available"), "datatype": "Currency", "indicator": "Cyan"},
    ]


def _chart(data):
    if not data:
        return None
    top = sorted(data, key=lambda r: flt(r.current_balance), reverse=True)[:10]
    return {
        "data": {
            "labels": [r.customer_name or r.customer for r in top],
            "datasets": [
                {"name": _("Balance"), "values": [flt(r.current_balance) for r in top]},
                {"name": _("Held"), "values": [flt(r.held_amount) for r in top]},
            ],
        },
        "type": "bar",
        "colors": ["#7A2F87", "#D9A54A"],
    }
