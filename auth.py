"""Registration, login, logout, and admin authorization."""
import re
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import User, db


auth_bp = Blueprint("auth", __name__)


def admin_required(view):
    """Allow administrators only; redirect guests to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        if current_user.role != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form_data = {"name": "", "email": ""}
    if request.method == "POST":
        form_data["name"] = request.form.get("name", "").strip()
        form_data["email"] = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")

        errors = []
        if not form_data["name"]:
            errors.append("Please enter your name.")
        elif len(form_data["name"]) > 100:
            errors.append("Name must be at most 100 characters.")

        if (len(form_data["email"]) > 120 or
                not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", form_data["email"])):
            errors.append("Please enter a valid email address.")

        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirmation:
            errors.append("Passwords do not match.")

        if not errors and User.query.filter(
            func.lower(User.email) == form_data["email"]
        ).first():
            errors.append("That email is already registered.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", form_data=form_data), 400

        user = User(name=form_data["name"], email=form_data["email"], role="customer")
        user.set_password(password)
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("That email is already registered.", "danger")
            return render_template("register.html", form_data=form_data), 400

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", form_data=form_data)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard") if current_user.role == "admin" else url_for("index"))

    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.email) == email).first()

        if user and user.is_enabled and user.check_password(password):
            login_user(user)
            flash(f"Welcome, {user.name}!", "success")
            return redirect(url_for("admin.dashboard") if user.role == "admin" else url_for("index"))

        flash("Incorrect email or password.", "danger")

    return render_template("login.html", email=email)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out.", "info")
    return redirect(url_for("index"))
