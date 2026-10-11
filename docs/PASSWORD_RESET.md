# Password recovery — Pharmacityville

The login page has a **Forgot password?** link. Users enter their registered
email, receive a one-time-use reset link, and choose a new password. Reset links
expire **30 minutes** after issuance. Their signatures are tied to the user's
current password hash, making them unusable after a successful reset. Previous
login sessions become invalid after changing the password; the first deployment
of this feature also signs out current sessions.

## PythonAnywhere `.env` settings

Configure these in your server's **private** `.env`, never in GitHub:

```dotenv
PUBLIC_BASE_URL=https://jakesawada.pythonanywhere.com
SUPPORT_SMTP_HOST=smtp.gmail.com
SUPPORT_SMTP_PORT=587
SUPPORT_SMTP_USERNAME=your-sending-address@gmail.com
SUPPORT_SMTP_PASSWORD=your-gmail-app-password
SUPPORT_SMTP_FROM=your-sending-address@gmail.com
```

The reset feature reuses the same SMTP configuration as support emails. You
need a working sender account and, for Gmail, a Google App Password with
2-Step Verification; do **not** use your normal Gmail password. SMTP access on
some PythonAnywhere plans or to certain SMTP hosts can be restricted. If email
delivery fails, view PythonAnywhere **Web → Error log** for a warning about
password reset email delivery, and verify outbound SMTP access.

## Deploy the update

Use the standalone hotfix ZIP installer if updating an existing live project,
not an entire project overwrite. Backup existing files first; the installer
saves copies of changed application files. Existing orders, inventory and
payment integration are unaffected. Reload the Web application.

## Testing

1. Go to `/login`, click **Forgot password?** and submit an account whose
   inbox you control.
2. Check the inbox and spam folder for a reset link. The page shows the same
   generic response whether an email is registered or not.
3. Follow the link, choose a new password (8–128 characters), and log in.
4. A reused, invalid or expired link must return to the request form.
5. Retry with an unknown email address and confirm no account information is revealed.

Safety notes: all forms use the site's existing CSRF guard. Tokens are signed,
expire in 30 minutes and are invalidated by password changes. The endpoint
has basic in-process throttling (3 attempts/email/hour, 8 attempts/IP/hour,
90-second email cooldown). Multi-process deployments need a shared rate-limit
store such as Redis for stronger abuse prevention. The reset screen sends
no-store and no-referrer headers to protect token URLs.