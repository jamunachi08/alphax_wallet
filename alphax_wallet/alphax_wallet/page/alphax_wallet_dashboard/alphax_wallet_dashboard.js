// AlphaX Wallet Dashboard — clean corporate
// =========================================
// Layout (top to bottom):
//   1. Hero header bar (brand colour, welcome, reconciliation badge)
//   2. KPI strip (4 large number cards with sparkline + delta)
//   3. Quick action cards (6 big visual shortcuts in a grid)
//   4. Liability trend chart + Recent transactions list (2-col)
//   5. Top wallets table

frappe.pages["alphax-wallet-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Wallet Dashboard"),
        single_column: true,
    });
    new AlphaXDashboard(page);
};

class AlphaXDashboard {
    constructor(page) {
        this.page = page;
        this.$body = $(page.body).addClass("alphax-dashboard");
        this._inject_styles();
        this._render_shell();
        this._bind_page_actions();
        this.refresh();
    }

    _inject_styles() {
        $("head").append(`
        <style id="alphax-dashboard-styles">
        :root {
            /* Nozol-inspired palette: dark violet base, pink and gold accents */
            --ax-primary: #7A2F87;
            --ax-primary-dark: #5A1F66;
            --ax-primary-light: #9A4BA7;
            --ax-primary-soft: #F3E5F5;       /* tinted bg for light-context icons */
            --ax-accent: #D9A54A;             /* gold */
            --ax-accent-light: #F0C06A;
            --ax-pink: #D97A9E;               /* rose accent */
            --ax-pink-dark: #C56B87;
            --ax-danger: #DC2626;

            /* Dark surfaces (used by hero, dashboard frame) */
            --ax-dark-base: #18061F;
            --ax-dark-mid: #220A2C;
            --ax-dark-elev: #2B1038;

            /* Text */
            --ax-text: #111827;               /* dark text on white */
            --ax-text-muted: #6B7280;
            --ax-text-faint: #9CA3AF;
            --ax-text-on-dark: #F5EDEF;       /* off-white on dark */
            --ax-text-on-dark-muted: #E6D6BE; /* beige */
            --ax-text-on-dark-faint: #B56CC0;

            --ax-border: #E5E7EB;
            --ax-border-soft: #F3F4F6;
            --ax-border-dark: rgba(181, 108, 192, 0.25);

            --ax-bg: #FFFFFF;
            --ax-bg-soft: #FAFBFC;
        }

        .alphax-dashboard { padding: 0 0 40px; }

        /* === HERO === */
        .ax-hero {
            background: linear-gradient(135deg,
                var(--ax-dark-base, #18061F) 0%,
                var(--ax-dark-mid, #2B1038) 55%,
                var(--ax-dark-elev, #3C1745) 100%);
            border: 1px solid var(--ax-dark-elev);
            border-radius: 16px;
            padding: 28px 32px;
            margin: 16px 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 24px;
            flex-wrap: wrap;
            position: relative;
            overflow: hidden;
        }
        /* Decorative pink glow in the hero corner — uses --ax-pink with low alpha.
           We can't put var() inside rgba(), so we use a CSS color-mix fallback. */
        .ax-hero::after {
            content: "";
            position: absolute;
            top: -40px; right: -40px;
            width: 200px; height: 200px;
            border-radius: 50%;
            background: radial-gradient(circle,
                color-mix(in srgb, var(--ax-pink, #D97A9E) 25%, transparent) 0%,
                transparent 70%);
            pointer-events: none;
        }
        .ax-hero-left { display: flex; align-items: center; gap: 18px; position: relative; z-index: 1; }
        .ax-hero-logo {
            width: 56px; height: 56px;
            border-radius: 14px;
            background: linear-gradient(135deg, var(--ax-accent) 0%, var(--ax-accent-light) 100%);
            display: flex; align-items: center; justify-content: center;
            color: var(--ax-dark-base); font-size: 28px; font-weight: 700;
            font-family: Georgia, serif;
            box-shadow: 0 4px 14px color-mix(in srgb, var(--ax-accent, #D9A54A) 45%, transparent);
        }
        .ax-hero-text h1 {
            margin: 0 0 4px 0;
            font-size: 22px; font-weight: 700;
            color: var(--ax-text-on-dark);
        }
        .ax-hero-text p {
            margin: 0;
            font-size: 13.5px;
            color: var(--ax-text-on-dark-muted);
        }
        .ax-hero-badge {
            display: inline-flex; align-items: center; gap: 8px;
            padding: 10px 18px;
            border-radius: 999px;
            font-size: 13px; font-weight: 600;
            background: rgba(245, 237, 239, 0.08);
            backdrop-filter: blur(6px);
            border: 1px solid rgba(245, 237, 239, 0.2);
            color: var(--ax-text-on-dark);
            position: relative; z-index: 1;
        }
        .ax-hero-badge.ok { color: var(--ax-accent-light); border-color: rgba(217, 165, 74, 0.4); }
        .ax-hero-badge.drift { color: var(--ax-pink); border-color: rgba(217, 122, 158, 0.4); }
        .ax-hero-badge .dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--ax-accent);
        }
        .ax-hero-badge.drift .dot { background: var(--ax-danger); }

        /* === KPI STRIP === */
        .ax-kpi-strip {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .ax-kpi {
            background: var(--ax-bg);
            border: 1px solid var(--ax-border);
            border-radius: 14px;
            padding: 20px 22px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            position: relative;
            overflow: hidden;
        }
        .ax-kpi:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.06);
        }
        .ax-kpi-label {
            font-size: 11.5px;
            font-weight: 600;
            color: var(--ax-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }
        .ax-kpi-value {
            font-size: 28px;
            font-weight: 700;
            color: var(--ax-text);
            line-height: 1.1;
            margin-bottom: 4px;
        }
        .ax-kpi-meta {
            font-size: 12px;
            color: var(--ax-text-faint);
        }
        .ax-kpi.primary .ax-kpi-value { color: var(--ax-primary); }
        .ax-kpi-icon {
            position: absolute;
            top: 18px; right: 18px;
            width: 36px; height: 36px;
            border-radius: 10px;
            background: var(--ax-primary-soft);
            color: var(--ax-primary);
            display: flex; align-items: center; justify-content: center;
            font-size: 18px;
        }
        .ax-spark { margin-top: 10px; height: 28px; width: 100%; }

        /* === SECTION HEADERS === */
        .ax-section-title {
            font-size: 13px;
            font-weight: 700;
            color: var(--ax-text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin: 32px 0 14px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--ax-border-soft);
        }

        /* === QUICK ACTION CARDS === */
        .ax-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 14px;
        }
        .ax-action {
            background: var(--ax-bg);
            border: 1px solid var(--ax-border);
            border-radius: 14px;
            padding: 18px 20px;
            cursor: pointer;
            display: flex; align-items: flex-start; gap: 14px;
            transition: all 0.15s ease;
            text-decoration: none !important;
        }
        .ax-action:hover {
            border-color: var(--ax-primary);
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(14, 124, 102, 0.10);
        }
        .ax-action-icon {
            flex-shrink: 0;
            width: 44px; height: 44px;
            border-radius: 11px;
            background: var(--ax-primary-soft);
            color: var(--ax-primary);
            display: flex; align-items: center; justify-content: center;
            font-size: 20px;
        }
        .ax-action.amber .ax-action-icon { background: #FEF3C7; color: #B45309; }
        .ax-action.blue  .ax-action-icon { background: #DBEAFE; color: #1D4ED8; }
        .ax-action.violet .ax-action-icon { background: #EDE9FE; color: #6D28D9; }
        .ax-action.rose  .ax-action-icon { background: #FCE7F3; color: #BE185D; }
        .ax-action.grey  .ax-action-icon { background: #F3F4F6; color: #374151; }
        .ax-action-text { flex: 1; min-width: 0; }
        .ax-action-title {
            font-size: 14.5px; font-weight: 600;
            color: var(--ax-text); margin-bottom: 4px;
        }
        .ax-action-desc {
            font-size: 12.5px; color: var(--ax-text-muted);
            line-height: 1.4;
        }
        .ax-action-badge {
            display: inline-block;
            margin-left: 8px;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px; font-weight: 600;
            background: #FEF3C7; color: #92400E;
        }

        /* === TWO-COLUMN: TREND + RECENT === */
        .ax-two-col {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
        }
        @media (max-width: 980px) { .ax-two-col { grid-template-columns: 1fr; } }

        .ax-card {
            background: var(--ax-bg);
            border: 1px solid var(--ax-border);
            border-radius: 14px;
            padding: 20px 22px;
        }
        .ax-card-head {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 14px;
        }
        .ax-card-title {
            font-size: 14px; font-weight: 700; color: var(--ax-text);
        }
        .ax-card-link {
            font-size: 12.5px; color: var(--ax-primary);
            cursor: pointer; font-weight: 500;
        }
        .ax-card-link:hover { text-decoration: underline; }

        /* === RECENT TXN LIST === */
        .ax-txn-list { display: flex; flex-direction: column; gap: 10px; }
        .ax-txn {
            display: flex; align-items: center; gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid var(--ax-border-soft);
        }
        .ax-txn:last-child { border-bottom: none; }
        .ax-txn-icon {
            flex-shrink: 0;
            width: 32px; height: 32px;
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 700; font-size: 12px;
        }
        .ax-txn-icon.in { background: var(--ax-primary-soft); color: var(--ax-primary); }
        .ax-txn-icon.out { background: #FEE2E2; color: var(--ax-danger); }
        .ax-txn-icon.hold { background: #FEF3C7; color: #92400E; }
        .ax-txn-body { flex: 1; min-width: 0; }
        .ax-txn-customer {
            font-size: 13px; font-weight: 600; color: var(--ax-text);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .ax-txn-meta {
            font-size: 11.5px; color: var(--ax-text-faint);
        }
        .ax-txn-amount {
            font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums;
        }
        .ax-txn-amount.in { color: var(--ax-primary); }
        .ax-txn-amount.out { color: var(--ax-danger); }
        .ax-txn-amount.neutral { color: var(--ax-text-muted); }

        /* === TOP WALLETS TABLE === */
        .ax-table { width: 100%; border-collapse: collapse; }
        .ax-table th {
            text-align: left;
            font-size: 11px; font-weight: 600;
            color: var(--ax-text-muted); text-transform: uppercase;
            letter-spacing: 0.04em;
            padding: 10px 8px; border-bottom: 1px solid var(--ax-border);
        }
        .ax-table td {
            padding: 12px 8px;
            border-bottom: 1px solid var(--ax-border-soft);
            font-size: 13px; color: var(--ax-text);
        }
        .ax-table tr:last-child td { border-bottom: none; }
        .ax-table .num { text-align: right; font-variant-numeric: tabular-nums; }

        .ax-empty {
            text-align: center; padding: 40px 20px;
            color: var(--ax-text-faint); font-size: 13px;
        }
        </style>
        `);
    }

    _render_shell() {
        this.$body.html(`
            <div class="ax-hero">
                <div class="ax-hero-left">
                    <div class="ax-hero-logo" id="ax-hero-logo">α</div>
                    <div class="ax-hero-text">
                        <div id="ax-hero-eyebrow" style="font-size:11px;letter-spacing:0.12em;
                             text-transform:uppercase;color:var(--ax-accent, #D9A54A);
                             font-weight:600;margin-bottom:4px;"></div>
                        <h1 id="ax-hero-title">${__("Wallet Dashboard")}</h1>
                        <p id="ax-hero-subtitle">${__("Loading...")}</p>
                    </div>
                </div>
                <div id="ax-hero-badge"></div>
            </div>

            <div class="ax-kpi-strip" id="ax-kpis"></div>

            <div class="ax-section-title">${__("Quick Actions")}</div>
            <div class="ax-actions" id="ax-actions"></div>

            <div class="ax-section-title">${__("Activity")}</div>
            <div class="ax-two-col">
                <div class="ax-card">
                    <div class="ax-card-head">
                        <div class="ax-card-title">${__("Wallet Flows — Last 30 Days")}</div>
                        <span class="ax-card-link" id="ax-open-ledger">${__("View Ledger →")}</span>
                    </div>
                    <div id="ax-trend-chart" style="height: 260px;"></div>
                </div>
                <div class="ax-card">
                    <div class="ax-card-head">
                        <div class="ax-card-title">${__("Recent Transactions")}</div>
                        <span class="ax-card-link" id="ax-open-txns">${__("See all →")}</span>
                    </div>
                    <div class="ax-txn-list" id="ax-txn-list"></div>
                </div>
            </div>

            <div class="ax-section-title">${__("Top Wallets by Balance")}</div>
            <div class="ax-card">
                <div id="ax-top-wallets"></div>
            </div>
        `);
    }

    _bind_page_actions() {
        this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
        this.page.set_secondary_action(__("Open Workspace"), () => {
            frappe.set_route("Workspaces", "AlphaX Wallet");
        });

        this.$body.on("click", "#ax-open-ledger", () =>
            frappe.set_route("query-report", "Wallet Transaction Ledger"));
        this.$body.on("click", "#ax-open-txns", () =>
            frappe.set_route("List", "Wallet Transaction"));
    }

    refresh() {
        frappe.call({
            method: "alphax_wallet.alphax_wallet.api_dashboard.get_dashboard_metrics",
            freeze: true,
            freeze_message: __("Loading dashboard..."),
        }).then((r) => {
            if (!r || !r.message) return;
            this.data = r.message;
            this._render_hero();
            this._render_kpis();
            this._render_actions();
            this._render_trend_chart();
            this._render_recent_txns();
            this._render_top_wallets();
        });
    }

    // ------------------------------------------------------------------
    _render_hero() {
        const { reconciliation } = this.data;
        const user = frappe.session.user_fullname || frappe.session.user;
        const hour = new Date().getHours();
        const greeting = hour < 12 ? __("Good morning") :
                         hour < 17 ? __("Good afternoon") :
                         __("Good evening");

        // Brand sourced from frappe.boot.alphax_wallet_brand (refreshed on Company switch)
        const brand = (window.alphax_wallet && window.alphax_wallet.brand) ||
                      (frappe.boot && frappe.boot.alphax_wallet_brand) ||
                      {};
        const display_name = brand.brand_display_name || "AlphaX Wallet";
        const tagline = brand.tagline ||
                        __("Here's where your wallet system stands today.");
        const company = brand.company || frappe.defaults.get_user_default("Company") || "";

        // Eyebrow line — the tenant Company in caps
        this.$body.find("#ax-hero-eyebrow").text(company || display_name);
        // Main title — the brand display name
        this.$body.find("#ax-hero-title").text(display_name);
        // Subtitle — greeting + tagline
        this.$body.find("#ax-hero-subtitle").text(
            `${greeting}, ${user}. ${tagline}`
        );

        // Hero logo — use the brand's logo_on_dark or fall back to α
        const $logo = this.$body.find("#ax-hero-logo");
        if (brand.logo_on_dark || brand.logo) {
            $logo.html(`<img src="${brand.logo_on_dark || brand.logo}"
                style="width:100%;height:100%;object-fit:contain;border-radius:10px;"/>`)
                .css("padding", "6px");
        } else {
            $logo.text("α").css("padding", "");
        }

        const $badge = this.$body.find("#ax-hero-badge");
        if (reconciliation.in_sync) {
            $badge.html(`
                <div class="ax-hero-badge ok">
                    <span class="dot"></span>
                    ${__("Reconciliation: in sync")}
                </div>
            `);
        } else {
            $badge.html(`
                <div class="ax-hero-badge drift">
                    <span class="dot"></span>
                    ${__("Drift: {0}", [format_currency(reconciliation.drift, this.data.currency)])}
                </div>
            `);
        }
    }

    _render_kpis() {
        const k = this.data.kpis;
        const cur = this.data.currency;
        const $strip = this.$body.find("#ax-kpis").empty();

        const kpis = [
            {
                label: __("Wallet Liability"),
                value: format_currency(k.total_liability, cur),
                meta: __("Available: {0}", [format_currency(k.available_to_spend, cur)]),
                icon: "💼",
                primary: true,
                sparkline: this.data.sparkline_7d,
            },
            {
                label: __("Active Wallets"),
                value: k.active_wallets,
                meta: k.active_holds_count
                    ? __("{0} active holds", [k.active_holds_count])
                    : __("No active holds"),
                icon: "👥",
            },
            {
                label: __("Top-ups Today"),
                value: format_currency(k.topups_today, cur),
                meta: k.pending_topup_requests
                    ? __("⚠ {0} pending approval", [k.pending_topup_requests])
                    : __("All approved"),
                icon: "↑",
            },
            {
                label: __("Bookings Today"),
                value: k.bookings_today,
                meta: __("Spend: {0}", [format_currency(k.spend_today, cur)]),
                icon: "📅",
            },
        ];

        kpis.forEach((kpi) => {
            const sparkId = kpi.sparkline ? `ax-spark-${Math.random().toString(36).slice(2,8)}` : null;
            const card = $(`
                <div class="ax-kpi ${kpi.primary ? 'primary' : ''}">
                    <div class="ax-kpi-icon">${kpi.icon}</div>
                    <div class="ax-kpi-label">${kpi.label}</div>
                    <div class="ax-kpi-value">${kpi.value}</div>
                    <div class="ax-kpi-meta">${kpi.meta}</div>
                    ${sparkId ? `<svg class="ax-spark" id="${sparkId}"></svg>` : ''}
                </div>
            `);
            $strip.append(card);
            if (sparkId && kpi.sparkline.length) {
                this._draw_sparkline(sparkId, kpi.sparkline);
            }
        });
    }

    _draw_sparkline(id, values) {
        const svg = this.$body.find(`#${id}`)[0];
        if (!svg) return;
        const w = svg.clientWidth || 180;
        const h = 28;
        const min = Math.min(...values, 0);
        const max = Math.max(...values, 1);
        const range = max - min || 1;
        const stepX = w / Math.max(values.length - 1, 1);
        const points = values.map((v, i) => {
            const x = i * stepX;
            const y = h - ((v - min) / range) * (h - 4) - 2;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
        const rootStyle = getComputedStyle(document.documentElement);
        const sparkColor = rootStyle.getPropertyValue("--ax-primary").trim() || "#7A2F87";
        const sparkFill = sparkColor + "22";  // 22 = ~13% alpha
        svg.innerHTML = `
            <polyline points="${points}" fill="none"
                stroke="${sparkColor}" stroke-width="2"
                stroke-linecap="round" stroke-linejoin="round"/>
            <polyline points="0,${h} ${points} ${w},${h}" fill="${sparkFill}" stroke="none"/>
        `;
        svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    }

    _render_actions() {
        const $grid = this.$body.find("#ax-actions").empty();
        const actions = [
            {
                icon: "💳", title: __("Customer Wallets"),
                desc: __("Manage balances, freeze accounts, view ledgers"),
                route: () => frappe.set_route("List", "Customer Wallet"),
                colour: "",
            },
            {
                icon: "↑", title: __("Top-up Requests"),
                desc: __("Approve pending requests above the threshold"),
                route: () => frappe.set_route("List", "Wallet Topup Request", {"status": "Pending"}),
                colour: "amber",
                badge: this.data.kpis.pending_topup_requests || null,
            },
            {
                icon: "📈", title: __("Booking Flow"),
                desc: __("Visual stepper for each customer booking"),
                route: () => frappe.set_route("alphax-booking-flow"),
                colour: "blue",
            },
            {
                icon: "📊", title: __("Balance Summary"),
                desc: __("Every wallet, current balance, available"),
                route: () => frappe.set_route("query-report", "Wallet Balance Summary"),
                colour: "violet",
            },
            {
                icon: "🧾", title: __("Transaction Ledger"),
                desc: __("Full immutable history with filters"),
                route: () => frappe.set_route("query-report", "Wallet Transaction Ledger"),
                colour: "rose",
            },
            {
                icon: "⚙", title: __("Wallet Settings"),
                desc: __("GL accounts, thresholds, reconciliation"),
                route: () => frappe.set_route("Form", "Wallet Settings"),
                colour: "grey",
            },
        ];

        actions.forEach((a) => {
            const $card = $(`
                <div class="ax-action ${a.colour}">
                    <div class="ax-action-icon">${a.icon}</div>
                    <div class="ax-action-text">
                        <div class="ax-action-title">
                            ${a.title}
                            ${a.badge ? `<span class="ax-action-badge">${a.badge}</span>` : ''}
                        </div>
                        <div class="ax-action-desc">${a.desc}</div>
                    </div>
                </div>
            `);
            $card.on("click", a.route);
            $grid.append($card);
        });
    }

    _render_trend_chart() {
        const trend = this.data.trend_30d;
        if (!trend || !trend.length) {
            this.$body.find("#ax-trend-chart").html(
                `<div class="ax-empty">${__("No activity in the last 30 days.")}</div>`
            );
            return;
        }
        const labels = trend.map(t => t.date.slice(5));  // MM-DD
        const inflow = trend.map(t => t.inflow);
        const outflow = trend.map(t => t.outflow);

        this.$body.find("#ax-trend-chart").empty();
        new frappe.Chart(this.$body.find("#ax-trend-chart")[0], {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    { name: __("Top-ups + Refunds"), values: inflow, chartType: "bar" },
                    { name: __("Withdrawals"), values: outflow, chartType: "bar" },
                ],
            },
            colors: [
                (getComputedStyle(document.documentElement).getPropertyValue("--ax-primary").trim() || "#7A2F87"),
                (getComputedStyle(document.documentElement).getPropertyValue("--ax-pink").trim() || "#D97A9E"),
            ],
            height: 250,
            axisOptions: {
                xAxisMode: "tick",
                xIsSeries: 1,
            },
            barOptions: { spaceRatio: 0.5 },
            truncateLegends: 1,
        });
    }

    _render_recent_txns() {
        const txns = this.data.recent_txns || [];
        const $list = this.$body.find("#ax-txn-list").empty();
        if (!txns.length) {
            $list.html(`<div class="ax-empty">${__("No transactions yet.")}</div>`);
            return;
        }
        txns.forEach((t) => {
            const isIn = ["Deposit", "Refund", "Hold Release"].includes(t.transaction_type);
            const isHold = t.transaction_type === "Hold";
            const iconClass = isHold ? "hold" : (isIn ? "in" : "out");
            const amtClass = isHold ? "neutral" : (isIn ? "in" : "out");
            const sign = isHold ? "⏸" : (isIn ? "+" : "−");
            const initials = (t.customer || "?").slice(0, 2).toUpperCase();

            const $row = $(`
                <div class="ax-txn">
                    <div class="ax-txn-icon ${iconClass}">${initials}</div>
                    <div class="ax-txn-body">
                        <div class="ax-txn-customer">${frappe.utils.escape_html(t.customer)}</div>
                        <div class="ax-txn-meta">
                            ${t.transaction_type} · ${frappe.datetime.comment_when(t.posting_datetime)}
                        </div>
                    </div>
                    <div class="ax-txn-amount ${amtClass}">
                        ${sign}${format_currency(t.amount, t.currency)}
                    </div>
                </div>
            `);
            $row.css("cursor", "pointer").on("click", () =>
                frappe.set_route("Form", "Wallet Transaction", t.name));
            $list.append($row);
        });
    }

    _render_top_wallets() {
        const wallets = this.data.top_wallets || [];
        const $wrap = this.$body.find("#ax-top-wallets").empty();
        if (!wallets.length) {
            $wrap.html(`<div class="ax-empty">${__("No wallets to show.")}</div>`);
            return;
        }
        const cur = this.data.currency;
        const rows = wallets.map(w => `
            <tr style="cursor:pointer;" data-wallet="${w.name}">
                <td><b>${frappe.utils.escape_html(w.customer_name || w.customer)}</b></td>
                <td>${w.currency}</td>
                <td class="num">${format_currency(w.current_balance, w.currency)}</td>
                <td class="num" style="color: var(--ax-text-muted);">
                    ${format_currency(w.held_amount, w.currency)}
                </td>
                <td class="num"><b style="color: var(--ax-primary);">
                    ${format_currency((w.current_balance||0) - (w.held_amount||0), w.currency)}
                </b></td>
            </tr>
        `).join("");
        $wrap.html(`
            <table class="ax-table">
                <thead>
                    <tr>
                        <th>${__("Customer")}</th>
                        <th>${__("Currency")}</th>
                        <th class="num">${__("Balance")}</th>
                        <th class="num">${__("Held")}</th>
                        <th class="num">${__("Available")}</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        `);
        $wrap.on("click", "tr[data-wallet]", function () {
            frappe.set_route("Form", "Customer Wallet", $(this).data("wallet"));
        });
    }
}
