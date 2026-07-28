"""
Database layer for the KSU Wallet web app.

Uses Python's built-in sqlite3 module (no external DB dependency) with
raw SQL - this keeps the app easy to run anywhere, including free
hosting tiers that don't provide a managed database.
"""

import os
import sqlite3
import random
from datetime import datetime

from security import hash_password

DB_PATH = os.environ.get("KSU_WALLET_DB_PATH", "ksuwallet.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            wallet_number TEXT PRIMARY KEY,
            wallet_type TEXT NOT NULL,
            balance INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            wallet_number TEXT NOT NULL REFERENCES wallets(wallet_number)
        );

        CREATE TABLE IF NOT EXISTS admins (
            admin_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entities (
            entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            wallet_number TEXT NOT NULL REFERENCES wallets(wallet_number)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_wallet TEXT,
            to_wallet TEXT,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()

    existing_admin = conn.execute("SELECT 1 FROM admins LIMIT 1").fetchone()
    if existing_admin is None:
        # NOTE: demo/default account created only on first run so the app
        # is usable out of the box. The password is hashed before storage,
        # but you should still change it after logging in for the first
        # time on any real deployment.
        conn.execute(
            "INSERT INTO admins (admin_id, name, password_hash) VALUES (?, ?, ?)",
            ("1233211233", "Main Admin", hash_password("Admin123")),
        )
        conn.commit()

    conn.close()


def _generate_wallet_number(conn):
    while True:
        number = "".join(str(random.randint(0, 9)) for _ in range(10))
        exists = conn.execute(
            "SELECT 1 FROM wallets WHERE wallet_number = ?", (number,)
        ).fetchone()
        if exists is None:
            return number


def create_student(student_id, first_name, last_name, email, phone, password):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if existing is not None:
            return False, "Student already registered."

        wallet_number = _generate_wallet_number(conn)
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            "INSERT INTO wallets (wallet_number, wallet_type, balance, created_at) "
            "VALUES (?, 'student', 1000, ?)",
            (wallet_number, now),
        )
        conn.execute(
            "INSERT INTO students "
            "(student_id, first_name, last_name, email, phone, password_hash, wallet_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, first_name, last_name, email, phone,
             hash_password(password), wallet_number),
        )
        conn.commit()
        return True, wallet_number
    finally:
        conn.close()


def login(user_id, password):
    conn = get_db()
    try:
        student = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (user_id,)
        ).fetchone()
        if student is not None and verify_password_row(password, student["password_hash"]):
            return "student"

        admin = conn.execute(
            "SELECT * FROM admins WHERE admin_id = ?", (user_id,)
        ).fetchone()
        if admin is not None and verify_password_row(password, admin["password_hash"]):
            return "admin"

        return None
    finally:
        conn.close()


def verify_password_row(password, password_hash):
    from security import verify_password
    return verify_password(password, password_hash)


def get_student_wallet(student_id):
    conn = get_db()
    try:
        student = conn.execute(
            "SELECT * FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            return None
        wallet = conn.execute(
            "SELECT * FROM wallets WHERE wallet_number = ?",
            (student["wallet_number"],),
        ).fetchone()
        if not wallet:
            return None
        return wallet["wallet_number"], wallet["balance"]
    finally:
        conn.close()


def wallet_exists(wallet_number):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT 1 FROM wallets WHERE wallet_number = ?", (wallet_number,)
        ).fetchone() is not None
    finally:
        conn.close()


def get_balance(wallet_number):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT balance FROM wallets WHERE wallet_number = ?", (wallet_number,)
        ).fetchone()
        return row["balance"] if row else None
    finally:
        conn.close()


def pay(from_wallet_number, to_wallet_number, amount):
    conn = get_db()
    try:
        source = conn.execute(
            "SELECT * FROM wallets WHERE wallet_number = ?", (from_wallet_number,)
        ).fetchone()
        if source is None:
            return False, "Source wallet does not exist."

        target = conn.execute(
            "SELECT * FROM wallets WHERE wallet_number = ?", (to_wallet_number,)
        ).fetchone()
        if target is None:
            return False, "Target wallet does not exist."

        if source["balance"] < amount:
            return False, "Not enough balance."

        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE wallets SET balance = balance - ? WHERE wallet_number = ?",
            (amount, from_wallet_number),
        )
        conn.execute(
            "UPDATE wallets SET balance = balance + ? WHERE wallet_number = ?",
            (amount, to_wallet_number),
        )
        conn.execute(
            "INSERT INTO transactions (from_wallet, to_wallet, amount, created_at) "
            "VALUES (?, ?, ?, ?)",
            (from_wallet_number, to_wallet_number, amount, now),
        )
        conn.commit()
        return True, "Payment completed successfully."
    finally:
        conn.close()


def get_entities():
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT entity_id, name, wallet_number FROM entities ORDER BY entity_id"
        ).fetchall()
        result = []
        for row in rows:
            wallet = conn.execute(
                "SELECT balance FROM wallets WHERE wallet_number = ?",
                (row["wallet_number"],),
            ).fetchone()
            result.append({
                "entity_id": row["entity_id"],
                "name": row["name"],
                "balance": wallet["balance"] if wallet else None,
            })
        return result
    finally:
        conn.close()


def add_entity(entity_name):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT 1 FROM entities WHERE name = ?", (entity_name,)
        ).fetchone()
        if existing is not None:
            return False, "Entity already exists."

        wallet_number = _generate_wallet_number(conn)
        now = datetime.now().isoformat(timespec="seconds")

        conn.execute(
            "INSERT INTO wallets (wallet_number, wallet_type, balance, created_at) "
            "VALUES (?, 'ksu', 0, ?)",
            (wallet_number, now),
        )
        conn.execute(
            "INSERT INTO entities (name, wallet_number) VALUES (?, ?)",
            (entity_name, wallet_number),
        )
        conn.commit()
        return True, {
            "name": entity_name,
            "wallet": wallet_number,
            "type": "KSU",
            "created": now,
            "balance": 0,
        }
    finally:
        conn.close()


def pay_stipends():
    conn = get_db()
    try:
        wallets = conn.execute(
            "SELECT wallet_number FROM wallets WHERE wallet_type = 'student'"
        ).fetchall()
        now = datetime.now().isoformat(timespec="seconds")

        for wallet in wallets:
            conn.execute(
                "UPDATE wallets SET balance = balance + 1000 WHERE wallet_number = ?",
                (wallet["wallet_number"],),
            )
            conn.execute(
                "INSERT INTO transactions (from_wallet, to_wallet, amount, created_at) "
                "VALUES (NULL, ?, 1000, ?)",
                (wallet["wallet_number"], now),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"pay_stipends failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def cash_out():
    conn = get_db()
    try:
        wallets = conn.execute(
            "SELECT wallet_number, balance FROM wallets WHERE wallet_type = 'ksu'"
        ).fetchall()
        now = datetime.now().isoformat(timespec="seconds")

        for wallet in wallets:
            if wallet["balance"] > 0:
                conn.execute(
                    "INSERT INTO transactions (from_wallet, to_wallet, amount, created_at) "
                    "VALUES (?, NULL, ?, ?)",
                    (wallet["wallet_number"], wallet["balance"], now),
                )
            conn.execute(
                "UPDATE wallets SET balance = 0 WHERE wallet_number = ?",
                (wallet["wallet_number"],),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"cash_out failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
