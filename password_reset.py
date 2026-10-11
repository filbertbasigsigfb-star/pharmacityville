"""Email-based, time-limited password recovery for Pharmacityville.

Does not reveal whether an email is registered. A reset token is invalidated
when the user's password hash changes; no extra database table is needed.
"""
import os
import re
import threading
import time
from collections import defaultdict, deque
from urllib.parse import quote

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func

from auth import password_fingerprint
from models import User, db
from support_tickets import _send_notice

reset_bp = Blueprint("password_reset", __name__)
TOKEN_LIFETIME_SECONDS = 30 * 60
GENERIC_NOTICE = "If the email is registered and enabled, a password reset link will be sent shortly. Check your inbox and spam folder."

# Best-effort per-process protection. For a large multi-worker production site,
# use a shared backend (e.g. Redis) for global rate limiting.
_recent_attempts = defaultdict(deque)
_attempt_lock = threading.Lock()


def _allow_attempt(email, remote_ip):
    """Limit resets per email and IP to discourage automated email abuse."""
    now = time.monotonic()
    keys = (("ip", remote_ip, 8), ("email", email, 3))
    with _attempt_lock:
        # Remove expired entries and prune empty keys to bound cache growth.
        if len(_recent_attempts) > 3000:
            for old_key in list(_recent_attempts):
                q = _recent_attempts[old_key]
                while q and q[0] < now - 3600:
                    q.popleft()
                if not q:
                    del _recent_attempts[old_key]
        for kind, key, maximum in keys:
            queue = _recent_attempts.get((kind, key))
            if queue is None:
                continue
            while queue and queue[0] < now - 3600:
                queue.popleft()
            if len(queue) >= maximum or (kind == "email" and queue and now - queue[-1] < 90):
                return False
        for kind, key, maximum in keys:
            _recent_attempts[(kind, key)].append(now)
    return True


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pvc-password-reset-v1")


def _valid_user_for_token(token):
    if not token or len(token) > 600:
        return None
    try:
        payload = _serializer().loads(token, max_age=TOKEN_LIFETIME_SECONDS)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or type(payload.get("uid")) is not int or not isinstance(payload.get("ph"), str):
        return None
    user = db.session.get(User, payload["uid"])
    if not user or not user.is_enabled:
        return None
    from hmac import compare_digest
    return user if compare_digest(payload["ph"], password_fingerprint(user)) else None


def _get_public_base_url():
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if re.fullmatch(r"https://[^/?#\s]+", base):
        return base
    # Development-only convenience, never mail a link to a production HTTP host.
    if current_app.testing and re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?", base):
        return base
    return None


@reset_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        # Validate length before database lookup; response remains generic.
        email = request.form.get("email", "").strip().lower()
        if 0 < len(email) <= 120 and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            if _allow_attempt(email, request.remote_addr or "unknown"):
                user = User.query.filter(func.lower(User.email) == email).first()
                if user and user.is_enabled:
                    base = _get_public_base_url()
                    if base:
                        token = _serializer().dumps({"uid": user.id, "ph": password_fingerprint(user)})
                        url = base + url_for("password_reset.reset_password", token=quote(token, safe=""))
                        outcome = _send_notice(
                            user.email,
                            "Pharmacityville: Reset your password",
                            "A password reset was requested for your Pharmacityville account.\n\n"
                            "To choose a new password, open this link within 30 minutes:\n"
                            f"{url}\n\n"
                            "If you didn't request this, ignore this email. Your password has not changed.\n"
                            "Never share this link with anyone.\n",
                        )
                        if outcome != "sent":
                            current_app.logger.warning("Password reset email not sent (%s). Check SMTP settings.", outcome)
                    else:
                        current_app.logger.warning("Password reset email not sent: PUBLIC_BASE_URL must be set to your HTTPS website origin.")
        flash(GENERIC_NOTICE, "info")
        return redirect(url_for("password_reset.forgot_password"))
    return render_template("forgot_password.html")


@reset_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = _valid_user_for_token(token)
    if not user:
        flash("This reset link is invalid, expired, or already used. Request another link.", "warning")
        return redirect(url_for("password_reset.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        if not 8 <= len(password) <= 128:
            flash("Choose a password between 8 and 128 characters.", "danger")
        elif password != confirmation:
            flash("The passwords do not match.", "danger")
        else:
            user.set_password(password)
            db.session.commit()
            from flask_login import logout_user
            from flask import session
            logout_user()
            session.pop("_password_fingerprint", None)
            flash("Your password has been updated. Log in with your new password.", "success")
            return redirect(url_for("auth.login"))

    response = make_response(render_template("reset_password.html", token=token))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response