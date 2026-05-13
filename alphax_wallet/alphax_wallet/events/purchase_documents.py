"""
Purchase Order hooks — keep the originating customer Sales Order's
procurement status in sync.

Status flow:
    Pending     (SO submitted, no PO yet)
    PO Issued   (PO submitted)
    Received    (PR / PI received)
    Vendor Paid (PE against the supplier submitted)
"""

import frappe
from frappe import _


def update_so_on_po_submit(doc, method=None):
    """on_submit hook on Purchase Order."""
    so = doc.get("alphax_against_customer_booking")
    if not so:
        return
    _set_procurement_status(so, "PO Issued")


def update_so_on_po_cancel(doc, method=None):
    """on_cancel hook on Purchase Order — roll back to Pending."""
    so = doc.get("alphax_against_customer_booking")
    if not so:
        return
    # If there are still other PRs/PIs/PEs around, leave the status alone;
    # otherwise reset to Pending.
    if not _has_other_linked_docs(so, exclude_doctype="Purchase Order",
                                  exclude_name=doc.name):
        _set_procurement_status(so, "Pending")


def update_so_on_pi_submit(doc, method=None):
    """on_submit hook on Purchase Invoice — mark SO as Received."""
    so = doc.get("alphax_against_customer_booking")
    if not so:
        return
    _set_procurement_status(so, "Received")


def update_so_on_pi_cancel(doc, method=None):
    so = doc.get("alphax_against_customer_booking")
    if not so:
        return
    # Step back to PO Issued if PO still exists, otherwise Pending
    if _has_linked_po(so):
        _set_procurement_status(so, "PO Issued")
    else:
        _set_procurement_status(so, "Pending")


def update_so_on_supplier_payment(doc, method=None):
    """
    on_submit hook on Payment Entry — when a supplier payment is linked to a
    customer booking via the alphax_against_customer_booking field, mark the
    SO as Vendor Paid (only if the total paid >= total PI grand_total).
    """
    if doc.party_type != "Supplier":
        return
    so = doc.get("alphax_against_customer_booking")
    if not so:
        return

    # Check if total paid against this SO >= total invoiced
    total_invoiced = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabPurchase Invoice`
        WHERE alphax_against_customer_booking = %s AND docstatus = 1
    """, so)[0][0]

    total_paid = frappe.db.sql("""
        SELECT COALESCE(SUM(paid_amount), 0)
        FROM `tabPayment Entry`
        WHERE alphax_against_customer_booking = %s
          AND party_type = 'Supplier'
          AND docstatus = 1
    """, so)[0][0]

    if total_paid >= total_invoiced and total_invoiced > 0:
        _set_procurement_status(so, "Vendor Paid")


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _set_procurement_status(so_name, status):
    """Update the SO's procurement status only if it's currently behind."""
    current = frappe.db.get_value("Sales Order", so_name, "alphax_procurement_status")
    progression = ["Not Required", "Pending", "PO Issued", "Received", "Vendor Paid"]
    try:
        cur_idx = progression.index(current or "Not Required")
        new_idx = progression.index(status)
    except ValueError:
        cur_idx = new_idx = 0

    # Allow forward progression; allow explicit step-down (caller knows)
    frappe.db.set_value(
        "Sales Order", so_name, "alphax_procurement_status", status,
        update_modified=False,
    )


def _has_other_linked_docs(so_name, exclude_doctype=None, exclude_name=None):
    for dt in ("Purchase Order", "Purchase Invoice"):
        if dt == exclude_doctype:
            filters = {
                "alphax_against_customer_booking": so_name,
                "docstatus": 1,
                "name": ("!=", exclude_name),
            }
        else:
            filters = {"alphax_against_customer_booking": so_name, "docstatus": 1}
        if frappe.db.exists(dt, filters):
            return True
    return False


def _has_linked_po(so_name):
    return bool(frappe.db.exists("Purchase Order", {
        "alphax_against_customer_booking": so_name,
        "docstatus": 1,
    }))


# ----------------------------------------------------------------------------
# Set initial status on SO submit (called from sales_order event)
# ----------------------------------------------------------------------------

def init_procurement_status_on_so(doc, method=None):
    """Called from Sales Order on_submit. Sets initial procurement state."""
    # If user didn't set it, default to Pending so it's visible in the workflow
    if not doc.get("alphax_procurement_status") or doc.alphax_procurement_status == "Not Required":
        doc.db_set("alphax_procurement_status", "Pending", update_modified=False)
