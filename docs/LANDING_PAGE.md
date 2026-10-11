# Pharmacityville landing page redesign

This homepage redesign is **the safe version** of the October 2026 upgrade.
It does not replace the application with a historical `app.py` copy.

## Includes
- Responsive branded hero and direct medicine search
- Category shortcuts and live counts based on current medicine records
- Featured medicines with stock, price, prescription labels and images
- Customer and admin-specific quick links
- Demo opening-hours status explicitly labeled as sample data (Philippines time)
- Ordering explanation, FAQ accordion, and back-to-top button

## Deployment to PythonAnywhere

GitHub changes do not automatically update PythonAnywhere. Use the verified
`pharmacityville_landing_recovery_safe_fix.zip` installer on the **live** project.
The installer modifies only the `index()` handler in app.py and injects the
assets, rather than overwriting the entire application file. Run `--check`
before `--apply`, then reload the PythonAnywhere web app.

Do not run the original `pharmacityville_landing_page_upgrade.zip`; that older
installer overwrote `app.py` and could disable Forgot Password.

Hours and address information in the school demonstration are illustrative,
not verified store-opening information.