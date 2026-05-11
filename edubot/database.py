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

        # Foydalanuvchilar
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT,
                status      TEXT DEFAULT 'new',
                joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Testlar
        c.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Savollar
        c.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id        INTEGER NOT NULL,
                question       TEXT NOT NULL,
                option_a       TEXT NOT NULL,
                option_b       TEXT NOT NULL,
                option_c       TEXT NOT NULL,
                option_d       TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                FOREIGN KEY (test_id) REFERENCES tests(id)
            )
        """)

        # Natijalar
        c.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                test_id    INTEGER NOT NULL,
                correct    INTEGER NOT NULL,
                total      INTEGER NOT NULL,
                taken_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (test_id) REFERENCES tests(id)
            )
        """)

        # Qo'llanmalar
        c.execute("""
            CREATE TABLE IF NOT EXISTS guides (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Videolar
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

    # ─── FOYDALANUVCHILAR ─────────────────────

    def add_user(self, user_id, username, first_name):
        c = self.conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        self.conn.commit()

    def get_user_status(self, user_id) -> str:
        c = self.conn.cursor()
        row = c.execute("SELECT status FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["status"] if row else "new"

    def set_user_status(self, user_id, status):
        c = self.conn.cursor()
        c.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        self.conn.commit()

    def is_user_approved(self, user_id) -> bool:
        return self.get_user_status(user_id) == "approved"

    def get_all_users(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ─── TESTLAR ─────────────────────────────

    def add_test(self, title):
        c = self.conn.cursor()
        c.execute("INSERT INTO tests (title) VALUES (?)", (title,))
        self.conn.commit()

    def get_last_test_id(self):
        c = self.conn.cursor()
        row = c.execute("SELECT id FROM tests ORDER BY id DESC LIMIT 1").fetchone()
        return row["id"] if row else None

    def get_all_tests(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT * FROM tests ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def add_question(self, test_id, question, opt_a, opt_b, opt_c, opt_d, correct):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO questions (test_id, question, option_a, option_b, option_c, option_d, correct_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (test_id, question, opt_a, opt_b, opt_c, opt_d, correct))
        self.conn.commit()

    def get_test_questions(self, test_id):
        c = self.conn.cursor()
        rows = c.execute(
            "SELECT * FROM questions WHERE test_id = ? ORDER BY id", (test_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ─── NATIJALAR ───────────────────────────

    def save_result(self, user_id, test_id, correct, total):
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO results (user_id, test_id, correct, total)
            VALUES (?, ?, ?, ?)
        """, (user_id, test_id, correct, total))
        self.conn.commit()

    def get_user_results(self, user_id):
        c = self.conn.cursor()
        rows = c.execute("""
            SELECT r.correct, r.total, r.taken_at, t.title as test_title
            FROM results r
            JOIN tests t ON r.test_id = t.id
            WHERE r.user_id = ?
            ORDER BY r.taken_at DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    # ─── QO'LLANMALAR ────────────────────────

    def add_guide(self, title, content):
        c = self.conn.cursor()
        c.execute("INSERT INTO guides (title, content) VALUES (?, ?)", (title, content))
        self.conn.commit()

    def get_all_guides(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT id, title FROM guides ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_guide(self, guide_id):
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM guides WHERE id = ?", (guide_id,)).fetchone()
        return dict(row) if row else None

    # ─── VIDEOLAR ────────────────────────────

    def add_video(self, title, description, url):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO videos (title, description, url) VALUES (?, ?, ?)",
            (title, description, url)
        )
        self.conn.commit()

    def get_all_videos(self):
        c = self.conn.cursor()
        rows = c.execute("SELECT id, title FROM videos ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_video(self, video_id):
        c = self.conn.cursor()
        row = c.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
        return dict(row) if row else None

    # ─── STATISTIKA ──────────────────────────

    def get_stats(self):
        c = self.conn.cursor()
        return {
            "total_users":    c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "approved_users": c.execute("SELECT COUNT(*) FROM users WHERE status='approved'").fetchone()[0],
            "pending_users":  c.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0],
            "total_tests":    c.execute("SELECT COUNT(*) FROM tests").fetchone()[0],
            "total_guides":   c.execute("SELECT COUNT(*) FROM guides").fetchone()[0],
            "total_videos":   c.execute("SELECT COUNT(*) FROM videos").fetchone()[0],
        }
