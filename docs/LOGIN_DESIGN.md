# Pharmacityville login page design

The `/login` route uses a two-panel responsive layout with a welcome panel on desktop and a focused sign-in form on mobile. Shared site pages are unaffected.

## Features

- Show/hide password (keyboard and screen-reader accessible)
- Caps Lock hint when entering a password
- Optional "Remember my email on this device" preference, saved in browser `localStorage` only after explicit opt-in
- Trim surrounding email whitespace and preserve native HTML validation
- Loading/submission state and double-click protection
- Existing Forgot Password, customer registration, and Help & FAQ links

Only four web files change: `templates/login.html`, one small Jinja head-block in `templates/base.html`, `static/css/login_refresh.css`, and `static/js/login_refresh.js`.

## Security and privacy

The login POST and CSRF token are unchanged. The password is never saved to localStorage. Sign-in, sessions, enabled-user verification, and password-reset handling remain server-side. The remember-email preference is best avoided on shared computers. The script does not submit credentials to third-party services.

The Forgot Password feature (`password_reset.py` and registered `reset_bp`) must be installed before deploying this login template.

## Install on PythonAnywhere

Use `login_redesign/install_login_redesign.py --check` followed by `--apply` from the project root. The installer creates backups before modifying files and is safe to repeat. Reload the web app and hard-refresh `/login` after installing.