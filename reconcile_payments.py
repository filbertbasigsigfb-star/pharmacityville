"""Recover missed Xendit webhooks. Run manually or by scheduled task.

Never invent a payment result: inspect Xendit's authenticated API first.
Existing completed payments are not altered.
"""
from datetime import datetime, timezone
import os

import requests
from sqlalchemy import update

from app import app
from models import Order, PaymentAttempt, db
from payments import _restore_order_stock


def main():
    key = os.getenv("XENDIT_API_KEY", "")
    if not key:
        print("XENDIT_API_KEY is not configured. Nothing to reconcile.")
        return
    with app.app_context():
        pending = PaymentAttempt.query.filter_by(state="Pending").all()
        for attempt in pending:
            try:
                response = requests.get(
                    "https://api.xendit.co/sessions/" + attempt.provider_session_id,
                    auth=(key, ""), timeout=15,
                    headers={"api-version": "2024-11-11"},
                )
                response.raise_for_status()
                info = response.json()
                if info.get("reference_id") != attempt.reference_id:
                    raise ValueError("Provider session reference mismatch")
                if info.get("currency") != "PHP":
                    raise ValueError("Provider currency mismatch")
                from decimal import Decimal
                if Decimal(str(info.get("amount"))) != attempt.amount:
                    raise ValueError("Provider session amount mismatch")
                if info.get("payment_session_id") != attempt.provider_session_id:
                    raise ValueError("Provider session ID mismatch")
                status = info.get("status")
                order = attempt.order
                if status == "COMPLETED":
                    if order.status == "Awaiting Payment":
                        order.status = "Pending"
                        attempt.state = "Paid"
                        attempt.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    elif order.status == "Cancelled":
                        attempt.state = "LatePaid"  # Requires manual refund
                elif status in ("EXPIRED", "CANCELED") and order.status == "Awaiting Payment":
                    result = db.session.execute(update(Order).where(
                        Order.id == order.id, Order.status == "Awaiting Payment"
                    ).values(status="Cancelled"))
                    if result.rowcount == 1:
                        _restore_order_stock(order)
                        attempt.state = "Expired" if status == "EXPIRED" else "Cancelled"
                db.session.commit()
                print(attempt.reference_id, status, "->", attempt.state)
            except (requests.RequestException, ValueError, KeyError) as error:
                db.session.rollback()
                print(attempt.reference_id, "not updated:", str(error)[:180])
            except Exception as error:
                db.session.rollback()
                print(attempt.reference_id, "error, review manually:", type(error).__name__)


if __name__ == "__main__":
    main()
