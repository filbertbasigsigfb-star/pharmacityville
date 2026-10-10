"""Database models for Pharmacityville."""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def is_active(self):
        """Flask-Login must reject disabled accounts."""
        return bool(self.is_enabled)

    orders = db.relationship("Order", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=False, default="")
    requires_prescription = db.Column(db.Boolean, nullable=False, default=False)
    image_url = db.Column(db.String(500), nullable=True)

    order_items = db.relationship("OrderItem", back_populates="medicine")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    # Offline checkout choice. Existing orders default to pay at pickup.
    payment_method = db.Column(db.String(20), nullable=False, default="pickup", server_default="pickup")
    delivery_name = db.Column(db.String(100), nullable=True)
    delivery_phone = db.Column(db.String(20), nullable=True)
    delivery_address = db.Column(db.String(500), nullable=True)
    # Only an administrator confirms that cash was actually collected.
    cod_paid_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    medicine = db.relationship("Medicine", back_populates="order_items")


class PrescriptionRequest(db.Model):
    """Private upload awaiting pharmacist review; one request for one medicine."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    medicine_id = db.Column(db.Integer, db.ForeignKey("medicine.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    used_quantity = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="Pending")
    stored_filename = db.Column(db.String(80), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    reviewed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship("User")
    medicine = db.relationship("Medicine")


class PrescriptionUse(db.Model):
    """Tracks approval quantities consumed by orders for safe cancellation."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescription_request.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    prescription = db.relationship("PrescriptionRequest")


class PaymentAttempt(db.Model):
    """One provider-hosted payment session for a reserved order."""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), unique=True, nullable=False)
    reference_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    provider_session_id = db.Column(db.String(100), unique=True, nullable=False)
    method = db.Column(db.String(20), nullable=False)
    state = db.Column(db.String(20), nullable=False, default="Pending")
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    checkout_url = db.Column(db.String(800), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    paid_at = db.Column(db.DateTime, nullable=True)

    order = db.relationship("Order", backref=db.backref("payment_attempt", uselist=False))
