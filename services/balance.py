import sqlite3
from datetime import datetime

DB_PATH = "db/users.db"

def get_balance(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()

    conn.close()

    return row[0] if row and row[0] is not None else 0


def deduct_balance(user_id: int, amount: int) -> bool:
    """
    Deducts amount from balance.
    Returns True if deduction was successful.
    Returns False if balance is insufficient.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET balance = balance - ?
        WHERE user_id = ? AND balance >= ?
        """,
        (amount, user_id, amount)
    )

    success = cur.rowcount > 0

    conn.commit()
    conn.close()

    return success

def add_balance(user_id: int, amount: int):
    """Add amount to user's balance and record the payment in the payments table."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1️⃣ Add to user balance
    cur.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )

    # 2️⃣ Record the payment
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO payments (user_id, amount, date) VALUES (?, ?, ?)",
        (user_id, amount, today)
    )

    conn.commit()
    conn.close()

