"""Customers submit private prescription proof; admins review before ordering.

Demonstration only: actual dispensing requires a qualified pharmacist, legal
prescription validation, records retention, and data-protection safeguards.
"""
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, redirect, render_template,
                   request, send_file, url_for)
from flask_login import current_user, login_required
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from auth import admin_required
from models import Medicine, PrescriptionRequest, db

prescriptions_bp = Blueprint("prescriptions", __name__)
MAX_UPLOAD = 4 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def private_upload_folder():
    folder = Path(current_app.instance_path) / "prescriptions"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def checked_upload(file):
    """Accept small PDF/JPEG/PNG files with matching magic bytes."""
    if not file or not file.filename:
        return None, None, "Please attach a prescription image or PDF."
    original = Path(file.filename.replace("\\", "/")).name[:200]
    extension = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    header = file.stream.read(8)
    file.stream.seek(0)
    kinds = {
        "pdf": header.startswith(b"%PDF-"),
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\xff\xd8\xff"),
    }
    if not kinds.get(extension):
        return None, None, "Only genuine PDF, PNG, and JPEG files are supported."
    data = file.stream.read(MAX_UPLOAD + 1)
    if not data or len(data) > MAX_UPLOAD:
        return None, None, "Prescription files must be 4 MB or smaller."
    return (data, original, None)


@prescriptions_bp.route("/prescriptions", methods=["GET"])
@login_required
def my_requests():
    requests = PrescriptionRequest.query.filter_by(user_id=current_user.id).order_by(
        PrescriptionRequest.created_at.desc(), PrescriptionRequest.id.desc()).all()
    return render_template("my_prescriptions.html", requests=requests, now=utc_now())


@prescriptions_bp.route("/prescriptions/request/<int:medicine_id>", methods=["GET", "POST"])
@login_required
def request_prescription(medicine_id):
    medicine = db.get_or_404(Medicine, medicine_id)
    if not medicine.requires_prescription:
        flash("This medicine does not require a prescription request.", "info")
        return redirect(url_for("customer.catalog"))
    if request.method == "GET":
        return render_template("prescription_form.html", medicine=medicine)

    raw_quantity = request.form.get("quantity", "").strip()
    if not raw_quantity.isdecimal() or len(raw_quantity) > 3 or not (1 <= int(raw_quantity) <= 999):
        flash("Requested quantity must be a whole number from 1 to 999.", "danger")
        return render_template("prescription_form.html", medicine=medicine), 400
    quantity = int(raw_quantity)
    existing = PrescriptionRequest.query.filter_by(
        user_id=current_user.id, medicine_id=medicine.id, status="Pending").first()
    if existing:
        flash("You already have a pending request for this medicine.", "warning")
        return redirect(url_for("prescriptions.my_requests"))
    data, original, error = checked_upload(request.files.get("document"))
    if error:
        flash(error, "danger")
        return render_template("prescription_form.html", medicine=medicine), 400
    extension = original.rsplit(".", 1)[-1].lower()
    stored = secrets.token_hex(24) + "." + extension
    path = private_upload_folder() / stored
    try:
        with path.open("xb") as f:
            f.write(data)
        row = PrescriptionRequest(
            user_id=current_user.id, medicine_id=medicine.id, quantity=quantity,
            stored_filename=stored, original_filename=original, status="Pending",
        )
        db.session.add(row)
        db.session.commit()
    except (OSError, SQLAlchemyError):
        db.session.rollback()
        path.unlink(missing_ok=True)
        flash("Unable to submit your prescription. Please try again.", "danger")
        return render_template("prescription_form.html", medicine=medicine), 500
    flash("Prescription submitted for pharmacist review. Approval is not automatic.", "success")
    return redirect(url_for("prescriptions.my_requests"))


@prescriptions_bp.route("/prescriptions/<int:request_id>/file", methods=["GET"])
@login_required
def prescription_file(request_id):
    row = db.get_or_404(PrescriptionRequest, request_id)
    if row.user_id != current_user.id and current_user.role != "admin":
        abort(403)
    path = private_upload_folder() / row.stored_filename
    if not path.is_file():
        abort(404)
    response = send_file(path, as_attachment=True,
                         download_name=row.original_filename,
                         mimetype="application/octet-stream", max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@prescriptions_bp.route("/admin/prescriptions", methods=["GET"])
@admin_required
def admin_requests():
    requests = PrescriptionRequest.query.order_by(
        PrescriptionRequest.created_at.desc(), PrescriptionRequest.id.desc()).all()
    return render_template("admin_prescriptions.html", requests=requests, now=utc_now())


@prescriptions_bp.route("/admin/prescriptions/<int:request_id>/review", methods=["POST"])
@admin_required
def review_request(request_id):
    decision = request.form.get("decision", "")
    if decision not in ("Approved", "Rejected"):
        abort(400, description="Invalid prescription decision.")
    row = db.get_or_404(PrescriptionRequest, request_id)
    if row.status != "Pending":
        flash("This request has already been reviewed.", "warning")
        return redirect(url_for("prescriptions.admin_requests"))
    now = utc_now()
    values = {"status": decision, "reviewed_at": now}
    if decision == "Approved":
        # Time-limited authorization for the school demonstration.
        values["expires_at"] = now + timedelta(days=30)
    try:
        result = db.session.execute(update(PrescriptionRequest).where(
            PrescriptionRequest.id == request_id,
            PrescriptionRequest.status == "Pending").values(**values))
        if result.rowcount != 1:
            db.session.rollback()
            flash("Request changed; refresh the page.", "warning")
        else:
            db.session.commit()
            flash(f"Prescription request #{request_id} {decision.lower()}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not review request.", "danger")
    return redirect(url_for("prescriptions.admin_requests"))
