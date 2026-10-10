"""Admin-only medicine inventory CRUD."""
import re
import csv
import io
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from auth import admin_required
from models import Medicine, OrderItem, PrescriptionRequest, db

medicines_bp = Blueprint(
    "admin_medicines", __name__, url_prefix="/admin/medicines"
)


def validate_medicine(form):
    """Return original form values, parsed price/stock, and friendly errors."""
    data = {
        "name": form.get("name", "").strip(),
        "category": form.get("category", "").strip(),
        "price": form.get("price", "").strip(),
        "stock": form.get("stock", "").strip(),
        "description": form.get("description", "").strip(),
        "image_url": form.get("image_url", "").strip(),
        "requires_prescription": form.get("requires_prescription") == "on",
    }
    errors = []

    if not data["name"]:
        errors.append("Medicine name is required.")
    elif len(data["name"]) > 150:
        errors.append("Medicine name must be at most 150 characters.")

    if not data["category"]:
        errors.append("Category is required.")
    elif len(data["category"]) > 100:
        errors.append("Category must be at most 100 characters.")

    if len(data["description"]) > 3000:
        errors.append("Description must be at most 3000 characters.")

    # Both bundled medicine pictures and remote HTTPS/HTTP images are supported.
    # Local paths are restricted to the intended static images folder.
    if data["image_url"]:
        image = data["image_url"]
        local_image = re.fullmatch(
            r"/static/img/medicines/[A-Za-z0-9_-]+\.(?:webp|png|jpg|jpeg|svg)",
            image, flags=re.IGNORECASE,
        ) is not None
        try:
            parsed = urlparse(image)
            external_image = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:
            external_image = False
        if len(image) > 500 or not (local_image or external_image):
            errors.append(
                "Enter a local /static/img/medicines/ picture or a full HTTP/HTTPS image URL "
                "(up to 500 characters)."
            )

    price = None
    try:
        price = Decimal(data["price"])
        if not price.is_finite() or price < 0 or price > Decimal("99999999.99"):
            raise ValueError
        if price != price.quantize(Decimal("0.01")):
            errors.append("Price can have no more than 2 decimal places.")
    except (InvalidOperation, ValueError):
        errors.append("Price must be a number from 0 to 99999999.99.")

    stock = None
    if not re.fullmatch(r"[0-9]+", data["stock"]):
        errors.append("Stock must be a whole number of 0 or greater.")
    else:
        stock = int(data["stock"])
        if stock > 2147483647:
            errors.append("Stock cannot exceed 2147483647.")

    return data, price, stock, errors


@medicines_bp.route("/", methods=["GET"])
@admin_required
def list_medicines():
    search = request.args.get("search", "").strip()[:100]
    category = request.args.get("category", "").strip()[:100]

    stock_filter = request.args.get("stock", "all")
    if stock_filter not in {"all", "low", "out", "available"}:
        stock_filter = "all"
    medicines = _filtered_medicines(search, category, stock_filter).order_by(Medicine.name.asc()).all()
    categories = [row[0] for row in db.session.query(Medicine.category)
                  .distinct().order_by(Medicine.category).all() if row[0]]

    return render_template(
        "admin_medicines.html", medicines=medicines, categories=categories,
        search=search, selected_category=category, selected_stock=stock_filter,
    )


def _filtered_medicines(search, category, stock_filter):
    """Apply the same authorized inventory filters to the table and CSV export."""
    query = Medicine.query
    if search:
        query = query.filter(or_(
            Medicine.name.ilike(f"%{search}%"),
            Medicine.description.ilike(f"%{search}%"),
        ))
    if category:
        query = query.filter(Medicine.category == category)
    if stock_filter == "low":
        query = query.filter(Medicine.stock.between(1, 10))
    elif stock_filter == "out":
        query = query.filter(Medicine.stock == 0)
    elif stock_filter == "available":
        query = query.filter(Medicine.stock > 0)
    return query


def _csv_safe(value):
    """Neutralize spreadsheet formulas in editable medicine fields."""
    text = str(value if value is not None else "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


@medicines_bp.route("/export.csv", methods=["GET"])
@admin_required
def export_inventory():
    """Download the currently filtered inventory (never private customer data)."""
    search = request.args.get("search", "").strip()[:100]
    category = request.args.get("category", "").strip()[:100]
    stock_filter = request.args.get("stock", "all")
    if stock_filter not in {"all", "low", "out", "available"}:
        stock_filter = "all"

    medicines = _filtered_medicines(search, category, stock_filter).order_by(Medicine.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Medicine", "Category", "Price (PHP)", "Stock", "Prescription required", "Description", "Image URL"])
    for m in medicines:
        writer.writerow([
            m.id, _csv_safe(m.name), _csv_safe(m.category), f"{m.price:.2f}", m.stock,
            "Yes" if m.requires_prescription else "No", _csv_safe(m.description), _csv_safe(m.image_url),
        ])
    # UTF-8 BOM makes Philippine peso/catalog labels readable in common spreadsheet apps.
    response = Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=pharmacityville_inventory.csv"
    response.headers["Cache-Control"] = "private, no-store"
    return response



@medicines_bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_medicine():
    if request.method == "POST":
        data, price, stock, errors = validate_medicine(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("medicine_form.html", medicine=None, form_data=data), 400

        medicine = Medicine(
            name=data["name"], category=data["category"],
            price=price, stock=stock,
            description=data["description"],
            image_url=data["image_url"] or None,
            requires_prescription=data["requires_prescription"],
        )
        try:
            db.session.add(medicine)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Medicine could not be saved. Please try again.", "danger")
            return render_template("medicine_form.html", medicine=None, form_data=data), 500

        flash("Medicine added successfully!", "success")
        return redirect(url_for("admin_medicines.list_medicines"))

    return render_template("medicine_form.html", medicine=None, form_data={})


@medicines_bp.route("/<int:medicine_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_medicine(medicine_id):
    medicine = db.get_or_404(Medicine, medicine_id)

    if request.method == "POST":
        data, price, stock, errors = validate_medicine(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("medicine_form.html", medicine=medicine, form_data=data), 400

        medicine.name = data["name"]
        medicine.category = data["category"]
        medicine.price = price
        medicine.stock = stock
        medicine.description = data["description"]
        medicine.image_url = data["image_url"] or None
        medicine.requires_prescription = data["requires_prescription"]

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Medicine could not be updated. Please try again.", "danger")
            return render_template("medicine_form.html", medicine=medicine, form_data=data), 500

        flash("Medicine updated successfully!", "success")
        return redirect(url_for("admin_medicines.list_medicines"))

    form_data = {
        "name": medicine.name,
        "category": medicine.category,
        "price": str(medicine.price),
        "stock": str(medicine.stock),
        "description": medicine.description or "",
        "image_url": medicine.image_url or "",
        "requires_prescription": medicine.requires_prescription,
    }
    return render_template("medicine_form.html", medicine=medicine, form_data=form_data)


@medicines_bp.route("/<int:medicine_id>/delete", methods=["POST"])
@admin_required
def delete_medicine(medicine_id):
    medicine = db.get_or_404(Medicine, medicine_id)
    if OrderItem.query.filter_by(medicine_id=medicine.id).first():
        flash("This medicine is in an existing order and cannot be deleted.", "warning")
        return redirect(url_for("admin_medicines.list_medicines"))

    if PrescriptionRequest.query.filter_by(medicine_id=medicine.id).first():
        flash("This medicine has prescription requests and cannot be deleted.", "warning")
        return redirect(url_for("admin_medicines.list_medicines"))


    try:
        db.session.delete(medicine)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Medicine could not be deleted.", "danger")
        return redirect(url_for("admin_medicines.list_medicines"))

    flash("Medicine deleted successfully!", "success")
    return redirect(url_for("admin_medicines.list_medicines"))


@medicines_bp.route("/restock", methods=["POST"])
@admin_required
def restock_selected():
    """Raise selected medicine stocks to TARGET, never reduce existing stock."""
    raw_ids = request.form.getlist("medicine_ids")
    if not raw_ids or len(raw_ids) > 200 or len(set(raw_ids)) != len(raw_ids):
        flash("Choose between 1 and 200 different medicines to restock.", "warning")
        return redirect(url_for("admin_medicines.list_medicines"))
    if any(not re.fullmatch(r"[1-9][0-9]*", x) or len(x) > 9 for x in raw_ids):
        flash("Invalid medicine selection.", "danger")
        return redirect(url_for("admin_medicines.list_medicines"))
    ids = [int(x) for x in raw_ids]
    existing = Medicine.query.filter(Medicine.id.in_(ids)).all()
    if len(existing) != len(ids):
        flash("A selected medicine no longer exists. Reload and retry.", "warning")
        return redirect(url_for("admin_medicines.list_medicines"))
    target = 100
    try:
        # One statement updates only records below target. High stock is never reduced.
        result = db.session.query(Medicine).filter(
            Medicine.id.in_(ids), Medicine.stock < target
        ).update({Medicine.stock: target}, synchronize_session=False)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Restocking failed. No inventory quantities were changed.", "danger")
        return redirect(url_for("admin_medicines.list_medicines"))
    flash(f"Restocked {result} medicine(s) to 100 units. {len(ids)-result} already had 100 or more.", "success")
    return redirect(url_for("admin_medicines.list_medicines"))
