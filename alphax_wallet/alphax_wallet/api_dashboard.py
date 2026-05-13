"""
alphax_wallet.alphax_wallet.api_dashboard
=========================================

Server-side metrics for the Wallet Dashboard page.
Returns aggregated KPIs and chart-ready time-series data.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, today, add_days, getdate


@frappe.whitelist()
def get_dashboard_metrics() -> dict:
    """
    Single endpoint returning everything the dashboard needs.
    Keeps the round-trip count to one for fast first paint.
    """
    today_str = today()
    week_ago = add_days(today_str, -7)
    month_ago = add_days(today_str, -30)

    settings = frappe.get_single("Wallet Settings")
    company_currency = None
    if settings.default_company:
        company_currency = frappe.db.get_value(
            "Company", settings.default_company, "default_currency"
        )

    # ----- KPIs -----
    active_wallets = frappe.db.count("Customer Wallet", {"status": "Active"})
    total_liability = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(current_balance), 0)
        FROM `tabCustomer Wallet`
        WHERE status != 'Closed'
    """)[0][0])
    total_held = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(held_amount), 0)
        FROM `tabCustomer Wallet`
        WHERE status != 'Closed'
    """)[0][0])

    topups_today = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabWallet Transaction`
        WHERE transaction_type IN ('Deposit', 'Refund')
          AND DATE(posting_datetime) = %s
    """, today_str)[0][0])

    spend_today = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabWallet Transaction`
        WHERE transaction_type = 'Withdrawal'
          AND DATE(posting_datetime) = %s
    """, today_str)[0][0])

    pending_topup_requests = frappe.db.count("Wallet Topup Request",
                                              {"status": "Pending", "docstatus": 0})

    active_holds_count = frappe.db.count("Wallet Transaction",
                                          {"transaction_type": "Hold",
                                           "status": "Active"})

    bookings_today = frappe.db.count("Sales Order", {
        "transaction_date": today_str,
        "docstatus": 1,
        "use_wallet_payment": 1,
    })

    # ----- 30-day trend (liability + flows) -----
    daily_rows = frappe.db.sql("""
        SELECT
            DATE(posting_datetime) AS d,
            SUM(CASE WHEN transaction_type IN ('Deposit', 'Refund')
                     THEN amount ELSE 0 END) AS inflow,
            SUM(CASE WHEN transaction_type = 'Withdrawal'
                     THEN amount ELSE 0 END) AS outflow
        FROM `tabWallet Transaction`
        WHERE DATE(posting_datetime) >= %s
        GROUP BY DATE(posting_datetime)
        ORDER BY d
    """, month_ago, as_dict=True)

    # Fill missing days with zero (so the chart has a continuous x-axis)
    from datetime import timedelta
    start = getdate(month_ago)
    end = getdate(today_str)
    by_date = {r.d: r for r in daily_rows}
    trend = []
    d = start
    while d <= end:
        row = by_date.get(d)
        trend.append({
            "date": d.isoformat(),
            "inflow": flt(row.inflow) if row else 0,
            "outflow": flt(row.outflow) if row else 0,
        })
        d += timedelta(days=1)

    # ----- Top 5 wallets by balance -----
    top_wallets = frappe.db.sql("""
        SELECT name, customer, customer_name, current_balance, held_amount, currency
        FROM `tabCustomer Wallet`
        WHERE status = 'Active'
        ORDER BY current_balance DESC
        LIMIT 5
    """, as_dict=True)

    # ----- Recent transactions (last 10) -----
    recent_txns = frappe.db.sql("""
        SELECT name, customer, transaction_type, amount, balance_after,
               currency, posting_datetime, status
        FROM `tabWallet Transaction`
        ORDER BY posting_datetime DESC
        LIMIT 10
    """, as_dict=True)

    # ----- 7-day mini sparkline for the liability KPI -----
    sparkline_rows = frappe.db.sql("""
        SELECT
            DATE(posting_datetime) AS d,
            SUM(CASE WHEN transaction_type IN ('Deposit', 'Refund')
                     THEN amount
                     WHEN transaction_type = 'Withdrawal'
                     THEN -amount
                     ELSE 0 END) AS net
        FROM `tabWallet Transaction`
        WHERE DATE(posting_datetime) >= %s
        GROUP BY DATE(posting_datetime)
        ORDER BY d
    """, week_ago, as_dict=True)
    # Running total
    running = total_liability
    spark = []
    for r in reversed(sparkline_rows):
        spark.append(running)
        running -= flt(r.net)
    spark.reverse()
    if not spark:
        spark = [total_liability] * 7

    # ----- Reconciliation status -----
    gl_balance = 0
    if settings.wallet_liability_account:
        gl_rows = frappe.db.sql("""
            SELECT COALESCE(SUM(credit_in_account_currency), 0) -
                   COALESCE(SUM(debit_in_account_currency), 0)
            FROM `tabGL Entry`
            WHERE account = %s AND is_cancelled = 0
        """, settings.wallet_liability_account)
        gl_balance = flt(gl_rows[0][0]) if gl_rows else 0

    drift = round(total_liability - gl_balance, 2)
    in_sync = abs(drift) < 0.01

    return {
        "currency": company_currency or "USD",
        "kpis": {
            "active_wallets": active_wallets,
            "total_liability": total_liability,
            "total_held": total_held,
            "available_to_spend": total_liability - total_held,
            "topups_today": topups_today,
            "spend_today": spend_today,
            "pending_topup_requests": pending_topup_requests,
            "active_holds_count": active_holds_count,
            "bookings_today": bookings_today,
        },
        "reconciliation": {
            "ledger_total": total_liability,
            "gl_total": gl_balance,
            "drift": drift,
            "in_sync": in_sync,
        },
        "trend_30d": trend,
        "sparkline_7d": spark,
        "top_wallets": top_wallets,
        "recent_txns": recent_txns,
    }
