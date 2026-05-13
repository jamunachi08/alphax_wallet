"""
alphax_wallet.alphax_wallet.api_vendor
======================================

Vendor-side actions invoked from form buttons:
  - create_po_from_so: create a Purchase Order pre-linked to a customer SO
  - pay_supplier_against_booking: create a Payment Entry against a PI,
    pre-tagged with the originating customer booking

All operations preserve the supplier/customer linkage so the booking flow
view and the margin/settlement reports remain consistent.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def create_po_from_so(sales_order: str, supplier: str) -> str:
    """
    Create a draft Purchase Order whose items mirror the Sales Order, and
    pre-fill the AlphaX booking link fields. Returns the new PO name.

    Notes:
      - We do not submit the PO; the buyer edits rates/quantities first.
      - Item rates default to the SO rates as a starting point. The buyer
        should adjust them to the negotiated supplier rate — that delta is
        what becomes margin.
    """
    if not sales_order:
        frappe.throw(_("sales_order is required"))
    if not supplier:
        frappe.throw(_("supplier is required"))

    so = frappe.get_doc("Sales Order", sales_order)
    if so.docstatus != 1:
        frappe.throw(_("Sales Order must be Submitted to create a Vendor PO from it"))

    supplier_doc = frappe.get_doc("Supplier", supplier)

    po = frappe.new_doc("Purchase Order")
    po.supplier = supplier
    po.company = so.company
    po.currency = supplier_doc.default_currency or so.currency
    po.schedule_date = so.delivery_date

    # Linkage
    po.alphax_against_customer_booking = so.name
    po.alphax_booking_customer = so.customer

    for so_item in so.items:
        po.append("items", {
            "item_code": so_item.item_code,
            "item_name": so_item.item_name,
            "description": so_item.description,
            "qty": so_item.qty,
            "uom": so_item.uom,
            "rate": flt(so_item.rate),
            "schedule_date": so_item.delivery_date or so.delivery_date,
            "warehouse": so_item.warehouse,
        })

    po.insert(ignore_permissions=False)
    frappe.msgprint(
        _("Purchase Order {0} created. Adjust supplier rates before submitting.").format(po.name),
        indicator="blue", alert=True,
    )
    return po.name


@frappe.whitelist()
def get_booking_flow_data(sales_order: str) -> dict:
    """
    Return a complete snapshot of a customer booking and everything linked
    to it, used by the visual Booking Flow page.
    """
    if not sales_order:
        frappe.throw(_("sales_order is required"))

    so = frappe.get_doc("Sales Order", sales_order)

    # Wallet info for this booking
    wallet_txn = None
    if so.get("wallet_hold_reference"):
        wallet_txn = frappe.db.get_value(
            "Wallet Transaction", so.wallet_hold_reference,
            ["name", "status", "amount", "balance_after"], as_dict=True,
        )

    # Sales Invoice(s)
    sales_invoices = frappe.db.sql("""
        SELECT DISTINCT si.name, si.posting_date, si.grand_total, si.status, si.docstatus
        FROM `tabSales Invoice` si
        INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE sii.sales_order = %s
        ORDER BY si.posting_date
    """, so.name, as_dict=True)

    # Delivery Note(s)
    delivery_notes = frappe.db.sql("""
        SELECT DISTINCT dn.name, dn.posting_date, dn.status, dn.docstatus
        FROM `tabDelivery Note` dn
        INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
        WHERE dni.against_sales_order = %s
        ORDER BY dn.posting_date
    """, so.name, as_dict=True)

    # Purchase Orders linked to this booking
    purchase_orders = frappe.get_all(
        "Purchase Order",
        filters={"alphax_against_customer_booking": so.name},
        fields=["name", "supplier", "supplier_name", "grand_total",
                "transaction_date", "status", "docstatus"],
        order_by="transaction_date",
    )

    # Purchase Invoices
    purchase_invoices = frappe.get_all(
        "Purchase Invoice",
        filters={"alphax_against_customer_booking": so.name},
        fields=["name", "supplier", "supplier_name", "grand_total",
                "outstanding_amount", "posting_date", "status", "docstatus"],
        order_by="posting_date",
    )

    # Supplier payments
    supplier_payments = frappe.get_all(
        "Payment Entry",
        filters={
            "alphax_against_customer_booking": so.name,
            "party_type": "Supplier",
            "docstatus": 1,
        },
        fields=["name", "party", "party_name", "paid_amount", "posting_date"],
        order_by="posting_date",
    )

    # Compute margin
    total_revenue = flt(so.grand_total)
    total_cost = sum(flt(pi.grand_total) for pi in purchase_invoices if pi.docstatus == 1)
    total_paid_to_suppliers = sum(flt(pe.paid_amount) for pe in supplier_payments)
    margin = total_revenue - total_cost

    return {
        "sales_order": {
            "name": so.name,
            "customer": so.customer,
            "customer_name": so.customer_name,
            "currency": so.currency,
            "grand_total": flt(so.grand_total),
            "status": so.status,
            "docstatus": so.docstatus,
            "transaction_date": str(so.transaction_date),
            "use_wallet_payment": so.get("use_wallet_payment"),
            "procurement_status": so.get("alphax_procurement_status") or "Not Required",
        },
        "wallet_transaction": wallet_txn,
        "sales_invoices": sales_invoices,
        "delivery_notes": delivery_notes,
        "purchase_orders": purchase_orders,
        "purchase_invoices": purchase_invoices,
        "supplier_payments": supplier_payments,
        "margin": {
            "revenue": total_revenue,
            "cost": total_cost,
            "paid_to_suppliers": total_paid_to_suppliers,
            "margin": margin,
            "margin_pct": (margin / total_revenue * 100) if total_revenue else 0,
        },
    }
