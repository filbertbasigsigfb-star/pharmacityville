"""Admin order list, detail, status changes, and cancelled-order deletion."""
from datetime import datetime, timezone
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from auth import admin_required
from models import Order, PrescriptionUse, db
from support_tickets import SupportTicket

admin_orders_bp = Blueprint("admin_orders", __name__, url_prefix="/admin/orders")
NEXT_STATUS = {"Pending": "Preparing", "Preparing": "Ready", "Ready": "Completed"}


@admin_orders_bp.route("/", methods=["GET"])
@admin_orders_bp.route("", methods=["GET"])
@admin_required
def list_orders():
    orders = Order.query.order_by(Order.created_at.desc(), Order.id.desc()).all()
    return render_template("admin_orders.html", orders=orders)


@admin_orders_bp.route("/<int:order_id>", methods=["GET"])
@admin_required
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    return render_template("admin_order_detail.html", order=order,
                           next_status=NEXT_STATUS.get(order.status))


@admin_orders_bp.route("/<int:order_id>/status", methods=["POST"])
@admin_required
def advance_status(order_id):
    order = db.get_or_404(Order, order_id)
    next_status = NEXT_STATUS.get(order.status)
    requested_status = request.form.get("status", "")
    if not next_status or requested_status != next_status:
        flash("Invalid status change. Orders must progress one stage at a time.", "danger")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))
    if next_status == "Completed" and order.payment_method == "cod" and not order.cod_paid_at:
        flash("Confirm receiving the cash payment before completing a COD order.", "warning")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))

    try:
        result = db.session.execute(
            update(Order).where(Order.id == order_id, Order.status == order.status)
            .values(status=next_status)
        )
        if result.rowcount != 1:
            db.session.rollback()
            flash("Order status changed. Refresh and try again.", "warning")
        else:
            db.session.commit()
            flash(f"Order #{order_id} moved to {next_status}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update the order status.", "danger")
    return redirect(url_for("admin_orders.order_detail", order_id=order_id))




@admin_orders_bp.route("/<int:order_id>/confirm-cod-cash", methods=["POST"])
@admin_required
def confirm_cod_cash(order_id):
    """Manually record cash actually received for a Ready COD order.

    A change of order status alone must never be treated as payment.
    The global CSRF guard protects this POST endpoint.
    """
    if request.form.get("cash_received") != "yes":
        flash("Confirm that you actually received the cash.", "warning")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        updated = db.session.execute(
            update(Order).where(
                Order.id == order_id,
                Order.payment_method == "cod",
                Order.status == "Ready",
                Order.cod_paid_at.is_(None),
            ).values(cod_paid_at=now)
        )
        if updated.rowcount != 1:
            db.session.rollback()
            flash("COD cash can be recorded once, for a Ready COD order only.", "warning")
        else:
            db.session.commit()
            flash(f"Cash received for COD order #{order_id} has been recorded.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not record the cash payment. Please try again.", "danger")
    return redirect(url_for("admin_orders.order_detail", order_id=order_id))


@admin_orders_bp.route("/<int:order_id>/delete", methods=["POST"])
@admin_required
def delete_cancelled(order_id):
    order = db.get_or_404(Order, order_id)
    if order.status != "Cancelled":
        flash("Only cancelled orders can be deleted.", "danger")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))

    if SupportTicket.query.filter_by(order_id=order_id).first():
        flash("This order is referenced in a support report and must be kept for its history.", "warning")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))

    if order.payment_method == "cod" and order.cod_paid_at:
        flash("A cash-paid COD order cannot be deleted; retain its payment record.", "warning")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))
    if order.payment_attempt and order.payment_attempt.state in {"Paid", "LatePaid"}:
        flash("Paid or refund-required payment records cannot be deleted.", "danger")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))
    try:
        if order.payment_attempt:
            db.session.delete(order.payment_attempt)
        # Delete prescription-use rows and items before removing the order.
        for usage in PrescriptionUse.query.filter_by(order_id=order_id).all():
            db.session.delete(usage)
        for item in list(order.items):
            db.session.delete(item)
        db.session.delete(order)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete the cancelled order.", "danger")
        return redirect(url_for("admin_orders.order_detail", order_id=order_id))

    # Do NOT restore stock here: it was restored at cancellation time.
    flash(f"Cancelled order #{order_id} deleted.", "success")
    return redirect(url_for("admin_orders.list_orders"))
