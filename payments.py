"""Xendit-hosted online checkout for Pharmacityville.

Payment gateway is optional until configured. No card information enters Flask.
Only authenticated Xendit callbacks can mark an order paid.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hmac
import os
import re
import secrets

import requests
from flask import Blueprint, abort, current_app, flash, redirect, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from models import Medicine, Order, PaymentAttempt, PrescriptionRequest, PrescriptionUse, db
from customer_orders import cart_details, create_order_from_cart

payments_bp = Blueprint("payments", __name__)
API_URL = "https://api.xendit.co/sessions"
METHODS = {
    "gcash": ["GCASH"],
    "qrph": ["QRPH"],
    "card": ["CARDS"],
    "apple_pay": ["CARDS"],  # Apple Pay appears on Xendit only if account/browser/device eligible.
}


def gateway_ready():
    return bool(os.getenv("XENDIT_API_KEY") and os.getenv("XENDIT_WEBHOOK_TOKEN"))


def _auth():
    return (os.environ["XENDIT_API_KEY"], "")


def _return_url(endpoint, **params):
    configured = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    path = url_for(endpoint, **params)
    if configured:
        if not configured.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must start with https://")
        return configured + path
    # PythonAnywhere's front-facing domain is HTTPS even behind their proxy.
    return url_for(endpoint, _external=True, _scheme="https", **params)


def create_provider_session(method, reference, total, customer_id, email, customer_name):
    """Create a single-use hosted session; Xendit owns the GCash/card UI."""
    if method not in METHODS:
        raise ValueError("Unsupported online payment method")

    # Xendit requires an alphanumeric customer reference and individual name.
    clean_name = re.sub(r"[^A-Za-z0-9 ]", "", customer_name or "").strip()
    if not clean_name:
        raise ValueError("Customer name is required to start a payment")
    name_parts = clean_name.split(maxsplit=1)
    individual_detail = {"given_names": name_parts[0][:50]}
    if len(name_parts) > 1:
        individual_detail["surname"] = name_parts[1][:50]

    payload = {
        "reference_id": reference,
        "session_type": "PAY",
        "mode": "PAYMENT_LINK",
        "amount": float(total),
        "currency": "PHP",
        "country": "PH",
        "locale": "en",
        "capture_method": "AUTOMATIC",
        "allow_save_payment_method": "DISABLED",
        "allowed_payment_channels": METHODS[method],
        "description": "Pharmacityville medicine order " + reference,
        "customer": {
            "reference_id": f"PVCCUSTOMER{customer_id}{reference.replace('-', '')}",
            "type": "INDIVIDUAL",
            "email": email,
            "individual_detail": individual_detail,
        },
        "success_return_url": _return_url("payments.payment_return", reference=reference),
        "cancel_return_url": _return_url("payments.payment_return", reference=reference),
    }
    response = requests.post(
        API_URL,
        json=payload,
        auth=_auth(),
        timeout=15,
        headers={"api-version": "2024-11-11"},
    )
    if not response.ok:
        try:
            error_data = response.json()
            if not isinstance(error_data, dict):
                error_data = {}
        except ValueError:
            error_data = {}
        # Log the provider error, never the secret API key or request payload.
        current_app.logger.error(
            "Xendit session failed: HTTP %s, code=%s, message=%s",
            response.status_code,
            str(error_data.get("error_code", "UNKNOWN"))[:80],
            str(error_data.get("message", "No details provided"))[:300],
        )
        response.raise_for_status()

    result = response.json()
    checkout_url = result.get("payment_link_url", "")
    provider_id = result.get("payment_session_id", "")
    if (not isinstance(provider_id, str)
            or not provider_id.startswith("ps-")
            or not isinstance(checkout_url, str)
            or not checkout_url.startswith("https://")):
        raise ValueError("Gateway response was missing a secure checkout link")

    return {
        "reference_id": reference,
        "provider_session_id": provider_id,
        "method": method,
        "checkout_url": checkout_url,
    }


def cancel_provider_session(provider_id):
    """Only release reserved stock after payment was successfully cancelled upstream."""
    if not gateway_ready():
        return False
    try:
        res = requests.post(f"{API_URL}/{provider_id}/cancel", auth=_auth(),
                            timeout=15, headers={"api-version": "2024-11-11"})
        if res.status_code in (200, 201):
            return res.json().get("status") in {"CANCELED", "EXPIRED"}
        # 4xx might mean the checkout has already completed; never free stock.
    except (requests.RequestException, ValueError):
        pass
    return False


def _restore_order_stock(order):
    """Call within the transaction after the order has been marked Cancelled."""
    for item in order.items:
        db.session.execute(update(Medicine).where(Medicine.id == item.medicine_id)
                           .values(stock=Medicine.stock + item.quantity))
    for use in PrescriptionUse.query.filter_by(order_id=order.id).all():
        result = db.session.execute(update(PrescriptionRequest).where(
            PrescriptionRequest.id == use.prescription_id,
            PrescriptionRequest.used_quantity >= use.quantity,
        ).values(used_quantity=PrescriptionRequest.used_quantity - use.quantity))
        if result.rowcount != 1:
            raise ValueError("Prescription reservation could not be returned")


@payments_bp.route("/payments/start", methods=["POST"])
@login_required
def start_payment():
    method = request.form.get("payment_method", "")
    if method not in METHODS:
        abort(400, "Choose a valid payment method")
    if not gateway_ready():
        flash("Online payments are not configured. Use Pay at pickup or contact the pharmacy.", "warning")
        return redirect(url_for("customer.checkout"))
    lines, total, errors = cart_details()
    if not lines or errors or total <= 0 or total > Decimal("99999999.99"):
        flash("Review your cart before starting payment.", "danger")
        return redirect(url_for("customer.cart"))
    reference = "PVC-" + secrets.token_hex(12)
    try:
        pdata = create_provider_session(
            method, reference, total, current_user.id, current_user.email,
            current_user.name
        )
    except (requests.RequestException, ValueError, KeyError):
        flash("Payment provider is unavailable or the selected payment method is not enabled. Try another method.", "danger")
        return redirect(url_for("customer.checkout"))
    # Provider checkout is active; now reserve stock and prescription quantities
    # atomically. If local reservation fails, invalidate remote checkout first.
    try:
        order = create_order_from_cart(lines, "Awaiting Payment", payment_data=pdata)
    except (SQLAlchemyError, ValueError) as exc:
        cancel_provider_session(pdata["provider_session_id"])
        flash("Stock changed before payment started. Review your cart and retry.", "danger")
        return redirect(url_for("customer.cart"))
    session.pop("cart", None)
    return redirect(pdata["checkout_url"], code=303)


@payments_bp.route("/payments/return/<reference>", methods=["GET"])
@login_required
def payment_return(reference):
    attempt = PaymentAttempt.query.filter_by(reference_id=reference).first_or_404()
    if attempt.order.user_id != current_user.id:
        abort(403)
    flash("Returned from payment provider. Payment status updates only after verified confirmation; please check the order details.", "info")
    return redirect(url_for("customer.order_detail", order_id=attempt.order_id))


@payments_bp.route("/payments/xendit/webhook", methods=["POST"])
def xendit_webhook():
    """Authenticate before parsing; success URLs never mark an order as paid."""
    token = os.getenv("XENDIT_WEBHOOK_TOKEN", "")
    supplied = request.headers.get("x-callback-token", "")
    if not token or not supplied or not hmac.compare_digest(token, supplied):
        abort(401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    event = data.get("event", "")
    if event not in {"payment_session.completed", "payment_session.expired"}:
        return {"ok": True}
    info = data.get("data", {})
    if not isinstance(info, dict):
        abort(400)
    reference = info.get("reference_id", "")
    attempt = PaymentAttempt.query.filter_by(reference_id=reference).first()
    if attempt is None:
        # Do not try to create orders based on unrecognized notifications.
        return {"ok": True}
    order = attempt.order
    if info.get("payment_session_id") != attempt.provider_session_id:
        abort(400)
    if info.get("session_type") != "PAY" or info.get("currency") != "PHP":
        abort(400)
    try:
        payment_amount = Decimal(str(info.get("amount")))
    except (InvalidOperation, TypeError):
        abort(400)
    if not payment_amount.is_finite() or payment_amount != attempt.amount or attempt.amount != order.total:
        abort(400)
    # A payment cannot confirm an order that was deleted or was not reserved.
    try:
        if event == "payment_session.completed" and info.get("status") == "COMPLETED":
            if attempt.state == "Paid":
                return {"ok": True}  # Idempotent webhook retry
            if attempt.state in {"Cancelled", "Expired"} or order.status == "Cancelled":
                attempt.state = "LatePaid"  # Important: MANUAL REFUND NEEDED
            elif attempt.state == "Pending" and order.status == "Awaiting Payment":
                changed = db.session.execute(update(Order).where(
                    Order.id == order.id, Order.status == "Awaiting Payment"
                ).values(status="Pending"))
                if changed.rowcount == 1:
                    attempt.state = "Paid"
                    attempt.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.commit()
        elif event == "payment_session.expired" and info.get("status") == "EXPIRED":
            if attempt.state == "Pending" and order.status == "Awaiting Payment":
                changed = db.session.execute(update(Order).where(
                    Order.id == order.id, Order.status == "Awaiting Payment"
                ).values(status="Cancelled"))
                if changed.rowcount == 1:
                    _restore_order_stock(order)
                    attempt.state = "Expired"
                    db.session.commit()
            else:
                db.session.rollback()
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        return {"ok": False}, 500  # Provider should retry webhook.
    return {"ok": True}
