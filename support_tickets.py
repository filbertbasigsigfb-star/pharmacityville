"""Customer problem reports and administrator support inbox.

A report is saved to SQLite first. Optional SMTP notifications are sent only
AFTER the database commit; email failure must never lose a customer report.
"""
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
import os
import re
import smtplib
import ssl

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from auth import admin_required
from models import db, Order, User

support_bp = Blueprint("support", __name__, url_prefix="/support")
admin_support_bp = Blueprint("admin_support", __name__, url_prefix="/admin/support")

CATEGORIES = (
    "Order problem", "Payment question", "Delivery or pickup",
    "Medicine availability", "Prescription request", "Website issue", "Other",
)
STATUSES = ("Open", "In Progress", "Resolved")


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SupportTicket(db.Model):
    __tablename__ = "support_ticket"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=True)
    category = db.Column(db.String(40), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Open", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=_now)
    user = db.relationship("User", foreign_keys=[user_id])
    order = db.relationship("Order", foreign_keys=[order_id])
    messages = db.relationship(
        "SupportMessage", back_populates="ticket", cascade="all, delete-orphan",
        order_by="SupportMessage.id",
    )


class SupportMessage(db.Model):
    __tablename__ = "support_message"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("support_ticket.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_now)
    ticket = db.relationship("SupportTicket", back_populates="messages")
    author = db.relationship("User")


def _safe_email(value):
    """Reject newline injection and obvious invalid recipient addresses."""
    return bool(value and len(value) <= 254 and re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value))


def _smtp_config():
    """SMTP is optional; keep credentials in .env, never in a source file."""
    host = os.getenv("SUPPORT_SMTP_HOST", "").strip()
    username = os.getenv("SUPPORT_SMTP_USERNAME", "").strip()
    password = os.getenv("SUPPORT_SMTP_PASSWORD", "")
    sender = os.getenv("SUPPORT_SMTP_FROM", username).strip()
    try:
        port = int(os.getenv("SUPPORT_SMTP_PORT", "587"))
    except ValueError:
        return None
    if not (host and username and password and _safe_email(sender) and 1 <= port <= 65535):
        return None
    return host, port, username, password, sender


def _send_notice(recipient, subject, body):
    """Return sent/not-configured/failed; never expose credentials to users."""
    config = _smtp_config()
    if not config or not _safe_email(recipient):
        return "not_configured"
    host, port, username, password, sender = config
    mail = EmailMessage()
    mail["From"] = sender
    mail["To"] = recipient
    mail["Subject"] = subject
    mail.set_content(body)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=8, context=ssl.create_default_context()) as client:
                client.login(username, password)
                client.send_message(mail)
        else:
            with smtplib.SMTP(host, port, timeout=8) as client:
                client.ehlo()
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
                client.login(username, password)
                client.send_message(mail)
    except (OSError, smtplib.SMTPException) as exc:
        current_app.logger.warning("Support notification delivery failed (%s)", type(exc).__name__)
        return "failed"
    return "sent"


def _admin_notification(ticket):
    recipient = os.getenv("SUPPORT_ADMIN_EMAIL", "").strip()
    link = url_for("admin_support.ticket_detail", ticket_id=ticket.id, _external=True, _scheme="https")
    # Do NOT email the customer's complaint text or any prescription/health data.
    return _send_notice(
        recipient, f"Pharmacityville: Support report #{ticket.id}",
        f"A customer submitted or updated support report #{ticket.id}.\n"
        f"Category: {ticket.category}\n"
        f"Sign in to review the report securely: {link}\n",
    )


def _customer_notification(ticket):
    link = url_for("support.ticket_detail", ticket_id=ticket.id, _external=True, _scheme="https")
    return _send_notice(
        ticket.user.email, f"Pharmacityville: Update on report #{ticket.id}",
        f"Your report #{ticket.id} has a new update from the pharmacy team.\n"
        f"Sign in to view the response: {link}\n",
    )


def _validate_message(body):
    body = body.strip()
    if not 10 <= len(body) <= 2000:
        return body, "Please enter a message between 10 and 2,000 characters."
    return body, None


def _own_ticket(ticket_id):
    ticket = db.get_or_404(SupportTicket, ticket_id)
    if ticket.user_id != current_user.id:
        abort(403)
    return ticket


@support_bp.route("/", methods=["GET"])
@login_required
def my_tickets():
    tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(
        SupportTicket.updated_at.desc(), SupportTicket.id.desc()
    ).all()
    return render_template("support/my_tickets.html", tickets=tickets)


@support_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if current_user.role == "admin":
        return redirect(url_for("admin_support.list_tickets"))

    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).limit(50).all()
    data = {
        "category": request.form.get("category", "Other"),
        "subject": request.form.get("subject", "").strip(),
        "message": request.form.get("message", "").strip(),
        "order_id": request.form.get("order_id", request.args.get("order_id", "")).strip(),
    }
    if request.method == "POST":
        errors = []
        if data["category"] not in CATEGORIES:
            errors.append("Please choose a valid report category.")
        if not 5 <= len(data["subject"]) <= 150:
            errors.append("Subject must be between 5 and 150 characters.")
        body, error = _validate_message(data["message"])
        if error:
            errors.append(error)
        order = None
        if data["order_id"]:
            if not re.fullmatch(r"[1-9][0-9]{0,8}", data["order_id"]):
                errors.append("Select a valid order number.")
            else:
                order = db.session.get(Order, int(data["order_id"]))
                if order is None or order.user_id != current_user.id:
                    abort(403)  # Never attach another customer's order.
        # Basic per-account throttling without an extra dependency.
        latest = SupportTicket.query.filter_by(user_id=current_user.id).order_by(
            SupportTicket.created_at.desc()
        ).first()
        if latest and latest.created_at > _now() - timedelta(seconds=45):
            errors.append("Please wait a moment before creating another report.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("support/new_ticket.html", categories=CATEGORIES, orders=orders, data=data), 400

        ticket = SupportTicket(
            user_id=current_user.id, order_id=order.id if order else None,
            category=data["category"], subject=data["subject"],
        )
        try:
            db.session.add(ticket)
            db.session.flush()
            db.session.add(SupportMessage(ticket_id=ticket.id, author_id=current_user.id, body=body))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Your report could not be saved. Please try again.", "danger")
            return render_template("support/new_ticket.html", categories=CATEGORIES, orders=orders, data=data), 500

        mail_result = _admin_notification(ticket)
        flash(
            "Your report was saved and the admin was notified by email."
            if mail_result == "sent" else
            "Your report was saved in the admin inbox. Email notification is not yet available.",
            "success" if mail_result == "sent" else "info",
        )
        return redirect(url_for("support.ticket_detail", ticket_id=ticket.id))

    if data["order_id"] and not any(str(order.id) == data["order_id"] for order in orders):
        data["order_id"] = ""
    return render_template("support/new_ticket.html", categories=CATEGORIES, orders=orders, data=data)


@support_bp.route("/<int:ticket_id>", methods=["GET"])
@login_required
def ticket_detail(ticket_id):
    return render_template("support/ticket_detail.html", ticket=_own_ticket(ticket_id))


@support_bp.route("/<int:ticket_id>/reply", methods=["POST"])
@login_required
def customer_reply(ticket_id):
    ticket = _own_ticket(ticket_id)
    body, error = _validate_message(request.form.get("message", ""))
    if error:
        flash(error, "danger")
        return redirect(url_for("support.ticket_detail", ticket_id=ticket.id))
    if ticket.status == "Resolved":
        ticket.status = "Open"  # Customer may reopen a resolved report.
    ticket.updated_at = _now()
    try:
        db.session.add(SupportMessage(ticket_id=ticket.id, author_id=current_user.id, body=body))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Your reply could not be saved.", "danger")
        return redirect(url_for("support.ticket_detail", ticket_id=ticket.id))
    mail_result = _admin_notification(ticket)
    flash("Reply sent to the admin inbox." + (
        " An email notification was also sent." if mail_result == "sent" else ""
    ), "success")
    return redirect(url_for("support.ticket_detail", ticket_id=ticket.id))


@admin_support_bp.route("/", methods=["GET"])
@admin_required
def list_tickets():
    selected = request.args.get("status", "All")
    if selected not in (*STATUSES, "All"):
        selected = "All"
    query = SupportTicket.query
    if selected != "All":
        query = query.filter_by(status=selected)
    tickets = query.order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc()).all()
    counts = {status: SupportTicket.query.filter_by(status=status).count() for status in STATUSES}
    return render_template("support/admin_tickets.html", tickets=tickets, counts=counts, selected=selected)


@admin_support_bp.route("/<int:ticket_id>", methods=["GET"])
@admin_required
def ticket_detail(ticket_id):
    ticket = db.get_or_404(SupportTicket, ticket_id)
    return render_template("support/admin_ticket_detail.html", ticket=ticket, statuses=STATUSES)


@admin_support_bp.route("/<int:ticket_id>/reply", methods=["POST"])
@admin_required
def admin_reply(ticket_id):
    ticket = db.get_or_404(SupportTicket, ticket_id)
    body, error = _validate_message(request.form.get("message", ""))
    status = request.form.get("status", "In Progress")
    if error or status not in STATUSES:
        flash(error or "Select a valid status.", "danger")
        return redirect(url_for("admin_support.ticket_detail", ticket_id=ticket.id))
    ticket.updated_at = _now()
    ticket.status = status
    try:
        db.session.add(SupportMessage(ticket_id=ticket.id, author_id=current_user.id, body=body))
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not save your reply.", "danger")
        return redirect(url_for("admin_support.ticket_detail", ticket_id=ticket.id))
    mail_result = _customer_notification(ticket)
    flash("Reply saved. " + (
        "Customer email notification sent." if mail_result == "sent"
        else "Customer can read the reply in their account; email was not sent."
    ), "success" if mail_result == "sent" else "info")
    return redirect(url_for("admin_support.ticket_detail", ticket_id=ticket.id))


@admin_support_bp.route("/<int:ticket_id>/status", methods=["POST"])
@admin_required
def update_status(ticket_id):
    ticket = db.get_or_404(SupportTicket, ticket_id)
    status = request.form.get("status", "")
    if status not in STATUSES:
        abort(400, "Invalid support status")
    ticket.status = status
    ticket.updated_at = _now()
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Report status could not be changed.", "danger")
        return redirect(url_for("admin_support.ticket_detail", ticket_id=ticket.id))
    flash("Report status updated.", "success")
    return redirect(url_for("admin_support.ticket_detail", ticket_id=ticket.id))
