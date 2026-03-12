import sqlite3
import time
import os
import json

DB_PATH = "db/users.db"


def init_db():
    """Create the SQLite DB and required tables if they do not exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referat_left INTEGER DEFAULT 2,
            presentation_left INTEGER DEFAULT 2,
            Tezis_left INTEGER DEFAULT 2,
            Mustaqil_left INTEGER DEFAULT 2,
            balance INTEGER DEFAULT 0,
            referred INTEGER DEFAULT 0,
            files_generated INTEGER DEFAULT 0,
            last_used TEXT,
            is_onboarded BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id INTEGER,
            action TEXT,
            timestamps TEXT,  -- JSON array of timestamps
            PRIMARY KEY (user_id, action)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            date TEXT NOT NULL
        )
    """)

    # Migrate existing NULL balances to 0
    cur.execute("UPDATE users SET balance = 0 WHERE balance IS NULL")

    conn.commit()
    conn.close()


def ensure_user(user_id: int):
    """Ensure a user row exists in the DB; create it if missing."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR IGNORE INTO users (user_id)
        VALUES (?)
    """, (user_id,))

    conn.commit()
    conn.close()


def get_limits(user_id: int):
    """Return a tuple of available free attempts: (referat_left, presentation_left, ...)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT referat_left, presentation_left, Tezis_left, Mustaqil_left
        FROM users WHERE user_id = ?
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    return row or (0, 0)


def decrease_limit(user_id: int, content_type: str):
    """Decrease the corresponding free-attempt counter for user by one (if >0)."""
    limits = {
    "referat": "referat_left",
    "presentation": "presentation_left",
    "tezis": "Tezis_left",
    "mustaqil": "Mustaqil_left"
    }

    field = limits.get(content_type, 0)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(f"""
        UPDATE users
        SET {field} = {field} - 1
        WHERE user_id = ? AND {field} > 0
    """, (user_id,))

    conn.commit()
    conn.close()


def check_rate_limit(user_id: int, action: str, max_requests: int, window_seconds: int) -> bool:
    """
    Check if the user is within rate limits for a specific action.
    Returns True if allowed, False if rate limited.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT timestamps FROM rate_limits
        WHERE user_id = ? AND action = ?
    """, (user_id, action))

    row = cur.fetchone()
    now = time.time()

    if row:
        timestamps = json.loads(row[0])
    else:
        timestamps = []

    # Remove old timestamps outside the window
    timestamps = [t for t in timestamps if now - t < window_seconds]

    if len(timestamps) < max_requests:
        # Allow and record
        timestamps.append(now)
        cur.execute("""
            INSERT OR REPLACE INTO rate_limits (user_id, action, timestamps)
            VALUES (?, ?, ?)
        """, (user_id, action, json.dumps(timestamps)))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

def is_already_referred(user_id: int) -> bool:
    """Return True if the user has already been marked as referred."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT referred FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row and row[0] == 1


def mark_as_referred(user_id: int):
    """Mark the user as having been referred (set referred=1)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE users SET referred=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# def is_first_time_user(user_id: int) -> bool:
#     """
#     Check if the user exists in the database.
#     Returns True if first time, False otherwise.
#     """
#     conn = sqlite3.connect(DB_PATH)
#     cur = conn.cursor()
#     cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
#     result = cur.fetchone()
#     return result is None

# by chatgpt 
def is_first_time_user(user_id: int) -> bool:
    """Return True if the user has not completed onboarding (is_onboarded == 0) or is missing from DB."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT is_onboarded FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()

    # Fallback safety
    if row is None:
        return True

    return row[0] == 0

def mark_user_as_onboarded(user_id: int):
    """Set the is_onboarded flag for a user to True (1)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET is_onboarded = 1 WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

def user_exists(user_id: int) -> bool:
    """
    Check if a user exists in the database.
    Returns True if exists, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def parse_pages(text: str) -> int:
    """Parse string input for page count and validate range (2–20).

    Raises ValueError for invalid input.
    """
    text = text.strip()

    if not text.isdigit():
        raise ValueError("Not a valid integer")

    pages = int(text)

    if pages < 2 or pages > 20:
        raise ValueError("Out of allowed range")

    return pages
