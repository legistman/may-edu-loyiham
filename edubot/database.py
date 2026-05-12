import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "bot_data.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                status     TEXT DEFAULT 'new',
                joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS pdf_tests (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                title          TEXT NOT NULL,
                file_id        TEXT NOT NULL,
                question_count INTEGER DEFAULT 30,
                answer_key     TEXT NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS pdf_results (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                test_id    INTEGER NOT NULL,
                correct    INTEGER NOT NULL,
                total      INTEGER NOT NULL,
                answers    TEXT,
                taken_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS guides (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT,
                url         TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_user(self, user_id, username, first_name):
        self.conn.execute("INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?,?,?)", (user_id, username, first_name))
        self.conn.commit()

    def get_user_status(self, user_id):
        row = self.conn.execute("SELECT status FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["status"] if row else "new"

    def set_user_status(self, user_id, status):
        self.conn.execute("UPDATE users SET status=? WHERE user_id=?", (status, user_id))
        self.conn.commit()

    def is_user_approved(self, user_id):
        return self.get_user_status(user_id) == "approved"

    def get_all_users(self):
        rows = self.conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]

    def add_pdf_test(self, title, file_id, question_count, answer_key):
        self.conn.execute("INSERT INTO pdf_tests (title, file_id, question_count, answer_key) VALUES (?,?,?,?)", (title, file_id, question_count, answer_key))
        self.conn.commit()

    def get_all_pdf_tests(self):
        rows = self.conn.execute("SELECT * FROM pdf_tests ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_pdf_test(self, test_id):
        row = self.conn.execute("SELECT * FROM pdf_tests WHERE id=?", (test_id,)).fetchone()
        return dict(row) if row else None

    def get_answer_key(self, test_id):
        row = self.conn.execute("SELECT answer_key FROM pdf_tests WHERE id=?", (test_id,)).fetchone()
        return row["answer_key"] if row else None

    def save_pdf_result(self, user_id, test_id, correct, total, answers):
        self.conn.execute("INSERT INTO pdf_results (user_id, test_id, correct, total, answers) VALUES (?,?,?,?,?)", (user_id, test_id, correct, total, answers))
        self.conn.commit()

    def get_user_pdf_results(self, user_id):
        rows = self.conn.execute("""
            SELECT r.correct, r.total, r.taken_at, t.title as test_title
            FROM pdf_results r JOIN pdf_tests t ON r.test_id=t.id
            WHERE r.user_id=? ORDER BY r.taken_at DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def add_guide(self, title, content):
        self.conn.execute("INSERT INTO guides (title, content) VALUES (?,?)", (title, content))
        self.conn.commit()

    def get_all_guides(self):
        rows = self.conn.execute("SELECT id, title FROM guides ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_guide(self, guide_id):
        row = self.conn.execute("SELECT * FROM guides WHERE id=?", (guide_id,)).fetchone()
        return dict(row) if row else None

    def add_video(self, title, description, url):
        self.conn.execute("INSERT INTO videos (title, description, url) VALUES (?,?,?)", (title, description, url))
        self.conn.commit()

    def get_all_videos(self):
        rows = self.conn.execute("SELECT id, title FROM videos ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_video(self, video_id):
        row = self.conn.execute("SELECT * FROM videos WHERE id=?", (video_id,)).fetchone()
        return dict(row) if row else None

    def get_stats(self):
        c = self.conn.cursor()
        return {
            "total_users":     c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "approved_users":  c.execute("SELECT COUNT(*) FROM users WHERE status='approved'").fetchone()[0],
            "pending_users":   c.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0],
            "total_pdf_tests": c.execute("SELECT COUNT(*) FROM pdf_tests").fetchone()[0],
            "total_guides":    c.execute("SELECT COUNT(*) FROM guides").fetchone()[0],
            "total_videos":    c.execute("SELECT COUNT(*) FROM videos").fetchone()[0],
        }
