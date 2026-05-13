# AlphaX Wallet

A customer wallet, booking integration, and multi-party settlement app for ERPNext.

Adds the missing wallet layer on top of standard ERPNext so that a website
(travel/hotel/service-booking platform) can:

- Maintain a real-time customer wallet balance backed by a liability GL account
- Accept top-ups via Payment Entry with automatic wallet ledger posting
- Place authorised holds during booking, convert them to deductions on confirmation, and release them on cancellation
- Auto-calculate employee booking commissions and feed them into ERPNext Payroll via Additional Salary
- Reconcile wallet liability vs. the sum of customer wallet balances every day, with email alerts on drift
- Expose a clean, idempotent REST API for the website to consume

## Features

- **Customer Wallet** DocType — one per (customer, currency)
- **Wallet Transaction** — immutable ledger, every change in balance has a row
- **Wallet Top-up Request** — optional approval workflow for large deposits
- **Booking Commission** — employee/agent commission tied to Sales Orders
- **Wallet Settings** — single DocType, holds default accounts and limits
- **REST API** with idempotency keys: `get_balance`, `topup`, `hold`, `capture`, `release`, `refund`
- **Reports**: Wallet Balance Summary, Wallet Transaction Ledger, Supplier Settlement Statement
- **Workspace** "AlphaX Wallet" with shortcuts and dashboard charts
- **Scheduled jobs**: nightly reconciliation, weekly supplier settlement reminders
- **Hooks** into Payment Entry, Sales Invoice, Sales Order, Delivery Note for automatic GL posting

## Installation

```bash
# On your bench
cd ~/frappe-bench
bench get-app alphax_wallet /path/to/this/app
bench --site your.site.local install-app alphax_wallet
bench --site your.site.local migrate
```

## Quick Start

1. Open the **AlphaX Wallet** workspace.
2. Click **Step 1 — Configure Wallet Settings** in the onboarding card and pick the Wallet Liability, Deferred Revenue, and Commission accounts.
3. Click **Step 2 — Create your first Customer Wallet** (or let the auto-create hook do it on the first top-up).
4. Run **Step 3 — Test top-up** from the wallet form.

The onboarding panel walks new users through the full flow.

## License

MIT
