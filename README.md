# KSU Wallet (web)

A simple campus wallet web app built with Flask and SQLite (no external
database service needed). Students sign up, get a starting balance, and
transfer money to each other; an admin panel manages KSU entities, pays
stipends to every student, and cashes out entity balances.

This is a browser-based rewrite of the original desktop (Tkinter) version -
same features and validation rules, just accessible from a link instead of
needing to be downloaded and run locally.

## Features

- Student sign-up with validated Saudi phone numbers, KSU student email
  addresses, and 10-digit student IDs.
- Student login and wallet-to-wallet money transfers, with balance checks
  before every transfer.
- Admin panel to add KSU entities, view entity balances, pay a stipend to
  every student wallet at once, and cash out all KSU entity balances.
- Every transfer, stipend payout, and cash-out is recorded in a
  `transactions` table for a full audit trail.
- Passwords are never stored in plain text - they are hashed with
  PBKDF2-HMAC-SHA256 and a random per-user salt before being saved.
- Role-based access: student pages and the admin panel are separated, and
  visiting either without logging in redirects to the login page.

## Running it locally

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5000`. The first run creates `ksuwallet.db`
(SQLite) in the project folder and seeds one default admin account so the
app is usable immediately:

- Admin ID: `1233211233`
- Password: `Admin123`

This is a demo account for local testing only - log in and change it (or
remove the seeding block in `db.py`) before letting anyone else use a real
deployment.

## Project structure

| File / folder | Purpose |
|---|---|
| `app.py` | Flask routes: signup, login, student wallet, admin panel. |
| `db.py` | SQLite data layer - schema, queries, business logic. |
| `security.py` | Password hashing/verification helpers. |
| `templates/` | Jinja2 HTML templates for every page. |
| `static/style.css` | Page styling. |

## Notes / known limitations

- Storage is a local SQLite file. On some free hosting tiers the
  filesystem resets on redeploy, so data isn't guaranteed to persist
  across deploys - this is a demo app, not built for production scale.
- There's no password-reset flow yet.
