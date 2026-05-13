import logging, os, re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
db = Database()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "123456789"))

def S(key):        return db.get_setting(key) or ""
def is_admin(uid): return uid == ADMIN_ID

def is_premium(uid):
    u = db.get_user(uid)
    if not u or u["status"] != "premium": return False
    exp = db.get_premium_expiry(uid)
    if not exp or datetime.now() > exp:
        db.set_user_status(uid, "approved")
        return False
    return True

def is_approved(uid):
    return db.get_user_status(uid) in ("approved", "premium")

def exp_str(uid):
    exp = db.get_premium_expiry(uid)
    return exp.strftime("%d.%m.%Y") if exp else "?"

def uname(u): return u.get("full_name") or u.get("first_name") or "Foydalanuvchi"

# ═══════════════════════════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    if is_admin(user.id):
        db.add_user(user.id, user.username or "", user.first_name, user.first_name)
        await show_admin_menu(update, context)
        return
    ex = db.get_user(user.id)
    if ex and ex.get("full_name"):
        await show_welcome(update, context)
        return
    context.user_data["step"] = "waiting_fullname"
    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "Botdan foydalanish uchun ismingiz va familiyangizni to'liq kiriting:\n\n"
        "📝 Masalan: Mallayev Ozodbek"
    )

async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    u   = db.get_user(uid)
    fn  = uname(u) if u else ""
    prem = is_premium(uid)
    if prem:
        header = f"👑 Xush kelibsiz, {fn}!\n\n⭐️ Premium: {exp_str(uid)} gacha aktiv ✅"
    else:
        header = f"👋 Xush kelibsiz, {fn}!"
    kb = [[InlineKeyboardButton("ℹ️ Bot haqida ma'lumot", callback_data="about_bot")]]
    if prem:
        kb.append([InlineKeyboardButton("⭐️ Premium bo'lim", callback_data="premium_menu")])
    else:
        kb.append([InlineKeyboardButton("🆓 Bepul versiya",   callback_data="free_menu")])
        kb.append([InlineKeyboardButton("⭐️ Premium versiya", callback_data="premium_info")])
    if update.callback_query:
        await update.callback_query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(header, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT HAQIDA
# ═══════════════════════════════════════════════════════════════════════════════
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[InlineKeyboardButton("⬅️ Orqaga qaytish", callback_data="back_welcome")]]
    await q.edit_message_text(
        "🤖 Xush kelibsiz!\n\n"
        "Bu bot @legistman kanaliga tegishli hisoblanadi! 📚\n\n"
        "Bu yerda siz BMBA darajasidagi maxsus testlarni 📝 ishlashingiz\n"
        "va natijalarni tekshirishingiz mumkin ✅\n\n"
        "Shuningdek, maxsus o'quv qo'llanmalari 📖 bilan ham ta'minlanasiz.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  BEPUL MENYU
# ═══════════════════════════════════════════════════════════════════════════════
async def free_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests  = db.get_free_pdf_tests()
    guides = db.get_free_guides()
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    for g in guides:
        kb.append([InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")])
    if not tests and not guides:
        kb.append([InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_welcome")])
    txt = "🆓 Bepul bo'lim\n\n"
    txt += "Testlar va qo'llanmalar mavjud:" if (tests or guides) else "Hozircha bepul kontent yo'q."
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  PREMIUM INFO & MENYU
# ═══════════════════════════════════════════════════════════════════════════════
async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    price = S("premium_price")
    days  = S("premium_days")
    kb = [
        [InlineKeyboardButton("💳 To'lov qilish", callback_data="buy_premium")],
        [InlineKeyboardButton("⬅️ Orqaga",        callback_data="back_welcome")],
    ]
    await q.edit_message_text(
        f"⭐️ Premium versiya\n\n"
        f"✅ Barcha testlar\n"
        f"✅ Barcha qo'llanmalar\n"
        f"✅ Batafsil xato tahlili\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n\n"
        f"To'lov qilish uchun quyidagi tugmani bosing 👇",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    kb = [
        [InlineKeyboardButton("📝 Testlar",      callback_data="menu_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar", callback_data="menu_guides")],
        [InlineKeyboardButton("📊 Natijalarim",  callback_data="menu_results")],
        [InlineKeyboardButton("⬅️ Orqaga",       callback_data="back_welcome")],
    ]
    await q.edit_message_text(
        f"⭐️ Premium bo'lim\n\n👑 Premium: {exp_str(uid)} gacha aktiv",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  TO'LOV
# ═══════════════════════════════════════════════════════════════════════════════
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if is_premium(uid):
        await q.answer("Siz allaqachon premium foydalanuvchisiz!", show_alert=True)
        return
    price = S("premium_price")
    days  = S("premium_days")
    card  = S("card_number")
    owner = S("card_owner")
    kb = [
        [InlineKeyboardButton("✅ Chek yuboraman", callback_data="send_payment_proof")],
        [InlineKeyboardButton("⬅️ Orqaga",         callback_data="premium_info")],
    ]
    await q.edit_message_text(
        f"💳 To'lov ma'lumotlari\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n\n"
        f"Karta raqami:\n`{card}`\n"
        f"Karta egasi: {owner}\n\n"
        f"📋 Qadamlar:\n"
        f"1️⃣ Kartaga {price} so'm o'tkering\n"
        f"2️⃣ To'lov chekini (screenshot) saqlang\n"
        f"3️⃣ Quyidagi tugmani bosib chekni yuboring\n"
        f"4️⃣ Admin 24 soat ichida ko'rib chiqadi ✅",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def send_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_payment_proof"
    await q.edit_message_text("📸 To'lov chekini yuboring (rasm yoki screenshot).\n\nBekor: /start")

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_payment_proof": return False
    user  = update.effective_user
    photo = update.message.photo
    doc   = update.message.document
    if not photo and not doc:
        await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return True
    context.user_data.clear()
    await update.message.reply_text("✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏")
    u    = db.get_user(user.id)
    name = uname(u) if u else user.first_name
    kb = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{user.id}"),
        InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_no_{user.id}"),
    ]]
    cap = f"💎 Yangi to'lov so'rovi!\n\n👤 {name}\n🆔 {user.id}\n📛 @{user.username or 'yoq'}"
    if photo:
        await context.bot.send_photo(ADMIN_ID, photo[-1].file_id, caption=cap, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_document(ADMIN_ID, doc.file_id, caption=cap, reply_markup=InlineKeyboardMarkup(kb))
    db.add_payment_request(user.id)
    return True

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    action, tid = q.data.split("_")[1], int(q.data.split("_")[2])
    days = int(S("premium_days") or "30")
    old  = q.message.caption or q.message.text or ""
    if action == "ok":
        exp = datetime.now() + timedelta(days=days)
        db.set_premium(tid, exp)
        try: await q.edit_message_caption(old + f"\n\n✅ Tasdiqlandi! {exp.strftime('%d.%m.%Y')} gacha")
        except: await q.edit_message_text(old + f"\n\n✅ Tasdiqlandi!")
        await context.bot.send_message(tid, f"🎉 Premium faollashtirildi!\n\n👑 {days} kun ({exp.strftime('%d.%m.%Y')} gacha)\n\n/start bosing.")
    else:
        try: await q.edit_message_caption(old + "\n\n❌ Rad etildi.")
        except: await q.edit_message_text(old + "\n\n❌ Rad etildi.")
        await context.bot.send_message(tid, "😔 To'lovingiz tasdiqlanmadi.")

# ═══════════════════════════════════════════════════════════════════════════════
#  TESTLAR
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_premium(uid) or is_approved(uid)
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = []
    for t in tests:
        ic = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{ic} {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")])
    await q.edit_message_text("📝 Testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_pdf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid     = q.from_user.id
    test_id = int(q.data.split("_")[2])
    test    = db.get_pdf_test(test_id)
    if not test: return
    if not test.get("is_free") and not is_approved(uid):
        kb = [[InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium"),
               InlineKeyboardButton("⬅️ Orqaga",        callback_data="free_menu")]]
        await q.edit_message_text("⭐️ Bu test faqat premium uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    n = test.get("question_count", 30)
    context.user_data["step"] = "active_test"
    context.user_data["tid"]  = test_id
    context.user_data["tcnt"] = n
    await context.bot.send_document(
        q.message.chat_id, test["file_id"],
        caption=f"📝 {test['title']}\n❓ Savollar: {n} ta\n\nTestni yechib bo'lgach javob yuboring."
    )
    kb = [[InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_test_{test_id}")]]
    await context.bot.send_message(q.message.chat_id, "Tayyor bo'ldingizmi?", reply_markup=InlineKeyboardMarkup(kb))

async def submit_test_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[2])
    test    = db.get_pdf_test(test_id)
    n = test.get("question_count", 30) if test else 30
    context.user_data["step"] = "waiting_answers"
    context.user_data["tid"]  = test_id
    context.user_data["tcnt"] = n
    await q.edit_message_text(
        f"✏️ {n} ta javobni yuboring!\n\n"
        f"Faqat harflar ketma-ket (ABCD):\n"
        f"Masalan: ABCDABCDABCD...\n\n(Jami {n} ta harf)"
    )

async def handle_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_answers": return False
    uid     = update.effective_user.id
    test_id = context.user_data["tid"]
    n       = context.user_data["tcnt"]
    clean   = re.sub(r"[^ABCD]", "", update.message.text.strip().upper())
    if len(clean) != n:
        await update.message.reply_text(f"⚠️ {len(clean)} ta javob, {n} ta kerak. Qaytadan yuboring:")
        return True
    key = re.sub(r"[^ABCD]", "", (db.get_answer_key(test_id) or "").upper())
    if not key:
        await update.message.reply_text("⚠️ Kalit kiritilmagan. Adminga murojaat qiling.")
        return True
    correct  = sum(u == k for u, k in zip(clean, key))
    wrong    = n - correct
    ball     = round(correct * 3.1, 1)
    max_ball = round(n * 3.1, 1)
    pct      = round(correct / n * 100)
    if pct >= 85:   baho = "🏆 Ajoyib!"
    elif pct >= 70: baho = "👍 Yaxshi!"
    elif pct >= 50: baho = "📚 Qoniqarli"
    else:           baho = "💪 Ko'proq mashq kerak"

    xato_lines = [f"  {i+1}-savol: Siz ❌{u}  →  To'g'ri ✅{k}"
                  for i, (u, k) in enumerate(zip(clean, key)) if u != k]
    togri_list = "\n".join(f"  {i+1}–{k}" for i, k in enumerate(key))

    # Test bepulmi yoki premium?
    test_obj = db.get_pdf_test(test_id)
    is_free_test = test_obj.get("is_free", 0) if test_obj else 0
    prem_user = is_premium(uid)

    if is_free_test and not prem_user:
        # Bepul test — faqat statistika, tahlil yo'q
        result = (
            f"📊 Test natijasi\n{'─'*26}\n"
            f"📋 Jami savollar:    {n} ta\n"
            f"✅ To'g'ri javoblar: {correct} ta\n"
            f"❌ Xato javoblar:    {wrong} ta\n"
            f"🏅 Ball: {ball} / {max_ball}\n"
            f"📈 Foiz: {pct}%\n"
            f"🎯 {baho}\n\n"
            f"{'─'*26}\n"
            f"💡 Barcha to'g'ri javoblar va batafsil\n"
            f"xato tahlilini ko'rish uchun:\n\n"
            f"⭐️ Premium versiyani oling!"
        )
        db.save_pdf_result(uid, test_id, correct, n, clean)
        context.user_data.clear()
        kb = [
            [InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium")],
            [InlineKeyboardButton("📝 Yana test",      callback_data="menu_tests")],
            [InlineKeyboardButton("🏠 Bosh menyu",     callback_data="back_welcome")],
        ]
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))
    else:
        # Premium test — to'liq tahlil
        result = (
            f"📊 Test natijasi\n{'─'*26}\n"
            f"📋 Jami savollar:    {n} ta\n"
            f"✅ To'g'ri javoblar: {correct} ta\n"
            f"❌ Xato javoblar:    {wrong} ta\n"
            f"🏅 Ball: {ball} / {max_ball}\n"
            f"📈 Foiz: {pct}%\n"
            f"🎯 {baho}\n"
        )
        if xato_lines:
            result += f"\n{'─'*26}\n❌ Xato savollar ({wrong} ta):\n" + "\n".join(xato_lines[:30])
        result += f"\n\n{'─'*26}\n✅ To'g'ri javoblar kaliti:\n{togri_list}"
        db.save_pdf_result(uid, test_id, correct, n, clean)
        context.user_data.clear()
        kb = [
            [InlineKeyboardButton("📝 Yana test",  callback_data="menu_tests")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")],
        ]
        await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))
    return True

# ═══════════════════════════════════════════════════════════════════════════════
#  QO'LLANMALAR
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    # Premium foydalanuvchilar uchun kanal havolasi
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
    await q.edit_message_text(
        "📚 Qo'llanmalar\n\n"
        "Siz premium foydalanuvchisi hisoblanganingiz uchun\n"
        "@legistman_uz profili bilan bog'laning —\n"
        "sizni QO'LLANMA BAZA kanaliga qo'shib qo'yadi 📖",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    g = db.get_guide(int(q.data.split("_")[1]))
    if not g: return
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="free_menu")]]
    file_id = g.get("file_id","")
    if file_id:
        # Avval faylni yuborish, keyin matn
        await context.bot.send_document(
            q.message.chat_id, file_id,
            caption=f"📖 {g['title']}"
        )
        if g.get("content") and g["content"] != g["title"]:
            await context.bot.send_message(
                q.message.chat_id,
                g["content"][:4000],
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await context.bot.send_message(q.message.chat_id, "⬅️", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await q.edit_message_text(f"📖 {g['title']}\n\n{g['content']}"[:4000], reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  NATIJALAR
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    results = db.get_user_pdf_results(q.from_user.id)
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
    if not results:
        await q.edit_message_text("Hali test yechmagansiz.", reply_markup=InlineKeyboardMarkup(kb))
        return
    r = results[0]
    wrong = r["total"] - r["correct"]
    ball  = round(r["correct"] * 3.1, 1)
    maxb  = round(r["total"] * 3.1, 1)
    pct   = round(r["correct"] / r["total"] * 100) if r["total"] else 0
    text = (
        f"📊 Oxirgi test natijasi\n{'─'*26}\n"
        f"📝 {r['test_title']}\n"
        f"📋 Jami: {r['total']} ta\n"
        f"✅ To'g'ri: {r['correct']} ta\n"
        f"❌ Xato: {wrong} ta\n"
        f"🏅 Ball: {ball} / {maxb}\n"
        f"📈 Foiz: {pct}%\n"
    )
    if len(results) > 1:
        text += "\n📌 Oldingi natijalar:\n"
        for r2 in results[1:6]:
            b2 = round(r2["correct"] * 3.1, 1)
            p2 = round(r2["correct"] / r2["total"] * 100) if r2["total"] else 0
            text += f"  • {r2['test_title']}: {b2} ball ({p2}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════════
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar",           callback_data="adm_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",      callback_data="adm_guides")],
        [InlineKeyboardButton("👥 Foydalanuvchilar",  callback_data="adm_users")],
        [InlineKeyboardButton("💎 To'lov so'rovlari", callback_data="adm_payments")],
        [InlineKeyboardButton("📊 Statistika/Reyting",callback_data="adm_stats")],
        [InlineKeyboardButton("⚙️ Sozlamalar",        callback_data="adm_settings")],
        [InlineKeyboardButton("📢 Xabar yuborish",    callback_data="adm_broadcast")],
    ]
    txt = "🔧 Admin Panel"
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data.clear()
    await show_admin_menu(update, context)

# ── TESTLAR ──────────────────────────────────────────────────────────────────
async def adm_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton("➕ Yangi test", callback_data="adm_test_add")]]
    for t in tests:
        ic = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{ic} {t['title']}", callback_data=f"atv_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")])
    await q.edit_message_text("📝 Testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid  = int(q.data.split("_")[1])
    t    = db.get_pdf_test(tid)
    if not t: return
    res  = db.get_test_rating(tid)
    ic   = "🆓 Bepul" if t.get("is_free") else "⭐️ Premium"
    tog  = "⭐️ Premiumga" if t.get("is_free") else "🆓 Bepulga"
    text = (
        f"📝 {t['title']}\n{'─'*22}\n"
        f"❓ Savollar: {t['question_count']} ta\n"
        f"🔑 Kalit: {t['answer_key']}\n"
        f"📌 Turi: {ic}\n"
        f"👥 Yechganlar: {len(res)} ta"
    )
    kb = [
        [InlineKeyboardButton(f"🔄 {tog} o'tkazish",   callback_data=f"att_{tid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data=f"atn_{tid}")],
        [InlineKeyboardButton("🔑 Kalitni yangilash",   callback_data=f"atk_{tid}")],
        [InlineKeyboardButton("📊 Natijalar/Reyting",  callback_data=f"atr_{tid}")],
        [InlineKeyboardButton("🗑 O'chirish",           callback_data=f"atd_{tid}")],
        [InlineKeyboardButton("⬅️ Orqaga",             callback_data="adm_tests")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    db.update_pdf_test(tid, is_free=0 if t.get("is_free") else 1)
    q.data = f"atv_{tid}"; await adm_test_view(update, context)

async def adm_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    res = db.get_test_rating(tid)
    t   = db.get_pdf_test(tid)
    kb  = [[InlineKeyboardButton("⬅️ Orqaga", callback_data=f"atv_{tid}")]]
    if not res:
        await q.edit_message_text("Hali hech kim yechmagan.", reply_markup=InlineKeyboardMarkup(kb))
        return
    medals = ["🥇","🥈","🥉"]
    text = f"🏆 {t['title']} — Reyting:\n{'─'*24}\n"
    for i, r in enumerate(res[:20]):
        medal = medals[i] if i < 3 else f"{i+1}."
        ball  = round(r["correct"] * 3.1, 1)
        pct   = round(r["correct"] / r["total"] * 100) if r["total"] else 0
        name  = r.get("full_name") or r.get("first_name","?")
        text += f"{medal} {name}: {r['correct']}/{r['total']} — {ball} ball ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    kb  = [[InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"atdc_{tid}"),
            InlineKeyboardButton("❌ Bekor",         callback_data=f"atv_{tid}")]]
    await q.edit_message_text(
        f"⚠️ '{t['title']}' ni o'chirishni tasdiqlaysizmi?\nBu amalni qaytarib bo'lmaydi!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_test_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    db.delete_pdf_test(tid)
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_tests(update, context)

async def adm_test_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "pdf_title"
    await q.edit_message_text("📝 Yangi test nomi:\nBekor: /admin")

async def adm_test_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    context.user_data["step"]    = "rename_test"
    context.user_data["edit_id"] = tid
    t = db.get_pdf_test(tid)
    await q.edit_message_text(f"✏️ Yangi nom yozing:\nHozirgi: {t['title']}\n\nBekor: /admin")

async def adm_test_newkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    context.user_data["step"]    = "update_key"
    context.user_data["edit_id"] = tid
    context.user_data["edit_cnt"]= t.get("question_count", 30)
    await q.edit_message_text(
        f"🔑 Yangi kalit:\nTest: {t['title']}\n{t['question_count']} ta harf (ABCD)\nBekor: /admin"
    )

# ── QO'LLANMALAR (ADMIN) ─────────────────────────────────────────────────────
async def adm_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    guides = db.get_all_guides()
    kb = [[InlineKeyboardButton("➕ Yangi qo'llanma", callback_data="adm_guide_add")]]
    for g in guides:
        ic = "🆓" if g.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{ic} {g['title']}", callback_data=f"agv_{g['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")])
    await q.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_guide_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    if not g: return
    ic  = "🆓 Bepul" if g.get("is_free") else "⭐️ Premium (faqat bepulda ko'rinadi)"
    tog = "⭐️ Premiumga" if g.get("is_free") else "🆓 Bepulga"
    kb  = [
        [InlineKeyboardButton(f"🔄 {tog} o'tkazish",    callback_data=f"agt_{gid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish",  callback_data=f"agn_{gid}")],
        [InlineKeyboardButton("📝 Matnini o'zgartirish", callback_data=f"age_{gid}")],
        [InlineKeyboardButton("🗑 O'chirish",            callback_data=f"agd_{gid}")],
        [InlineKeyboardButton("⬅️ Orqaga",              callback_data="adm_guides")],
    ]
    await q.edit_message_text(
        f"📖 {g['title']}\n{'─'*20}\n📌 Turi: {ic}\n\n{g['content'][:300]}{'...' if len(g['content'])>300 else ''}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_guide_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    db.update_guide(gid, is_free=0 if g.get("is_free") else 1)
    q.data = f"agv_{gid}"; await adm_guide_view(update, context)

async def adm_guide_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    kb  = [[InlineKeyboardButton("✅ Ha", callback_data=f"agdc_{gid}"),
            InlineKeyboardButton("❌ Bekor", callback_data=f"agv_{gid}")]]
    await q.edit_message_text(f"'{g['title']}' ni o'chirishni tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(kb))

async def adm_guide_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    db.delete_guide(gid)
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_guides(update, context)

# ── FOYDALANUVCHILAR ─────────────────────────────────────────────────────────
async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("👥 Barchasi",     callback_data="aul_all")],
        [InlineKeyboardButton("✅ Tasdiqlangan", callback_data="aul_approved")],
        [InlineKeyboardButton("⭐️ Premium",      callback_data="aul_premium")],
        [InlineKeyboardButton("⏳ Kutayotgan",   callback_data="aul_pending")],
        [InlineKeyboardButton("⬅️ Orqaga",      callback_data="adm_back")],
    ]
    await q.edit_message_text("👥 Foydalanuvchilar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ft    = q.data.split("_")[1]
    users = db.get_users_by_status(None if ft == "all" else ft)
    icons = {"approved":"✅","premium":"⭐️","pending":"⏳","rejected":"❌","new":"🆕"}
    kb    = []
    for u in users[:25]:
        ic = icons.get(u["status"], "👤")
        nm = uname(u)
        kb.append([InlineKeyboardButton(f"{ic} {nm}", callback_data=f"aud_{u['user_id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_users")])
    await q.edit_message_text(f"👥 {ft} ({len(users)} ta):", reply_markup=InlineKeyboardMarkup(kb))

async def adm_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    u   = db.get_user(tid)
    if not u: return
    exp  = db.get_premium_expiry(tid)
    text = (
        f"👤 {uname(u)}\n🆔 {u['user_id']}\n"
        f"📛 @{u['username'] or 'yoq'}\n📌 Status: {u['status']}\n"
    )
    if exp: text += f"⭐️ Premium: {exp.strftime('%d.%m.%Y')} gacha\n"
    kb = []
    if u["status"] != "approved":
        kb.append([InlineKeyboardButton("✅ Tasdiqlash",             callback_data=f"aua_ok_{tid}")])
    if u["status"] != "premium":
        kb.append([InlineKeyboardButton("⭐️ Premium berish (30 kun)", callback_data=f"aua_prem_{tid}")])
    if u["status"] == "premium":
        kb.append([InlineKeyboardButton("🚫 Premiumdan chiqarish",   callback_data=f"aua_unprem_{tid}")])
    if u["status"] not in ("rejected","new"):
        kb.append([InlineKeyboardButton("🚫 Botdan chiqarib yuborish", callback_data=f"aua_kick_{tid}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="aul_all")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts  = q.data.split("_")
    action = parts[2]
    tid    = int(parts[3])
    days   = int(S("premium_days") or "30")
    msg    = ""
    if action == "ok":
        db.set_user_status(tid, "approved")
        try: await context.bot.send_message(tid, "✅ Botdan foydalanishga ruxsat berildi! /start bosing.")
        except: pass
        msg = "✅ Tasdiqlandi!"
    elif action == "prem":
        exp = datetime.now() + timedelta(days=days)
        db.set_premium(tid, exp)
        try: await context.bot.send_message(tid, f"⭐️ Premium berildi! {exp.strftime('%d.%m.%Y')} gacha. /start bosing.")
        except: pass
        msg = "⭐️ Premium berildi!"
    elif action == "unprem":
        db.remove_premium(tid)
        try: await context.bot.send_message(tid, "ℹ️ Premium obunangiz bekor qilindi.")
        except: pass
        msg = "Premium olib tashlandi!"
    elif action == "kick":
        db.set_user_status(tid, "rejected")
        try: await context.bot.send_message(tid, "🚫 Botdan foydalanish huquqingiz bekor qilindi.")
        except: pass
        msg = "🚫 Chiqarib yuborildi!"
    await q.answer(msg, show_alert=True)
    q.data = f"aud_{tid}"
    await adm_user_detail(update, context)

# ── TO'LOV SO'ROVLARI ────────────────────────────────────────────────────────
async def adm_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pays = db.get_pending_payments()
    kb   = [[InlineKeyboardButton(f"💳 {uname(p)}", callback_data=f"aud_{p['user_id']}")] for p in pays]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")])
    txt = f"💎 Kutayotgan to'lovlar: {len(pays)} ta" if pays else "✅ Kutayotgan to'lovlar yo'q."
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

# ── STATISTIKA / REYTING ─────────────────────────────────────────────────────
async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    s = db.get_stats()
    kb = [
        [InlineKeyboardButton("🏆 Umumiy reyting",      callback_data="adm_rating_all")],
        [InlineKeyboardButton("📝 Test bo'yicha reyting", callback_data="adm_rating_test")],
        [InlineKeyboardButton("⬅️ Orqaga",              callback_data="adm_back")],
    ]
    await q.edit_message_text(
        f"📊 Statistika\n{'─'*24}\n"
        f"👥 Jami: {s['total_users']}\n✅ Tasdiqlangan: {s['approved_users']}\n"
        f"⭐️ Premium: {s['premium_users']}\n⏳ Kutayotgan: {s['pending_users']}\n\n"
        f"📝 Testlar: {s['total_pdf_tests']}\n📚 Qo'llanmalar: {s['total_guides']}\n"
        f"🏆 Jami natijalar: {s['total_results']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_rating_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ratings = db.get_overall_rating()
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_stats")]]
    if not ratings:
        await q.edit_message_text("Hali natijalar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    medals = ["🥇","🥈","🥉"]
    text = "🏆 Umumiy reyting:\n\n"
    for i, r in enumerate(ratings[:20]):
        medal = medals[i] if i < 3 else f"{i+1}."
        ball  = round(r["correct"] * 3.1, 1)
        name  = r.get("full_name") or r.get("first_name","?")
        text += f"{medal} {name} — {ball} ball ({r['test_title']})\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_rating_test_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"atr_{t['id']}")] for t in tests]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_stats")])
    await q.edit_message_text("Qaysi test reytingini ko'rmoqchisiz?", reply_markup=InlineKeyboardMarkup(kb))

# ── SOZLAMALAR ───────────────────────────────────────────────────────────────
async def adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    price = S("premium_price")
    days  = S("premium_days")
    card  = S("card_number")
    owner = S("card_owner")
    kb = [
        [InlineKeyboardButton("💰 Narxni o'zgartirish",    callback_data="set_price")],
        [InlineKeyboardButton("📅 Kunni o'zgartirish",     callback_data="set_days")],
        [InlineKeyboardButton("💳 Karta raqamini o'zgartirish", callback_data="set_card")],
        [InlineKeyboardButton("👤 Karta egasini o'zgartirish",  callback_data="set_owner")],
        [InlineKeyboardButton("⬅️ Orqaga",                 callback_data="adm_back")],
    ]
    await q.edit_message_text(
        f"⚙️ Sozlamalar\n{'─'*22}\n"
        f"💰 Premium narx: {price} so'm\n"
        f"📅 Muddat: {days} kun\n"
        f"💳 Karta: {card}\n"
        f"👤 Egasi: {owner}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ── BROADCAST ────────────────────────────────────────────────────────────────
async def adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "broadcast"
    await q.edit_message_text("📢 Xabar yozing (barcha foydalanuvchilarga):\n\nBekor: /admin")

# ═══════════════════════════════════════════════════════════════════════════════
#  MATN XABARLARI
# ═══════════════════════════════════════════════════════════════════════════════
async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if context.user_data.get("step") != "waiting_pdf_file": return
    context.user_data["pdf_file_id"] = update.message.document.file_id
    context.user_data["step"]        = "pdf_key"
    n = context.user_data.get("pdf_count", 30)
    await update.message.reply_text(f"✅ PDF qabul qilindi!\n\n{n} ta javob kalitini yozing (ABCD):")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    step = context.user_data.get("step", "")
    txt  = update.message.text.strip() if update.message and update.message.text else ""

    # Yangi foydalanuvchi
    if step == "waiting_fullname":
        if len(txt.split()) < 2:
            await update.message.reply_text("To'liq ism va familiyangizni kiriting.\nMasalan: Aliyev Jasur")
            return
        db.add_user(uid, update.effective_user.username or "", update.effective_user.first_name, txt)
        context.user_data.clear()
        await show_welcome(update, context)
        return

    if step == "waiting_payment_proof":
        await handle_payment_proof(update, context); return

    if step == "waiting_answers":
        await handle_test_answers(update, context); return

    if not is_admin(uid): return

    if step == "pdf_title":
        context.user_data["pdf_title"] = txt
        context.user_data["step"] = "pdf_count"
        await update.message.reply_text(f"✅ Nom: {txt}\n\nNechta savol? (Masalan: 30)")

    elif step == "pdf_count":
        try:
            n = int(txt)
            context.user_data["pdf_count"] = n
            context.user_data["step"]      = "pdf_type"
            kb = [[InlineKeyboardButton("🆓 Bepul",    callback_data="pdf_type_free"),
                   InlineKeyboardButton("⭐️ Premium", callback_data="pdf_type_premium")]]
            await update.message.reply_text(f"Savollar: {n} ta\n\nTest turi:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "waiting_pdf_file":
        await update.message.reply_text("Iltimos PDF faylni yuboring.")

    elif step == "pdf_key":
        n     = context.user_data.get("pdf_count", 30)
        clean = re.sub(r"[^ABCD]", "", txt.upper())
        if len(clean) != n:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:")
            return
        db.add_pdf_test(context.user_data.get("pdf_title",""), context.user_data.get("pdf_file_id",""),
                        n, clean, context.user_data.get("pdf_is_free", 0))
        context.user_data.clear()
        await update.message.reply_text(f"✅ Test qo'shildi!\n\n/admin")

    elif step == "rename_test":
        db.update_pdf_test(context.user_data["edit_id"], title=txt)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}\n\n/admin")

    elif step == "update_key":
        n     = context.user_data.get("edit_cnt", 30)
        clean = re.sub(r"[^ABCD]", "", txt.upper())
        if len(clean) != n:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:")
            return
        db.update_pdf_test(context.user_data["edit_id"], answer_key=clean)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Kalit yangilandi: {clean}\n\n/admin")

    elif step == "add_guide_title":
        context.user_data["guide_title"] = txt
        context.user_data["step"]        = "add_guide_content"
        await update.message.reply_text("Qo'llanma matnini yozing:")

    elif step == "add_guide_content":
        context.user_data["guide_content"] = txt
        context.user_data["guide_file_id"] = ""
        context.user_data["step"] = "add_guide_type"
        kb = [[InlineKeyboardButton("🆓 Bepul",    callback_data="guide_type_free"),
               InlineKeyboardButton("⭐️ Premium", callback_data="guide_type_premium")]]
        await update.message.reply_text("Qo'llanma turi:", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "edit_guide_title":
        db.update_guide(context.user_data["edit_id"], title=txt)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}\n\n/admin")

    elif step == "edit_guide_content":
        db.update_guide(context.user_data["edit_id"], content=txt)
        context.user_data.clear()
        await update.message.reply_text("✅ Matn yangilandi!\n\n/admin")

    elif step == "set_price":
        db.set_setting("premium_price", txt)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Narx yangilandi: {txt} so'm\n\n/admin")

    elif step == "set_days":
        try:
            int(txt)
            db.set_setting("premium_days", txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Muddat yangilandi: {txt} kun\n\n/admin")
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "set_card":
        db.set_setting("card_number", txt)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Karta yangilandi: {txt}\n\n/admin")

    elif step == "set_owner":
        db.set_setting("card_owner", txt)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Karta egasi yangilandi: {txt}\n\n/admin")

    elif step == "broadcast":
        users = db.get_all_users()
        sent  = 0
        for u in users:
            if u["status"] in ("approved","premium"):
                try: await context.bot.send_message(u["user_id"], f"📢\n\n{txt}"); sent += 1
                except: pass
        context.user_data.clear()
        await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.")

async def handle_guide_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qo'llanmaga fayl (PDF, doc) yuklash"""
    if not is_admin(update.effective_user.id): return
    step = context.user_data.get("step", "")
    if step not in ("add_guide_content", "waiting_guide_file"): return
    doc = update.message.document
    if not doc: return
    context.user_data["guide_file_id"] = doc.file_id
    context.user_data["guide_file_name"] = doc.file_name or "fayl"
    # Agar matn ham kiritilmagan bo'lsa, shu fayl nom bo'lsin
    if not context.user_data.get("guide_content"):
        context.user_data["guide_content"] = doc.file_name or "Fayl"
    context.user_data["step"] = "add_guide_type"
    kb = [[InlineKeyboardButton("🆓 Bepul",    callback_data="guide_type_free"),
           InlineKeyboardButton("⭐️ Premium", callback_data="guide_type_premium")]]
    await update.message.reply_text(
        f"✅ Fayl qabul qilindi: {doc.file_name}\n\nQo'llanma turi:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER (qolgan barcha)
# ═══════════════════════════════════════════════════════════════════════════════
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    data = q.data

    if   data == "adm_back":         await show_admin_menu(update, context)
    elif data == "adm_tests":         await adm_tests(update, context)
    elif data == "adm_guides":        await adm_guides(update, context)
    elif data == "adm_users":         await adm_users(update, context)
    elif data == "adm_payments":      await adm_payments(update, context)
    elif data == "adm_stats":         await adm_stats(update, context)
    elif data == "adm_settings":      await adm_settings(update, context)
    elif data == "adm_broadcast":     await adm_broadcast(update, context)
    elif data == "adm_rating_all":    await adm_rating_all(update, context)
    elif data == "adm_rating_test":   await adm_rating_test_list(update, context)
    elif data == "adm_test_add":      await adm_test_add_prompt(update, context)
    elif data == "adm_guide_add":
        context.user_data["step"] = "add_guide_title"
        await q.edit_message_text("📚 Qo'llanma sarlavhasini yozing:\nBekor: /admin")

    elif data.startswith("pdf_type_"):
        is_free = 1 if data == "pdf_type_free" else 0
        context.user_data["pdf_is_free"] = is_free
        context.user_data["step"]        = "waiting_pdf_file"
        await q.edit_message_text("✅ Turi tanlandi!\n\nEndi PDF faylni yuboring:")

    elif data.startswith("guide_type_"):
        is_free  = 1 if data == "guide_type_free" else 0
        title    = context.user_data.get("guide_title","")
        text_c   = context.user_data.get("guide_content","")
        file_id  = context.user_data.get("guide_file_id","")
        db.add_guide(title, text_c, is_free, file_id)
        context.user_data.clear()
        await q.edit_message_text("✅ Qo'llanma qo'shildi!\n\n/admin")

    elif data.startswith("agv_"):   await adm_guide_view(update, context)
    elif data.startswith("agt_"):   await adm_guide_toggle(update, context)
    elif data.startswith("agd_"):   await adm_guide_delete(update, context)
    elif data.startswith("agdc_"):  await adm_guide_delete_ok(update, context)
    elif data.startswith("agn_"):
        gid = int(data.split("_")[1])
        context.user_data["step"]    = "edit_guide_title"
        context.user_data["edit_id"] = gid
        g = db.get_guide(gid)
        await q.edit_message_text(f"✏️ Yangi sarlavha:\nHozirgi: {g['title']}\nBekor: /admin")
    elif data.startswith("age_"):
        gid = int(data.split("_")[1])
        context.user_data["step"]    = "edit_guide_content"
        context.user_data["edit_id"] = gid
        await q.edit_message_text("📝 Yangi matnni yozing:\nBekor: /admin")

    elif data.startswith("set_"):
        key_map = {"set_price":"set_price","set_days":"set_days","set_card":"set_card","set_owner":"set_owner"}
        hints   = {"set_price":"Yangi narxni yozing (faqat raqam, masalan: 349000):","set_days":"Yangi muddatni yozing (kun, masalan: 30):","set_card":"Yangi karta raqamini yozing:","set_owner":"Yangi karta egasi ismini yozing:"}
        context.user_data["step"] = data
        await q.edit_message_text(hints.get(data,"Yangi qiymatni yozing:") + "\n\nBekor: /admin")

async def back_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await show_welcome(update, context)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Umumiy
    app.add_handler(CallbackQueryHandler(about_bot,          pattern=r"^about_bot$"))
    app.add_handler(CallbackQueryHandler(free_menu,          pattern=r"^free_menu$"))
    app.add_handler(CallbackQueryHandler(premium_info,       pattern=r"^premium_info$"))
    app.add_handler(CallbackQueryHandler(premium_menu,       pattern=r"^premium_menu$"))
    app.add_handler(CallbackQueryHandler(buy_premium,        pattern=r"^buy_premium$"))
    app.add_handler(CallbackQueryHandler(send_payment_proof, pattern=r"^send_payment_proof$"))
    app.add_handler(CallbackQueryHandler(payment_action,     pattern=r"^pay_(ok|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(back_welcome,       pattern=r"^back_welcome$"))
    app.add_handler(CallbackQueryHandler(menu_tests,         pattern=r"^menu_tests$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test,      pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_test_prompt, pattern=r"^submit_test_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_guides,        pattern=r"^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide,         pattern=r"^guide_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_results,       pattern=r"^menu_results$"))

    # Admin testlar
    app.add_handler(CallbackQueryHandler(adm_tests,          pattern=r"^adm_tests$"))
    app.add_handler(CallbackQueryHandler(adm_test_view,      pattern=r"^atv_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_toggle,    pattern=r"^att_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_results,   pattern=r"^atr_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete,    pattern=r"^atd_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete_ok, pattern=r"^atdc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_rename,    pattern=r"^atn_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_newkey,    pattern=r"^atk_\d+$"))

    # Admin foydalanuvchilar
    app.add_handler(CallbackQueryHandler(adm_users_list,   pattern=r"^aul_(all|approved|premium|pending)$"))
    app.add_handler(CallbackQueryHandler(adm_user_detail,  pattern=r"^aud_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_user_action,  pattern=r"^aua_(ok|prem|unprem|kick)_\d+$"))

    # Admin umumiy
    app.add_handler(CallbackQueryHandler(cb_handler, pattern=r"^(adm_|pdf_type_|guide_type_|set_|agv_|agt_|agd_|agdc_|agn_|age_)"))

    # Fayllar va matnlar
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.Document.PDF, handle_guide_file))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
