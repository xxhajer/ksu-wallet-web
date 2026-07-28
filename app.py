import os
import re
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

import db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")

EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@student\.ksu\.edu\.sa$"
PHONE_REGEX = r"^05\d{8}$"

with app.app_context():
    db.init_db()


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))
            if role is not None and session.get("role") != role:
                flash("You don't have access to that page.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    fn = request.form.get("first_name", "").strip()
    ln = request.form.get("last_name", "").strip()
    sid = request.form.get("student_id", "").strip()
    pw = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    def error(msg):
        flash(msg, "error")
        return render_template(
            "signup.html",
            first_name=fn, last_name=ln, student_id=sid,
            email=email, phone=phone,
        )

    if fn == "" or " " in fn or not fn.isalpha():
        return error("First name must be one word, letters only.")
    if ln == "" or " " in ln or not ln.isalpha():
        return error("Last name must be one word, letters only.")
    if len(sid) != 10 or not sid.isdigit():
        return error("Student ID must be 10 digits.")
    if len(pw) < 6:
        return error("Password must be at least 6 characters.")
    if not re.match(EMAIL_REGEX, email):
        return error("Email must be: X@student.ksu.edu.sa")
    if not re.match(PHONE_REGEX, phone):
        return error("Phone must be: 05XXXXXXXX")

    ok, result = db.create_student(sid, fn, ln, email, phone, pw)
    if not ok:
        return error(result)

    flash(
        f"Account created! Wallet number: {result} - starting balance: 1000 SR. "
        f"You can log in now.",
        "success",
    )
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    user_id = request.form.get("user_id", "").strip()
    password = request.form.get("password", "").strip()

    role = db.login(user_id, password)
    if role is None:
        flash("Invalid ID or password.", "error")
        return render_template("login.html", user_id=user_id)

    session["user_id"] = user_id
    session["role"] = role

    if role == "student":
        return redirect(url_for("wallet"))
    return redirect(url_for("admin_panel"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/wallet")
@login_required(role="student")
def wallet():
    data = db.get_student_wallet(session["user_id"])
    if data is None:
        flash("Wallet not found.", "error")
        return redirect(url_for("logout"))
    wallet_number, balance = data
    return render_template(
        "wallet.html", wallet_number=wallet_number, balance=balance
    )


@app.route("/wallet/pay", methods=["POST"])
@login_required(role="student")
def wallet_pay():
    target = request.form.get("target", "").strip()
    amount_str = request.form.get("amount", "").strip()

    data = db.get_student_wallet(session["user_id"])
    if data is None:
        flash("Wallet not found.", "error")
        return redirect(url_for("logout"))
    my_wallet, _ = data

    if not target.isdigit() or len(target) != 10:
        flash("Target wallet must be 10 digits.", "error")
    elif target == my_wallet:
        flash("You cannot transfer to your own wallet.", "error")
    elif not amount_str.isdigit() or int(amount_str) <= 0:
        flash("Amount must be a whole number greater than 0.", "error")
    elif not db.wallet_exists(target):
        flash("Target wallet does not exist.", "error")
    else:
        amount = int(amount_str)
        current_balance = db.get_balance(my_wallet)
        if current_balance < amount:
            flash("There is not enough money.", "error")
        else:
            ok, message = db.pay(my_wallet, target, amount)
            flash(message, "success" if ok else "error")

    return redirect(url_for("wallet"))


@app.route("/admin")
@login_required(role="admin")
def admin_panel():
    entities = db.get_entities()
    return render_template("admin.html", entities=entities)


@app.route("/admin/add-entity", methods=["POST"])
@login_required(role="admin")
def admin_add_entity():
    name = request.form.get("name", "").strip()
    if name == "":
        flash("Please enter an entity name.", "error")
    else:
        ok, result = db.add_entity(name)
        if ok:
            flash(f"Entity added: {result['name']} (wallet {result['wallet']}).", "success")
        else:
            flash(result, "error")
    return redirect(url_for("admin_panel"))


@app.route("/admin/pay-stipends", methods=["POST"])
@login_required(role="admin")
def admin_pay_stipends():
    ok = db.pay_stipends()
    flash(
        "1000 SR deposited to all student wallets." if ok else "Could not complete the operation.",
        "success" if ok else "error",
    )
    return redirect(url_for("admin_panel"))


@app.route("/admin/cash-out", methods=["POST"])
@login_required(role="admin")
def admin_cash_out():
    ok = db.cash_out()
    flash(
        "All KSU entity balances set to 0." if ok else "Cash out failed.",
        "success" if ok else "error",
    )
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True)
