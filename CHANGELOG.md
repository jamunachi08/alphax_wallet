# AlphaX Wallet — Changelog

## 1.5.0 — 13 May 2026

### Architectural change: per-Company branding

The theme system has been redesigned to support **white-label multi-tenancy**:
the app now stores a brand profile *per ERPNext Company*. When a user is
working in a Company, the entire app adopts that Company's brand. This is
the right model for SaaS platforms where each tenant business gets its
own branded experience on a shared bench.

### New
- **DocType: Wallet Brand** (replaces Wallet Theme) — one brand per Company.
  Identity fields: display name, tagline, logo (light + dark variants),
  favicon, support email, support phone, portal footer HTML.
- **One-click Activate** button — sets the brand as active for its Company.
- **Boot session** pushes the active brand to `frappe.boot.alphax_wallet_brand`;
  Company switches via the navbar trigger an automatic re-fetch.
- **Dashboard hero** shows the brand's display name, tagline, and logo —
  no longer hardcoded to "AlphaX Wallet". The eyebrow line shows the Company.
- **Portal `/wallet`** shows the brand's logo, display name, tagline, and
  custom footer HTML. The portal styles inject the brand's palette server-side
  so even guests see the right brand instantly.
- **Favicon** updates client-side when a brand is applied (best-effort).

### Removed
- The Per Customer and Per Portal User theme modes (replaced by Company-scoped).
- The `wallet_theme` Custom Field on Customer.
- The `theme_mode` and `default_theme` fields on Wallet Settings.
- The route-change listener that re-themed per Customer.

### Migration (v1.5)
- Existing `Wallet Theme` records are converted to `Wallet Brand` records
  keyed to the site's default Company. Active flag is preserved.
- The `wallet_theme` Custom Field on Customer is dropped.
- Stale Wallet Settings values for theme_mode / default_theme are cleaned up.
- `after_migrate` seeds a default brand for every Company that doesn't have
  one yet (Nozol palette as starter values).

### Compatibility
- All earlier APIs (`get_active_theme`, `get_active_theme_css`) continue to
  exist via the new Wallet Brand controller, but new code should use
  `get_active_brand` / `get_active_brand_css`.

---

## 1.4.0 — 13 May 2026

### New — Full theme system
- **New DocType: Wallet Theme** — store unlimited named palettes
- **Three theme modes** in Wallet Settings:
  - *Single Theme* — one palette site-wide (the original behaviour)
  - *Per Customer* — each Customer record uses its own theme on the desk
  - *Per Portal User* — the /wallet portal adapts to the logged-in customer
- **Default theme picker** in Wallet Settings — choose which theme to use
  when no per-record override is set
- **wallet_theme field on Customer** — the per-customer override
- **Logo → palette extraction**: upload a logo image to a Wallet Theme,
  click "Generate Palette from Logo", and the app extracts dominant colours
  from the image (client-side, via Canvas) and derives a full palette
  (primary, accent, pink, dark surfaces, light/dark variants) using HSL math
- **Live swatch preview** on the Wallet Theme form — see every colour with
  its hex value, plus a "Live Preview" gradient card showing how the theme
  will look on the dashboard
- **Preview on Dashboard** button — opens the dashboard with a theme applied
  via URL param, without saving as active
- **Default Nozol theme** seeded on install/migrate

### Internal
- New CSS variable architecture: all branded surfaces use `var(--ax-*)` so
  themes can override at runtime
- New `boot_session` hook pushes the active theme to `frappe.boot` so first
  paint is themed without a round-trip
- Route-change listener swaps themes when navigating between Customer
  Wallets / Booking Flow pages with different customers (Per Customer mode)
- Portal `/wallet` page injects per-customer CSS server-side
- Sparkline + Frappe Chart colours now read computed CSS variables at draw
  time (instead of hardcoded hex)

### Migration
- After upgrade: `bench migrate` runs `_ensure_default_theme` which seeds
  the Nozol theme as the system default if no theme exists
- Existing customers don't have a `wallet_theme` set, so they'll fall
  through to the default — no behavioural change unless you explicitly
  switch the Theme Mode

---

## 1.3.0 — 12 May 2026

### New
- **Nozol-inspired palette** applied across every surface of the app:
  - Hero gradients on the Workspace banner, Dashboard, and Customer Portal
    use a dark violet base (#18061F → #2B1038 → #3C1745) with a subtle pink glow
  - Brand primary: rich violet (#7A2F87) replaces the previous green
  - Accent: warm gold (#D9A54A) for done states, badges, and CTA buttons
  - Pink rose (#D97A9E) for the current step in the Booking Flow stepper
  - The stepper's progress bar is now a gold-to-pink gradient
- Updated **app logo SVG** with the new violet wallet body, gold chip,
  and pink glow accent
- Updated all chart colours (Wallet Balance Summary, Supplier Settlement,
  trend chart on the dashboard) to use the new palette
- Updated diagnostic dialog and workspace shortcut colours

### Changed
- `--alphax-primary` is now `#7A2F87` (was `#0E7C66`)
- `--alphax-accent` is now `#D9A54A` (was `#F59E0B`)
- New CSS variables added: `--alphax-pink`, `--alphax-dark-base`,
  `--alphax-dark-mid`, `--alphax-dark-elev`, `--alphax-text-on-dark`,
  `--alphax-text-on-dark-muted`

### Migration
- After upgrade, run `bench build --app alphax_wallet` and hard-refresh
  the browser (Ctrl+Shift+R) to pick up the new CSS and SVG assets.
- Existing data, GL postings, and wallet balances are unaffected.

---

## 1.2.1 — 12 May 2026

### Fixed
- **Dashboard page 404** — the page folder was named `alphax_dashboard` but
  Frappe lookups by page name (`alphax-wallet-dashboard`) require the folder
  to be `alphax_wallet_dashboard`. Folder and inner files renamed.

### New
- **Diagnostics tool** on Wallet Settings (Tools menu → "Run Diagnostics").
  Surfaces every place that can cause currency or GL drift errors:
  - Customers with non-base default_currency
  - Wallets in non-base currency
  - Customers with multiple wallets
  - Recent Sales Orders / Payment Entries in non-base currency
  - Reconciliation drift with orphan GL entries identified
  - Orphan Wallet Transactions (no JE attached)
  Each finding includes severity, explanation, fix guidance, and a row dump.
- **Add Currency Exchange dialog** on Wallet Settings (Tools menu → "Add
  Currency Exchange"). One-click creation of a rate record when you hit the
  "Unable to find exchange rate" error.

---

## 1.2.0 — 12 May 2026

### New
- **Wallet Dashboard page** at `/app/alphax-wallet-dashboard` — branded hero, KPI strip
  with sparklines, six action cards, 30-day flow chart, recent transactions list,
  and top wallets table. Single endpoint loads all metrics in one round-trip.
- **Redesigned Booking Flow stepper** — large circles (44px), AlphaX green ring on
  current step, animated progress bar, cleaner one-word titles. Matches modern
  multi-step wizard patterns.
- **Workspace rebuild** — green CTA banner linking to the new dashboard, KPI strip
  prominent, organised shortcuts grid with Wallet Dashboard first.

### Fixed
- Onboarding steps "Test Top-up Flow" and "Test Booking with Wallet" now auto-tick
  when the relevant document is created (was: needed a manual click).
- All onboarding steps now have `validate_action: 1` explicitly set.

### Internal
- New `api_dashboard.get_dashboard_metrics` whitelisted method.
- New Frappe Page: `alphax-wallet-dashboard`.

---

## 1.1.0 — 12 May 2026

### Fixed
- **Currency contamination bug.** Wallets were being silently auto-created in INR
  (or any non-base currency) when the customer record had `default_currency` set.
  This caused Journal Entry posting to fail with exchange-rate errors.
- The engine now refuses to auto-create a parallel wallet in a different currency;
  it uses the customer's existing wallet regardless of the document's currency.
- `Customer.default_currency` is no longer read by the wallet engine or the
  customer auto-create hook.
- Sales Order / Sales Invoice / Payment Entry hooks no longer pass `doc.currency`
  to the engine — they let the engine resolve to the existing wallet.

### Added
- Migration patch (`v1_1.audit_multi_currency_wallets`) that logs any customer
  with wallets in multiple currencies after upgrade, so admins can clean up
  legacy contamination.

---

## 1.0.0 — 10 May 2026

### Initial Release

- Customer Wallet, Wallet Transaction (immutable ledger), Wallet Settings (single),
  Wallet Top-up Request (approval workflow), Booking Commission.
- Wallet engine with row-level locking, idempotency keys, and atomic
  Hold → Capture → Release semantics.
- Automatic GL posting via Journal Entries for Deposit, Withdrawal, Refund.
- Event hooks on Customer, Payment Entry, Sales Order, Sales Invoice,
  Delivery Note, Purchase Order, Purchase Invoice.
- Customer-to-vendor procurement flow with `alphax_against_customer_booking`
  linkage on PO/PI/PE; automatic Sales Order procurement status updates.
- Booking Flow page — visual stepper showing each booking's lifecycle.
- Three reports: Wallet Balance Summary, Wallet Transaction Ledger,
  Supplier Settlement Statement.
- Customer-facing `/wallet` portal page.
- Scheduled jobs: daily reconciliation, hold expiry, hourly auto-approve,
  weekly supplier statements.
- REST API: `get_balance`, `topup`, `hold`, `capture`, `release`, `refund`.
- Test suite covering top-ups, holds, captures, releases, refunds,
  idempotency, and overdraw rejection.
