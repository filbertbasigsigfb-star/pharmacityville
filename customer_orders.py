"""Customer catalog, session cart, checkout, and personal orders."""
import re
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, update
from sqlalchemy.exc import SQLAlchemyError

from models import Medicine, Order, OrderItem, PrescriptionRequest, PrescriptionUse, PaymentAttempt, db

customer_bp = Blueprint("customer", __name__)
MAX_CART_ITEMS = 30
MAX_QUANTITY = 999
MAX_ORDER_TOTAL = Decimal("99999999.99")


def parse_quantity(raw):
    """Accept only positive whole numbers within the cart limit."""
    raw = str(raw).strip()
    if not re.fullmatch(r"[0-9]+", raw) or len(raw) > 9:
        return None
    quantity = int(raw)
    return quantity if 1 <= quantity <= MAX_QUANTITY else None


def get_cart():
    """Return a clean {medicine_id: quantity} cart from the signed session."""
    stored = session.get("cart", {})
    if not isinstance(stored, dict):
        return {}
    cleaned = {}
    for key, value in list(stored.items())[:MAX_CART_ITEMS]:
        if not re.fullmatch(r"[1-9][0-9]*", str(key)):
            continue
        if type(value) is int and 1 <= value <= MAX_QUANTITY:
            cleaned[str(key)] = value
    return cleaned


def prescription_coverage(user_id, medicine_id):
    """Return remaining, unexpired approved quantity for this customer/medicine."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows = PrescriptionRequest.query.filter(
        PrescriptionRequest.user_id == user_id,
        PrescriptionRequest.medicine_id == medicine_id,
        PrescriptionRequest.status == "Approved",
        PrescriptionRequest.expires_at > now,
    ).order_by(PrescriptionRequest.id).all()
    return sum(max(0, r.quantity - r.used_quantity) for r in rows)


def cart_details():
    """Read current price/stock from the database, never from the browser."""
    cart = get_cart()
    ids = [int(key) for key in cart]
    medicines = {m.id: m for m in db.session.query(Medicine).filter(Medicine.id.in_(ids)).all()} if ids else {}
    lines = []
    total = Decimal("0.00")
    problems = []
    for key, quantity in cart.items():
        medicine = medicines.get(int(key))
        if medicine is None:
            problems.append("An item in your cart is no longer available. Remove it before checking out.")
            lines.append({"id": int(key), "medicine": None, "quantity": quantity, "subtotal": Decimal("0")})
            continue
        if medicine.stock < quantity:
            problems.append(f"Only {medicine.stock} of {medicine.name} remain; update your cart.")
        if medicine.requires_prescription:
            available = prescription_coverage(current_user.id, medicine.id)
            if quantity > available:
                problems.append(
                    f"{medicine.name} needs approved prescription coverage for {quantity} unit(s). "
                    f"Available approved quantity: {available}. Submit a request or reduce quantity."
                )
        subtotal = medicine.price * quantity
        total += subtotal
        lines.append({"id": medicine.id, "medicine": medicine, "quantity": quantity, "subtotal": subtotal})
    if total > MAX_ORDER_TOTAL:
        problems.append("Cart total is too high. Reduce quantities before checkout.")
    return lines, total, problems


@customer_bp.route("/medicines", methods=["GET"])
def catalog():
    """Public searchable medicine catalog."""
    search = request.args.get("search", "").strip()[:100]
    query = Medicine.query
    if search:
        query = query.filter(or_(Medicine.name.ilike(f"%{search}%"), Medicine.category.ilike(f"%{search}%")))
    selected_category = request.args.get("category", "").strip()[:100]
    if selected_category:
        query = query.filter(Medicine.category == selected_category)
    # Public sort choices are an explicit whitelist: no raw SQL from query parameters.
    sort = request.args.get("sort", "name")
    if sort not in {"name", "price_low", "price_high", "stock_high"}:
        sort = "name"
    available_only = request.args.get("available") == "1"
    if available_only:
        query = query.filter(Medicine.stock > 0)
    if sort == "price_low":
        query = query.order_by(Medicine.price.asc(), Medicine.name.asc())
    elif sort == "price_high":
        query = query.order_by(Medicine.price.desc(), Medicine.name.asc())
    elif sort == "stock_high":
        query = query.order_by(Medicine.stock.desc(), Medicine.name.asc())
    else:
        query = query.order_by(Medicine.name.asc())

    medicines = query.all()
    categories = [row[0] for row in db.session.query(Medicine.category)
                  .distinct().order_by(Medicine.category).all() if row[0]]
    return render_template(
        "catalog.html", medicines=medicines, search=search,
        categories=categories, selected_category=selected_category,
        selected_sort=sort, available_only=available_only,
    )



@customer_bp.route("/cart", methods=["GET"])
@login_required
def cart():
    lines, total, problems = cart_details()
    return render_template("cart.html", lines=lines, total=total, problems=problems)


@customer_bp.route("/cart/add/<int:medicine_id>", methods=["POST"])
@login_required
def add_to_cart(medicine_id):
    medicine = db.get_or_404(Medicine, medicine_id)
    quantity = parse_quantity(request.form.get("quantity", "1"))
    if quantity is None:
        flash("Enter a whole quantity between 1 and 999.", "danger")
        return redirect(url_for("customer.catalog"))

    cart = get_cart()
    key = str(medicine.id)
    if key not in cart and len(cart) >= MAX_CART_ITEMS:
        flash("Your cart can contain at most 30 different medicines.", "warning")
    elif medicine.stock <= 0 or cart.get(key, 0) + quantity > min(medicine.stock, MAX_QUANTITY):
        flash(f"Not enough stock for {medicine.name}. Available: {medicine.stock}.", "danger")
    else:
        cart[key] = cart.get(key, 0) + quantity
        session["cart"] = cart
        flash(f"Added {medicine.name} to your cart.", "success")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/add-selected", methods=["POST"])
@login_required
def add_selected_to_cart():
    """Add several selected medicines to the session cart in one request.

    Either every selection is valid and added, or the cart stays unchanged.
    App-level before_request verifies the CSRF token for POST forms.
    """
    selected = request.form.getlist("medicine_ids")
    if not selected:
        flash("Select at least one medicine before adding to your cart.", "warning")
        return redirect(url_for("customer.catalog"))

    # Check the number of selected items before hitting the database.
    if len(selected) > MAX_CART_ITEMS or len(set(selected)) != len(selected):
        flash("Select at most 30 different medicines.", "danger")
        return redirect(url_for("customer.catalog"))

    if any(not re.fullmatch(r"[1-9][0-9]*", value) or len(value) > 9
           for value in selected):
        abort(400, description="Invalid medicine selection.")

    ids = [int(value) for value in selected]
    medicines = {
        medicine.id: medicine
        for medicine in Medicine.query.filter(Medicine.id.in_(ids)).all()
    }
    cart = get_cart()
    updated_cart = cart.copy()

    if len(set(updated_cart) | set(selected)) > MAX_CART_ITEMS:
        flash("Your cart can hold at most 30 different medicines.", "danger")
        return redirect(url_for("customer.catalog"))

    # Server-side quantity and stock validation for EVERY selected medicine.
    for key in selected:
        medicine = medicines.get(int(key))
        if medicine is None:
            flash("A selected medicine is no longer available.", "danger")
            return redirect(url_for("customer.catalog"))

        quantity = parse_quantity(request.form.get(f"quantity_{key}", ""))
        if quantity is None:
            flash(f"Choose a valid quantity for {medicine.name}.", "danger")
            return redirect(url_for("customer.catalog"))

        new_quantity = updated_cart.get(key, 0) + quantity
        if medicine.stock <= 0 or new_quantity > min(medicine.stock, MAX_QUANTITY):
            flash(
                f"Not enough stock for {medicine.name}. "
                f"Available: {medicine.stock}; already in cart: {cart.get(key, 0)}.",
                "danger",
            )
            return redirect(url_for("customer.catalog"))
        updated_cart[key] = new_quantity

    # Commit to the signed session only once everything passes validation.
    session["cart"] = updated_cart
    flash(f"Added {len(selected)} different medicine(s) to your cart!", "success")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/update/<int:medicine_id>", methods=["POST"])
@login_required
def update_cart(medicine_id):
    cart = get_cart()
    key = str(medicine_id)
    if key not in cart:
        flash("That item is not in your cart.", "warning")
        return redirect(url_for("customer.cart"))
    quantity = parse_quantity(request.form.get("quantity", ""))
    if quantity is None:
        flash("Quantity must be a whole number from 1 to 999. Use Remove to delete an item.", "danger")
        return redirect(url_for("customer.cart"))
    medicine = db.session.get(Medicine, medicine_id)
    if medicine is None:
        flash("That medicine is no longer available. Please remove it.", "warning")
    elif quantity > medicine.stock:
        flash(f"Only {medicine.stock} units of {medicine.name} are available.", "danger")
    else:
        cart[key] = quantity
        session["cart"] = cart
        flash("Cart quantity updated.", "success")
    return redirect(url_for("customer.cart"))


@customer_bp.route("/cart/remove/<int:medicine_id>", methods=["POST"])
@login_required
def remove_from_cart(medicine_id):
    cart = get_cart()
    if cart.pop(str(medicine_id), None) is not None:
        session["cart"] = cart
        flash("Medicine removed from cart.", "success")
    else:
        flash("That item is not in your cart.", "warning")
    return redirect(url_for("customer.cart"))


def validate_delivery_details(form):
    """Validate recipient, Philippine mobile number, and address for delivery orders."""
    name = form.get("delivery_name", "").strip()
    phone = re.sub(r"[\s()-]", "", form.get("delivery_phone", "").strip())
    address = form.get("delivery_address", "").strip()
    if not 2 <= len(name) <= 100:
        raise ValueError("Please enter a delivery recipient name (2–100 characters).")
    if not re.fullmatch(r"(?:09[0-9]{9}|\+639[0-9]{9})", phone):
        raise ValueError("Enter a valid Philippine mobile number, such as 09XXXXXXXXX.")
    if not 10 <= len(address) <= 500:
        raise ValueError("Enter a complete delivery address (10–500 characters).")
    return {"delivery_name": name, "delivery_phone": phone, "delivery_address": address}


def create_order_from_cart(lines, order_status="Pending", payment_data=None, offline_data=None, delivery_data=None):
    """Reserve stock, consume approved Rx units, and create an order atomically."""
    try:
        # Online orders are paid through Xendit; offline orders must be explicitly
        # pickup or COD. We never trust price, stock or payment status from a form.
        method = "online" if payment_data else (offline_data or {}).get("payment_method", "pickup")
        if method not in {"online", "pickup", "cod"}:
            raise ValueError("Invalid payment method.")
        # Existing Order columns hold delivery contact details for COD and online orders.
        details = (delivery_data or {}) if method == "online" else ((offline_data or {}) if method == "cod" else {})
        if method in {"online", "cod"}:
            details = validate_delivery_details(details)
        order = Order(
            user_id=current_user.id, status=order_status,
            total=Decimal("0.00"), payment_method=method,
            delivery_name=details.get("delivery_name"),
            delivery_phone=details.get("delivery_phone"),
            delivery_address=details.get("delivery_address"),
        )
        db.session.add(order)
        db.session.flush()  # Assign order.id without committing yet.
        actual_total = Decimal("0.00")

        for line in lines:
            medicine = line["medicine"]
            quantity = line["quantity"]
            # Atomically consume only the customer's still-valid prescription coverage.
            if medicine.requires_prescription:
                remaining = quantity
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                approvals = PrescriptionRequest.query.filter(
                    PrescriptionRequest.user_id == current_user.id,
                    PrescriptionRequest.medicine_id == medicine.id,
                    PrescriptionRequest.status == "Approved",
                    PrescriptionRequest.expires_at > now,
                ).order_by(PrescriptionRequest.id).all()
                for approval in approvals:
                    capacity = max(0, approval.quantity - approval.used_quantity)
                    to_use = min(remaining, capacity)
                    if not to_use:
                        continue
                    consumed = db.session.execute(update(PrescriptionRequest).where(
                        PrescriptionRequest.id == approval.id,
                        PrescriptionRequest.status == "Approved",
                        PrescriptionRequest.expires_at > now,
                        PrescriptionRequest.used_quantity + to_use <= PrescriptionRequest.quantity,
                    ).values(used_quantity=PrescriptionRequest.used_quantity + to_use))
                    if consumed.rowcount != 1:
                        raise ValueError("Prescription coverage changed. Please retry checkout.")
                    db.session.add(PrescriptionUse(
                        order_id=order.id, prescription_id=approval.id, quantity=to_use))
                    remaining -= to_use
                    if remaining == 0:
                        break
                if remaining:
                    raise ValueError(f"Not enough approved prescription quantity for {medicine.name}.")

            # Atomic conditional UPDATE prevents purchasing more than live stock.
            result = db.session.execute(
                update(Medicine)
                .where(Medicine.id == medicine.id, Medicine.stock >= quantity)
                .values(stock=Medicine.stock - quantity)
            )
            if result.rowcount != 1:
                raise ValueError(f"Stock changed for {medicine.name}. Review your cart and retry.")

            # Use current DB prices and store a unit-price snapshot.
            actual_total += medicine.price * quantity
            db.session.add(OrderItem(
                order_id=order.id, medicine_id=medicine.id,
                quantity=quantity, unit_price=medicine.price,
            ))

        if actual_total > MAX_ORDER_TOTAL:
            raise ValueError("Cart total exceeds the maximum allowed order total.")
        order.total = actual_total
        if payment_data:
            db.session.add(PaymentAttempt(
                order_id=order.id, reference_id=payment_data["reference_id"],
                provider_session_id=payment_data["provider_session_id"],
                method=payment_data["method"], state="Pending",
                amount=actual_total, checkout_url=payment_data["checkout_url"],
            ))
        db.session.commit()
        return order
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        raise



@customer_bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    lines, total, problems = cart_details()
    if not lines:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("customer.catalog"))
    if request.method == "GET":
        from payments import gateway_ready
        return render_template("checkout.html", lines=lines, total=total, problems=problems,
                               online_payment_ready=gateway_ready())
    if problems:
        for problem in problems:
            flash(problem, "danger")
        return redirect(url_for("customer.cart"))
    # Only explicit offline methods may be placed here. The Xendit flow
    # uses its own /payments/start route and never accepts these fields.
    method = request.form.get("payment_method", "")
    if method not in {"pickup", "cod"}:
        flash("Choose Pay at Pickup or Cash on Delivery.", "danger")
        return redirect(url_for("customer.checkout"))

    offline_data = {"payment_method": method}
    if method == "cod":
        try:
            offline_data.update(validate_delivery_details(request.form))
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("customer.checkout"))

    try:
        order = create_order_from_cart(lines, "Pending", offline_data=offline_data)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("customer.cart"))
    except SQLAlchemyError:
        flash("Checkout could not be completed. Please retry.", "danger")
        return redirect(url_for("customer.cart"))
    session.pop("cart", None)
    if method == "cod":
        flash(f"Order #{order.id} placed for cash on delivery. No payment has been collected. The pharmacy will confirm delivery arrangements.", "success")
    else:
        flash(f"Order #{order.id} placed. Pay at pickup; no payment was collected online.", "success")
    return redirect(url_for("customer.order_detail", order_id=order.id))


@customer_bp.route("/orders", methods=["GET"])
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(
        Order.created_at.desc(), Order.id.desc()
    ).all()
    return render_template("my_orders.html", orders=orders)


@customer_bp.route("/orders/<int:order_id>", methods=["GET"])
@login_required
def order_detail(order_id):
    order = db.get_or_404(Order, order_id)
    if order.user_id != current_user.id:
        abort(403)
    return render_template("order_detail.html", order=order)


@customer_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def cancel_order(order_id):
    order = db.get_or_404(Order, order_id)
    if order.user_id != current_user.id:
        abort(403)

    attempt = order.payment_attempt
    if attempt and attempt.state == "Paid":
        flash("This payment was received. Contact the pharmacy about refunds or cancellation.", "warning")
        return redirect(url_for("customer.order_detail", order_id=order_id))

    if attempt and order.status == "Awaiting Payment":
        # Cancel the provider checkout BEFORE releasing stock (prevents late charges).
        from payments import cancel_provider_session
        if not cancel_provider_session(attempt.provider_session_id):
            flash("Cannot safely cancel this payment yet. Check payment status or contact the pharmacy.", "danger")
            return redirect(url_for("customer.order_detail", order_id=order_id))
        attempt.state = "Cancelled"

    try:
        # Only one concurrent cancellation can change the order status.
        result = db.session.execute(
            update(Order).where(Order.id == order_id, Order.user_id == current_user.id,
                                Order.status.in_(["Pending", "Awaiting Payment"])).values(status="Cancelled")
        )
        if result.rowcount != 1:
            db.session.rollback()
            flash("Only unpaid orders awaiting payment or pending orders can be cancelled.", "warning")
            return redirect(url_for("customer.order_detail", order_id=order_id))
        for item in order.items:
            db.session.execute(
                update(Medicine).where(Medicine.id == item.medicine_id)
                .values(stock=Medicine.stock + item.quantity)
            )
        # Release any prescription authorization used by this cancelled order.
        for usage in PrescriptionUse.query.filter_by(order_id=order_id).all():
            released = db.session.execute(update(PrescriptionRequest).where(
                PrescriptionRequest.id == usage.prescription_id,
                PrescriptionRequest.used_quantity >= usage.quantity,
            ).values(used_quantity=PrescriptionRequest.used_quantity - usage.quantity))
            if released.rowcount != 1:
                raise ValueError("Unable to release prescription allocation.")
        db.session.commit()
    except (SQLAlchemyError, ValueError):
        db.session.rollback()
        flash("Unable to cancel the order. Try again.", "danger")
        return redirect(url_for("customer.order_detail", order_id=order_id))

    flash(f"Order #{order_id} cancelled; stock restored.", "success")
    return redirect(url_for("customer.order_detail", order_id=order_id))