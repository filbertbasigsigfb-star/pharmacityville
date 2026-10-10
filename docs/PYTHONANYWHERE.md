# PythonAnywhere deployment checklist

See the main README for first-time installation commands.

- **Never upload your `.env` or SQLite database to a public GitHub repository.** Keep both private on PythonAnywhere.
- A GitHub clone is not the same as a backup of your live account data. Use a private offline backup of `instance/pharmacityville.db` and `instance/prescriptions/` before deployments.
- The demo catalog is seeded on a new database with `python app.py`, but this does not migrate existing columns. For older deployed databases review `migrate_cod.py`, `migrate_payment_tables.py`, `migrate_user_management.py`, and `migrate_support_tickets.py` before running them.
- Add `.env` manually in the server's private project folder using the example provided. Generate an independent secret; don't publish it.
- Configure a WSGI file that imports `from app import app as application` and ensure the virtual environment is selected.
- Map `/static/` to your project's `static/` directory and reload the Web app.
- Confirm `/medicines`, `/cart`, `/admin/`, `/admin/inventory-insights` and the actual payment methods you intend to enable.
- Use private test credentials for the payment gateway; do not enable live payment processing until webhook verification and reconciliation are validated end-to-end.
- Existing medicine records retain saved custom image URLs. If an image still shows a placeholder, check and update its URL in Edit Medicine to `/static/img/medicines/<file>` where the file exists.

**Note:** This source code was reconstructed from development artifacts. The live PythonAnywhere environment and production database were not inspected; inspect any differences before using this as a deployment replacement.
