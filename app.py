"""Application setup, routes, and sample data for Pharmacityville."""
import hmac
import os
import secrets
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, render_template, request, session
from flask_login import LoginManager

from admin import admin_bp
from admin_medicines import medicines_bp
from admin_orders import admin_orders_bp
from admin_users import admin_users_bp
from customer_orders import customer_bp
from payments import payments_bp
from prescriptions import prescriptions_bp
from auth import auth_bp, password_fingerprint
from password_reset import reset_bp
from support_tickets import support_bp, admin_support_bp
from inventory_insights import insights_bp  # pvc-feature-pack-20261011
from models import Medicine, User, db
from demo_catalog import full_demo_catalog

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
login_manager = LoginManager()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    secret_key = os.getenv("SECRET_KEY", "")
    if not secret_key or secret_key == "replace-this-with-a-random-secret-key":
        raise RuntimeError("Add a generated SECRET_KEY to the .env file.")

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///" + (Path(app.instance_path) / "pharmacityville.db").as_posix()
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("PUBLIC_BASE_URL", "").startswith("https://")
    # Limit multipart uploads including request overhead (file limit is 4 MB).
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Register each blueprint once. This fixes the Step 3 BuildError.
    app.register_blueprint(auth_bp)
    app.register_blueprint(reset_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(admin_support_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(medicines_bp)
    app.register_blueprint(insights_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(admin_orders_bp)
    app.register_blueprint(admin_users_bp)
    app.register_blueprint(prescriptions_bp)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            # Invalidate previous login sessions after a password change.
            if user and user.is_enabled and session.get("_password_fingerprint") == password_fingerprint(user):
                return user
            return None
        except (ValueError, TypeError):
            return None

    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(32)
        return session["_csrf_token"]

    @app.context_processor
    def expose_csrf_token():
        # Cart is stored in the signed session. Display only validated quantities.
        cart = session.get("cart", {})
        count = 0
        if isinstance(cart, dict):
            count = sum(value for value in list(cart.values())[:30]
                        if type(value) is int and 1 <= value <= 999)
        return {"csrf_token": csrf_token, "nav_cart_count": count}

    @app.before_request
    def protect_post_forms():
        # All POST forms must include a session CSRF token.
        if request.method == "POST" and request.endpoint != "payments.xendit_webhook":
            expected = session.get("_csrf_token", "")
            submitted = request.form.get("_csrf_token", "")
            if not expected or not hmac.compare_digest(expected, submitted):
                abort(400, description="Invalid form token. Refresh the page and try again.")

    @app.route("/help", methods=["GET"])
    def help_center():
        """Public, read-only guide and demo contact information."""
        return render_template("help.html")

    @app.route("/")
    def index():
        featured_medicines = Medicine.query.order_by(Medicine.name).limit(4).all()
        categories = [row[0] for row in db.session.query(Medicine.category)
                      .distinct().order_by(Medicine.category).all() if row[0]]
        homepage_stats = {
            "medicine_count": Medicine.query.count(),
            "category_count": len(categories),
            "prescription_count": Medicine.query.filter_by(requires_prescription=True).count(),
        }
        return render_template(
            "index.html", featured_medicines=featured_medicines,
            homepage_categories=categories[:6], homepage_stats=homepage_stats,
        )

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("error.html", heading="Bad request", message=error.description), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("error.html", heading="Access denied",
                               message="You do not have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", heading="Page not found",
                               message="That page does not exist."), 404

    return app


def seed_database(app):
    """Create missing tables and insert demo data without overwriting records."""
    with app.app_context():
        db.create_all()

        # Do not seed accounts with known passwords on a publicly hosted app.
        # Create or change an administrator with set_admin_login.py instead.

        # First-time installs receive 54 demo medicines and local images.
        # Existing databases are deliberately left unchanged here.
        if Medicine.query.count() == 0:
            for item in full_demo_catalog():
                db.session.add(Medicine(
                    name=item["name"],
                    category=item["category"],
                    price=Decimal(item["price"]),
                    stock=item["stock"],
                    description=item["description"],
                    requires_prescription=item["requires_prescription"],
                    image_url=item["image_url"],
                ))

        db.session.commit()


app = create_app()

if __name__ == "__main__":
    seed_database(app)
    app.run(debug=os.getenv("FLASK_DEBUG") == "1")
