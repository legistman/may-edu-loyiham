import logging, os, re, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes)
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
db       = Database()
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "123456789"))
TZ        = ZoneInfo("Asia/Tashkent")

def now():       return datetime.now(TZ)
def S(k, d=""):  return db.get_setting(k) or d
def uname(u):    return (u.get("full_name") or u.get("first_name") or "Foydalanuvchi") if u else "?"
def back(cb):    return InlineKeyboardButton("⬅️ Orqaga", callback_data=cb)

def is_admin(uid):  return uid == ADMIN_ID
def is_pro(uid):
    u = db.get_user(uid)
    if not u or u["status"] != "pro": return False
    exp = db.get_pro_expiry(uid)
    if not exp or now() > exp:
        db.set_user_status(uid, "approved"); return False
    return True
def is_approved(uid): return db.get_user_status(uid) in ("approved","pro")
def exp_str(uid):
    e = db.get_pro_expiry(uid)
    return e.strftime("%d.%m.%Y") if e else "?"

async def check_channel(uid, bot):
    ch = S("channel", "@legistman")
    try:
        m = await bot.get_chat_member(ch, uid)
        return m.status not in ("left","kicked","banned")
    except: return True

# ═══════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()

    # Referral argument
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                rid = int(arg[4:])
                if rid != user.id: context.user_data["ref_id"] = rid
            except: pass

    if is_admin(user.id):
        db.add_user(user.id, user.username or "", user.first_name, user.first_name)
        await show_admin_menu(update, context); return

    # Kanal tekshiruvi
    ch = S("channel", "@legistman")
    if not await check_channel(user.id, context.bot):
        kb = [
            [InlineKeyboardButton(f"📢 {ch} kanaliga a'zo bo'lish",
                                  url=f"https://t.me/{ch.lstrip('@')}")],
            [InlineKeyboardButton("✅ A'zo bo'ldim — tekshirish", callback_data="check_join")],
        ]
        await update.message.reply_text(
            f"⚠️ Botdan foydalanish uchun avval\n{ch} kanaliga a'zo bo'ling!\n\n"
            f"A'zo bo'lgach '✅ A'zo bo'ldim' tugmasini bosing.",
            reply_markup=InlineKeyboardMarkup(kb)); return

    ex = db.get_user(user.id)
    if ex and ex.get("full_name"):
        await show_welcome(update, context); return

    # Yangi foydalanuvchi
    context.user_data["step"] = "waiting_fullname"
    sm = db.get_start_message()
    text = (sm["text"] if sm else "Xush kelibsiz!") + \
           "\n\n✍️ Ismingiz va familiyangizni to'liq kiriting:\n📝 Masalan: Mallayev Ozodbek"
    if sm and sm.get("photo_id"):
        await update.message.reply_photo(photo=sm["photo_id"], caption=text)
    else:
        await update.message.reply_text(text)

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if not await check_channel(uid, context.bot):
        await q.answer("Hali a'zo bo'lmadingiz!", show_alert=True); return
    ex = db.get_user(uid)
    if ex and ex.get("full_name"):
        await show_welcome(update, context)
    else:
        context.user_data["step"] = "waiting_fullname"
        sm = db.get_start_message()
        text = (sm["text"] if sm else "Xush kelibsiz!") + \
               "\n\n✍️ Ismingiz va familiyangizni kiriting:\n📝 Masalan: Mallayev Ozodbek"
        await q.edit_message_text(text)

# ═══════════════════════════════════════════════════════
#  XU SH KELIBSIZ
# ═══════════════════════════════════════════════════════
async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = (update.effective_user or update.callback_query.from_user).id
    u    = db.get_user(uid)
    fn   = uname(u)
    prem = is_pro(uid)

    # Kunlik maqsad
    today      = now().strftime("%Y-%m-%d")
    results    = db.get_user_pdf_results(uid)
    done_today = any(str(r.get("taken_at",""))[:10] == today for r in results)
    goal       = "✅ Bugungi maqsad bajarildi!" if done_today else "🎯 Bugungi maqsad: 1 ta test yeching!"

    # Nishonlar
    badges, _ = db.get_user_badges(uid)
    badge_str  = "  ".join(badges) if badges else ""

    if prem:
        header = (
            f"👑 Xush kelibsiz, {fn}!\n"
            f"PRO obuna: {exp_str(uid)} gacha aktiv ✅\n\n"
            f"{goal}"
        )
        if badge_str: header += f"\n{badge_str}"
        kb = [
            [InlineKeyboardButton("👑 PRO bo'lim",       callback_data="pro_menu")],
            [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        ]
    else:
        header = f"👋 Xush kelibsiz, {fn}!\n\n{goal}"
        if badge_str: header += f"\n{badge_str}"
        kb = [
            [InlineKeyboardButton("ℹ️ Bot haqida",       callback_data="about_bot")],
            [InlineKeyboardButton("🆓 Bepul versiya",     callback_data="free_menu")],
            [InlineKeyboardButton("👑 PRO versiya",       callback_data="pro_info")],
            [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        ]

    if update.callback_query:
        try: await update.callback_query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb))
        except: await context.bot.send_message(uid, header, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(header, reply_markup=InlineKeyboardMarkup(kb))

async def back_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await show_welcome(update, context)

# ═══════════════════════════════════════════════════════
#  BOT HAQIDA
# ═══════════════════════════════════════════════════════
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🚀 LEGISTMAN BOT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 @legistman kanalining rasmiy o'quv boti\n\n"
        "Bu bot orqali:\n"
        "⚖️ Huquqiy bilimlaringizni testlar orqali sinab ko'rasiz\n"
        "📚 Tizimli qo'llanmalar bilan o'rganasiz\n"
        "📊 Batafsil tahlil va reyting ko'rasiz\n\n"
        "🤖 Bot yaratuvchisi: @legistman_uz\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[back("back_welcome")]]))

# ═══════════════════════════════════════════════════════
#  BEPUL MENYU
# ═══════════════════════════════════════════════════════
async def free_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("📝 TESTLAR",          callback_data="free_tests")],
        [InlineKeyboardButton("📚 QO'LLANMALAR",     callback_data="free_guides")],
        [InlineKeyboardButton("📊 Statistika",       callback_data="user_stats")],
        [InlineKeyboardButton("🎁 Do'st taklif",     callback_data="my_referral")],
        [InlineKeyboardButton("👑 PRO olish",         callback_data="buy_pro")],
        [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        [back("back_welcome")],
    ]
    await q.edit_message_text("🆓 Bepul bo'lim", reply_markup=InlineKeyboardMarkup(kb))

async def free_tests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_free_pdf_tests()
    kb = [[InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"pdf_test_{t['id']}")] for t in tests]
    if not tests: kb.append([InlineKeyboardButton("👑 PRO olish", callback_data="buy_pro")])
    kb.append([back("free_menu")])
    await q.edit_message_text("📝 Bepul testlar:" if tests else "Hozircha bepul testlar yo'q.",
                              reply_markup=InlineKeyboardMarkup(kb))

async def free_guides_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    guides = db.get_free_guides()
    kb = [[InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")] for g in guides]
    if not guides: kb.append([InlineKeyboardButton("👑 PRO olish", callback_data="buy_pro")])
    kb.append([back("free_menu")])
    await q.edit_message_text("📚 Bepul qo'llanmalar:" if guides else "Hozircha bepul qo'llanmalar yo'q.",
                              reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════
#  PRO MENYU
# ═══════════════════════════════════════════════════════
async def pro_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    price = S("pro_price","349 000")
    days  = S("pro_days","30")
    await q.edit_message_text(
        f"👑 PRO versiya\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ Barcha testlar\n✅ Barcha qo'llanmalar\n"
        f"✅ Batafsil xato tahlili\n✅ Shaxsiy reyting\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 To'lov qilish", callback_data="buy_pro")],
            [back("back_welcome")],
        ]))

async def pro_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    kb = [
        [InlineKeyboardButton("📝 Testlar",          callback_data="pro_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",     callback_data="pro_guides")],
        [InlineKeyboardButton("📊 Statistika",       callback_data="user_stats")],
        [InlineKeyboardButton("🎁 Do'st taklif",     callback_data="my_referral")],
        [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        [back("back_welcome")],
    ]
    await q.edit_message_text(
        f"👑 PRO bo'lim\nPRO obuna: {exp_str(uid)} gacha aktiv ✅",
        reply_markup=InlineKeyboardMarkup(kb))

async def pro_tests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton(
        f"{'🆓' if t.get('is_free') else '👑'} {t['title']}",
        callback_data=f"pdf_test_{t['id']}")] for t in tests]
    kb.append([back("pro_menu")])
    await q.edit_message_text("📝 Barcha testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def pro_guides_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    await q.edit_message_text(
        "📚 Qo'llanmalar\n\n"
        "Siz PRO foydalanuvchisi sifatida\n"
        "@legistman_uz profili bilan bog'laning —\n"
        "QO'LLANMA BAZA kanaliga qo'shib qo'yilasiz 📖",
        reply_markup=InlineKeyboardMarkup([[back("pro_menu")]]))

# ═══════════════════════════════════════════════════════
#  TO'LOV
# ═══════════════════════════════════════════════════════
async def buy_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if is_pro(uid):
        await q.answer("Siz allaqachon PRO foydalanuvchisiz!", show_alert=True); return
    price = S("pro_price","349 000"); days = S("pro_days","30")
    card  = S("card_number","9860 3501 4876 2387")
    owner = S("card_owner","Mallayev Ozodbek")
    await q.edit_message_text(
        f"💳 To'lov ma'lumotlari\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n\n"
        f"Karta:\n`{card}`\n"
        f"Egasi: {owner}\n\n"
        f"📋 Qadamlar:\n"
        f"1️⃣ Kartaga {price} so'm o'tkiring\n"
        f"2️⃣ To'lov chekini (screenshot) saqlang\n"
        f"3️⃣ Quyidagi tugmani bosib chekni yuboring\n"
        f"4️⃣ Admin 24 soat ichida ko'rib chiqadi ✅",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Chek yuboraman", callback_data="send_proof")],
            [back("back_welcome")],
        ]))

async def send_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_proof"
    await q.edit_message_text(
        "📸 To'lov chekini yuboring (rasm yoki fayl).\n\nBekor: /start")

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    action, tid = q.data.split("_")[1], int(q.data.split("_")[2])
    days = int(S("pro_days","30"))
    cap  = q.message.caption or q.message.text or ""
    if action == "ok":
        exp = now() + timedelta(days=days)
        db.set_pro(tid, exp)
        try: await q.edit_message_caption(cap + f"\n\n✅ Tasdiqlandi! PRO: {exp.strftime('%d.%m.%Y')} gacha")
        except: await q.edit_message_text(cap + "\n\n✅ Tasdiqlandi!")
        await context.bot.send_message(
            tid, f"🎉 PRO obuna faollashtirildi!\n\n"
                 f"👑 {days} kun ({exp.strftime('%d.%m.%Y')} gacha)\n\n/start bosing.")
    else:
        try: await q.edit_message_caption(cap + "\n\n❌ Rad etildi.")
        except: await q.edit_message_text(cap + "\n\n❌ Rad etildi.")
        await context.bot.send_message(tid, "😔 To'lovingiz tasdiqlanmadi.")

# ═══════════════════════════════════════════════════════
#  TESTLAR
# ═══════════════════════════════════════════════════════
async def show_pdf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid     = q.from_user.id
    test_id = int(q.data.split("_")[2])
    test    = db.get_pdf_test(test_id)
    if not test: return
    prem = is_pro(uid) or is_approved(uid)
    if not test.get("is_free") and not prem:
        await q.edit_message_text(
            "👑 Bu test faqat PRO foydalanuvchilar uchun.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 PRO olish", callback_data="buy_pro")],
                [back("free_menu")],
            ])); return

    # Ketma-ketlik tekshiruvi: oldingi testni yechmagan bo'lsa kiritmaymiz
    prev_id = db.get_prev_test_id(test_id)
    if prev_id and not db.user_completed_test(uid, prev_id):
        prev_test = db.get_pdf_test(prev_id)
        await q.edit_message_text(
            f"⚠️ Ketma-ketlik buzildi!\n\n"
            f"Bu testni ishlash uchun avval:\n"
            f"📝 '{prev_test['title']}' testini yeching.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📝 {prev_test['title']}", callback_data=f"pdf_test_{prev_id}")],
                [back("free_menu" if not prem else "pro_menu")],
            ])); return

    # 30 daqiqa kutish tekshiruvi
    last_attempt = db.get_last_attempt_time(uid, test_id)
    if last_attempt:
        from datetime import timezone
        try:
            last_dt = datetime.fromisoformat(str(last_attempt))
            # Agar timezone yo'q bo'lsa qo'shamiz
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=TZ)
            diff_min = (now() - last_dt).total_seconds() / 60
            if diff_min < 30:
                wait_min = int(30 - diff_min) + 1
                await q.edit_message_text(
                    f"⏳ Ushbu testni qayta ishlash uchun\n"
                    f"{wait_min} daqiqa kutishingiz kerak.\n\n"
                    f"Oxirgi urinish: {last_dt.strftime('%H:%M')}",
                    reply_markup=InlineKeyboardMarkup([
                        [back("free_menu" if not prem else "pro_menu")]
                    ])); return
        except: pass

    t_limit = test.get("time_limit", 30)
    tstart  = time.time()
    context.user_data.update({
        "step": "waiting_answers", "tid": test_id,
        "tcnt": test["question_count"], "tstart": tstart
    })
    await context.bot.send_document(
        q.message.chat_id, test["file_id"],
        caption=f"📝 {test['title']}\n❓ Savollar: {test['question_count']} ta\n⏱ Vaqt: {t_limit} daqiqa\n\nTestni yechib bo'lgach javob yuboring.",
        protect_content=True)

    # Dastlabki timer xabari
    def make_timer_text(remaining_min):
        total   = t_limit
        elapsed = total - remaining_min
        filled  = max(0, min(10, int((elapsed / total) * 10)))
        empty   = 10 - filled
        bar     = "🟥" * filled + "🟩" * empty
        if remaining_min > 0:
            return (
                f"⏱ Qolgan vaqt: {remaining_min} daqiqa\n"
                f"{bar}\n\n"
                f"Javob yuborishga shoshilmang, vaqtingiz bor."
            )
        else:
            return "⏰ Vaqt tugadi!"

    sent_msg = await context.bot.send_message(
        q.message.chat_id,
        make_timer_text(t_limit),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_{test_id}")]]))

    # Har daqiqada timer yangilanadi
    msg_id  = sent_msg.message_id
    chat_id = q.message.chat_id

    async def update_timer(ctx):
        elapsed_min = int((time.time() - tstart) / 60)
        remaining   = t_limit - elapsed_min
        if remaining <= 0:
            try:
                await ctx.bot.edit_message_text(
                    "⏰ Vaqt tugadi!\n\nJavobingiz qabul qilinmaydi.",
                    chat_id=chat_id, message_id=msg_id)
            except: pass
            return
        try:
            await ctx.bot.edit_message_text(
                make_timer_text(remaining),
                chat_id=chat_id, message_id=msg_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_{test_id}")]]))
        except: pass

    # Job queue orqali har t_limit/10 daqiqada yangilash
    interval_sec = max(60, (t_limit * 60) // 10)  # vaqtning 1/10 qismi
    if context.application.job_queue:
        job_name = f"timer_{uid}_{test_id}"
        for job in context.application.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        context.application.job_queue.run_repeating(
            update_timer,
            interval=interval_sec,
            first=interval_sec,
            name=job_name,
            chat_id=chat_id,
            user_id=uid)

async def submit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    test    = db.get_pdf_test(test_id)
    n       = test["question_count"] if test else 30
    t_limit = test.get("time_limit", 30) if test else 30
    context.user_data.update({
        "step": "waiting_answers", "tid": test_id,
        "tcnt": n, "tstart": context.user_data.get("tstart", time.time())
    })
    await q.edit_message_text(
        f"✏️ {n} ta javobni yuboring!\n\n"
        f"Harflar ketma-ket (ABCD):\nMasalan: ABCDABCD...\n\n"
        f"(Vergul, bo'shliq shart emas)")

async def handle_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_answers": return False
    uid     = update.effective_user.id
    test_id = context.user_data["tid"]
    n       = context.user_data["tcnt"]
    tstart  = context.user_data.get("tstart", time.time())
    test    = db.get_pdf_test(test_id)
    t_limit = (test.get("time_limit", 30) if test else 30)

    # Vaqt tekshiruvi
    elapsed     = (time.time() - tstart) / 60
    elapsed_min = round(elapsed, 1)
    remaining   = max(0, round(t_limit - elapsed))

    if elapsed > t_limit:
        context.user_data.clear()
        prem = is_pro(uid)
        kb = [[InlineKeyboardButton("📝 Yana test", callback_data="pro_tests" if prem else "free_tests"),
               InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]]
        await update.message.reply_text(
            f"⏰ Vaqt tugadi! ({t_limit} daqiqa)\n\n"
            f"Javobingiz qabul qilinmadi.\nQaytadan urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup(kb))
        return True

    clean = re.sub(r"[^ABCD]", "", update.message.text.strip().upper())
    if len(clean) != n:
        # Qolgan vaqtni vizual ko'rsatish
        bars_done = max(0, min(10, int((elapsed / t_limit) * 10)))
        bars_left = 10 - bars_done
        timer_bar = "🟥" * bars_done + "🟩" * bars_left
        await update.message.reply_text(
            f"⚠️ {len(clean)} ta javob, {n} ta kerak.\n\n"
            f"⏱ {timer_bar}\n"
            f"Sarflangan: {elapsed_min} daq | Qolgan: ~{remaining} daq\n\n"
            f"Qaytadan yuboring:")
        return True

    key     = re.sub(r"[^ABCD]", "", (db.get_pdf_test(test_id) or {}).get("answer_key","").upper())
    if not key:
        await update.message.reply_text("⚠️ Kalit kiritilmagan. Adminga murojaat qiling.")
        return True

    correct  = sum(u == k for u, k in zip(clean, key))
    wrong    = n - correct
    ball     = round(correct * 3.1, 1)
    max_ball = round(n * 3.1, 1)
    pct      = round(correct / n * 100)
    elapsed_real = round(elapsed, 1)

    if pct >= 85: baho = "🏆 Ajoyib!"
    elif pct >= 70: baho = "👍 Yaxshi!"
    elif pct >= 50: baho = "📚 Qoniqarli"
    else: baho = "💪 Ko'proq mashq kerak"

    prem = is_pro(uid)
    # Timer jobni to'xtatish
    if context.application.job_queue:
        job_name = f"timer_{uid}_{test_id}"
        for job in context.application.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()

    db.save_pdf_result(uid, test_id, correct, n, clean)

    # Nishon tekshiruvi
    badges, test_count = db.get_user_badges(uid)
    badge_map = {5: "🌟 Faol o'quvchi", 10: "📚 Bilimdon", 20: "🏆 Ustoz"}
    new_badge = badge_map.get(test_count, "")

    result = (
        f"📊 Test natijasi\n{'━'*24}\n"
        f"📋 Jami savollar: {n} ta\n"
        f"✅ To'g'ri: {correct} ta\n"
        f"❌ Xato: {wrong} ta\n"
        f"🏅 Ball: {ball} / {max_ball}\n"
        f"📈 Foiz: {pct}%\n"
        f"⏱ Vaqt sarflandi: {elapsed_real} daqiqa\n"
        f"🎯 {baho}\n"
    )
    kb_rows = [[InlineKeyboardButton("📝 Yana test", callback_data="pro_tests" if prem else "free_tests"),
                InlineKeyboardButton("📊 Statistika", callback_data="user_stats")],
               [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]]

    is_free_test = db.get_pdf_test(test_id).get("is_free", 0) if db.get_pdf_test(test_id) else 0

    if prem or not is_free_test:
        # PRO — to'liq tahlil
        xato = [f"  {i+1}-savol: Siz ❌{u}  →  To'g'ri ✅{k}"
                for i, (u, k) in enumerate(zip(clean, key)) if u != k]
        togri = "\n".join(f"  {i+1}–{k}" for i, k in enumerate(key))
        if xato:
            result += f"\n{'━'*24}\n❌ Xato savollar ({wrong} ta):\n" + "\n".join(xato[:30])
        result += f"\n\n{'━'*24}\n✅ To'g'ri javoblar kaliti:\n{togri}"
        context.user_data.clear()
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb_rows))
    else:
        # Bepul — statistika + marketing
        context.user_data.clear()
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb_rows))

        # Alohida marketing xabari
        price = S("pro_price","349 000")
        u_obj = db.get_user(uid)
        fn = uname(u_obj)
        if pct >= 85:
            msg = (f"🏆 {fn}, zo'r natija!\n\nLekin qaysi savollarda xato qildingiz?\n"
                   f"✅ To'g'ri javoblar kaliti qayerda?\n\n"
                   f"Bularni faqat 👑 PRO foydalanuvchilar ko'radi!\n\n"
                   f"💰 {price} so'm / 30 kun")
        elif pct >= 50:
            msg = (f"📈 {fn}, yaxshi natija — {pct}%!\n\nXatolaringizni bilib, keyingisida yaxshiroq qiling.\n\n"
                   f"👑 PRO bilan:\n🔍 Har bir xato ko'rsatiladi\n✅ To'g'ri javoblar beriladi\n\n"
                   f"💰 {price} so'm / 30 kun")
        else:
            msg = (f"💪 {fn}, boshlash qiyin — davom etish oson!\n\n"
                   f"👑 PRO bilan xatolaringizdan o'rganing:\n🔍 Batafsil tahlil\n📚 Maxsus qo'llanmalar\n\n"
                   f"💰 {price} so'm / 30 kun")
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 PRO olish — hoziroq!", callback_data="buy_pro")]]))

    if new_badge:
        await update.message.reply_text(f"🎉 Tabrik! Yangi nishon oldingiz:\n{new_badge}")
    return True

# ═══════════════════════════════════════════════════════
#  QO'LLANMALAR (BEPUL)
# ═══════════════════════════════════════════════════════
async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    if not g: return
    uid   = q.from_user.id
    prem  = is_pro(uid)
    fback = "free_guides" if g.get("is_free") else "pro_menu"
    kb    = [[back(fback)]]

    if g.get("file_id"):
        await context.bot.send_document(
            q.message.chat_id, g["file_id"],
            caption=f"📖 {g['title']}", protect_content=True)
        await context.bot.send_message(q.message.chat_id, "👆", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await q.edit_message_text(
            f"📖 {g['title']}\n\n{g['content']}"[:4000],
            reply_markup=InlineKeyboardMarkup(kb))

    # Bepul qo'llanmadan keyin marketing
    if g.get("is_free") and not prem:
        price = S("pro_price","349 000")
        u_obj = db.get_user(uid)
        await context.bot.send_message(
            q.message.chat_id,
            f"📚 Bu faqat namuna qo'llanma!\n\n"
            f"👑 PRO bilan barcha qo'llanmalar va\n"
            f"maxsus BMBA materiallari ochiladi.\n\n"
            f"💰 {price} so'm / 30 kun\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bilim — eng foydali investitsiya! 📈",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 PRO olish — hoziroq!", callback_data="buy_pro")]]))

# ═══════════════════════════════════════════════════════
#  STATISTIKA (FOYDALANUVCHI)
# ═══════════════════════════════════════════════════════
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid)
    back_cb = "pro_menu" if prem else "free_menu"
    await q.edit_message_text(
        "📊 Statistika\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 Shaxsiy natijalar — faqat o'z natijalaringiz\n"
        "🏆 Ommaviy reyting — barcha ishtirokchilar",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Shaxsiy natijalar", callback_data="my_results")],
            [InlineKeyboardButton("🏆 Ommaviy reyting",   callback_data="public_rating")],
            [back(back_cb)],
        ]))

async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid) or is_approved(uid)
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = [[InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"my_result_{t['id']}")] for t in tests]
    kb.append([back("user_stats")])
    await q.edit_message_text(
        "👤 Shaxsiy natijalar\nQaysi test natijasini ko'rmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(kb))

async def my_result_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    uid = q.from_user.id
    tid = int(q.data.replace("my_result_", ""))
    t   = db.get_pdf_test(tid)
    if not t: return
    results = db.get_user_results_for_test(uid, tid)
    kb = [[back("my_results")]]
    if not results:
        await q.edit_message_text(
            f"📝 {t['title']}\n\nBu testni hali yechmagansiz.",
            reply_markup=InlineKeyboardMarkup(kb)); return
    best    = max(results, key=lambda x: x["correct"])
    last    = results[0]
    max_b   = round(t["question_count"] * 3.1, 1)
    text = (
        f"👤 Shaxsiy natija\n{'━'*24}\n"
        f"📝 {t['title']}\n"
        f"🔢 Jami urinish: {len(results)} marta\n"
        f"{'━'*24}\n"
        f"🏆 Eng yaxshi:\n"
        f"  ✅ {best['correct']}/{t['question_count']} — {round(best['correct']*3.1,1)} ball "
        f"({round(best['correct']/t['question_count']*100)}%)\n"
        f"{'━'*24}\n"
        f"🕐 Oxirgi urinish:\n"
        f"  ✅ {last['correct']}/{t['question_count']} — {round(last['correct']*3.1,1)} ball "
        f"({round(last['correct']/t['question_count']*100)}%)\n"
    )
    if len(results) > 1:
        text += f"{'━'*24}\n📋 Barcha urinishlar:\n"
        for i, r in enumerate(results[:5]):
            text += f"  {i+1}. {round(r['correct']*3.1,1)} ball ({round(r['correct']/t['question_count']*100)}%) — {str(r.get('taken_at',''))[:10]}\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def public_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid) or is_approved(uid)
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = [[InlineKeyboardButton(f"🏆 {t['title']}", callback_data=f"pub_rating_{t['id']}")] for t in tests]
    kb.append([back("user_stats")])
    await q.edit_message_text(
        "🏆 Ommaviy reyting\nQaysi test reytingini ko'rmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(kb))

async def pub_rating_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    # pub_rating_ID formatidan ID olish
    raw = q.data.replace("pub_rating_", "")
    try:
        tid = int(raw)
    except:
        await q.answer("Xato!", show_alert=True); return
    t = db.get_pdf_test(tid)
    if not t: return
    ratings = db.get_test_rating(tid)
    kb = [[back("public_rating")]]
    if not ratings:
        await q.edit_message_text(
            f"🏆 {t['title']}\n\nHali hech kim bu testni yechmagan.",
            reply_markup=InlineKeyboardMarkup(kb)); return
    medals  = {0:"🥇",1:"🥈",2:"🥉"}
    max_b   = round(t["question_count"] * 3.1, 1)
    q_count = t["question_count"]
    text    = f"🏆 {t['title']}\n{'━'*24}\n👥 Ishtirokchilar: {len(ratings)} ta\n{'━'*24}\n"
    for i, r in enumerate(ratings[:20]):
        correct = r.get("correct") or 0
        total   = r.get("total") or q_count
        ball    = round(correct * 3.1, 1)
        pct     = round(correct / total * 100) if total else 0
        name    = r.get("full_name") or r.get("first_name","?")
        text   += f"{medals.get(i,str(i+1)+'.')} {name} — {ball}/{max_b} ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════
#  REFERRAL
# ═══════════════════════════════════════════════════════
async def my_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid)
    back_cb = "pro_menu" if prem else "free_menu"
    count   = db.get_referral_count(uid)
    needed  = int(S("ref_needed","10"))
    left    = needed - (count % needed) if count % needed != 0 else 0
    bot_me  = await context.bot.get_me()
    link    = f"https://t.me/{bot_me.username}?start=ref_{uid}"
    text = (
        f"🎁 Do'st taklif tizimi\n{'━'*24}\n\n"
        f"📊 Siz taklif qilganlar: {count} ta\n"
        f"🎯 Keyingi sovg'a uchun: {left} ta qoldi\n\n"
        f"📌 Qoida:\n"
        f"{needed} ta do'stingiz botga qo'shilsa —\n"
        f"sizga 7 kunlik 👑 PRO obuna sovg'a! 🎉\n\n"
        f"🔗 Taklif havolangiz:\n{link}"
    )
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[back(back_cb)]]))

# ═══════════════════════════════════════════════════════
#  ADMINGA MUROJAAT
# ═══════════════════════════════════════════════════════
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    back_cb = "pro_menu" if is_pro(uid) else "free_menu"
    context.user_data["step"]         = "waiting_contact"
    context.user_data["contact_back"] = back_cb
    await q.edit_message_text(
        "📩 Adminga murojaat\n\n"
        "💬 @legistman_uz — to'g'ridan-to'g'ri yozing\n\n"
        "✍️ Yoki murojaatingizni shu yerga yozing —\n"
        "admin 24 soat ichida ko'rib chiqadi:",
        reply_markup=InlineKeyboardMarkup([[back(back_cb)]]))

async def admin_reply_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    tid  = int(q.data.replace("reply_", ""))
    u    = db.get_user(tid)
    name = uname(u) if u else str(tid)
    context.user_data["step"]          = "admin_reply"
    context.user_data["reply_to_uid"]  = tid
    context.user_data["reply_to_name"] = name
    await q.edit_message_text(f"✍️ {name} ga javob yozing:\n\nBekor: /admin")

# ═══════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar",            callback_data="adm_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",       callback_data="adm_guides")],
        [InlineKeyboardButton("👥 Foydalanuvchilar",   callback_data="adm_users")],
        [InlineKeyboardButton("💎 To'lov so'rovlari",  callback_data="adm_payments")],
        [InlineKeyboardButton("📊 Statistika",         callback_data="adm_stats")],
        [InlineKeyboardButton("⚙️ Sozlamalar",         callback_data="adm_settings")],
        [InlineKeyboardButton("📢 Xabar yuborish",     callback_data="adm_broadcast")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text("🔧 Admin Panel", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text("🔧 Admin Panel", reply_markup=InlineKeyboardMarkup(kb))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data.clear()
    await show_admin_menu(update, context)

# ── TESTLAR ──────────────────────────────────────────
async def adm_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton("➕ Yangi test", callback_data="adm_add_test")]]
    for t in tests:
        kb.append([InlineKeyboardButton(
            f"{'🆓' if t.get('is_free') else '👑'} {t['title']}",
            callback_data=f"atv_{t['id']}")])
    kb.append([back("adm_back")])
    await q.edit_message_text("📝 Testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    if not t: return
    res   = db.get_test_rating(tid)
    ic    = "🆓 Bepul" if t.get("is_free") else "👑 PRO"
    tog   = "👑 PROga" if t.get("is_free") else "🆓 Bepulga"
    text  = (
        f"📝 {t['title']}\n{'━'*22}\n"
        f"❓ Savollar: {t['question_count']} ta\n"
        f"⏱ Vaqt: {t.get('time_limit',30)} daqiqa\n"
        f"🔑 Kalit: {t['answer_key']}\n"
        f"📌 Turi: {ic}\n"
        f"👥 Yechganlar: {len(res)} ta"
    )
    kb = [
        [InlineKeyboardButton(f"🔄 {tog} o'tkazish",    callback_data=f"att_{tid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish",  callback_data=f"atn_{tid}")],
        [InlineKeyboardButton("🔑 Kalitni yangilash",    callback_data=f"atk_{tid}")],
        [InlineKeyboardButton("⏱ Vaqtni o'zgartirish",  callback_data=f"att_time_{tid}")],
        [InlineKeyboardButton("📊 Natijalar/Reyting",   callback_data=f"atr_{tid}")],
        [InlineKeyboardButton("📦 Arxiv (kalit)",        callback_data=f"arv_{tid}")],
        [InlineKeyboardButton("🗑 O'chirish",            callback_data=f"atd_{tid}")],
        [back("adm_tests")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    db.update_pdf_test(tid, is_free=0 if t.get("is_free") else 1)
    q.data = f"atv_{tid}"; await adm_test_view(update, context)

async def adm_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    res = db.get_test_rating(tid)
    t   = db.get_pdf_test(tid)
    kb  = [[back(f"atv_{tid}")]]
    if not res:
        await q.edit_message_text("Hali hech kim yechmagan.", reply_markup=InlineKeyboardMarkup(kb)); return
    medals = {0:"🥇",1:"🥈",2:"🥉"}
    text = f"📊 {t['title']} — Reyting:\n{'━'*24}\n"
    for i, r in enumerate(res[:20]):
        ball = round(r["correct"] * 3.1, 1)
        pct  = round(r["correct"]/r["total"]*100) if r["total"] else 0
        name = r.get("full_name") or r.get("first_name","?")
        text += f"{medals.get(i,f'{i+1}.')} {name}: {r['correct']}/{r['total']} — {ball} ball ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_archive_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.replace("arv_", ""))
    t   = db.get_pdf_test(tid)
    if not t: await q.answer("Test topilmadi!", show_alert=True); return
    key = t.get("answer_key","")
    rows = []
    for i in range(0, len(key), 5):
        rows.append("  ".join(f"{i+j+1}.{c}" for j, c in enumerate(key[i:i+5])))
    text = (
        f"📦 Kalit arxivi\n{'━'*22}\n"
        f"📝 {t['title']}\n"
        f"❓ {t['question_count']} ta savol\n"
        f"{'━'*22}\n✅ To'g'ri javoblar:\n\n" + "\n".join(rows)
    )
    await q.edit_message_text(text[:4096], reply_markup=InlineKeyboardMarkup([[back(f"atv_{tid}")]]))

async def adm_test_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    await q.edit_message_text(
        f"⚠️ '{t['title']}' ni o'chirishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha", callback_data=f"atdc_{tid}"),
             InlineKeyboardButton("❌ Yo'q", callback_data=f"atv_{tid}")]]))

async def adm_test_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    db.delete_pdf_test(tid)
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_tests(update, context)

# ── QO'LLANMALAR (ADMIN) ─────────────────────────────
async def adm_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    guides = db.get_all_guides()
    kb = [[InlineKeyboardButton("➕ Yangi qo'llanma", callback_data="adm_add_guide")]]
    for g in guides:
        kb.append([InlineKeyboardButton(
            f"{'🆓' if g.get('is_free') else '👑'} {g['title']}",
            callback_data=f"agv_{g['id']}")])
    kb.append([back("adm_back")])
    await q.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_guide_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    if not g: return
    ic  = "🆓 Bepul" if g.get("is_free") else "👑 PRO"
    tog = "👑 PROga" if g.get("is_free") else "🆓 Bepulga"
    kb  = [
        [InlineKeyboardButton(f"🔄 {tog} o'tkazish",    callback_data=f"agt_{gid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish",  callback_data=f"agn_{gid}")],
        [InlineKeyboardButton("📝 Matnini o'zgartirish", callback_data=f"age_{gid}")],
        [InlineKeyboardButton("🗑 O'chirish",            callback_data=f"agd_{gid}")],
        [back("adm_guides")],
    ]
    preview = g['content'][:200] + "..." if len(g.get('content','')) > 200 else g.get('content','')
    await q.edit_message_text(
        f"📖 {g['title']}\n{'━'*20}\n📌 Turi: {ic}\n📄 Fayl: {'✅' if g.get('file_id') else '❌'}\n\n{preview}",
        reply_markup=InlineKeyboardMarkup(kb))

async def adm_guide_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    db.update_guide(gid, is_free=0 if g.get("is_free") else 1)
    q.data = f"agv_{gid}"; await adm_guide_view(update, context)

async def adm_guide_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    await q.edit_message_text(
        f"'{g['title']}' ni o'chirishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha", callback_data=f"agdc_{gid}"),
             InlineKeyboardButton("❌ Yo'q", callback_data=f"agv_{gid}")]]))

async def adm_guide_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    db.delete_guide(gid)
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_guides(update, context)

# ── FOYDALANUVCHILAR ─────────────────────────────────
async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "👥 Foydalanuvchilar:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👥 Barchasi",     callback_data="aul_all")],
            [InlineKeyboardButton("✅ Tasdiqlangan", callback_data="aul_approved")],
            [InlineKeyboardButton("👑 PRO",          callback_data="aul_pro")],
            [InlineKeyboardButton("⏳ Kutayotgan",   callback_data="aul_pending")],
            [back("adm_back")],
        ]))

async def adm_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query; await q.answer()
    ft = q.data.split("_")[1]
    users = db.get_users_by_status(None if ft == "all" else ft)
    icons = {"approved":"✅","pro":"👑","pending":"⏳","rejected":"❌","new":"🆕"}
    kb = []
    for u in users[:25]:
        ic = icons.get(u["status"],"👤")
        kb.append([InlineKeyboardButton(f"{ic} {uname(u)}", callback_data=f"aud_{u['user_id']}")])
    kb.append([back("adm_users")])
    await q.edit_message_text(f"👥 {ft} ({len(users)} ta):", reply_markup=InlineKeyboardMarkup(kb))

async def adm_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    u   = db.get_user(tid)
    if not u: return
    exp  = db.get_pro_expiry(tid)
    refs = db.get_referral_count(tid)
    badges, cnt = db.get_user_badges(tid)
    text = (
        f"👤 {uname(u)}\n🆔 {u['user_id']}\n"
        f"📛 @{u['username'] or 'yoq'}\n"
        f"📌 Status: {u['status']}\n"
        f"📊 Yechgan testlar: {cnt} ta\n"
        f"🎁 Taklif qilinganlar: {refs} ta\n"
    )
    if badges: text += f"🏅 Nishonlar: {' '.join(badges)}\n"
    if exp: text += f"👑 PRO: {exp.strftime('%d.%m.%Y')} gacha\n"
    kb = []
    if u["status"] != "approved":
        kb.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"aua_ok_{tid}")])
    if u["status"] != "pro":
        kb.append([InlineKeyboardButton("👑 PRO berish (30 kun)", callback_data=f"aua_prem_{tid}")])
    if u["status"] == "pro":
        kb.append([InlineKeyboardButton("🚫 PROdan chiqarish", callback_data=f"aua_unprem_{tid}")])
    if u["status"] not in ("rejected","new"):
        kb.append([InlineKeyboardButton("🚫 Botdan chiqarish", callback_data=f"aua_kick_{tid}")])
    kb.append([InlineKeyboardButton("🔄 Qayta ro'yxatdan o'tkazish", callback_data=f"aua_reset_{tid}")])
    kb.append([back("aul_all")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, action, tid_str = q.data.split("_", 2)
    tid  = int(tid_str)
    days = int(S("pro_days","30"))
    msg  = ""
    if action == "ok":
        db.set_user_status(tid, "approved")
        try: await context.bot.send_message(tid, "✅ Botdan foydalanishga ruxsat berildi! /start bosing.")
        except: pass
        msg = "✅ Tasdiqlandi!"
    elif action == "prem":
        exp = now() + timedelta(days=days)
        db.set_pro(tid, exp)
        try: await context.bot.send_message(tid, f"👑 PRO berildi! {exp.strftime('%d.%m.%Y')} gacha. /start bosing.")
        except: pass
        msg = "👑 PRO berildi!"
    elif action == "unprem":
        db.remove_pro(tid)
        try: await context.bot.send_message(tid, "ℹ️ PRO obunangiz bekor qilindi.")
        except: pass
        msg = "PRO olib tashlandi!"
    elif action == "kick":
        db.set_user_status(tid, "rejected")
        try: await context.bot.send_message(tid, "🚫 Botdan foydalanish huquqingiz bekor qilindi.")
        except: pass
        msg = "🚫 Chiqarildi!"
    elif action == "reset":
        db.reset_user(tid)
        try: await context.bot.send_message(tid, "🔄 Ma'lumotlaringiz o'chirildi. /start bosing.")
        except: pass
        msg = "🔄 Reset qilindi!"
    await q.answer(msg, show_alert=True)
    q.data = f"aud_{tid}"; await adm_user_detail(update, context)

# ── TO'LOV SO'ROVLARI ────────────────────────────────
async def adm_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    pays = db.get_pending_payments()
    kb   = [[InlineKeyboardButton(f"💳 {uname(p)}", callback_data=f"aud_{p['user_id']}")] for p in pays]
    kb.append([back("adm_back")])
    await q.edit_message_text(
        f"💎 Kutayotgan to'lovlar: {len(pays)} ta" if pays else "✅ Kutayotgan to'lovlar yo'q.",
        reply_markup=InlineKeyboardMarkup(kb))

# ── STATISTIKA (ADMIN) ───────────────────────────────
async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q  = update.callback_query; await q.answer()
    s  = db.get_stats()
    t  = now().strftime("%d.%m.%Y %H:%M")
    await q.edit_message_text(
        f"📊 Statistika\n{'━'*24}\n🕐 {t}\n{'━'*24}\n"
        f"👥 Jami: {s['total_users']}\n✅ Tasdiqlangan: {s['approved_users']}\n"
        f"👑 PRO: {s['pro_users']}\n⏳ Kutayotgan: {s['pending_users']}\n"
        f"🆕 Bugun: {s['today_users']}\n{'━'*24}\n"
        f"📝 Testlar: {s['total_tests']}\n📚 Qo'llanmalar: {s['total_guides']}\n"
        f"🏆 Jami natijalar: {s['total_results']}\n📈 Bugungi: {s['today_results']}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Yangilash",              callback_data="adm_stats")],
            [InlineKeyboardButton("👥 So'nggi a'zolar",        callback_data="adm_last_users")],
            [InlineKeyboardButton("🏆 Umumiy reyting",         callback_data="adm_rating_all")],
            [InlineKeyboardButton("📝 Test bo'yicha reyting",  callback_data="adm_rating_test")],
            [back("adm_back")],
        ]))

async def adm_last_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    users = db.get_users_by_status(None)[:15]
    icons = {"approved":"✅","pro":"👑","pending":"⏳","rejected":"❌","new":"🆕"}
    parts = [f"👥 So'nggi a'zolar:\n{'━'*24}"]
    for u in users:
        ic   = icons.get(u["status"],"👤")
        date = str(u.get("joined_at",""))[:10]
        parts.append(f"{ic} {uname(u)} (@{u['username'] or 'yoq'}) — {date}")
    await q.edit_message_text(
        "\n".join(parts),
        reply_markup=InlineKeyboardMarkup([[back("adm_stats")]]))

async def adm_rating_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ratings = db.get_overall_rating()
    kb = [[back("adm_stats")]]
    if not ratings:
        await q.edit_message_text("Hali natijalar yo'q.", reply_markup=InlineKeyboardMarkup(kb)); return
    medals = {0:"🥇",1:"🥈",2:"🥉"}
    text = f"🏆 Umumiy reyting:\n{'━'*24}\n"
    for i, r in enumerate(ratings[:20]):
        ball = round(r["correct"] * 3.1, 1)
        name = r.get("full_name") or r.get("first_name","?")
        text += f"{medals.get(i,f'{i+1}.')} {name} — {ball} ball ({r['test_title']})\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_rating_test_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"atr_{t['id']}")] for t in tests]
    kb.append([back("adm_stats")])
    await q.edit_message_text("Test reytingini tanlang:", reply_markup=InlineKeyboardMarkup(kb))

# ── SOZLAMALAR ───────────────────────────────────────
async def adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    price = S("pro_price","349 000"); card = S("card_number"); owner = S("card_owner")
    ch    = S("channel","@legistman")
    sm    = db.get_start_message()
    photo = "✅ Bor" if sm and sm.get("photo_id") else "❌ Yo'q"
    await q.edit_message_text(
        f"⚙️ Sozlamalar\n{'━'*22}\n"
        f"💰 PRO narx: {price} so'm\n💳 Karta: {card}\n"
        f"👤 Egasi: {owner}\n📢 Kanal: {ch}\n🖼 Start rasmi: {photo}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Narxni o'zgartirish",    callback_data="set_price")],
            [InlineKeyboardButton("💳 Karta raqami",           callback_data="set_card")],
            [InlineKeyboardButton("👤 Karta egasi",            callback_data="set_owner")],
            [InlineKeyboardButton("📢 Kanal username",         callback_data="set_channel")],
            [InlineKeyboardButton("📝 Start xabarini tahrirlash", callback_data="set_starttext")],
            [InlineKeyboardButton("🖼 Start rasmi yuklash",    callback_data="set_startphoto")],
            [InlineKeyboardButton("🗑 Start rasmini o'chirish", callback_data="set_startphoto_del")],
            [back("adm_back")],
        ]))

async def adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "broadcast"
    await q.edit_message_text("📢 Xabar matnini yozing:\n\nBekor: /admin")

# ═══════════════════════════════════════════════════════
#  RASM HANDLERI
# ═══════════════════════════════════════════════════════
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    step = context.user_data.get("step","")
    photo = update.message.photo
    if not photo: return

    # To'lov cheki
    if step == "waiting_proof":
        user = update.effective_user
        u    = db.get_user(uid)
        name = uname(u) if u else user.first_name
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏")
        kb = [[InlineKeyboardButton(f"✅ Tasdiqlash", callback_data=f"pay_ok_{uid}"),
               InlineKeyboardButton(f"❌ Rad etish",  callback_data=f"pay_no_{uid}")]]
        await context.bot.send_photo(
            ADMIN_ID, photo[-1].file_id,
            caption=f"💎 Yangi to'lov!\n\n👤 {name}\n🆔 {uid}\n📛 @{user.username or 'yoq'}",
            reply_markup=InlineKeyboardMarkup(kb))
        db.add_payment_request(uid)
        return

    # Start rasmi (admin)
    if is_admin(uid) and step in ("set_startphoto",):
        db.update_start_message(photo_id=photo[-1].file_id)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Start rasmi yangilandi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings")]]))

# ═══════════════════════════════════════════════════════
#  PDF HANDLERI
# ═══════════════════════════════════════════════════════
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    step = context.user_data.get("step","")
    doc  = update.message.document
    if not doc: return
    if step == "waiting_pdf_file":
        context.user_data["pdf_file_id"] = doc.file_id
        context.user_data["step"]        = "pdf_key"
        n = context.user_data.get("pdf_count",30)
        await update.message.reply_text(f"✅ PDF qabul qilindi!\n\n{n} ta javob kalitini yozing (ABCD):")
    elif step == "waiting_guide_file":
        context.user_data["guide_file_id"]  = doc.file_id
        context.user_data["guide_content"]  = doc.file_name or "PDF fayl"
        context.user_data["step"] = "add_guide_type"
        kb = [[InlineKeyboardButton("🆓 Bepul", callback_data="guide_type_free"),
               InlineKeyboardButton("👑 PRO",   callback_data="guide_type_pro")]]
        await update.message.reply_text(
            f"✅ PDF qabul qilindi: {doc.file_name}\n\nQo'llanma turi:",
            reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════
#  MATN XABARLARI
# ═══════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    step = context.user_data.get("step","")
    txt  = (update.message.text or "").strip()

    # Admin reply
    if step == "admin_reply" and is_admin(uid):
        tid  = context.user_data.get("reply_to_uid")
        name = context.user_data.get("reply_to_name","")
        context.user_data.clear()
        if tid:
            try:
                await context.bot.send_message(
                    tid, f"📬 Admin javobi:\n{'━'*22}\n{txt}")
                await update.message.reply_text(
                    f"✅ Javob yuborildi → {name}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]))
            except:
                await update.message.reply_text("❌ Xabar yuborib bo'lmadi.")
        return

    # Yangi foydalanuvchi ro'yxati
    if step == "waiting_fullname":
        if len(txt.split()) < 2:
            await update.message.reply_text(
                "To'liq ism va familiyangizni kiriting.\nMasalan: Mallayev Ozodbek"); return
        db.add_user(uid, update.effective_user.username or "", update.effective_user.first_name, txt)
        # Referral
        ref_id = context.user_data.get("ref_id")
        if ref_id and not db.referral_exists(uid):
            db.add_referral(ref_id, uid)
            ref_count = db.get_referral_count(ref_id)
            needed    = int(S("ref_needed","10"))
            if ref_count >= needed and ref_count % needed == 0:
                exp = now() + timedelta(days=7)
                db.set_pro(ref_id, exp)
                try:
                    await context.bot.send_message(
                        ref_id,
                        f"🎁 Tabrik! {needed} ta do'stingiz qo'shildi!\n"
                        f"7 kunlik 👑 PRO obuna sovg'a! {exp.strftime('%d.%m.%Y')} gacha.")
                except: pass
        context.user_data.clear()
        # Adminga bildirishnoma
        try:
            tg_name = update.effective_user.first_name or ""
            tg_user = update.effective_user.username or "yoq"
            await context.bot.send_message(
                ADMIN_ID,
                "🆕 Yangi a'zo!\n" + "━"*20 + "\n"
                f"👤 Kiritilgan ism: {txt}\n"
                f"📱 Telegram ismi: {tg_name}\n"
                f"🆔 ID: {uid}\n"
                f"📛 @{tg_user}")
        except: pass
        await show_welcome(update, context)
        return
    # To'lov cheki (fayl)
    if step == "waiting_proof":
        doc = update.message.document
        if doc:
            user = update.effective_user
            u    = db.get_user(uid)
            name = uname(u) if u else user.first_name
            context.user_data.clear()
            await update.message.reply_text("✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏")
            kb = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{uid}"),
                   InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_no_{uid}")]]
            await context.bot.send_document(
                ADMIN_ID, doc.file_id,
                caption=f"💎 Yangi to'lov (fayl)!\n\n👤 {name}\n🆔 {uid}\n📛 @{user.username or 'yoq'}",
                reply_markup=InlineKeyboardMarkup(kb))
            db.add_payment_request(uid)
        else:
            await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return

    # Murojaat
    if step == "waiting_contact":
        back_cb = context.user_data.get("contact_back","free_menu")
        u       = db.get_user(uid)
        name    = uname(u) if u else str(uid)
        context.user_data.clear()
        kb_admin = [[InlineKeyboardButton(f"↩️ {name} ga javob", callback_data=f"reply_{uid}")]]
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Yangi murojaat!\n{'━'*22}\n"
            f"👤 {name}\n🆔 {uid}\n📛 @{update.effective_user.username or 'yoq'}\n"
            f"{'━'*22}\n💬 {txt}",
            reply_markup=InlineKeyboardMarkup(kb_admin))
        await update.message.reply_text(
            "✅ Murojaatingiz adminga yuborildi! 🙏\n\nAdmin 24 soat ichida ko'rib chiqadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Yana murojaat", callback_data="contact_admin")],
                [InlineKeyboardButton("🏠 Menyuga qaytish", callback_data=back_cb)],
            ]))
        return

    # Test javoblari
    if step == "waiting_answers":
        await handle_test_answers(update, context); return

    if not is_admin(uid): return

    # ── ADMIN AMALLAR ──────────────────────────────────────────────────
    if step == "pdf_title":
        context.user_data["pdf_title"] = txt
        context.user_data["step"] = "pdf_count"
        await update.message.reply_text(f"✅ Nom: {txt}\n\nNechta savol? (Masalan: 30)")

    elif step == "pdf_count":
        try:
            n = int(txt)
            context.user_data["pdf_count"] = n
            context.user_data["step"]      = "pdf_time"
            await update.message.reply_text(f"Savollar: {n} ta\n\nTest vaqt chegarasi (daqiqada)? (Masalan: 30)")
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "pdf_time":
        try:
            t = int(txt)
            context.user_data["pdf_time"] = t
            context.user_data["step"]     = "pdf_type"
            kb = [[InlineKeyboardButton("🆓 Bepul", callback_data="pdf_type_free"),
                   InlineKeyboardButton("👑 PRO",   callback_data="pdf_type_pro")]]
            await update.message.reply_text(f"Vaqt: {t} daqiqa\n\nTest turi:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "waiting_pdf_file":
        await update.message.reply_text("Iltimos PDF faylni yuboring.")

    elif step == "pdf_key":
        n     = context.user_data.get("pdf_count",30)
        clean = re.sub(r"[^ABCD]", "", txt.upper())
        if len(clean) != n:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:"); return
        title   = context.user_data.get("pdf_title","")
        file_id = context.user_data.get("pdf_file_id","")
        is_free = context.user_data.get("pdf_is_free",0)
        t_limit = context.user_data.get("pdf_time",30)
        db.add_pdf_test(title, file_id, n, clean, is_free, t_limit)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📝 Testlarga", callback_data="adm_tests"),
               InlineKeyboardButton("🔧 Admin",     callback_data="adm_back")]]
        await update.message.reply_text(
            f"✅ Test qo'shildi!\n📝 {title}\n❓ {n} savol\n⏱ {t_limit} daqiqa",
            reply_markup=InlineKeyboardMarkup(kb))

    elif step == "rename_test":
        tid = context.user_data["edit_id"]
        db.update_pdf_test(tid, title=txt)
        context.user_data.clear()
        q_fake = type('obj', (object,), {'data': f"atv_{tid}"})()
        update.callback_query = q_fake
        kb = [[InlineKeyboardButton("📝 Testga qaytish", callback_data=f"atv_{tid}"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "update_key":
        n     = context.user_data.get("edit_cnt",30)
        clean = re.sub(r"[^ABCD]", "", txt.upper())
        if len(clean) != n:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:"); return
        tid = context.user_data["edit_id"]
        db.update_pdf_test(tid, answer_key=clean)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📝 Testga qaytish", callback_data=f"atv_{tid}"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await update.message.reply_text("✅ Kalit yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "update_time":
        try:
            t   = int(txt)
            tid = context.user_data["edit_id"]
            db.update_pdf_test(tid, time_limit=t)
            context.user_data.clear()
            kb = [[InlineKeyboardButton("📝 Testga qaytish", callback_data=f"atv_{tid}"),
                   InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
            await update.message.reply_text(f"✅ Vaqt yangilandi: {t} daqiqa", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing.")

    elif step == "add_guide_title":
        context.user_data["guide_title"] = txt
        context.user_data["step"]        = "waiting_guide_file"
        await update.message.reply_text(f"✅ Sarlavha: {txt}\n\nEndi PDF faylni yuboring:")

    elif step == "add_guide_content":
        context.user_data["guide_content"] = txt
        context.user_data["step"] = "add_guide_type"
        kb = [[InlineKeyboardButton("🆓 Bepul", callback_data="guide_type_free"),
               InlineKeyboardButton("👑 PRO",   callback_data="guide_type_pro")]]
        await update.message.reply_text("Qo'llanma turi:", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "edit_guide_title":
        gid = context.user_data["edit_id"]
        db.update_guide(gid, title=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📖 Qo'llanmaga", callback_data=f"agv_{gid}"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "edit_guide_content":
        gid = context.user_data["edit_id"]
        db.update_guide(gid, content=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📖 Qo'llanmaga", callback_data=f"agv_{gid}"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await update.message.reply_text("✅ Matn yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "set_starttext":
        db.update_start_message(text=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings")]]
        await update.message.reply_text("✅ Start xabari yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step in ("set_price","set_card","set_owner","set_channel"):
        key_map = {"set_price":"pro_price","set_card":"card_number","set_owner":"card_owner","set_channel":"channel"}
        db.set_setting(key_map[step], txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings")]]
        await update.message.reply_text(f"✅ Yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "broadcast":
        users = db.get_users_by_status(None)
        sent  = 0
        for u in users:
            if u["status"] in ("approved","pro"):
                try: await context.bot.send_message(u["user_id"], f"📢\n\n{txt}"); sent += 1
                except: pass
        context.user_data.clear()
        kb = [[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.", reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════
#  CALLBACK HANDLER (qolganlar)
# ═══════════════════════════════════════════════════════
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    data = q.data

    # Admin menyu
    if data == "adm_back":           await show_admin_menu(update, context)
    elif data == "adm_tests":        await adm_tests(update, context)
    elif data == "adm_guides":       await adm_guides(update, context)
    elif data == "adm_users":        await adm_users(update, context)
    elif data == "adm_payments":     await adm_payments(update, context)
    elif data == "adm_stats":        await adm_stats(update, context)
    elif data == "adm_settings":     await adm_settings(update, context)
    elif data == "adm_broadcast":    await adm_broadcast(update, context)
    elif data == "adm_last_users":   await adm_last_users(update, context)
    elif data == "adm_rating_all":   await adm_rating_all(update, context)
    elif data == "adm_rating_test":  await adm_rating_test_list(update, context)
    elif data == "adm_add_test":
        context.user_data["step"] = "pdf_title"
        await q.edit_message_text("📝 Yangi test nomi:\nBekor: /admin")
    elif data == "adm_add_guide":
        context.user_data["step"] = "add_guide_title"
        await q.edit_message_text("📚 Qo'llanma sarlavhasini yozing:\nBekor: /admin")

    # Test tahrirlash
    elif data.startswith("att_time_"):
        tid = int(data.replace("att_time_",""))
        context.user_data["step"] = "update_time"; context.user_data["edit_id"] = tid
        t   = db.get_pdf_test(tid)
        await q.edit_message_text(f"⏱ Yangi vaqt (daqiqada):\nHozirgi: {t.get('time_limit',30)} daqiqa\nBekor: /admin")
    elif data.startswith("atn_"):
        tid = int(data.split("_")[1])
        context.user_data["step"] = "rename_test"; context.user_data["edit_id"] = tid
        t   = db.get_pdf_test(tid)
        await q.edit_message_text(f"✏️ Yangi nom:\nHozirgi: {t['title']}\nBekor: /admin")
    elif data.startswith("atk_"):
        tid = int(data.split("_")[1])
        t   = db.get_pdf_test(tid)
        context.user_data["step"] = "update_key"
        context.user_data["edit_id"] = tid; context.user_data["edit_cnt"] = t["question_count"]
        await q.edit_message_text(f"🔑 Yangi kalit ({t['question_count']} ta ABCD harf):\nBekor: /admin")

    # Qo'llanma tahrirlash
    elif data.startswith("agn_"):
        gid = int(data.split("_")[1])
        context.user_data["step"] = "edit_guide_title"; context.user_data["edit_id"] = gid
        g   = db.get_guide(gid)
        await q.edit_message_text(f"✏️ Yangi sarlavha:\nHozirgi: {g['title']}\nBekor: /admin")
    elif data.startswith("age_"):
        gid = int(data.split("_")[1])
        context.user_data["step"] = "edit_guide_content"; context.user_data["edit_id"] = gid
        await q.edit_message_text("📝 Yangi matnni yozing:\nBekor: /admin")

    # Guide type
    elif data == "guide_type_free":
        db.add_guide(context.user_data.get("guide_title",""),
                     context.user_data.get("guide_content",""), 1,
                     context.user_data.get("guide_file_id",""))
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📚 Qo'llanmalarga", callback_data="adm_guides"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await q.edit_message_text("✅ Qo'llanma qo'shildi! (Bepul)", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "guide_type_pro":
        db.add_guide(context.user_data.get("guide_title",""),
                     context.user_data.get("guide_content",""), 0,
                     context.user_data.get("guide_file_id",""))
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📚 Qo'llanmalarga", callback_data="adm_guides"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        await q.edit_message_text("✅ Qo'llanma qo'shildi! (PRO)", reply_markup=InlineKeyboardMarkup(kb))

    # PDF test type
    elif data == "pdf_type_free":
        context.user_data["pdf_is_free"] = 1; context.user_data["step"] = "waiting_pdf_file"
        await q.edit_message_text("✅ Bepul tanlandi!\n\nEndi PDF faylni yuboring:")
    elif data == "pdf_type_pro":
        context.user_data["pdf_is_free"] = 0; context.user_data["step"] = "waiting_pdf_file"
        await q.edit_message_text("✅ PRO tanlandi!\n\nEndi PDF faylni yuboring:")

    # Sozlamalar
    elif data == "set_startphoto_del":
        db.update_start_message(photo_id="")
        await q.answer("✅ Rasm o'chirildi!", show_alert=True)
        await adm_settings(update, context)
    elif data in ("set_price","set_card","set_owner","set_channel","set_starttext","set_startphoto"):
        hints = {
            "set_price":     "💰 Yangi narxni yozing (masalan: 349 000):",
            "set_card":      "💳 Yangi karta raqamini yozing:",
            "set_owner":     "👤 Yangi karta egasi ismini yozing:",
            "set_channel":   "📢 Yangi kanal username yozing (masalan: @legistman):",
            "set_starttext": "📝 Yangi start xabari matnini yozing:",
            "set_startphoto":"🖼 Start uchun rasm yuboring:",
        }
        context.user_data["step"] = data
        await q.edit_message_text(hints[data] + "\n\nBekor: /admin")

# ═══════════════════════════════════════════════════════
#  PRO ESLATMA (har kuni)
# ═══════════════════════════════════════════════════════
async def pro_expiry_reminder(context):
    for u in db.get_users_by_status("pro"):
        exp = db.get_pro_expiry(u["user_id"])
        if not exp: continue
        days_left = (exp - now()).days
        if days_left == 3:
            try:
                await context.bot.send_message(
                    u["user_id"],
                    f"⏰ Eslatma!\n\n👑 PRO obunangiz {exp.strftime('%d.%m.%Y')} da tugaydi\n"
                    f"(3 kun qoldi)\n\nUzilmaslik uchun yangilang! 👇",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👑 PRO yangilash", callback_data="buy_pro")]]))
            except: pass

# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Umumiy
    app.add_handler(CallbackQueryHandler(check_join,      pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(back_welcome,    pattern=r"^back_welcome$"))
    app.add_handler(CallbackQueryHandler(about_bot,       pattern=r"^about_bot$"))
    app.add_handler(CallbackQueryHandler(free_menu,       pattern=r"^free_menu$"))
    app.add_handler(CallbackQueryHandler(free_tests_list, pattern=r"^free_tests$"))
    app.add_handler(CallbackQueryHandler(free_guides_list,pattern=r"^free_guides$"))
    app.add_handler(CallbackQueryHandler(pro_info,        pattern=r"^pro_info$"))
    app.add_handler(CallbackQueryHandler(pro_menu,        pattern=r"^pro_menu$"))
    app.add_handler(CallbackQueryHandler(pro_tests_list,  pattern=r"^pro_tests$"))
    app.add_handler(CallbackQueryHandler(pro_guides_list, pattern=r"^pro_guides$"))
    app.add_handler(CallbackQueryHandler(buy_pro,         pattern=r"^buy_pro$"))
    app.add_handler(CallbackQueryHandler(send_proof,      pattern=r"^send_proof$"))
    app.add_handler(CallbackQueryHandler(payment_action,  pattern=r"^pay_(ok|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(contact_admin,   pattern=r"^contact_admin$"))
    app.add_handler(CallbackQueryHandler(admin_reply_prompt, pattern=r"^reply_\d+$"))
    app.add_handler(CallbackQueryHandler(my_referral,     pattern=r"^my_referral$"))

    # Testlar
    app.add_handler(CallbackQueryHandler(show_pdf_test,      pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_prompt,      pattern=r"^submit_\d+$"))
    app.add_handler(CallbackQueryHandler(show_guide,         pattern=r"^guide_\d+$"))

    # Statistika
    app.add_handler(CallbackQueryHandler(user_stats,         pattern=r"^user_stats$"))
    app.add_handler(CallbackQueryHandler(my_results,         pattern=r"^my_results$"))
    app.add_handler(CallbackQueryHandler(my_result_detail,   pattern=r"^my_result_\d+$"))
    app.add_handler(CallbackQueryHandler(public_rating,      pattern=r"^public_rating$"))
    app.add_handler(CallbackQueryHandler(pub_rating_detail,  pattern=r"^pub_rating_\d+$"))

    # Admin testlar
    app.add_handler(CallbackQueryHandler(adm_test_view,      pattern=r"^atv_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_toggle,    pattern=r"^att_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_results,   pattern=r"^atr_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_archive_view,   pattern=r"^arv_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete,    pattern=r"^atd_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete_ok, pattern=r"^atdc_\d+$"))

    # Admin qo'llanmalar
    app.add_handler(CallbackQueryHandler(adm_guide_view,      pattern=r"^agv_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_guide_toggle,    pattern=r"^agt_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_guide_delete,    pattern=r"^agd_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_guide_delete_ok, pattern=r"^agdc_\d+$"))

    # Admin foydalanuvchilar
    app.add_handler(CallbackQueryHandler(adm_users_list,  pattern=r"^aul_(all|approved|pro|pending)$"))
    app.add_handler(CallbackQueryHandler(adm_user_detail, pattern=r"^aud_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_user_action, pattern=r"^aua_(ok|prem|unprem|kick|reset)_\d+$"))

    # Qolgan callbacklar
    app.add_handler(CallbackQueryHandler(cb_handler))

    # Fayllar va rasmlar
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # PRO eslatma scheduleri
    from datetime import time as dtime
    if app.job_queue:
        app.job_queue.run_daily(
            pro_expiry_reminder,
            time=dtime(hour=10, minute=0),
            name="pro_reminder")

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
