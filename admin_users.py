"""Admin-only account management; never expose these routes to customers."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth import admin_required
from models import Order, PrescriptionRequest, User, db
from support_tickets import SupportTicket

admin_users_bp = Blueprint("admin_users", __name__, url_prefix="/admin/users")
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+\Z")


def _user_details(form):
    """Validate editable user fields without losing non-password inputs."""
    values = {
        "name": form.get("name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "role": form.get("role", "customer").strip(),
    }
    errors = []
    if not values["name"] or len(values["name"]) > 100:
        errors.append("Full name is required (maximum 100 characters).")
    if len(values["email"]) > 120 or not EMAIL_PATTERN.fullmatch(values["email"]):
        errors.append("Enter a valid email address (maximum 120 characters).")
    if values["role"] not in ("customer", "admin"):
        errors.append("Choose Customer or Administrator as the role.")
    return values, errors


def _email_exists(email, except_id=None):
    query = User.query.filter(func.lower(User.email) == email)
    if except_id is not None:
        query = query.filter(User.id != except_id)
    return query.first() is not None


def _active_admin_count():
    return User.query.filter_by(role="admin", is_enabled=True).count()


@admin_users_bp.route("/", methods=["GET"])
@admin_required
def list_users():
    search = request.args.get("q", "").strip()[:120]
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()

    query = User.query
    if search:
        # Treat '%' and '_' as literal characters, not SQL wildcards.
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(or_(
            User.name.ilike(f"%{escaped}%", escape="\\"),
            User.email.ilike(f"%{escaped}%", escape="\\"),
        ))
    if role in ("admin", "customer"):
        query = query.filter(User.role == role)
    if status == "active":
        query = query.filter(User.is_enabled.is_(True))
    elif status == "disabled":
        query = query.filter(User.is_enabled.is_(False))

    users = query.order_by(User.role.asc(), User.name.asc(), User.id.asc()).all()
    # One membership lookup to avoid a query for every user row.
    users_with_orders = {row[0] for row in db.session.query(Order.user_id).distinct().all()}
    users_with_requests = {row[0] for row in db.session.query(PrescriptionRequest.user_id).distinct().all()}
    users_with_tickets = {row[0] for row in db.session.query(SupportTicket.user_id).distinct().all()}
    return render_template(
        "admin_users.html", users=users, search=search, role=role, status=status,
        users_with_history=users_with_orders | users_with_requests | users_with_tickets,
    )


@admin_users_bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_user():
    form_data = {"name": "", "email": "", "role": "customer"}
    if request.method == "POST":
        form_data, errors = _user_details(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 8 or len(password) > 128:
            errors.append("Password must be between 8 and 128 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if not errors and _email_exists(form_data["email"]):
            errors.append("That email is already used by another account.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("admin_user_form.html", user=None, form_data=form_data), 400

        user = User(**form_data, is_enabled=True)
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email is already in use.", "danger")
            return render_template("admin_user_form.html", user=None, form_data=form_data), 400
        except SQLAlchemyError:
            db.session.rollback()
            flash("Account could not be created. Try again.", "danger")
            return render_template("admin_user_form.html", user=None, form_data=form_data), 500
        flash("User account created successfully.", "success")
        return redirect(url_for("admin_users.list_users"))

    return render_template("admin_user_form.html", user=None, form_data=form_data)


@admin_users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    form_data = {"name": user.name, "email": user.email, "role": user.role}
    if request.method == "POST":
        form_data, errors = _user_details(request.form)
        if user.id == current_user.id and form_data["role"] != "admin":
            errors.append("You cannot remove your own administrator access.")
        if user.role == "admin" and form_data["role"] != "admin" and user.is_enabled and _active_admin_count() <= 1:
            errors.append("You cannot demote the last active administrator.")
        if not errors and _email_exists(form_data["email"], except_id=user.id):
            errors.append("That email is already used by another account.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("admin_user_form.html", user=user, form_data=form_data), 400

        user.name = form_data["name"]
        user.email = form_data["email"]
        user.role = form_data["role"]
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email is already in use.", "danger")
            return render_template("admin_user_form.html", user=user, form_data=form_data), 400
        except SQLAlchemyError:
            db.session.rollback()
            flash("Account changes could not be saved.", "danger")
            return render_template("admin_user_form.html", user=user, form_data=form_data), 500
        flash("User details updated successfully.", "success")
        return redirect(url_for("admin_users.list_users"))
    return render_template("admin_user_form.html", user=user, form_data=form_data)


@admin_users_bp.route("/<int:user_id>/reset-password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        new_password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        errors = []
        if len(new_password) < 8 or len(new_password) > 128:
            errors.append("Password must be between 8 and 128 characters.")
        if new_password != confirmation:
            errors.append("Passwords do not match.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("admin_user_password.html", user=user), 400
        user.set_password(new_password)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Password reset failed. Try again.", "danger")
            return render_template("admin_user_password.html", user=user), 500
        flash("Password updated successfully. Share it securely with the account owner.", "success")
        return redirect(url_for("admin_users.list_users"))
    return render_template("admin_user_password.html", user=user)


@admin_users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def toggle_status(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot disable your own account.", "warning")
        return redirect(url_for("admin_users.list_users"))
    if user.role == "admin" and user.is_enabled and _active_admin_count() <= 1:
        flash("The last active administrator cannot be disabled.", "warning")
        return redirect(url_for("admin_users.list_users"))
    user.is_enabled = not user.is_enabled
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Account status could not be updated.", "danger")
        return redirect(url_for("admin_users.list_users"))
    flash("Account enabled." if user.is_enabled else "Account disabled; login is blocked.", "success")
    return redirect(url_for("admin_users.list_users"))


@admin_users_bp.route("/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin_users.list_users"))
    if user.role == "admin":
        flash("Admin accounts cannot be permanently deleted here. Disable them instead.", "warning")
        return redirect(url_for("admin_users.list_users"))

    if (Order.query.filter_by(user_id=user.id).first()
            or PrescriptionRequest.query.filter_by(user_id=user.id).first()
            or SupportTicket.query.filter_by(user_id=user.id).first()):
        flash("This account has orders, prescriptions, or support reports. Disable it to preserve history.", "warning")
        return redirect(url_for("admin_users.list_users"))
    try:
        db.session.delete(user)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete this user; there may be related records.", "danger")
        return redirect(url_for("admin_users.list_users"))
    flash("User account deleted successfully.", "success")
    return redirect(url_for("admin_users.list_users"))
