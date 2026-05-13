// AlphaX Booking Flow — visual stepper page
// =========================================
// Shows a customer booking's end-to-end lifecycle as a horizontal stepper.
// Stages (left → right):
//   1. Booking Created       (Sales Order submitted)
//   2. Wallet Hold           (funds reserved)
//   3. Invoice & Capture     (Sales Invoice submitted, wallet captured)
//   4. Vendor PO             (Purchase Order to supplier)
//   5. Vendor Invoice        (Purchase Invoice received)
//   6. Vendor Paid           (Supplier payment submitted)
//   7. Service Delivered     (Delivery Note submitted, revenue recognised)
//
// Previous / Next buttons walk between consecutive bookings of the same customer
// or, if no customer is fixed, across all recent bookings.

frappe.pages["alphax-booking-flow"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Booking Flow"),
        single_column: true,
    });
    new AlphaXBookingFlow(page);
};

class AlphaXBookingFlow {
    constructor(page) {
        this.page = page;
        this.$body = $(page.body).addClass("alphax-flow-page");
        this.current_so = frappe.utils.get_url_arg("sales_order") || null;

        this._render_skeleton();
        this._bind_actions();

        if (this.current_so) {
            this.load(this.current_so);
        } else {
            this._render_picker_only();
        }
    }

    // ----------------------------------------------------------------
    // Initial layout
    // ----------------------------------------------------------------
    _render_skeleton() {
        this.$body.html(`
            <style>
                .alphax-flow-page { padding: 16px 24px 48px; }
                .alphax-flow-picker { display:flex; gap:12px; align-items:flex-end;
                    margin-bottom: 24px; flex-wrap:wrap; }
                .alphax-flow-picker .picker-input { flex: 1; min-width:240px; }

                .alphax-flow-summary { background: var(--bg-color, #F8FAFC);
                    border-radius: 10px; padding: 20px 24px; margin-bottom: 28px;
                    display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                    gap:20px; border-left:4px solid var(--ax-primary, #7A2F87); }
                .alphax-flow-summary .label { font-size:0.72rem; text-transform:uppercase;
                    letter-spacing:0.05em; color: var(--text-muted, #6B7280); margin-bottom:4px; }
                .alphax-flow-summary .value { font-size:1.05rem; font-weight:600;
                    color: var(--text-color, #111827); }
                .alphax-flow-summary .value.muted { color: var(--text-muted, #6B7280);
                    font-weight:500; }
                .alphax-flow-summary .value.big { font-size:1.4rem; }

                /* ============================================================
                   STEPPER — clean style with large circles and ring on current
                   ============================================================ */
                .alphax-stepper-wrap {
                    background: #F8FAFC;
                    border-radius: 12px;
                    padding: 28px 24px 20px;
                    margin-bottom: 28px;
                }
                .alphax-stepper-caption {
                    text-align: center;
                    font-size: 0.78rem;
                    letter-spacing: 0.06em;
                    text-transform: uppercase;
                    color: #6B7280;
                    margin-bottom: 4px;
                }
                .alphax-stepper-sub {
                    text-align: center;
                    font-size: 0.95rem;
                    color: #111827;
                    margin-bottom: 24px;
                    font-weight: 500;
                }

                .alphax-stepper {
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    position: relative;
                    padding: 0 8px;
                    overflow-x: auto;
                    min-height: 110px;
                }
                /* The connector line sits behind the circles */
                .alphax-stepper::before {
                    content: "";
                    position: absolute;
                    top: 22px;
                    left: 44px;
                    right: 44px;
                    height: 2px;
                    background: #E5E7EB;
                    z-index: 0;
                }
                /* Progress line that grows with completed steps */
                .alphax-stepper-progress {
                    position: absolute;
                    top: 22px;
                    left: 44px;
                    height: 2px;
                    background: linear-gradient(to right, var(--ax-accent, #D9A54A) 0%, var(--ax-pink, #D97A9E) 100%);
                    z-index: 0;
                    transition: width 0.3s ease;
                }

                .alphax-step {
                    position: relative;
                    z-index: 1;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    flex: 1;
                    min-width: 100px;
                    cursor: pointer;
                    transition: transform 0.15s ease;
                }
                .alphax-step:hover { transform: translateY(-2px); }

                .alphax-step .dot {
                    width: 44px; height: 44px;
                    border-radius: 50%;
                    display: flex; align-items: center; justify-content: center;
                    font-weight: 600;
                    font-size: 15px;
                    transition: all 0.2s ease;
                }
                /* Done state — filled gold with checkmark */
                .alphax-step.done .dot {
                    background: var(--ax-accent, #D9A54A);
                    color: var(--ax-dark-base, #18061F);
                    border: none;
                    box-shadow: 0 2px 8px rgba(217, 165, 74, 0.35);
                }
                .alphax-step.done .dot::before {
                    content: "✓";
                    font-size: 20px;
                    font-weight: 700;
                }
                .alphax-step.done .dot .num { display: none; }
                /* Current state — white with pink border and halo */
                .alphax-step.current .dot {
                    background: #FFFFFF;
                    border: 2px solid var(--ax-pink, #D97A9E);
                    color: var(--ax-pink-dark, #C56B87);
                    box-shadow: 0 0 0 5px rgba(217, 122, 158, 0.22);
                }
                /* Future state — white with grey border */
                .alphax-step.future .dot {
                    background: #FFFFFF;
                    border: 1.5px solid #E5E7EB;
                    color: #9CA3AF;
                }
                /* Skipped — faded grey */
                .alphax-step.skipped .dot {
                    background: #F3F4F6;
                    border: 1.5px solid #E5E7EB;
                    color: #D1D5DB;
                }
                .alphax-step.skipped .dot::before { content: "—"; }
                .alphax-step.skipped .dot .num { display: none; }

                .alphax-step .title {
                    font-size: 0.82rem;
                    line-height: 1.2;
                    margin-top: 12px;
                    margin-bottom: 2px;
                    color: #6B7280;
                    text-align: center;
                    padding: 0 4px;
                }
                .alphax-step.current .title {
                    color: var(--ax-pink-dark, #C56B87);
                    font-weight: 600;
                }
                .alphax-step.done .title {
                    color: #374151;
                }

                .alphax-step .meta {
                    font-size: 0.7rem;
                    color: #9CA3AF;
                    text-align: center;
                    line-height: 1.3;
                    padding: 0 4px;
                }

                .alphax-detail-card { background:#FFFFFF; border:1px solid #E5E7EB;
                    border-radius:10px; padding:20px 24px; margin-bottom:16px; }
                .alphax-detail-card h4 { margin:0 0 12px; font-size:1rem;
                    color:var(--ax-primary, #7A2F87); font-weight:600; }
                .alphax-detail-card .empty { color: var(--text-muted, #6B7280);
                    font-style:italic; font-size:0.9rem; }
                .alphax-detail-card table { width:100%; font-size:0.9rem; }
                .alphax-detail-card table th { text-align:left; padding:6px 8px;
                    border-bottom:1px solid #E5E7EB; font-weight:600;
                    color: var(--text-muted, #6B7280); font-size:0.78rem;
                    text-transform:uppercase; letter-spacing:0.04em; }
                .alphax-detail-card table td { padding:8px; border-bottom:1px solid #F3F4F6; }
                .alphax-detail-card table tr:last-child td { border-bottom: none; }
                .alphax-detail-card .link { color:var(--ax-primary, #7A2F87); cursor:pointer; font-weight:500; }
                .alphax-detail-card .link:hover { text-decoration:underline; }

                .alphax-margin { display:grid;
                    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
                    gap:16px; }
                .alphax-margin .cell { padding:12px 16px; border-radius:8px;
                    background:#F9FAFB; }
                .alphax-margin .cell .label { font-size:0.72rem; text-transform:uppercase;
                    color: var(--text-muted, #6B7280); letter-spacing:0.04em; margin-bottom:4px; }
                .alphax-margin .cell .value { font-size:1.15rem; font-weight:700; }
                .alphax-margin .cell.profit { background:rgba(122,47,135,0.08); }
                .alphax-margin .cell.profit .value { color:var(--ax-primary, #7A2F87); }
                .alphax-margin .cell.loss { background:rgba(220,38,38,0.08); }
                .alphax-margin .cell.loss .value { color:#DC2626; }
            </style>

            <div class="alphax-flow-picker">
                <div class="picker-input" id="ax-picker-customer"></div>
                <div class="picker-input" id="ax-picker-so"></div>
                <button class="btn btn-primary btn-sm" id="ax-load">${__("Load")}</button>
            </div>

            <div id="ax-content"></div>
        `);

        // Add Frappe controls inside the placeholders
        this.customer_picker = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", options: "Customer",
                fieldname: "customer", label: __("Customer"),
                placeholder: __("Pick a customer to filter"),
            },
            parent: this.$body.find("#ax-picker-customer"),
            render_input: true,
        });

        this.so_picker = frappe.ui.form.make_control({
            df: {
                fieldtype: "Link", options: "Sales Order",
                fieldname: "sales_order", label: __("Sales Order"),
                placeholder: __("Pick a booking"),
                get_query: () => {
                    const filters = { docstatus: 1 };
                    const c = this.customer_picker.get_value();
                    if (c) filters.customer = c;
                    return { filters };
                },
            },
            parent: this.$body.find("#ax-picker-so"),
            render_input: true,
        });

        if (this.current_so) {
            this.so_picker.set_value(this.current_so);
        }
    }

    _bind_actions() {
        this.$body.find("#ax-load").on("click", () => {
            const so = this.so_picker.get_value();
            if (!so) {
                frappe.show_alert({ message: __("Pick a Sales Order first"),
                    indicator: "orange" });
                return;
            }
            this.load(so);
        });

        // Prev / Next buttons in the page header
        this.page.set_secondary_action(__("Next →"), () => this._navigate("next"));
        this.page.add_menu_item(__("Previous Booking"), () => this._navigate("prev"));
        this.page.add_menu_item(__("Next Booking"), () => this._navigate("next"));
        this.page.add_menu_item(__("Refresh"), () => {
            if (this.current_so) this.load(this.current_so);
        });
    }

    _render_picker_only() {
        this.$body.find("#ax-content").html(`
            <div class="alphax-detail-card">
                <h4>${__("Pick a booking to begin")}</h4>
                <p>${__("Use the controls above to load a Sales Order's full lifecycle — wallet hold, invoicing, vendor procurement, settlement, and revenue recognition — as a visual flow.")}</p>
            </div>
        `);
    }

    // ----------------------------------------------------------------
    // Load + render
    // ----------------------------------------------------------------
    load(sales_order) {
        this.current_so = sales_order;
        // Update URL so the back button works and links are shareable
        const url = new URL(window.location.href);
        url.searchParams.set("sales_order", sales_order);
        window.history.replaceState({}, "", url.toString());

        frappe.dom.freeze(__("Loading booking flow..."));
        frappe.call({
            method: "alphax_wallet.alphax_wallet.api_vendor.get_booking_flow_data",
            args: { sales_order },
        }).then((r) => {
            frappe.dom.unfreeze();
            if (r.message) {
                this.data = r.message;
                this._render();
            }
        }).catch(() => frappe.dom.unfreeze());
    }

    _render() {
        const d = this.data;
        const so = d.sales_order;
        const stages = this._compute_stages(d);
        const cur = format_currency.bind(null);

        this.$body.find("#ax-content").html(`
            <div class="alphax-flow-summary">
                <div>
                    <div class="label">${__("Sales Order")}</div>
                    <div class="value">
                        <a href="/app/sales-order/${so.name}">${so.name}</a>
                    </div>
                </div>
                <div>
                    <div class="label">${__("Customer")}</div>
                    <div class="value">${so.customer_name || so.customer}</div>
                </div>
                <div>
                    <div class="label">${__("Booking Value")}</div>
                    <div class="value big">${cur(so.grand_total, so.currency)}</div>
                </div>
                <div>
                    <div class="label">${__("Wallet Payment")}</div>
                    <div class="value ${so.use_wallet_payment ? '' : 'muted'}">
                        ${so.use_wallet_payment ? __("Yes") : __("No")}
                    </div>
                </div>
                <div>
                    <div class="label">${__("Procurement")}</div>
                    <div class="value">${so.procurement_status}</div>
                </div>
            </div>

            <div class="alphax-stepper-wrap">
                <div class="alphax-stepper-caption">${__("AlphaX Booking Lifecycle")}</div>
                <div class="alphax-stepper-sub">
                    ${__("Track {0} from creation to delivery", [so.name])}
                </div>
                <div class="alphax-stepper" id="ax-stepper">
                    <div class="alphax-stepper-progress" id="ax-stepper-progress" style="width: 0;"></div>
                </div>
            </div>

            <div id="ax-detail"></div>

            <div class="alphax-detail-card">
                <h4>${__("Margin")}</h4>
                <div class="alphax-margin">
                    <div class="cell">
                        <div class="label">${__("Revenue")}</div>
                        <div class="value">${cur(d.margin.revenue, so.currency)}</div>
                    </div>
                    <div class="cell">
                        <div class="label">${__("Vendor Cost")}</div>
                        <div class="value">${cur(d.margin.cost, so.currency)}</div>
                    </div>
                    <div class="cell">
                        <div class="label">${__("Paid to Vendors")}</div>
                        <div class="value">${cur(d.margin.paid_to_suppliers, so.currency)}</div>
                    </div>
                    <div class="cell ${d.margin.margin >= 0 ? 'profit' : 'loss'}">
                        <div class="label">${__("Margin")}</div>
                        <div class="value">
                            ${cur(d.margin.margin, so.currency)}
                            <small>(${d.margin.margin_pct.toFixed(1)}%)</small>
                        </div>
                    </div>
                </div>
            </div>
        `);

        this._render_stages(stages);
        this._render_detail_for_stage(stages.findIndex(s => s.state === "current"));
    }

    _render_stages(stages) {
        const $stepper = this.$body.find("#ax-stepper");
        // Keep the progress div, remove only step children
        $stepper.find(".alphax-step").remove();

        stages.forEach((s, idx) => {
            const $step = $(`
                <div class="alphax-step ${s.state}" data-idx="${idx}">
                    <div class="dot"><span class="num">${idx + 1}</span></div>
                    <div class="title">${s.title}</div>
                    <div class="meta">${s.meta}</div>
                </div>
            `);
            $step.on("click", () => this._render_detail_for_stage(idx));
            $stepper.append($step);
        });

        // Animate the progress bar — width = % of completed steps
        const total = stages.length;
        let last_done = -1;
        stages.forEach((s, i) => { if (s.state === "done") last_done = i; });
        // Bar runs from first dot center to current dot center
        const pct = total > 1
            ? Math.max(0, Math.min(100, (last_done / (total - 1)) * 100))
            : 0;
        // We set it as a width percentage of the available track
        // Track width = container width minus left & right padding (44px each side)
        setTimeout(() => {
            const $track = this.$body.find("#ax-stepper-progress");
            $track.css("width", `calc((100% - 88px) * ${pct / 100})`);
        }, 50);
    }

    _compute_stages(d) {
        const so = d.sales_order;
        const has_si = (d.sales_invoices || []).some(si => si.docstatus === 1);
        const has_dn = (d.delivery_notes || []).some(dn => dn.docstatus === 1);
        const has_po = (d.purchase_orders || []).some(po => po.docstatus === 1);
        const has_pi = (d.purchase_invoices || []).some(pi => pi.docstatus === 1);
        const has_pay = (d.supplier_payments || []).length > 0;
        const has_hold = !!d.wallet_transaction;

        // Determine state of each stage. "current" is the first not-yet-done.
        const stages = [
            {
                key: "booking",
                title: __("Booking"),
                meta: so.transaction_date,
                done: so.docstatus === 1,
            },
            {
                key: "hold",
                title: __("Wallet Hold"),
                meta: has_hold
                    ? `${frappe.utils.fmt_money(d.wallet_transaction.amount, 2, so.currency)}`
                    : (so.use_wallet_payment ? __("Pending") : __("Skipped")),
                done: has_hold,
                skip: !so.use_wallet_payment,
            },
            {
                key: "invoice",
                title: __("Invoiced"),
                meta: has_si ? `${d.sales_invoices.length} ${__("invoice(s)")}` : __("Pending"),
                done: has_si,
            },
            {
                key: "po",
                title: __("Vendor PO"),
                meta: has_po
                    ? `${d.purchase_orders.length} ${__("PO(s)")}`
                    : (so.procurement_status === "Not Required" ? __("Not Required") : __("Pending")),
                done: has_po,
                skip: so.procurement_status === "Not Required",
            },
            {
                key: "pi",
                title: __("Vendor PI"),
                meta: has_pi ? `${d.purchase_invoices.length} ${__("invoice(s)")}` : __("Pending"),
                done: has_pi,
                skip: so.procurement_status === "Not Required",
            },
            {
                key: "vendor_paid",
                title: __("Vendor Paid"),
                meta: has_pay
                    ? `${d.supplier_payments.length} ${__("payment(s)")}`
                    : __("Pending"),
                done: has_pay,
                skip: so.procurement_status === "Not Required",
            },
            {
                key: "delivered",
                title: __("Delivered"),
                meta: has_dn ? `${d.delivery_notes.length} ${__("delivery(s)")}` : __("Pending"),
                done: has_dn,
            },
        ];

        // Mark states
        let first_pending = -1;
        stages.forEach((s, i) => {
            if (s.skip) {
                s.state = "skipped";
            } else if (s.done) {
                s.state = "done";
            } else if (first_pending === -1) {
                s.state = "current";
                first_pending = i;
            } else {
                s.state = "future";
            }
        });
        return stages;
    }

    _render_detail_for_stage(stage_idx) {
        const d = this.data;
        const so = d.sales_order;
        if (stage_idx < 0) stage_idx = 0;
        const stage_key = ["booking", "hold", "invoice", "po", "pi",
                           "vendor_paid", "delivered"][stage_idx];

        let html = "";
        const cur = format_currency.bind(null);

        if (stage_key === "booking") {
            html = `
                <div class="alphax-detail-card">
                    <h4>${__("Booking — {0}", [so.name])}</h4>
                    <table>
                        <tr><th>${__("Customer")}</th><td>${so.customer_name || so.customer}</td></tr>
                        <tr><th>${__("Date")}</th><td>${so.transaction_date}</td></tr>
                        <tr><th>${__("Total")}</th><td>${cur(so.grand_total, so.currency)}</td></tr>
                        <tr><th>${__("Status")}</th><td>${so.status}</td></tr>
                    </table>
                </div>
            `;
        } else if (stage_key === "hold") {
            if (d.wallet_transaction) {
                const w = d.wallet_transaction;
                html = `
                    <div class="alphax-detail-card">
                        <h4>${__("Wallet Hold — {0}", [w.name])}</h4>
                        <table>
                            <tr><th>${__("Amount Held")}</th><td>${cur(w.amount, so.currency)}</td></tr>
                            <tr><th>${__("Status")}</th><td>${w.status}</td></tr>
                            <tr><th>${__("Balance After")}</th><td>${cur(w.balance_after, so.currency)}</td></tr>
                            <tr><th></th><td>
                                <span class="link" onclick="frappe.set_route('Form','Wallet Transaction','${w.name}')">
                                    ${__("Open Transaction")} →
                                </span>
                            </td></tr>
                        </table>
                    </div>
                `;
            } else {
                html = `<div class="alphax-detail-card"><div class="empty">${__("No wallet hold for this booking.")}</div></div>`;
            }
        } else if (stage_key === "invoice") {
            html = this._render_table(__("Sales Invoices"), d.sales_invoices, [
                ["name", __("Invoice"), "Sales Invoice"],
                ["posting_date", __("Date")],
                ["grand_total", __("Total"), null, so.currency],
                ["status", __("Status")],
            ]);
        } else if (stage_key === "po") {
            html = this._render_table(__("Purchase Orders to Vendors"), d.purchase_orders, [
                ["name", __("PO"), "Purchase Order"],
                ["supplier_name", __("Supplier")],
                ["transaction_date", __("Date")],
                ["grand_total", __("Total"), null, so.currency],
                ["status", __("Status")],
            ]) + this._render_create_po_cta();
        } else if (stage_key === "pi") {
            html = this._render_table(__("Vendor Invoices Received"), d.purchase_invoices, [
                ["name", __("PI"), "Purchase Invoice"],
                ["supplier_name", __("Supplier")],
                ["posting_date", __("Date")],
                ["grand_total", __("Total"), null, so.currency],
                ["outstanding_amount", __("Outstanding"), null, so.currency],
                ["status", __("Status")],
            ]);
        } else if (stage_key === "vendor_paid") {
            html = this._render_table(__("Supplier Payments"), d.supplier_payments, [
                ["name", __("Payment Entry"), "Payment Entry"],
                ["party_name", __("Supplier")],
                ["posting_date", __("Date")],
                ["paid_amount", __("Paid"), null, so.currency],
            ]);
        } else if (stage_key === "delivered") {
            html = this._render_table(__("Delivery Notes"), d.delivery_notes, [
                ["name", __("DN"), "Delivery Note"],
                ["posting_date", __("Date")],
                ["status", __("Status")],
            ]);
        }

        this.$body.find("#ax-detail").html(html);
    }

    _render_table(title, rows, cols) {
        if (!rows || !rows.length) {
            return `<div class="alphax-detail-card">
                        <h4>${title}</h4>
                        <div class="empty">${__("No records at this stage yet.")}</div>
                    </div>`;
        }
        const header = cols.map(c => `<th>${c[1]}</th>`).join("");
        const body = rows.map(r => {
            return "<tr>" + cols.map(c => {
                const val = r[c[0]];
                if (val === null || val === undefined) return "<td>—</td>";
                if (c[2]) { // link
                    return `<td><span class="link"
                        onclick="frappe.set_route('Form','${c[2]}','${val}')">${val}</span></td>`;
                }
                if (c[3]) { // currency
                    return `<td>${format_currency(val, c[3])}</td>`;
                }
                return `<td>${val}</td>`;
            }).join("") + "</tr>";
        }).join("");
        return `<div class="alphax-detail-card">
                    <h4>${title}</h4>
                    <table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>
                </div>`;
    }

    _render_create_po_cta() {
        return `<div class="alphax-detail-card" style="text-align:center;">
            <button class="btn btn-primary btn-sm" id="ax-create-po">
                + ${__("Create Vendor PO")}
            </button>
            <div class="text-muted small" style="margin-top:8px;">
                ${__("Opens the Sales Order's vendor PO dialog.")}
            </div>
        </div>`;
    }

    // ----------------------------------------------------------------
    // Prev / Next navigation across bookings
    // ----------------------------------------------------------------
    _navigate(direction) {
        if (!this.current_so) {
            frappe.show_alert({ message: __("Load a booking first"), indicator: "orange" });
            return;
        }
        const customer = this.customer_picker.get_value();
        const filters = { docstatus: 1 };
        if (customer) filters.customer = customer;

        // Get the current SO's transaction_date and name to find adjacent
        frappe.db.get_value("Sales Order", this.current_so, "transaction_date").then((r) => {
            if (!r.message) return;
            const cur_date = r.message.transaction_date;

            const operator = direction === "next" ? ">=" : "<=";
            const order_dir = direction === "next" ? "asc" : "desc";
            // Pull a window around the current SO
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Sales Order",
                    filters: {
                        ...filters,
                        transaction_date: [operator, cur_date],
                        name: ["!=", this.current_so],
                    },
                    fields: ["name", "transaction_date"],
                    order_by: `transaction_date ${order_dir}, name ${order_dir}`,
                    limit_page_length: 1,
                },
            }).then((res) => {
                if (res.message && res.message.length) {
                    const target = res.message[0].name;
                    this.so_picker.set_value(target);
                    this.load(target);
                } else {
                    frappe.show_alert({
                        message: direction === "next"
                            ? __("This is the most recent booking.")
                            : __("This is the oldest booking."),
                        indicator: "blue",
                    });
                }
            });
        });
    }
}
