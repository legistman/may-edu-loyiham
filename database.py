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
            user_id    INTEGER PRIMARY KEY,
            username   TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            full_name  TEXT DEFAULT '',
            status     TEXT DEFAULT 'new',
            pro_until  TEXT DEFAULT NULL,
            joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pdf_tests (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            title          TEXT NOT NULL,
            file_id        TEXT NOT NULL,
            question_count INTEGER DEFAULT 30,
            answer_key     TEXT NOT NULL,
            is_free        INTEGER DEFAULT 0,
            time_limit     INTEGER DEFAULT 30,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS pdf_results (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id  INTEGER, test_id INTEGER,
            correct  INTEGER, total   INTEGER,
            answers  TEXT,
            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS guides (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            content    TEXT DEFAULT '',
            is_free    INTEGER DEFAULT 1,
            file_id    TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS payment_requests (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            status     TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS referrals (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            invited_id INTEGER UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS points (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            amount     INTEGER NOT NULL,
            reason     TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS start_message (
            id       INTEGER PRIMARY KEY,
            text     TEXT NOT NULL,
            photo_id TEXT DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS sahovat_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER,
            amount       TEXT DEFAULT '',
            payment_type TEXT DEFAULT 'guide',
            status       TEXT DEFAULT 'pending',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS sahovat_reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            period        TEXT NOT NULL,
            total_sum     TEXT NOT NULL,
            charity_sum   TEXT NOT NULL,
            author_sum    TEXT NOT NULL,
            donors_count  INTEGER DEFAULT 0,
            note          TEXT DEFAULT '',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

        defaults = [
            ('pro_price',         '349 000'),
            ('pro_days',          '30'),
            ('card_number',       '9860 3501 4876 2387'),
            ('card_owner',        'Mallayev Ozodbek'),
            ('ref_needed',        '10'),
            ('channel',           '@legistman'),
            ('sahovat_card',      '9860 3501 4876 2387'),
            ('sahovat_owner',     'Mallayev Ozodbek'),
            ('sahovat_percent',   '10'),
        ]
        for k, v in defaults:
            c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", (k, v))

        c.execute("""INSERT OR IGNORE INTO start_message (id,text) VALUES (1,
            '🚀 LEGISTMAN BOT ga xush kelibsiz!

Assalomu alaykum! 👋

Siz huquq sohasida bilimni testlar va qo''llanmalar uyg''unligida o''rganish imkonini beruvchi LEGISTMAN BOT ga kirdingiz.

📚 Ushbu bot @legistman kanaliga tegishli bo''lib, tizimli va amaliy huquqiy bilimlar taqdim etadi.

🤖 Bot yaratuvchisi: @legistman_uz')""")

        # Eski bazalar uchun yangi ustunlar
        for sql in [
            "ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT ''",
            "ALTER TABLE pdf_tests ADD COLUMN time_limit INTEGER DEFAULT 30",
            "ALTER TABLE guides ADD COLUMN file_id TEXT DEFAULT ''",
            "ALTER TABLE start_message ADD COLUMN photo_id TEXT DEFAULT ''",
            "ALTER TABLE sahovat_payments ADD COLUMN payment_type TEXT DEFAULT 'guide'",
        ]:
            try: c.execute(sql)
            except: pass
        self.conn.commit()

    # ── SOZLAMALAR ────────────────────────────────────────────────────────────
    def get_setting(self, key, default=""):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        self.conn.commit()

    # ── START XABARI ─────────────────────────────────────────────────────────
    def get_start_message(self):
        r = self.conn.execute("SELECT * FROM start_message WHERE id=1").fetchone()
        return dict(r) if r else None

    def update_start_message(self, text=None, photo_id=None):
        sm = self.get_start_message()
        t  = text     if text     is not None else (sm["text"]     if sm else "")
        p  = photo_id if photo_id is not None else (sm["photo_id"] if sm else "")
        self.conn.execute("INSERT OR REPLACE INTO start_message (id,text,photo_id) VALUES (1,?,?)", (t, p))
        self.conn.commit()

    # ── FOYDALANUVCHILAR ──────────────────────────────────────────────────────
    def add_user(self, user_id, username, first_name, full_name=""):
        ex = self.get_user(user_id)
        if ex:
            if full_name:
                self.conn.execute(
                    "UPDATE users SET username=?,first_name=?,full_name=? WHERE user_id=?",
                    (username, first_name, full_name, user_id))
                self.conn.commit()
        else:
            self.conn.execute(
                "INSERT INTO users (user_id,username,first_name,full_name) VALUES (?,?,?,?)",
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

    def reset_user(self, user_id):
        self.conn.execute(
            "UPDATE users SET full_name='',status='new',pro_until=NULL WHERE user_id=?",
            (user_id,))
        self.conn.commit()

    def wipe_user(self, user_id):
        """Foydalanuvchining BARCHA ma'lumotlarini o'chirish"""
        self.conn.execute("DELETE FROM pdf_results WHERE user_id=?", (user_id,))
        self.conn.execute("DELETE FROM payment_requests WHERE user_id=?", (user_id,))
        self.conn.execute(
            "UPDATE users SET full_name='',status='new',pro_until=NULL WHERE user_id=?",
            (user_id,))
        self.conn.commit()

    def get_all_users(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM users ORDER BY joined_at DESC").fetchall()]

    def get_users_by_status(self, status=None):
        if status:
            rows = self.conn.execute(
                "SELECT * FROM users WHERE status=? ORDER BY joined_at DESC", (status,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]

    def set_pro(self, user_id, expiry: datetime):
        self.conn.execute(
            "UPDATE users SET status='pro',pro_until=? WHERE user_id=?",
            (expiry.isoformat(), user_id))
        self.conn.commit()

    def remove_pro(self, user_id):
        self.conn.execute(
            "UPDATE users SET status='approved',pro_until=NULL WHERE user_id=?",
            (user_id,))
        self.conn.commit()

    def get_pro_expiry(self, user_id):
        r = self.conn.execute("SELECT pro_until FROM users WHERE user_id=?", (user_id,)).fetchone()
        if r and r["pro_until"]:
            try: return datetime.fromisoformat(r["pro_until"])
            except: return None
        return None

    # ── PDF TESTLAR ───────────────────────────────────────────────────────────
    def add_pdf_test(self, title, file_id, question_count, answer_key, is_free=0, time_limit=30):
        self.conn.execute(
            "INSERT INTO pdf_tests (title,file_id,question_count,answer_key,is_free,time_limit) VALUES (?,?,?,?,?,?)",
            (title, file_id, question_count, answer_key, is_free, time_limit))
        self.conn.commit()

    def get_all_pdf_tests(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM pdf_tests ORDER BY created_at DESC").fetchall()]

    def get_all_pdf_tests_asc(self):
        """Ketma-ketlik uchun — eng eski birinchi"""
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM pdf_tests ORDER BY created_at ASC").fetchall()]

    def get_free_pdf_tests(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM pdf_tests WHERE is_free=1 ORDER BY created_at DESC").fetchall()]

    def get_pdf_test(self, test_id):
        r = self.conn.execute("SELECT * FROM pdf_tests WHERE id=?", (test_id,)).fetchone()
        return dict(r) if r else None

    def update_pdf_test(self, test_id, title=None, answer_key=None, is_free=None, time_limit=None):
        t = self.get_pdf_test(test_id)
        if not t: return
        self.conn.execute(
            "UPDATE pdf_tests SET title=?,answer_key=?,is_free=?,time_limit=? WHERE id=?",
            (title or t["title"], answer_key or t["answer_key"],
             is_free if is_free is not None else t["is_free"],
             time_limit if time_limit is not None else t.get("time_limit", 30),
             test_id))
        self.conn.commit()

    def delete_pdf_test(self, test_id):
        self.conn.execute("DELETE FROM pdf_tests WHERE id=?", (test_id,))
        self.conn.commit()

    # ── NATIJALAR ─────────────────────────────────────────────────────────────
    def save_pdf_result(self, user_id, test_id, correct, total, answers):
        self.conn.execute(
            "INSERT INTO pdf_results (user_id,test_id,correct,total,answers) VALUES (?,?,?,?,?)",
            (user_id, test_id, correct, total, answers))
        self.conn.commit()

    def get_user_pdf_results(self, user_id):
        rows = self.conn.execute("""
            SELECT r.correct,r.total,r.answers,r.taken_at,t.title as test_title,t.answer_key,t.id as test_id
            FROM pdf_results r JOIN pdf_tests t ON r.test_id=t.id
            WHERE r.user_id=? ORDER BY r.taken_at DESC""", (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_user_results_for_test(self, user_id, test_id):
        rows = self.conn.execute(
            "SELECT * FROM pdf_results WHERE user_id=? AND test_id=? ORDER BY taken_at DESC",
            (user_id, test_id)).fetchall()
        return [dict(r) for r in rows]

    def get_test_rating(self, test_id):
        rows = self.conn.execute("""
            SELECT r.user_id, MAX(r.correct) as correct, r.total,
                   u.first_name, u.full_name, u.username
            FROM pdf_results r JOIN users u ON r.user_id=u.user_id
            WHERE r.test_id=? GROUP BY r.user_id ORDER BY correct DESC""",
            (test_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_overall_rating(self):
        rows = self.conn.execute("""
            SELECT r.user_id, MAX(r.correct) as correct, r.total, t.title as test_title,
                   u.first_name, u.full_name
            FROM pdf_results r
            JOIN users u ON r.user_id=u.user_id
            JOIN pdf_tests t ON r.test_id=t.id
            WHERE r.correct=(SELECT MAX(r2.correct) FROM pdf_results r2 WHERE r2.user_id=r.user_id)
            GROUP BY r.user_id ORDER BY r.correct DESC""").fetchall()
        return [dict(r) for r in rows]

    def get_last_attempt_time(self, user_id, test_id):
        """Foydalanuvchining oxirgi urinish vaqti"""
        r = self.conn.execute(
            "SELECT taken_at FROM pdf_results WHERE user_id=? AND test_id=? ORDER BY taken_at DESC LIMIT 1",
            (user_id, test_id)).fetchone()
        return r["taken_at"] if r else None

    def user_completed_test(self, user_id, test_id):
        """Foydalanuvchi bu testni yechdimi?"""
        r = self.conn.execute(
            "SELECT id FROM pdf_results WHERE user_id=? AND test_id=?",
            (user_id, test_id)).fetchone()
        return r is not None

    def get_first_test_id(self):
        """Birinchi (eng eski) test ID si"""
        r = self.conn.execute(
            "SELECT id FROM pdf_tests ORDER BY id ASC LIMIT 1").fetchone()
        return r["id"] if r else None

    def get_test_order(self, test_id):
        """Testning tartib raqami (1, 2, 3...)"""
        r = self.conn.execute(
            "SELECT COUNT(*) FROM pdf_tests WHERE id <= ?", (test_id,)).fetchone()
        return r[0] if r else 1

    def get_prev_test_id(self, test_id):
        """Testdan oldingi test ID si"""
        r = self.conn.execute(
            "SELECT id FROM pdf_tests WHERE id < ? ORDER BY id DESC LIMIT 1",
            (test_id,)).fetchone()
        return r["id"] if r else None

    def get_user_test_count(self, user_id):
        r = self.conn.execute(
            "SELECT COUNT(DISTINCT test_id) FROM pdf_results WHERE user_id=?",
            (user_id,)).fetchone()
        return r[0] if r else 0

    def get_user_badges(self, user_id):
        count = self.get_user_test_count(user_id)
        badges = []
        if count >= 5:  badges.append("🌟 Faol o'quvchi")
        if count >= 10: badges.append("📚 Bilimdon")
        if count >= 20: badges.append("🏆 Ustoz")
        return badges, count

    # ── QO'LLANMALAR ─────────────────────────────────────────────────────────
    def add_guide(self, title, content, is_free=1, file_id=""):
        self.conn.execute(
            "INSERT INTO guides (title,content,is_free,file_id) VALUES (?,?,?,?)",
            (title, content, is_free, file_id))
        self.conn.commit()

    def get_all_guides(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM guides ORDER BY created_at DESC").fetchall()]

    def get_free_guides(self):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM guides WHERE is_free=1 ORDER BY created_at DESC").fetchall()]

    def get_guide(self, guide_id):
        r = self.conn.execute("SELECT * FROM guides WHERE id=?", (guide_id,)).fetchone()
        return dict(r) if r else None

    def update_guide(self, guide_id, title=None, content=None, is_free=None, file_id=None):
        g = self.get_guide(guide_id)
        if not g: return
        self.conn.execute(
            "UPDATE guides SET title=?,content=?,is_free=?,file_id=? WHERE id=?",
            (title or g["title"], content if content is not None else g["content"],
             is_free if is_free is not None else g["is_free"],
             file_id if file_id is not None else g.get("file_id",""),
             guide_id))
        self.conn.commit()

    def delete_guide(self, guide_id):
        self.conn.execute("DELETE FROM guides WHERE id=?", (guide_id,))
        self.conn.commit()

    # ── TO'LOVLAR ────────────────────────────────────────────────────────────
    def add_payment_request(self, user_id):
        self.conn.execute("INSERT INTO payment_requests (user_id) VALUES (?)", (user_id,))
        self.conn.commit()

    def get_pending_payments(self):
        rows = self.conn.execute("""
            SELECT p.*,u.first_name,u.full_name,u.username
            FROM payment_requests p JOIN users u ON p.user_id=u.user_id
            WHERE p.status='pending' ORDER BY p.created_at DESC""").fetchall()
        return [dict(r) for r in rows]

    # ── SAHOVAT TO'LOVLARI ───────────────────────────────────────────────────
    def add_sahovat_payment(self, user_id, amount="", payment_type="guide"):
        self.conn.execute(
            "INSERT INTO sahovat_payments (user_id, amount, payment_type) VALUES (?,?,?)",
            (user_id, amount, payment_type))
        self.conn.commit()

    def get_pending_sahovat_payments(self):
        rows = self.conn.execute("""
            SELECT s.*,u.first_name,u.full_name,u.username
            FROM sahovat_payments s JOIN users u ON s.user_id=u.user_id
            WHERE s.status='pending' ORDER BY s.created_at DESC""").fetchall()
        return [dict(r) for r in rows]

    def confirm_sahovat_payment(self, payment_id):
        self.conn.execute(
            "UPDATE sahovat_payments SET status='confirmed' WHERE id=?", (payment_id,))
        self.conn.commit()

    def reject_sahovat_payment(self, payment_id):
        self.conn.execute(
            "UPDATE sahovat_payments SET status='rejected' WHERE id=?", (payment_id,))
        self.conn.commit()

    def get_sahovat_stats(self):
        r = self.conn.execute(
            "SELECT COUNT(*) FROM sahovat_payments WHERE status='confirmed'").fetchone()
        return {"confirmed_count": r[0] if r else 0}

    def get_weekly_sahovat_stats(self):
        """Haftalik (oxirgi 7 kun) statistika — type bo'yicha ajratilgan"""
        from datetime import datetime, timedelta
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        rows = self.conn.execute(
            "SELECT amount, payment_type FROM sahovat_payments "
            "WHERE status='confirmed' AND created_at >= ?", (week_ago,)).fetchall()
        guide_total = 0; ehson_total = 0; guide_cnt = 0; ehson_cnt = 0
        for r in rows:
            try:
                val = int(str(r["amount"]).replace(" ","").replace(",",""))
            except: val = 0
            if r["payment_type"] == "ehson":
                ehson_total += val; ehson_cnt += 1
            else:
                guide_total += val; guide_cnt += 1
        # Hisoblash: guide → 50/50, ehson → 100% xayriya
        guide_charity = guide_total // 2
        guide_author  = guide_total - guide_charity
        ehson_charity = ehson_total
        total_charity = guide_charity + ehson_charity
        total_author  = guide_author
        grand_total   = guide_total + ehson_total
        return {
            "grand_total":   grand_total,
            "guide_total":   guide_total,
            "guide_cnt":     guide_cnt,
            "ehson_total":   ehson_total,
            "ehson_cnt":     ehson_cnt,
            "total_charity": total_charity,
            "total_author":  total_author,
            "donors_cnt":    guide_cnt + ehson_cnt,
        }

    # ── SAHOVAT HISOBOTLARI ──────────────────────────────────────────────────
    def add_sahovat_report(self, period, total_sum, charity_sum, author_sum, donors_count, note=""):
        self.conn.execute(
            """INSERT INTO sahovat_reports
               (period, total_sum, charity_sum, author_sum, donors_count, note)
               VALUES (?,?,?,?,?,?)""",
            (period, total_sum, charity_sum, author_sum, donors_count, note))
        self.conn.commit()

    def get_sahovat_reports(self, limit=5):
        rows = self.conn.execute(
            "SELECT * FROM sahovat_reports ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete_sahovat_report(self, report_id):
        self.conn.execute("DELETE FROM sahovat_reports WHERE id=?", (report_id,))
        self.conn.commit()

    # ── REFERRAL ─────────────────────────────────────────────────────────────
    def add_referral(self, inviter_id, invited_id):
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO referrals (inviter_id,invited_id) VALUES (?,?)",
                (inviter_id, invited_id))
            self.conn.commit()
        except: pass

    def get_referral_count(self, user_id):
        r = self.conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id=?", (user_id,)).fetchone()
        return r[0] if r else 0

    def referral_exists(self, invited_id):
        r = self.conn.execute(
            "SELECT id FROM referrals WHERE invited_id=?", (invited_id,)).fetchone()
        return r is not None

    # ── STATISTIKA ────────────────────────────────────────────────────────────
    def get_stats(self):
        c = self.conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "total_users":    c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "approved_users": c.execute("SELECT COUNT(*) FROM users WHERE status='approved'").fetchone()[0],
            "pro_users":      c.execute("SELECT COUNT(*) FROM users WHERE status='pro'").fetchone()[0],
            "pending_users":  c.execute("SELECT COUNT(*) FROM users WHERE status='pending'").fetchone()[0],
            "today_users":    c.execute("SELECT COUNT(*) FROM users WHERE joined_at LIKE ?", (today+"%",)).fetchone()[0],
            "total_tests":    c.execute("SELECT COUNT(*) FROM pdf_tests").fetchone()[0],
            "total_guides":   c.execute("SELECT COUNT(*) FROM guides").fetchone()[0],
            "total_results":  c.execute("SELECT COUNT(*) FROM pdf_results").fetchone()[0],
            "today_results":  c.execute("SELECT COUNT(*) FROM pdf_results WHERE taken_at LIKE ?", (today+"%",)).fetchone()[0],
        }
