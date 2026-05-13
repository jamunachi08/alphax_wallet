# AlphaX Wallet — Installation & Usage Guide

Tested with Frappe v15 / ERPNext v15.

## 1. Prerequisites

You need a working ERPNext bench. If you don't have one yet:

```bash
# Install bench (skip if already installed)
pip install frappe-bench

# Create a new bench using Frappe v15
bench init --frappe-branch version-15 frappe-bench
cd frappe-bench

# Create a site
bench new-site your.site.local

# Install ERPNext
bench get-app --branch version-15 erpnext
bench --site your.site.local install-app erpnext
```

## 2. Install AlphaX Wallet

```bash
cd ~/frappe-bench

# Option A — from a local folder
bench get-app alphax_wallet /path/to/alphax_wallet

# Option B — from a git repo (once you push it)
# bench get-app https://github.com/your-org/alphax_wallet

bench --site your.site.local install-app alphax_wallet
bench --site your.site.local migrate
bench restart
```

You should see "AlphaX Wallet" in the desk sidebar.

## 3. First-time configuration (5 minutes)

Open the **AlphaX Wallet** workspace. The onboarding panel walks you through the six steps:

1. **Configure Wallet Settings** — pick default company, currency, hold expiry hours, top-up approval threshold.
2. **Verify GL Accounts** — pick four accounts:
   - *Customer Wallet Liability* (the app tries to auto-create this under Current Liabilities)
   - *Default Bank Account*
   - *Deferred Revenue*
   - *Commission Expense*
3. **Create First Customer Wallet** — or let the auto-create hook handle it.
4. **Test Top-up Flow** — the form has a **Top Up** button under Actions.
5. **Test Booking with Wallet** — create a Sales Order with *Pay using Wallet* ticked.
6. **Review Wallet Reports** — check that Balance Summary totals match your GL.

## 4. The website integration

The website (your customer-facing booking site) talks to ERPNext over the REST API.

### Authentication

Generate an API key + secret for a service user with the **Wallet Manager** role:

```bash
bench --site your.site.local execute frappe.core.doctype.user.user.generate_keys --kwargs "{'user':'wallet-bot@your.site.local'}"
```

Use the resulting key/secret in the `Authorization` header:

```
Authorization: token <api_key>:<api_secret>
```

### Endpoints

All endpoints are under `/api/method/alphax_wallet.api.wallet.<func>`.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `get_balance?customer=CUST-001` | Check balance before showing "Pay with Wallet" |
| GET | `get_transactions?customer=CUST-001&limit=20` | History page |
| POST | `topup` | After payment-gateway webhook fires |
| POST | `hold` | When customer clicks Book |
| POST | `capture` | When booking is confirmed |
| POST | `release` | When booking is cancelled before confirmation |
| POST | `refund` | When a confirmed booking is cancelled |

### Idempotency

**Every write endpoint requires an `idempotency_key`.** Use the gateway's transaction id, the booking id, or any UUID — but reuse the same key on retries. The same key on the same wallet returns the original transaction without re-posting.

### Example flow (curl)

```bash
# 1. Customer visits checkout — website checks balance
curl -H "Authorization: token KEY:SECRET" \
  "https://erpnext.local/api/method/alphax_wallet.api.wallet.get_balance?customer=CUST-001"

# 2. Customer clicks Book — website places a hold
curl -X POST -H "Authorization: token KEY:SECRET" \
  -d "customer=CUST-001&amount=2500&reference_doctype=Sales Order&reference_name=SO-2025-0042&idempotency_key=BOOKING-9f7a3" \
  "https://erpnext.local/api/method/alphax_wallet.api.wallet.hold"

# 3. Booking confirmed — website captures the hold
curl -X POST -H "Authorization: token KEY:SECRET" \
  -d "hold_transaction=WTX-2025-000123&idempotency_key=CONFIRM-9f7a3" \
  "https://erpnext.local/api/method/alphax_wallet.api.wallet.capture"
```

## 5. Day-to-day operations

**The four reports under the AlphaX Wallet workspace:**

- **Wallet Balance Summary** — the daily snapshot
- **Wallet Transaction Ledger** — drill-down with filters
- **Supplier Settlement Statement** — what each supplier was paid this period

**Scheduled jobs (already running):**

- *Daily*: reconciliation (compares wallet ledger total against GL Wallet Liability — emails on drift)
- *Daily*: auto-release expired holds
- *Hourly*: auto-approve top-up requests below the threshold
- *Weekly*: email each supplier their settlement statement

**Manual reconciliation** — open Wallet Settings and click **Run Reconciliation Now**.

## 6. Running the tests

```bash
bench --site your.site.local run-tests --app alphax_wallet
```

The test suite covers top-up, holds, captures, releases, refunds, idempotency, and overdraw rejection.

## 7. Uninstall

```bash
bench --site your.site.local uninstall-app alphax_wallet
```

This removes the DocTypes but leaves your data. To wipe data first, drop the wallet tables manually before uninstalling.

## 8. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Top-up fails with "Configure Wallet Liability Account" | Step 2 of onboarding skipped — set the four GL accounts |
| Reconciliation drift email | A Journal Entry was posted manually against the wallet liability account, OR a wallet transaction failed mid-flight; check the Error Log |
| `Customer Wallet` not auto-creating | Check Wallet Settings → Auto-create Wallet on Customer is on |
| Sales Order with Pay using Wallet ticked, but no hold appears | Customer may not have enough available balance; check the SO timeline for the rejection |
| Portal /wallet page shows "No customer linked" | The portal user has no Contact linked to a Customer; create one in Customer → Contacts |

For anything not in this list, check **Error Log** (search for "AlphaX Wallet").
