"""Admin dashboard."""
from decimal import Decimal
import hashlib
import json

from flask import Blueprint, render_template, jsonify
from sqlalchemy import func

from auth import admin_required
from models import Medicine, Order, User, PrescriptionRequest, PaymentAttempt, db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@admin_required
def dashboard():
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    # Completed orders only: a sales-value proxy, not confirmed cash receipts.
    completed_value = db.session.query(func.sum(Order.total)).filter(
        Order.status == "Completed").scalar() or Decimal("0.00")
    active_value = db.session.query(func.sum(Order.total)).filter(
        Order.status.in_(["Pending", "Preparing", "Ready"])).scalar() or Decimal("0.00")
    # Inventory attention list: these are low-stock products, not confirmed purchase needs.
    low_stock = (Medicine.query.filter(Medicine.stock <= 10)
                 .order_by(Medicine.stock.asc(), Medicine.name.asc()).limit(8).all())
    low_stock_count = Medicine.query.filter(Medicine.stock.between(1, 10)).count()
    out_of_stock_count = Medicine.query.filter(Medicine.stock == 0).count()
    return render_template(
        "admin_dashboard.html",
        user_count=User.query.count(),
        medicine_count=Medicine.query.count(),
        order_count=Order.query.count(),
        recent_orders=recent_orders,
        completed_value=completed_value,
        active_value=active_value,
        online_paid_value=(db.session.query(func.sum(PaymentAttempt.amount)).filter(PaymentAttempt.state == "Paid").scalar() or Decimal("0.00")),
        cod_cash_value=(db.session.query(func.sum(Order.total)).filter(
            Order.payment_method == "cod", Order.cod_paid_at.is_not(None)
        ).scalar() or Decimal("0.00")),
        awaiting_payment_count=Order.query.filter_by(status="Awaiting Payment").count(),
        refund_alert_count=PaymentAttempt.query.filter_by(state="LatePaid").count(),
        pending_prescriptions=PrescriptionRequest.query.filter_by(status="Pending").count(),
        low_stock=low_stock,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
    )


def _version(rows):
    """Stable digest for checking whether admin-visible data changed."""
    payload = json.dumps(
        [[str(value) if value is not None else None for value in row] for row in rows],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@admin_bp.route("/live-state", methods=["GET"])
@admin_required
def live_state():
    """Minimal, admin-only summary polled by the browser. No private orders data."""
    order_rows = (
        db.session.query(
            Order.id, Order.user_id, Order.status, Order.total, Order.created_at,
            User.name, User.email, PaymentAttempt.state,
            Order.payment_method, Order.cod_paid_at
        )
        .join(User, User.id == Order.user_id)
        .outerjoin(PaymentAttempt, PaymentAttempt.order_id == Order.id)
        .order_by(Order.id.asc()).all()
    )
    medicine_rows = (
        db.session.query(
            Medicine.id, Medicine.name, Medicine.category, Medicine.price,
            Medicine.stock, Medicine.description, Medicine.requires_prescription,
            Medicine.image_url
        ).order_by(Medicine.id.asc()).all()
    )
    orders_version = _version(order_rows)
    medicines_version = _version(medicine_rows)
    users_count = User.query.count()
    pending_prescriptions = PrescriptionRequest.query.filter_by(status="Pending").count()
    pending_orders = sum(1 for row in order_rows if row[2] == "Pending")
    latest_order_id = max((row[0] for row in order_rows if row[2] in ("Pending", "Preparing", "Ready", "Completed")), default=0)
    dashboard_version = _version([(orders_version, medicines_version,
                                   users_count, pending_prescriptions)])
    response = jsonify(
        orders_version=orders_version,
        medicines_version=medicines_version,
        dashboard_version=dashboard_version,
        latest_order_id=latest_order_id,
        pending_orders=pending_orders,
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response
