import logging
import os
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "123456789"))
KARTA      = "9860 3501 4876 2387"
KARTA_EGASI= "Mallayev Ozodbek"
NARX       = "349 000 so'm"
PREMIUM_KUN= 30

db = Database()

# ─── yordamchi ───────────────────────────────────────────────────────────────
def is_admin(uid):  return uid == ADMIN_ID

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

def premium_exp_str(uid):
    exp = db.get_premium_expiry(uid)
    return exp.strftime("%d.%m.%Y") if exp else "?"

# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = user.id
    context.user_data.clear()

    # Admin
    if is_admin(uid):
        db.add_user(uid, user.username or "", user.first_name, user.first_name)
        await show_admin_menu(update, context)
        return

    existing = db.get_user(uid)

    # Qaytib kelgan foydalanuvchi
    if existing and existing.get("full_name"):
        await show_welcome_menu(update, context, existing["full_name"])
        return

    # Yangi foydalanuvchi — ism so'ra
    context.user_data["step"] = "waiting_fullname"
    await update.message.reply_text(
        "👋 Assalomu alaykum!\n\n"
        "Botdan foydalanish uchun ismingiz va familiyangizni to'liq kiriting:\n\n"
        "📝 Masalan: Aliyev Jasur"
    )

async def show_welcome_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, full_name: str = ""):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    prem = is_premium(uid)

    if prem:
        header = (
            f"👑 Xush kelibsiz, {full_name}!\n\n"
            f"Premium: {premium_exp_str(uid)} gacha aktiv ✅"
        )
        kb = [
            [InlineKeyboardButton("ℹ️ Bot haqida ma'lumot", callback_data="about_bot")],
            [InlineKeyboardButton("⭐️ Premium versiya", callback_data="premium_menu")],
        ]
    else:
        status = db.get_user_status(uid)
        header = f"👋 Xush kelibsiz, {full_name}!"
        kb = [
            [InlineKeyboardButton("ℹ️ Bot haqida ma'lumot", callback_data="about_bot")],
            [InlineKeyboardButton("🆓 Bepul versiya", callback_data="free_menu")],
            [InlineKeyboardButton("⭐️ Premium versiya", callback_data="premium_info")],
        ]

    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(header, reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  BOT HAQIDA
# ─────────────────────────────────────────────────────────────────────────────
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton("⬅️ Orqaga qaytish", callback_data="back_welcome")]]
    await q.edit_message_text(
        "🤖 Xush kelibsiz!\n\n"
        "Bu bot @legistman kanaliga tegishli hisoblanadi! 📚\n\n"
        "Bu yerda siz BMBA darajasidagi maxsus testlarni 📝 ishlashingiz\n"
        "va natijalarni tekshirishingiz mumkin ✅\n\n"
        "Shuningdek, maxsus o'quv qo'llanmalari 📖 bilan ham ta'minlanasiz.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─────────────────────────────────────────────────────────────────────────────
#  BEPUL MENYU
# ─────────────────────────────────────────────────────────────────────────────
async def free_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tests = db.get_free_pdf_tests()
    kb = []
    if tests:
        for t in tests:
            kb.append([InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    else:
        pass
    kb.append([InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_welcome")])
    txt = "🆓 Bepul bo'lim\n\n"
    txt += "📝 Mavjud bepul testlar:\n" if tests else "ℹ️ Hozircha bepul testlar yo'q.\n"
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  PREMIUM INFO (sotib olish)
# ─────────────────────────────────────────────────────────────────────────────
async def premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [
        [InlineKeyboardButton("💳 To'lov qilish", callback_data="buy_premium")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_welcome")],
    ]
    await q.edit_message_text(
        "⭐️ Premium versiya\n\n"
        "Premium imkoniyatlar:\n"
        "✅ Barcha testlar\n"
        "✅ Barcha qo'llanmalar\n"
        "✅ Barcha video darslar\n"
        "✅ Batafsil xato tahlili\n\n"
        f"💰 Narx: {NARX} / 30 kun\n\n"
        "To'lov qilish uchun quyidagi tugmani bosing 👇",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─────────────────────────────────────────────────────────────────────────────
#  PREMIUM MENYU (premium foydalanuvchi uchun)
# ─────────────────────────────────────────────────────────────────────────────
async def premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    kb = [
        [InlineKeyboardButton("📝 Testlar", callback_data="menu_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar", callback_data="menu_guides")],
        [InlineKeyboardButton("🎬 Video darslar", callback_data="menu_videos")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="menu_results")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_welcome")],
    ]
    await q.edit_message_text(
        f"⭐️ Premium bo'lim\n\n"
        f"👑 Premium: {premium_exp_str(uid)} gacha aktiv",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─────────────────────────────────────────────────────────────────────────────
#  TO'LOV
# ─────────────────────────────────────────────────────────────────────────────
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if is_premium(uid):
        await q.answer("Siz allaqachon premium foydalanuvchisiz!", show_alert=True)
        return
    kb = [
        [InlineKeyboardButton("✅ Chek yuboraman", callback_data="send_payment_proof")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_info")],
    ]
    await q.edit_message_text(
        f"💳 To'lov ma'lumotlari\n\n"
        f"💰 Narx: {NARX} / 30 kun\n\n"
        f"Karta raqami:\n`{KARTA}`\n"
        f"Karta egasi: {KARTA_EGASI}\n\n"
        f"📋 Qadamlar:\n"
        f"1️⃣ Yuqoridagi kartaga {NARX} o'tkering\n"
        f"2️⃣ To'lov cheki (screenshot)ni saqlang\n"
        f"3️⃣ Quyidagi tugmani bosib chekni yuboring\n"
        f"4️⃣ Admin 24 soat ichida ko'rib chiqadi ✅",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def send_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["step"] = "waiting_payment_proof"
    await q.edit_message_text(
        "📸 To'lov chekini yuboring\n\n"
        "Rasm yoki screenshot ko'rinishida yuboring.\n\n"
        "Bekor qilish: /start"
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_payment_proof":
        return False
    user = update.effective_user
    photo = update.message.photo
    document = update.message.document
    if not photo and not document:
        await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return True
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Chek qabul qilindi!\n\n"
        "Admin 24 soat ichida ko'rib chiqadi.\n"
        "Tasdiqlangach xabar olasiz. 🙏"
    )
    u = db.get_user(user.id)
    fname = u["full_name"] if u else user.first_name
    kb = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_approve_{user.id}"),
        InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_reject_{user.id}"),
    ]]
    caption = (
        f"💎 Yangi to'lov so'rovi!\n\n"
        f"👤 {fname}\n"
        f"🆔 {user.id}\n"
        f"📛 @{user.username or 'yoq'}"
    )
    if photo:
        await context.bot.send_photo(ADMIN_ID, photo[-1].file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_document(ADMIN_ID, document.file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    db.add_payment_request(user.id)
    return True

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    action, target_id = parts[1], int(parts[2])
    old_cap = q.message.caption or q.message.text or ""
    if action == "approve":
        expiry = datetime.now() + timedelta(days=PREMIUM_KUN)
        db.set_premium(target_id, expiry)
        new_cap = old_cap + f"\n\n✅ Tasdiqlandi! Premium: {expiry.strftime('%d.%m.%Y')} gacha"
        try: await q.edit_message_caption(new_cap)
        except: await q.edit_message_text(new_cap)
        await context.bot.send_message(
            target_id,
            f"🎉 Premium faollashtirildi!\n\n"
            f"👑 Muddat: {expiry.strftime('%d.%m.%Y')} gacha\n\n"
            f"/start bosib kiring."
        )
    else:
        new_cap = old_cap + "\n\n❌ Rad etildi."
        try: await q.edit_message_caption(new_cap)
        except: await q.edit_message_text(new_cap)
        await context.bot.send_message(target_id, "😔 To'lovingiz tasdiqlanmadi. Muammo bo'lsa adminga murojaat qiling.")

# ─────────────────────────────────────────────────────────────────────────────
#  TESTLAR
# ─────────────────────────────────────────────────────────────────────────────
async def menu_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    prem = is_premium(uid)
    appr = is_approved(uid)
    if prem or appr:
        tests = db.get_all_pdf_tests()
    else:
        tests = db.get_free_pdf_tests()
    kb = []
    for t in tests:
        icon = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu" if prem else "back_welcome")])
    await q.edit_message_text("📝 Testlar:", reply_markup=InlineKeyboardMarkup(kb) if kb else None)

async def show_pdf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    test_id = int(q.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    if not test:
        await q.edit_message_text("Test topilmadi.")
        return
    if not test.get("is_free") and not is_approved(uid):
        kb = [
            [InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="free_menu")],
        ]
        await q.edit_message_text("⭐️ Bu test faqat premium foydalanuvchilar uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    q_count = test.get("question_count", 30)
    context.user_data["active_test_id"]    = test_id
    context.user_data["active_test_count"] = q_count
    await context.bot.send_document(
        q.message.chat_id,
        test["file_id"],
        caption=f"📝 {test['title']}\n❓ Savollar: {q_count} ta\n\nTestni yechib bo'lgach javob yuboring."
    )
    kb = [[InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_test_{test_id}")]]
    await context.bot.send_message(q.message.chat_id, "Tayyor bo'ldingizmi?", reply_markup=InlineKeyboardMarkup(kb))

async def submit_test_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    test_id = int(q.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    q_count = test.get("question_count", 30) if test else 30
    context.user_data["step"]             = "waiting_answers"
    context.user_data["waiting_test_id"]  = test_id
    context.user_data["waiting_test_cnt"] = q_count
    await q.edit_message_text(
        f"✏️ {q_count} ta javobni yuboring!\n\n"
        f"Faqat harflar ketma-ket (bo'sh joy shart emas):\n"
        f"Masalan: ABCDABCDABCD...\n\n"
        f"(Jami {q_count} ta harf — A, B, C yoki D)"
    )

async def handle_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_answers":
        return False
    uid      = update.effective_user.id
    test_id  = context.user_data["waiting_test_id"]
    q_count  = context.user_data["waiting_test_cnt"]
    raw      = update.message.text.strip().upper()
    clean    = re.sub(r"[^ABCD]", "", raw)
    if len(clean) != q_count:
        await update.message.reply_text(
            f"⚠️ {len(clean)} ta javob yubordingiz, {q_count} ta kerak.\n\nQaytadan yuboring:"
        )
        return True
    key = re.sub(r"[^ABCD]", "", (db.get_answer_key(test_id) or "").upper())
    if not key:
        await update.message.reply_text("⚠️ Javob kaliti kiritilmagan. Adminga murojaat qiling.")
        return True
    correct = sum(u == k for u, k in zip(clean, key))
    wrong   = q_count - correct
    pct     = round(correct / q_count * 100)
    if pct >= 85:   baho = "🏆 Ajoyib!"
    elif pct >= 70: baho = "👍 Yaxshi!"
    elif pct >= 50: baho = "📚 Qoniqarli"
    else:           baho = "💪 Ko'proq mashq kerak"

    wrong_lines = [
        f"  {i+1}-savol: Siz {u} ✗  →  To'g'ri: {k} ✓"
        for i, (u, k) in enumerate(zip(clean, key)) if u != k
    ]
    result = (
        f"📊 Natija\n{'─'*24}\n"
        f"✅ To'g'ri: {correct}/{q_count}\n"
        f"❌ Xato:   {wrong}/{q_count}\n"
        f"📈 Foiz:   {pct}%\n"
        f"🎯 Baho:   {baho}\n"
    )
    if wrong_lines:
        result += f"\n❌ Xato javoblar ({wrong} ta):\n"
        result += "\n".join(wrong_lines[:25])
        if wrong > 25:
            result += f"\n  ... va yana {wrong-25} ta xato"

    db.save_pdf_result(uid, test_id, correct, q_count, clean)
    context.user_data.clear()
    prem = is_premium(uid)
    kb = [
        [InlineKeyboardButton("📝 Yana test", callback_data="menu_tests")],
        [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")],
    ]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))
    return True

# ─────────────────────────────────────────────────────────────────────────────
#  QO'LLANMALAR
# ─────────────────────────────────────────────────────────────────────────────
async def menu_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_approved(q.from_user.id):
        kb = [[InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium"), InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
        await q.edit_message_text("⭐️ Qo'llanmalar faqat premium uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    guides = db.get_all_guides()
    if not guides:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
        await q.edit_message_text("Hozircha qo'llanmalar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")] for g in guides]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")])
    await q.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    guide = db.get_guide(int(q.data.split("_")[1]))
    if not guide: return
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_guides")]]
    await q.edit_message_text(f"📖 {guide['title']}\n\n{guide['content']}"[:4000], reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  VIDEOLAR
# ─────────────────────────────────────────────────────────────────────────────
async def menu_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_approved(q.from_user.id):
        kb = [[InlineKeyboardButton("⭐️ Premium olish", callback_data="buy_premium"), InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
        await q.edit_message_text("⭐️ Videolar faqat premium uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    videos = db.get_all_videos()
    if not videos:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
        await q.edit_message_text("Hozircha videolar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(f"▶️ {v['title']}", callback_data=f"video_{v['id']}")] for v in videos]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")])
    await q.edit_message_text("🎬 Video darslar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    v = db.get_video(int(q.data.split("_")[1]))
    if not v: return
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_videos")]]
    await q.edit_message_text(f"🎬 {v['title']}\n\n{v['description']}\n\n🔗 {v['url']}", reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  NATIJALAR
# ─────────────────────────────────────────────────────────────────────────────
async def menu_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    results = db.get_user_pdf_results(q.from_user.id)
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="premium_menu")]]
    if not results:
        await q.edit_message_text("Hali test yechmagansiz.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = "📊 Natijalaringiz:\n\n"
    for r in results[:20]:
        pct = round(r["correct"]/r["total"]*100) if r["total"] else 0
        text += f"📝 {r['test_title']}: {r['correct']}/{r['total']} ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────────────────────────────────────────
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar",            callback_data="admin_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",       callback_data="admin_guides")],
        [InlineKeyboardButton("🎬 Videolar",            callback_data="admin_videos")],
        [InlineKeyboardButton("👥 Foydalanuvchilar",   callback_data="admin_users")],
        [InlineKeyboardButton("💎 To'lov so'rovlari",  callback_data="admin_payments")],
        [InlineKeyboardButton("📊 Statistika",         callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Xabar yuborish",     callback_data="admin_broadcast")],
    ]
    msg = "🔧 Admin Panel"
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb))

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    context.user_data.clear()
    await show_admin_menu(update, context)

# ─── TESTLAR BOSHQARUVI ──────────────────────────────────────────────────────
async def admin_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton("➕ Yangi test qo'shish", callback_data="admin_add_pdf")]]
    for t in tests:
        icon = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{icon} {t['title']}", callback_data=f"atv_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await q.edit_message_text("📝 Testlar boshqaruvi:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    test_id = int(q.data.split("_")[1])
    test    = db.get_pdf_test(test_id)
    if not test: return
    results = db.get_test_results(test_id)
    icon    = "🆓 Bepul" if test.get("is_free") else "⭐️ Premium"
    toggle  = "⭐️ Premiumga o'tkazish" if test.get("is_free") else "🆓 Bepulga o'tkazish"
    text = (
        f"📝 {test['title']}\n{'─'*22}\n"
        f"❓ Savollar: {test['question_count']} ta\n"
        f"🔑 Kalit: {test['answer_key']}\n"
        f"📌 Turi: {icon}\n"
        f"👥 Yechganlar: {len(results)} ta"
    )
    kb = [
        [InlineKeyboardButton(toggle,                   callback_data=f"att_{test_id}")],
        [InlineKeyboardButton("🔑 Kalitni yangilash",   callback_data=f"atk_{test_id}")],
        [InlineKeyboardButton("📊 Natijalar",           callback_data=f"atr_{test_id}")],
        [InlineKeyboardButton("🗑 O'chirish",           callback_data=f"atd_{test_id}")],
        [InlineKeyboardButton("⬅️ Orqaga",             callback_data="admin_tests")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    test = db.get_pdf_test(test_id)
    db.set_test_free(test_id, 0 if test.get("is_free") else 1)
    q.data = f"atv_{test_id}"
    await admin_test_view(update, context)

async def admin_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    results = db.get_test_results(test_id)
    test    = db.get_pdf_test(test_id)
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data=f"atv_{test_id}")]]
    if not results:
        await q.edit_message_text("Hali hech kim yechmagan.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = f"📊 {test['title']}:\n\n"
    for r in results[:20]:
        pct = round(r["correct"]/r["total"]*100)
        text += f"👤 {r['first_name']}: {r['correct']}/{r['total']} ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    test = db.get_pdf_test(test_id)
    kb = [
        [InlineKeyboardButton("✅ Ha, o'chirish",  callback_data=f"atdc_{test_id}")],
        [InlineKeyboardButton("❌ Bekor qilish",   callback_data=f"atv_{test_id}")],
    ]
    await q.edit_message_text(
        f"⚠️ '{test['title']}' ni o'chirishni tasdiqlaysizmi?\n\nBu amalni qaytarib bo'lmaydi!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_test_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    db.delete_pdf_test(test_id)
    await q.answer("✅ Test o'chirildi!", show_alert=True)
    await admin_tests(update, context)

async def admin_test_newkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[1])
    test = db.get_pdf_test(test_id)
    context.user_data["step"]         = "update_answer_key"
    context.user_data["key_test_id"]  = test_id
    context.user_data["key_count"]    = test.get("question_count", 30)
    await q.edit_message_text(
        f"🔑 Yangi kalit kiriting:\n\n"
        f"Test: {test['title']}\n"
        f"Savollar: {test['question_count']} ta\n\n"
        f"{test['question_count']} ta harf (ABCD):\n"
        f"Masalan: ABCDABCD...\n\nBekor: /admin"
    )

# ─── FOYDALANUVCHILAR BOSHQARUVI ─────────────────────────────────────────────
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("👥 Barchasi",       callback_data="aul_all")],
        [InlineKeyboardButton("✅ Tasdiqlangan",   callback_data="aul_approved")],
        [InlineKeyboardButton("⭐️ Premium",        callback_data="aul_premium")],
        [InlineKeyboardButton("⏳ Kutayotgan",     callback_data="aul_pending")],
        [InlineKeyboardButton("⬅️ Orqaga",        callback_data="admin_back")],
    ]
    await q.edit_message_text("👥 Foydalanuvchilar:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ftype = q.data.split("_")[1]
    users = db.get_users_by_status(None if ftype == "all" else ftype)
    icons = {"approved":"✅","premium":"⭐️","pending":"⏳","rejected":"❌","new":"🆕"}
    kb = []
    for u in users[:25]:
        ico = icons.get(u["status"], "👤")
        kb.append([InlineKeyboardButton(f"{ico} {u['full_name'] or u['first_name']}", callback_data=f"aud_{u['user_id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_users")])
    text = f"👥 {ftype.capitalize()} ({len(users)} ta):"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    u = db.get_user(tid)
    if not u: return
    exp = db.get_premium_expiry(tid)
    text = (
        f"👤 {u['full_name'] or u['first_name']}\n"
        f"🆔 {u['user_id']}\n"
        f"📛 @{u['username'] or 'yoq'}\n"
        f"📌 Status: {u['status']}\n"
    )
    if exp: text += f"⭐️ Premium: {exp.strftime('%d.%m.%Y')} gacha\n"
    kb = []
    if u["status"] != "approved":
        kb.append([InlineKeyboardButton("✅ Tasdiqlash",           callback_data=f"aua_approve_{tid}")])
    if u["status"] != "premium":
        kb.append([InlineKeyboardButton("⭐️ Premium berish (30 kun)", callback_data=f"aua_premium_{tid}")])
    if u["status"] not in ("rejected","new"):
        kb.append([InlineKeyboardButton("🚫 Chiqarib yuborish",   callback_data=f"aua_kick_{tid}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="aul_all")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, action, tid = q.data.split("_", 2)
    tid = int(tid)
    if action == "approve":
        db.set_user_status(tid, "approved")
        await context.bot.send_message(tid, "✅ Botdan foydalanishga ruxsat berildi! /start bosing.")
        await q.answer("✅ Tasdiqlandi!", show_alert=True)
    elif action == "premium":
        exp = datetime.now() + timedelta(days=PREMIUM_KUN)
        db.set_premium(tid, exp)
        await context.bot.send_message(tid, f"⭐️ Premium berildi! {exp.strftime('%d.%m.%Y')} gacha. /start bosing.")
        await q.answer("⭐️ Premium berildi!", show_alert=True)
    elif action == "kick":
        db.set_user_status(tid, "rejected")
        await context.bot.send_message(tid, "🚫 Botdan foydalanish huquqingiz bekor qilindi.")
        await q.answer("🚫 Chiqarib yuborildi!", show_alert=True)
    q.data = f"aud_{tid}"
    await admin_user_detail(update, context)

# ─── TO'LOV SO'ROVLARI ───────────────────────────────────────────────────────
async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    payments = db.get_pending_payments()
    if not payments:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]]
        await q.edit_message_text("Hozircha kutayotgan to'lovlar yo'q. ✅", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(f"💳 {p['full_name'] or p['first_name']}", callback_data=f"aud_{p['user_id']}")] for p in payments]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await q.edit_message_text(f"💎 Kutayotgan to'lovlar: {len(payments)} ta", reply_markup=InlineKeyboardMarkup(kb))

# ─── STATISTIKA ──────────────────────────────────────────────────────────────
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    s = db.get_stats()
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]]
    await q.edit_message_text(
        f"📊 Statistika:\n\n"
        f"👥 Jami foydalanuvchilar: {s['total_users']}\n"
        f"✅ Tasdiqlangan: {s['approved_users']}\n"
        f"⭐️ Premium: {s['premium_users']}\n"
        f"⏳ Kutayotgan: {s['pending_users']}\n"
        f"📝 Testlar: {s['total_pdf_tests']}\n"
        f"📚 Qo'llanmalar: {s['total_guides']}\n"
        f"🎬 Videolar: {s['total_videos']}\n"
        f"🏆 Jami natijalar: {s['total_results']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ─── BROADCAST ───────────────────────────────────────────────────────────────
async def admin_broadcast_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "broadcast"
    await q.edit_message_text("📢 Xabar matnini yozing (barcha foydalanuvchilarga):\n\nBekor: /admin")

# ─── CONTENT QO'SHISH ────────────────────────────────────────────────────────
async def admin_add_pdf_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "pdf_title"
    await q.edit_message_text("📝 Yangi test nomi:\n(Masalan: Ona tili — 1-variant)\n\nBekor: /admin")

async def admin_guides_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    guides = db.get_all_guides()
    kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="admin_add_guide")]]
    for g in guides:
        kb.append([InlineKeyboardButton(f"🗑 {g['title']}", callback_data=f"agd_{g['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await q.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_videos_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    videos = db.get_all_videos()
    kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="admin_add_video")]]
    for v in videos:
        kb.append([InlineKeyboardButton(f"🗑 {v['title']}", callback_data=f"avd_{v['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await q.edit_message_text("🎬 Videolar:", reply_markup=InlineKeyboardMarkup(kb))

# ─────────────────────────────────────────────────────────────────────────────
#  MATN XABARLARI — ASOSIY HANDLER
# ─────────────────────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    step = context.user_data.get("step", "")

    # ── Yangi foydalanuvchi ism-familiya ──
    if step == "waiting_fullname":
        full_name = update.message.text.strip()
        if len(full_name.split()) < 2:
            await update.message.reply_text("Iltimos, to'liq ism va familiyangizni kiriting.\nMasalan: Aliyev Jasur")
            return
        db.add_user(uid, update.effective_user.username or "", update.effective_user.first_name, full_name)
        context.user_data.clear()
        await show_welcome_menu(update, context, full_name)
        return

    # ── To'lov cheki ──
    if step == "waiting_payment_proof":
        await handle_payment_proof(update, context)
        return

    # ── Test javoblari ──
    if step == "waiting_answers":
        await handle_test_answers(update, context)
        return

    # ── Admin amallar ──
    if not is_admin(uid): return
    text = update.message.text.strip() if update.message and update.message.text else ""

    if step == "pdf_title":
        context.user_data["pdf_title"] = text
        context.user_data["step"] = "pdf_count"
        await update.message.reply_text(f"✅ Nom: {text}\n\nNechta savol? (Masalan: 30)")

    elif step == "pdf_count":
        try:
            count = int(text)
            context.user_data["pdf_count"] = count
            context.user_data["step"] = "pdf_type"
            kb = [
                [InlineKeyboardButton("🆓 Bepul",    callback_data="pdf_type_free")],
                [InlineKeyboardButton("⭐️ Premium", callback_data="pdf_type_premium")],
            ]
            await update.message.reply_text(f"Savollar: {count} ta\n\nTest turi:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "waiting_pdf_file":
        await update.message.reply_text("Iltimos PDF faylni yuboring.")

    elif step == "pdf_key":
        count    = context.user_data.get("pdf_count", 30)
        file_id  = context.user_data.get("pdf_file_id", "")
        title    = context.user_data.get("pdf_title", "")
        is_free  = context.user_data.get("pdf_is_free", 0)
        clean    = re.sub(r"[^ABCD]", "", text.upper())
        if len(clean) != count:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {count} ta kerak. Qaytadan:")
            return
        db.add_pdf_test(title, file_id, count, clean, is_free)
        context.user_data.clear()
        await update.message.reply_text(
            f"✅ Test qo'shildi!\n📝 {title}\n❓ {count} savol\n"
            f"{'🆓 Bepul' if is_free else '⭐️ Premium'}\n\n/admin"
        )

    elif step == "update_answer_key":
        test_id = context.user_data.get("key_test_id")
        count   = context.user_data.get("key_count", 30)
        clean   = re.sub(r"[^ABCD]", "", text.upper())
        if len(clean) != count:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {count} ta kerak. Qaytadan:")
            return
        db.update_answer_key(test_id, clean)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Kalit yangilandi: {clean}\n\n/admin")

    elif step == "add_guide_title":
        context.user_data["guide_title"] = text
        context.user_data["step"] = "add_guide_content"
        await update.message.reply_text("Qo'llanma matnini yozing:")

    elif step == "add_guide_content":
        db.add_guide(context.user_data.get("guide_title",""), text)
        context.user_data.clear()
        await update.message.reply_text("✅ Qo'llanma qo'shildi! /admin")

    elif step == "add_video_title":
        context.user_data["video_title"] = text
        context.user_data["step"] = "add_video_desc"
        await update.message.reply_text("Video tavsifini yozing:")

    elif step == "add_video_desc":
        context.user_data["video_desc"] = text
        context.user_data["step"] = "add_video_url"
        await update.message.reply_text("Video havolasini yozing (YouTube link):")

    elif step == "add_video_url":
        db.add_video(context.user_data.get("video_title",""), context.user_data.get("video_desc",""), text)
        context.user_data.clear()
        await update.message.reply_text("✅ Video qo'shildi! /admin")

    elif step == "broadcast":
        users = db.get_all_users()
        sent = 0
        for u in users:
            if u["status"] in ("approved","premium"):
                try:
                    await context.bot.send_message(u["user_id"], f"📢 Xabar:\n\n{text}")
                    sent += 1
                except: pass
        context.user_data.clear()
        await update.message.reply_text(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")

async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if context.user_data.get("step") != "waiting_pdf_file": return
    file_id = update.message.document.file_id
    context.user_data["pdf_file_id"] = file_id
    context.user_data["step"]        = "pdf_key"
    count = context.user_data.get("pdf_count", 30)
    await update.message.reply_text(
        f"✅ PDF qabul qilindi!\n\n{count} ta javob kalitini yozing:\nMasalan: ABCDABCD... ({count} ta harf)"
    )

# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACK — ADMIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    data = q.data

    if data == "admin_back":     await show_admin_menu(update, context)
    elif data == "admin_tests":  await admin_tests(update, context)
    elif data == "admin_users":  await admin_users(update, context)
    elif data == "admin_payments": await admin_payments(update, context)
    elif data == "admin_stats":  await admin_stats(update, context)
    elif data == "admin_guides": await admin_guides_menu(update, context)
    elif data == "admin_videos": await admin_videos_menu(update, context)
    elif data == "admin_add_pdf": await admin_add_pdf_prompt(update, context)
    elif data == "admin_broadcast": await admin_broadcast_prompt(update, context)

    elif data == "admin_add_guide":
        context.user_data["step"] = "add_guide_title"
        await q.edit_message_text("📚 Qo'llanma sarlavhasini yozing:\n\nBekor: /admin")

    elif data == "admin_add_video":
        context.user_data["step"] = "add_video_title"
        await q.edit_message_text("🎬 Video sarlavhasini yozing:\n\nBekor: /admin")

    elif data.startswith("agd_"):
        gid = int(data.split("_")[1])
        db.delete_guide(gid)
        await q.answer("O'chirildi!", show_alert=True)
        await admin_guides_menu(update, context)

    elif data.startswith("avd_"):
        vid = int(data.split("_")[1])
        db.delete_video(vid)
        await q.answer("O'chirildi!", show_alert=True)
        await admin_videos_menu(update, context)

    elif data.startswith("pdf_type_"):
        is_free = 1 if data == "pdf_type_free" else 0
        context.user_data["pdf_is_free"] = is_free
        context.user_data["step"]        = "waiting_pdf_file"
        await q.edit_message_text("✅ Tanlandi!\n\nEndi PDF faylni yuboring:")

async def back_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    u = db.get_user(uid)
    fname = u["full_name"] if u and u.get("full_name") else (u["first_name"] if u else "")
    await show_welcome_menu(update, context, fname)

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
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
    app.add_handler(CallbackQueryHandler(payment_action,     pattern=r"^pay_(approve|reject)_\d+$"))
    app.add_handler(CallbackQueryHandler(back_welcome,       pattern=r"^back_welcome$"))

    # Testlar
    app.add_handler(CallbackQueryHandler(menu_tests,         pattern=r"^menu_tests$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test,      pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_test_prompt, pattern=r"^submit_test_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_guides,        pattern=r"^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide,         pattern=r"^guide_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_videos,        pattern=r"^menu_videos$"))
    app.add_handler(CallbackQueryHandler(show_video,         pattern=r"^video_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_results,       pattern=r"^menu_results$"))

    # Admin — test
    app.add_handler(CallbackQueryHandler(admin_test_view,           pattern=r"^atv_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_toggle,         pattern=r"^att_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_results,        pattern=r"^atr_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_delete,         pattern=r"^atd_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_delete_confirm, pattern=r"^atdc_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_newkey,         pattern=r"^atk_\d+$"))

    # Admin — foydalanuvchi
    app.add_handler(CallbackQueryHandler(admin_users_list,  pattern=r"^aul_(all|approved|premium|pending)$"))
    app.add_handler(CallbackQueryHandler(admin_user_detail, pattern=r"^aud_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_user_action, pattern=r"^aua_(approve|premium|kick)_\d+$"))

    # Admin — umumiy
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^pdf_type_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^agd_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^avd_\d+$"))

    # Xabarlar
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
