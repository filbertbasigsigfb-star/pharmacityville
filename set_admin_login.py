"""Change the admin's email and password using a private terminal prompt.

    python set_admin_login.py
    python set_admin_login.py --admin-id 1

NEVER hard-code the administrator password in this script or .env.
"""
import argparse
from getpass import getpass

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import app
from models import User, db

DEFAULT_NEW_EMAIL = "admin@example.com"


def main():
    parser = argparse.ArgumentParser(description="Safely set the Pharmacityville admin login")
    parser.add_argument("--admin-id", type=int, help="Specific administrator ID if multiple admins exist")
    parser.add_argument("--email", default=DEFAULT_NEW_EMAIL, help="Desired administrator login email")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if len(email) > 120 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        parser.error("Please enter a valid admin email.")

    with app.app_context():
        admins = User.query.filter_by(role="admin").order_by(User.id).all()
        if args.admin_id:
            admin = db.session.get(User, args.admin_id)
            if not admin or admin.role != "admin":
                parser.error("That ID is not an administrator account.")
        else:
            admin = next((u for u in admins if u.email.lower() == email), None)
            if admin is None:
                admin = next((u for u in admins if u.email.lower() == "admin@pharmacityville.com"), None)
            if admin is None and len(admins) == 1:
                admin = admins[0]
            if admin is None and len(admins) > 1:
                print("More than one administrator exists. Choose a target:")
                for u in admins:
                    print(f"  ID {u.id}: {u.name} <{u.email}>")
                parser.error("Rerun with --admin-id ID")

        collision = User.query.filter(func.lower(User.email) == email).first()
        if collision and (admin is None or collision.id != admin.id):
            parser.error("That email is already assigned to a different user account.")

        if admin:
            print(f"Updating administrator ID {admin.id} (currently {admin.email})")
        else:
            print("No admin exists. A new administrator will be created.")
        print(f"New email: {email}")
        password = getpass("New administrator password (hidden): ")
        confirm = getpass("Repeat password (hidden): ")
        if password != confirm:
            parser.error("Passwords did not match. No changes were made.")
        if len(password) < 8 or len(password) > 128:
            parser.error("Password must be between 8 and 128 characters.")
        if admin is None:
            admin = User(name="Pharmacy Admin", role="admin")
            db.session.add(admin)
        admin.email = email
        admin.is_enabled = True
        admin.set_password(password)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            parser.error("The email is already in use. No changes were saved.")
        print("Administrator login updated successfully.")
        print("Sign in with the new email and the password you just entered.")


if __name__ == "__main__":
    main()
