import sqlite3
import os
import time
import random

DB_path = "db/models.db"


def init_models_db():
    os.makedirs(os.path.dirname(DB_path), exist_ok=True)
    conn = sqlite3.connect(DB_path)
    cur = conn.cursor()

    # Enable foreign keys (IMPORTANT in SQLite)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            fail_count INTEGER DEFAULT 0,
            time_added DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            fail_count INTEGER DEFAULT 0,
            time_added DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

#-- keylarni qo'shish qismi

def add_key(new_key):
    try:
        conn = sqlite3.connect(DB_path)
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO api_keys (api_key) VALUES (?)",
            (new_key,)
        )

        conn.commit()
        return "key_added"

    except sqlite3.IntegrityError:
        return "key_exists"

    finally:
        conn.close()


def count_key():
    conn = sqlite3.connect(DB_path)
    cur = conn.cursor()
    cur.execute("""
            SELECT COUNT(*) FROM api_keys WHERE status = 'active'
        """)
    count = cur.fetchone()[0]
    conn.close()
    return count


def show_keys():
    conn = sqlite3.connect(DB_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT api_key FROM api_keys WHERE status = 'active' ORDER BY id"
    )

    keys = [row[0] for row in cur.fetchall()]

    conn.close()
    return keys

# modellsarni qo'shish bilan ishlaydigan qismi


def add_model(new_model):
    try:
        conn = sqlite3.connect(DB_path)
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO models (model_name) VALUES (?)",
            (new_model,)
        )

        conn.commit()
        return "model_added"

    except sqlite3.IntegrityError:
        return "model_exists"

    finally:
        conn.close()


def count_model():
    conn = sqlite3.connect(DB_path)
    cur = conn.cursor()
    cur.execute("""
            SELECT COUNT(*) FROM models WHERE status = 'active'
        """)
    count = cur.fetchone()[0]
    conn.close()
    return count

def show_models():
    conn = sqlite3.connect(DB_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT model_name FROM models WHERE status = 'active' ORDER BY id"
    )

    models = [row[0] for row in cur.fetchall()]

    conn.close()
    return models



class APIKeyManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.current_index = 0

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_active_keys(self):
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT api_key FROM api_keys WHERE status = 'active' ORDER BY id"
        )
        keys = [row["api_key"] for row in cur.fetchall()]

        conn.close()
        return keys

    def get_next_key(self):
        # keys = self._get_active_keys()

        # if not keys:
        #     return None

        # key = keys[self.current_index % len(keys)]
        # self.current_index += 1
        # return key
        keys = self._get_active_keys()
        if not keys:
            return None
        return random.choice(keys)

    def remove_broken_key(self, key):
        conn = self._get_conn()
        cur = conn.cursor()

        # 1️⃣ Increase fail_count
        cur.execute("""
                UPDATE api_keys
                SET fail_count = fail_count + 1
                WHERE api_key = ?
            """, (key,))

        # 2️⃣ Get updated fail_count
        cur.execute("""
                SELECT fail_count FROM api_keys WHERE api_key = ?
            """, (key,))
        row = cur.fetchone()

        if not row:
            conn.close()
            return

        fail_count = row[0]

        # 3️⃣ If failed 3 times → deactivate
        if fail_count >= 3:
            cur.execute("""
                    UPDATE api_keys
                    SET status = 'inactive'
                    WHERE api_key = ?
                """, (key,))
            print(f"❌ Kalit o‘chirildi (inactive): {key}")
        else:
            print(f"⚠️ Kalit {key} failed {fail_count} times")

        # 4️⃣ Count remaining active keys
        cur.execute("""
                SELECT COUNT(*) FROM api_keys WHERE status = 'active'
            """)
        count = cur.fetchone()[0]

        conn.commit()
        conn.close()

        # 5️⃣ Alert if low keys
        if count < 5:
            self.alert_admin_key(count)

    def alert_admin_key(self, count):
        # Here you can send Telegram / email / log
        print(f"⚠️ DIQQAT! Atigi {count} ta faol kalit qoldi!")
        return "attention"




class ModelManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.current_index = 0

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_active_models(self):
        conn = self._get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT model_name
            FROM models
            WHERE status = 'active'
            ORDER BY id
        """)

        models = [row["model_name"] for row in cur.fetchall()]
        conn.close()
        return models

    def get_next_model(self):
        # models = self._get_active_models()

        # if not models:
        #     return None

        # model = models[self.current_index % len(models)]
        # self.current_index += 1
        # return model
        models = self._get_active_models()

        if not models:
            return None

        return random.choice(models)

    def remove_broken_model(self, model):
        """Increment fail count, remove only if >=3"""
        conn = self._get_conn()
        cur = conn.cursor()

        # Increase fail count
        cur.execute("""
                UPDATE models
                SET fail_count = fail_count + 1
                WHERE model_name = ?
            """, (model,))

        # Check current fail_count
        cur.execute("""
                SELECT fail_count FROM models WHERE model_name = ?
            """, (model,))
        fail_count = cur.fetchone()[0]

        if fail_count >= 3:
            # Mark as inactive
            cur.execute("""
                    UPDATE models
                    SET status = 'inactive'
                    WHERE model_name = ?
                """, (model,))
            print(f"❌ Model o‘chirildi (inactive): {model}")
        else:
            print(f"⚠️ Model {model} failed {fail_count} times")

        # Check how many active models left
        cur.execute("""SELECT COUNT(*) FROM models WHERE status = 'active'""")
        count = cur.fetchone()[0]

        conn.commit()
        conn.close()

        if count < 3:
            self.alert_admin_model(count)

    def alert_admin_model(self, count):
        # Telegram / log / email bo‘lishi mumkin
        return "attention"






# keys = [
#     "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",
#     "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",
#     "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",
#     "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",
#     "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",
#     "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",
#     "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",
#     "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",
#     "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",
#     "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"
# ]
#
# #this saves the models for the mexanizm
# models = ["openai/gpt-oss-20b:free",
#           "google/gemma-3-27b-it:free",
#           "google/gemma-3-12b-it:free",
#           "tngtech/deepseek-r1t2-chimera:free",
#            "deepseek/deepseek-r1-0528:free",
#            "tngtech/deepseek-r1t-chimera:free",
#            "stepfun/step-3.5-flash:free",
#            "arcee-ai/trinity-large-preview:free",
#            "liquid/lfm-2.5-1.2b-thinking:free",
#            "liquid/lfm-2.5-1.2b-instruct:free",
#            "nvidia/nemotron-3-nano-30b-a3b:free",
#            "qwen/qwen3-next-80b-a3b-instruct:free",
#            "qwen/qwen3-next-80b-a3b-instruct",
#            "mistralai/mistral-small-3.1-24b-instruct:free"
#         ]
#
#
# def add_keylarni(new_key):
#     init_models_db()
#     try:
#         with sqlite3.connect(DB_path) as conn:
#             cur = conn.cursor()
#             cur.execute(
#                 "INSERT INTO models (model_name) VALUES (?)",
#                 (new_key,)
#             )
#         return "key_added"
#
#     except sqlite3.IntegrityError:
#         return "key_exists"
#
# def give_item():
#     for key in models:
#         result = add_keylarni(key)
#         print(f"{key} → {result}")
#
# give_item()
#