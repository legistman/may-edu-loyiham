import sqlite3, os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "bot_data.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT    DEFAULT '',
            first_name    TEXT    DEFAULT '',
            full_name     TEXT    DEFAULT '',
            status        TEXT    DEFAULT 'new',
            premium_until TEXT    DEFAULT NULL,
            joined_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pdf_tests (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL,
            file_id        TEXT NOT NULL,
            question_count INTEGER DEFAULT 30,
            answer_key     TEXT NOT NULL,
            is_free        INTEGER DEFAULT 0,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pdf_results (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER, test_id INTEGER,
            correct   INTEGER, total   INTEGER,
            answers   TEXT,
            taken_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS guides (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            content    TEXT NOT NULL,
            is_free    INTEGER DEFAULT 1,
            file_id    TEXT    DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS payment_requests (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            status     TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL)""")
        # Default sozlamalar
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('premium_price','349 000')")
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('premium_days','30')")
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('card_number','9860 3501 4876 2387')")
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('card_owner','Mallayev Ozodbek')")
        # Eski bazaga yangi ustunlar
        for col in [("full_name","TEXT DEFAULT ''"),("is_free","INTEGER DEFAULT 1")]:
            for tbl in [("users", col[0]), ("guides", "is_free")]:
                try: c.execute(f"ALTER TABLE {tbl[0]} ADD COLUMN {col[0]} {col[1]}")
                except: pass
        try: c.execute("ALTER TABLE guides ADD COLUMN is_free INTEGER DEFAULT 1")
        except: pass
        try: c.execute("ALTER TABLE guides ADD COLUMN file_id TEXT DEFAULT ''")
        except: pass
        self.conn.commit()

    # ── SETTINGS ──────────────────────────────────────────────────────────────
    def get_setting(self, key):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        self.conn.commit()

    # ── USERS ─────────────────────────────────────────────────────────────────
    def add_user(self, user_id, username, first_name, full_name=""):
        ex = self.get_user(user_id)
        if ex:
            if full_name:
                self.conn.execute("UPDATE users SET username=?,first_name=?,full_name=? WHERE user_id=?",
                                  (username, first_name, full_name, user_id))
                self.conn.commit()
        else:
            self.conn.execute("INSERT INTO users (user_id,username,first_name,full_name) VALUES (?,?,?,?)",
                              (user_id, username, first_name, full_name))
            self.conn.commit()

    def get_user(self, user_id):
        r = self.conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(r) if r else None

    def get_user_status(self, user_id):
        r = self.conn.execute("SELECT status FROM users WHERE user_id=?", (user_id,)).fetchone()
        return r["status"] if r else "new"

    def set_user_status(self, user_id, status):
        self.conn.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        self.conn.commit()

    def get_all_users(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()]

    def get_users_by_status(self, status=None):
        if status:
            rows = self.conn.execute("SELECT * FROM users WHERE status=? ORDER BY joined_at DESC", (status,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_premium(self, user_id, expiry: datetime):
        self.conn.execute("UPDATE users SET status='premium',premium_until=? WHERE user_id=?",
                          (expiry.isoformat(), user_id))
        self.conn.commit()

    def remove_premium(self, user_id):
        self.conn.execute("UPDATE users SET status='approved',premium_until=NULL WHERE user_id=?", (user_id,))
        self.conn.commit()

    def get_premium_expiry(self, user_id):
        r = self.conn.execute("SELECT premium_until FROM users WHERE user_id=?", (user_id,)).fetchone()
        if r and r["premium_until"]:
            try: return datetime.fromisoformat(r["premium_until"])
            except: return None
        return None

    # ── PDF TESTS ─────────────────────────────────────────────────────────────
    def add_pdf_test(self, title, file_id, question_count, answer_key, is_free=0):
        self.conn.execute("INSERT INTO pdf_tests (title,file_id,question_count,answer_key,is_free) VALUES (?,?,?,?,?)",
                          (title, file_id, question_count, answer_key, is_free))
        self.conn.commit()

    def get_all_pdf_tests(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM pdf_tests ORDER BY created_at DESC").fetchall()]

    def get_free_pdf_tests(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM pdf_tests WHERE is_free=1 ORDER BY created_at DESC").fetchall()]

    def get_pdf_test(self, test_id):
        r = self.conn.execute("SELECT * FROM pdf_tests WHERE id=?", (test_id,)).fetchone()
        return dict(r) if r else None

    def update_pdf_test(self, test_id, title=None, answer_key=None, is_free=None):
        test = self.get_pdf_test(test_id)
        if not test: return
        t = title if title is not None else test["title"]
        k = answer_key if answer_key is not None else test["answer_key"]
        f = is_free if is_free is not None else test["is_free"]
        self.conn.execute("UPDATE pdf_tests SET title=?,answer_key=?,is_free=? WHERE id=?", (t, k, f, test_id))
        self.conn.commit()

    def delete_pdf_test(self, test_id):
        self.conn.execute("DELETE FROM pdf_tests WHERE id=?", (test_id,))
        self.conn.commit()

    def get_answer_key(self, test_id):
        r = self.conn.execute("SELECT answer_key FROM pdf_tests WHERE id=?", (test_id,)).fetchone()
        return r["answer_key"] if r else None

    # ── RESULTS ───────────────────────────────────────────────────────────────
    def save_pdf_result(self, user_id, test_id, correct, total, answers):
        self.conn.execute("INSERT INTO pdf_results (user_id,test_id,correct,total,answers) VALUES (?,?,?,?,?)",
                          (user_id, test_id, correct, total, answers))
        self.conn.commit()

    def get_user_pdf_results(self, user_id):
        rows = self.conn.execute("""
            SELECT r.correct,r.total,r.answers,r.taken_at,t.title as test_title,t.answer_key
            FROM pdf_results r JOIN pdf_tests t ON r.test_id=t.id
            WHERE r.user_id=? ORDER BY r.taken_at DESC""", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_test_rating(self, test_id):
        rows = self.conn.execute("""
            SELECT r.user_id, MAX(r.correct) as correct, r.total,
                   u.first_name, u.full_name, u.username
            FROM pdf_results r JOIN users u ON r.user_id=u.user_id
            WHERE r.test_id=? GROUP BY r.user_id ORDER BY correct DESC""", (test_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_overall_rating(self):
        rows = self.conn.execute("""
            SELECT r.user_id, r.correct, r.total, t.title as test_title,
                   u.first_name, u.full_name
            FROM pdf_results r
            JOIN users u ON r.user_id=u.user_id
            JOIN pdf_tests t ON r.test_id=t.id
            WHERE r.correct=(SELECT MAX(r2.correct) FROM pdf_results r2 WHERE r2.user_id=r.user_id)
            GROUP BY r.user_id ORDER BY r.correct DESC""").fetchall()
        return [dict(r) for r in rows]

    # ── GUIDES ────────────────────────────────────────────────────────────────
    def add_guide(self, title, content, is_free=1, file_id=""):
        self.conn.execute("INSERT INTO guides (title,content,is_free,file_id) VALUES (?,?,?,?)", (title, content, is_free, file_id))
        self.conn.commit()

    def get_all_guides(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM guides ORDER BY created_at DESC").fetchall()]

    def get_free_guides(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM guides WHERE is_free=1 ORDER BY created_at DESC").fetchall()]

    def get_guide(self, guide_id):
        r = self.conn.execute("SELECT * FROM guides WHERE id=?", (guide_id,)).fetchone()
        return dict(r) if r else None

    def update_guide(self, guide_id, title=None, content=None, is_free=None, file_id=None):
        g = self.get_guide(guide_id)
        if not g: return
        t  = title   if title   is not None else g["title"]
        c  = content if content is not None else g["content"]
        f  = is_free if is_free is not None else g["is_free"]
        fi = file_id if file_id is not None else g.get("file_id","")
        self.conn.execute("UPDATE guides SET title=?,content=?,is_free=?,file_id=? WHERE id=?", (t, c, f, fi, guide_id))
        self.conn.commit()

    def delete_guide(self, guide_id):
        self.conn.execute("DELETE FROM guides WHERE id=?", (guide_id,))
        self.conn.commit()

    # ── PAYMENTS ──────────────────────────────────────────────────────────────
    def add_payment_request(self, user_id):
        self.conn.execute("INSERT INTO payment_requests (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def get_pending_payments(self):
        rows = self.conn.execute("""
            SELECT p.*,u.first_name,u.full_name,u.username
            FROM payment_requests p JOIN users u ON p.user_id=u.user_id
            WHERE p.status='pending' ORDER BY p.created_at DESC""").fetchall()
        return [dict(r) for r in rows]

    # ── STATS ─────────────────────────────────────────────────────────────────
    def get_stats(self):
        c = self.conn.cursor()
        return {
            "total_users":     c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "approved_users":  c.execute("SELECT COUNT(*) FROM users WHERE status='approved'").fetchone()[0],
            "premium_users":   c.execute("SELECT COUNT(*) FROM users WHERE status='premium'").fetchone()[0],
            "pending_users":   c.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0],
            "total_pdf_tests": c.execute("SELECT COUNT(*) FROM pdf_tests").fetchone()[0],
            "total_guides":    c.execute("SELECT COUNT(*) FROM guides").fetchone()[0],
            "total_results":   c.execute("SELECT COUNT(*) FROM pdf_results").fetchone()[0],
        }
