"""Admin-only, read-only inventory insights for Pharmacityville.

Does not change stock or pricing. Suggested replenishment is a planning aid,
not a purchase order; inventory value uses retail list prices, not cost.
"""
import csv
import io
from decimal import Decimal

from flask import Blueprint, Response, render_template, request
from models import Medicine
from auth import admin_required

insights_bp = Blueprint("inventory_insights", __name__, url_prefix="/admin")
VALID_THRESHOLDS = (5, 10, 20, 30)
TARGET_STOCK = 100


def threshold_from_query():
    raw = request.args.get("threshold", "10")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 10
    return value if value in VALID_THRESHOLDS else 10


def get_snapshot(threshold):
    rows = Medicine.query.order_by(Medicine.stock.asc(), Medicine.name.asc()).all()
    low = [m for m in rows if m.stock <= threshold]
    out_count = sum(1 for m in rows if m.stock <= 0)
    low_count = sum(1 for m in rows if 0 < m.stock <= threshold)
    value = sum((Decimal(m.price or 0) * max(m.stock, 0) for m in rows), Decimal("0"))
    needed = sum(max(0, TARGET_STOCK - m.stock) for m in low)
    categories = {}
    for m in low:
        key = m.category or "Uncategorized"
        categories[key] = categories.get(key, 0) + 1
    category_rows = sorted(categories.items(), key=lambda row: (-row[1], row[0]))
    return rows, low, out_count, low_count, value, needed, category_rows


@insights_bp.get("/inventory-insights")
@admin_required
def inventory_insights():
    threshold = threshold_from_query()
    rows, low, out_count, low_count, value, needed, categories = get_snapshot(threshold)
    response = Response(render_template(
        "inventory_insights.html", medicines=low,
        total_count=len(rows), out_count=out_count, low_count=low_count,
        stock_units=sum(max(0, m.stock) for m in rows),
        inventory_value=value, suggested_units=needed,
        category_rows=categories[:8], threshold=threshold,
        valid_thresholds=VALID_THRESHOLDS, target_stock=TARGET_STOCK,
    ))
    response.headers["Cache-Control"] = "private, no-store"
    return response


def safe_csv_text(value):
    """Protect Excel/Sheets from formula evaluation of admin-supplied fields."""
    text = str(value or "")
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


@insights_bp.get("/inventory-insights/reorder.csv")
@admin_required
def reorder_csv():
    threshold = threshold_from_query()
    _, low, _, _, _, _, _ = get_snapshot(threshold)
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Medicine ID", "Medicine", "Category", "Current units",
                     "Suggested units to reach 100", "Retail price per unit PHP",
                     "Prescription required", "Planning threshold"])
    for m in low:
        writer.writerow([m.id, safe_csv_text(m.name), safe_csv_text(m.category), m.stock,
                         max(0, TARGET_STOCK - m.stock), format(m.price, ".2f"),
                         "Yes" if m.requires_prescription else "No", threshold])
    response = Response("\ufeff" + stream.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=pharmacityville_reorder_plan.csv"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
