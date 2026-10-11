# Pharmacityville

A Flask + SQLite school-project pharmacy web application, packaged as a **complete source-code repository** for local development or deployment to PythonAnywhere. This is a reconstructed development snapshot built from available project packages; it is **not a live export** of the currently running PythonAnywhere server or its private database.

## What is included

- **Customer:** landing page, sign-up and login, medicine catalog (54 sample products), search and filters, favorites, compare medicines, quick view, recently viewed, multi-select cart, floating Add to Cart actions, quantity controls, checkout and order tracking, prescription requests and report/support tickets.
- **Admin:** role-protected dashboard, medicine CRUD, low-stock filters and alerts, multi-select restock-to-100, inventory CSV, Inventory Insights and reorder CSV, order workflow and status filters, prescription reviews, account management, support inbox, image-preview and unsaved-form warnings.
- **Payments:** Cash on Delivery, Pay at Pickup and optional Xendit hosted checkout/webhooks. Xendit requires your **own environment variables**, verified callback settings, and testing. No API credentials are shipped.
- **Frontend:** Jinja2, Bootstrap 5 CDN, CSS/JS, product illustrations, some photorealistic **AI-generated demo mockups** (not authenticated branded product photographs).

### Stack

Python 3.12+ · Flask 3 · Flask-SQLAlchemy · Flask-Login · SQLite · Jinja2 · Bootstrap 5 · python-dotenv · requests.

## First-time setup (Windows PowerShell)

1. Install Python 3.12 or later and extract/clone this repository.
2. Open a terminal in the folder containing `app.py`.
3. Create and activate a virtual environment:

   ```powershell
   py -3.12 -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

4. Configure your local secret:

   ```powershell
   Copy-Item .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Open `.env` and replace `SECRET_KEY=replace-this-with-a-random-secret-key` with the generated secret. Never commit `.env`.

5. Create the SQLite database, seed **54 sample medicines**, and start the dev server:

   ```powershell
   python app.py
   ```

6. Open `http://127.0.0.1:5000`. **No preconfigured admin password is shipped.** In a second terminal, set up your own administrator:

   ```powershell
   python set_admin_login.py --email admin@yourdomain.example
   ```

   Enter a unique password at the private prompts. Customers can register using the site.

### macOS/Linux terminal

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_hex(32))'
# Add the generated SECRET_KEY to .env
python app.py
```

## Updating an **existing** PythonAnywhere deployment

**Do not unzip this repository over your live site without first backing it up and reviewing file changes.** Your running website may include fixes not reflected in this reconstruction. Do **not** overwrite the live `.env` or `instance/pharmacityville.db`, and preserve any uploaded prescriptions stored under `instance/prescriptions/`.

The new features in this repository are already integrated; you do not need to run the previous upgrade ZIP installers. On a **copy** of your deployment, check the existing schema and migrations; then test the site before switching the WSGI configuration.

For a fresh PythonAnywhere installation:

1. Upload/extract or clone the repository under `/home/YOUR_USERNAME/pharmacityville`.
2. Create a virtual environment and install `requirements.txt` with PythonAnywhere-supported Python.
3. Create a `.env` with a strong `SECRET_KEY`. Keep `PUBLIC_BASE_URL` unset for local HTTP or set it to your **own HTTPS domain** in production.
4. Run `python app.py` once (stop it after initial seed), or in a Bash console with activated venv run `python -c 'from app import app, seed_database; seed_database(app)'`.
5. In the PythonAnywhere Web tab, configure WSGI to import `application`: `from app import app as application` after adding the project directory to `sys.path`.
6. Configure the virtualenv path, static mapping `/static/` → `/home/YOUR_USERNAME/pharmacityville/static/`, then reload.
7. Create an admin using `python set_admin_login.py --email YOUR_PRIVATE_ADMIN_EMAIL` in the console.

### Existing demo records / database migration

- `python seed_demo_catalog.py --check` previews missing sample products; `--apply` **backs up the database and adds only missing entries**, never replacing existing products or images.
- If importing an older project database, review and run the relevant `migrate_*.py` scripts from a backup. `db.create_all()` creates tables, but **does not add new columns** to existing tables.
- The 40 demo-product image defaults are defined in `catalog_images.json`; new installations get the corrected Alcohol Prep Pads image at `/static/img/medicines/alcohol-prep-pads-real.webp`. Existing databases retain their stored image URL until edited or migrated.
- The new tablet display descriptions are `Per piece` for the applicable sample entries. Existing customized descriptions are not overwritten by `seed_demo_catalog.py`.

## Developer checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

These are basic static checks and **not** a substitute for browser, checkout, and payment-provider integration tests. The live server, payment credentials, actual database, and user uploads were not available to export.

## Security and responsible use

- Local-development demo; **not an approved live medicine-dispensing or patient-care system**. A real pharmacy requires regulatory review, verified prescriptions, qualified oversight, strong privacy protections and production security auditing.
- Keep `.env`, SQLite database files, customer/order data, private prescription uploads, SMTP passwords and Xendit API/webhook tokens **out of GitHub**.
- Generate unique admin credentials; disable Flask debug mode in production.
- Demo prices and availability are illustrative; some product images are synthetic mockups or generic representations, not specific commercial products.
- The homepage may contain placeholder business/contact content; review before publishing.

## Code layout

| Path | Purpose |
| --- | --- |
| `app.py`, `models.py`, `auth.py` | App, ORM and login |
| `admin*.py`, `inventory_insights.py` | Admin medicine, user, order, inventory workflows |
| `customer_orders.py`, `prescriptions.py`, `payments.py`, `support_tickets.py` | Customer checkout, approvals, gateway integrations and support |
| `medicine_data.py`, `more_medicines.py`, `demo_catalog.py`, `catalog_images.json` | 54 demonstration medicines and images |
| `templates/` | Jinja2 pages |
| `static/css/`, `static/js/`, `static/img/` | Frontend and medicine images |
| `migrate_*.py`, `seed_demo_catalog.py`, `set_admin_login.py` | Database and admin setup |
| `tests/` | Basic repository checks |
| `docs/` | Original feature and upgrade notes (some historical) |

## Publish to GitHub

From the repository folder (after checking there is no `.env` or private data):

```bash
git init
git add .
git commit -m "Initial Pharmacityville repository"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/pharmacityville.git
git push -u origin main
```

Create the empty GitHub repository in your account before pushing. This ZIP **does not automatically create or publish** a GitHub repository.


## Forgot password (email recovery)

The Login page includes a **Forgot password?** link at `/forgot-password`. A request
sends a 30-minute reset link to an enabled account's registered email. Resetting a
password invalidates earlier login sessions. The feature reuses the optional
`SUPPORT_SMTP_*` email settings and requires `PUBLIC_BASE_URL` to be set to the
site's HTTPS origin. See [docs/PASSWORD_RESET.md](docs/PASSWORD_RESET.md) for setup
and testing instructions. No database migration is needed.
