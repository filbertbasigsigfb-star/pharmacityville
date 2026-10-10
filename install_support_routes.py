"""Safely add support blueprints to the existing app.py without replacing it.

This matters because users may have custom edits to checkout/Xendit routes.
Run ONCE after copying the update; safe to run again.
"""
import ast
from datetime import datetime
from pathlib import Path
import shutil

APP = Path(__file__).resolve().parent / "app.py"
IMPORT = "from support_tickets import support_bp, admin_support_bp"
ROUTES = ("    app.register_blueprint(support_bp)", "    app.register_blueprint(admin_support_bp)")


def main():
    code = APP.read_text(encoding="utf-8")
    original = code
    if IMPORT not in code:
        candidates = ["from auth import auth_bp", "from prescriptions import prescriptions_bp"]
        anchor = next((item for item in candidates if item in code), None)
        if not anchor:
            raise SystemExit("Cannot find blueprint import anchor. app.py unchanged; ask for a manual patch.")
        code = code.replace(anchor, anchor + "\n" + IMPORT, 1)
    if any(route.strip() not in code for route in ROUTES):
        anchor = "    app.register_blueprint(auth_bp)"
        if anchor not in code:
            raise SystemExit("Cannot find blueprint registration anchor. app.py unchanged; ask for a manual patch.")
        new_lines = "\n".join(route for route in ROUTES if route.strip() not in code)
        code = code.replace(anchor, anchor + "\n" + new_lines, 1)
    # Never write invalid Python; write a backup first.
    ast.parse(code, filename=str(APP))
    if code == original:
        print("Support blueprint imports and registrations are already installed.")
        return
    backup = APP.with_name("app.py.before_support_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(APP, backup)
    APP.write_text(code, encoding="utf-8")
    print("Added support routes to app.py.")
    print("Backup saved:", backup.name)
    print("No payment, prescription, COD, or existing blueprint code was replaced.")


if __name__ == "__main__":
    main()
