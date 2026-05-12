import logging
import os
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
KARTA_RAQAM = "9860 3501 4876 2387"
KARTA_EGASI = "Mallayev Ozodbek"
PREMIUM_NARX = "349 000 so'm"
PREMIUM_KUN = 30

db = Database()

def is_admin(uid): return uid == ADMIN_ID
def is_approved(uid): return db.get_user_status(uid) in ("approved", "premium")
def is_premium(uid):
    status = db.get_user_status(uid)
    if status != "premium": return False
    exp = db.get_premium_expiry(uid)
    if not exp: return False
    if datetime.now() > exp:
        db.set_user_status(uid, "approved")
        return False
    return True

# ═══════════════════════════════════════════
#  START
# ═══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username or "", user.first_name)

    if is_admin(user.id):
        await show_admin_menu(update, context)
        return

    status = db.get_user_status(user.id)

    if status in ("approved", "premium"):
        await show_main_menu(update, context)
        return

    # Yangi yoki oddiy foydalanuvchi
    kb = [
        [InlineKeyboardButton("📋 Bot haqida ma'lumot", callback_data="about_bot")],
        [InlineKeyboardButton("🆓 Bepul sinab ko'rish", callback_data="free_tests")],
        [InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium")],
        [InlineKeyboardButton("📨 To'liq kirish so'rovi", callback_data="request_access")],
    ]
    await update.message.reply_text(
        f"👋 Salom, {user.first_name}!\n\n"
        f"Bu bot o'quv testlari va qo'llanmalar platformasi.\n\n"
        f"📌 Quyidagilardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════
#  MENYULAR
# ═══════════════════════════════════════════
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    premium = is_premium(uid)

    crown = "👑 " if premium else ""
    kb = [
        [InlineKeyboardButton("📝 Testlar", callback_data="menu_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar", callback_data="menu_guides")],
        [InlineKeyboardButton("🎬 Video darslar", callback_data="menu_videos")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="menu_results")],
    ]
    if not premium:
        kb.append([InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium")])

    text = f"{crown}Asosiy menyu"
    if premium:
        exp = db.get_premium_expiry(uid)
        if exp:
            text += f"\n👑 Premium: {exp.strftime('%d.%m.%Y')} gacha"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar boshqaruvi", callback_data="admin_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar", callback_data="admin_guides")],
        [InlineKeyboardButton("🎬 Videolar", callback_data="admin_videos")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("💎 To'lov so'rovlari", callback_data="admin_payments")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast")],
    ]
    text = "🔧 Admin Panel"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  BOT HAQIDA
# ═══════════════════════════════════════════
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("🆓 Bepul sinab ko'rish", callback_data="free_tests")],
        [InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_start")],
    ]
    await query.edit_message_text(
        "📌 Bot haqida\n\n"
        "Bu platforma orqali:\n"
        "✅ Test ishlash va natijalarni bilish\n"
        "✅ O'quv qo'llanmalarni o'qish\n"
        "✅ Video darslarni ko'rish\n\n"
        "🆓 Bepul versiya:\n"
        "• Admin belgilagan testlarni ishlash\n\n"
        "💎 Premium versiya (349 000 so'm/oy):\n"
        "• Barcha testlar\n"
        "• Barcha qo'llanmalar\n"
        "• Barcha video darslar\n"
        "• Batafsil xato tahlili",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════
#  BEPUL TESTLAR
# ═══════════════════════════════════════════
async def free_tests_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tests = db.get_free_pdf_tests()
    if not tests:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_start")]]
        await query.edit_message_text("Hozircha bepul testlar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_start")])
    await query.edit_message_text("🆓 Bepul testlar:", reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  PREMIUM SOTIB OLISH
# ═══════════════════════════════════════════
async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("✅ To'lov qildim, chek yuboraman", callback_data="send_payment_proof")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_start")],
    ]
    await query.edit_message_text(
        "💎 Premium obuna\n\n"
        f"💰 Narx: {PREMIUM_NARX} / 30 kun\n\n"
        "💳 To'lov qilish:\n"
        f"Karta: `{KARTA_RAQAM}`\n"
        f"Egasi: {KARTA_EGASI}\n\n"
        "📋 Qadamlar:\n"
        "1. Yuqoridagi kartaga pul o'tkazing\n"
        "2. To'lov chekini saqlang\n"
        "3. Quyidagi tugmani bosib chekni yuboring\n"
        "4. Admin 24 soat ichida ko'rib chiqadi\n"
        "5. Tasdiqlangandan so'ng premium yoqiladi ✅",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def send_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_payment_proof"] = True
    await query.edit_message_text(
        "📸 To'lov chekini yuboring\n\n"
        "Rasm yoki screenshot ko'rinishida yuboring.\n"
        "Bekor qilish: /start"
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_payment_proof"):
        return False
    user = update.effective_user
    photo = update.message.photo
    document = update.message.document

    if not photo and not document:
        await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return True

    context.user_data.pop("waiting_payment_proof", None)

    # Foydalanuvchiga
    await update.message.reply_text(
        "✅ To'lov cheki qabul qilindi!\n\n"
        "Admin 24 soat ichida ko'rib chiqadi.\n"
        "Tasdiqlangandan so'ng xabar olasiz."
    )

    # Adminga
    kb = [
        [
            InlineKeyboardButton("✅ Tasdiqlash (30 kun)", callback_data=f"pay_approve_{user.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_reject_{user.id}"),
        ]
    ]
    caption = (
        f"💎 Yangi to'lov so'rovi!\n\n"
        f"👤 {user.first_name}\n"
        f"🆔 {user.id}\n"
        f"📛 @{user.username or 'yoq'}"
    )
    if photo:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo[-1].file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await context.bot.send_document(chat_id=ADMIN_ID, document=document.file_id, caption=caption, reply_markup=InlineKeyboardMarkup(kb))

    db.add_payment_request(user.id)
    return True

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    parts = query.data.split("_")
    action = parts[1]
    target_id = int(parts[2])

    if action == "approve":
        expiry = datetime.now() + timedelta(days=PREMIUM_KUN)
        db.set_premium(target_id, expiry)
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n✅ Tasdiqlandi! Premium: {expiry.strftime('%d.%m.%Y')} gacha"
        )
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 Premium faollashtirildi!\n\n👑 Muddat: 30 kun ({expiry.strftime('%d.%m.%Y')} gacha)\n\n/start bosing."
        )
    else:
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ Rad etildi.")
        await context.bot.send_message(
            chat_id=target_id,
            text="😔 To'lovingiz tasdiqlanmadi. Muammo bo'lsa adminga murojaat qiling."
        )

# ═══════════════════════════════════════════
#  KIRISH SO'ROVI
# ═══════════════════════════════════════════
async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    status = db.get_user_status(user.id)
    if status == "pending":
        await query.edit_message_text("⏳ So'rovingiz kutilmoqda.")
        return
    if status in ("approved", "premium"):
        await show_main_menu(update, context)
        return
    db.set_user_status(user.id, "pending")
    kb = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user.id}"),
    ]]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📨 Kirish so'rovi!\n\n👤 {user.first_name}\n🆔 {user.id}\n📛 @{user.username or 'yoq'}",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    await query.edit_message_text("✅ So'rov yuborildi! Admin tasdiqlashini kuting.")

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    action, uid = query.data.split("_", 1)
    target = int(uid)
    if action == "approve":
        db.set_user_status(target, "approved")
        await query.edit_message_text(query.message.text + "\n\n✅ Tasdiqlandi.")
        await context.bot.send_message(chat_id=target, text="✅ Kirish tasdiqlandi! /start bosing.")
    else:
        db.set_user_status(target, "rejected")
        await query.edit_message_text(query.message.text + "\n\n❌ Rad etildi.")
        await context.bot.send_message(chat_id=target, text="❌ So'rovingiz rad etildi.")

# ═══════════════════════════════════════════
#  TESTLAR
# ═══════════════════════════════════════════
async def menu_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if is_premium(uid) or is_approved(uid):
        tests = db.get_all_pdf_tests()
    else:
        tests = db.get_free_pdf_tests()

    if not tests:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Testlar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return

    kb = []
    for t in tests:
        free_tag = " 🆓" if t.get("is_free") else " 💎"
        kb.append([InlineKeyboardButton(f"📝 {t['title']}{free_tag}", callback_data=f"pdf_test_{t['id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
    await query.edit_message_text("📝 Testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_pdf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    test_id = int(query.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    if not test:
        await query.edit_message_text("Test topilmadi.")
        return

    # Bepul test emas va foydalanuvchi premium emas
    if not test.get("is_free") and not is_premium(uid) and not is_approved(uid):
        kb = [
            [InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_tests")],
        ]
        await query.edit_message_text("💎 Bu test faqat premium foydalanuvchilar uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return

    q_count = test.get("question_count", 30)
    context.user_data["active_test_id"] = test_id
    context.user_data["active_test_count"] = q_count

    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=test["file_id"],
        caption=f"📝 {test['title']}\n\n❓ Savollar: {q_count} ta\n\nTestni yechib bo'lgach javoblaringizni yuboring."
    )
    kb = [[InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_test_{test_id}")]]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Testni yechib bo'ldingizmi?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def submit_test_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    q_count = test.get("question_count", 30) if test else 30
    context.user_data["waiting_answers_for"] = test_id
    context.user_data["active_test_count"] = q_count
    await query.edit_message_text(
        f"✏️ Javoblaringizni yuboring!\n\n"
        f"{q_count} ta harf ketma-ket (ABCD):\n"
        f"Masalan: ABCDABCDABCD...\n\n"
        f"Vergul, bo'shliq shart emas."
    )

async def handle_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    test_id = context.user_data.get("waiting_answers_for")
    if not test_id:
        return False

    q_count = context.user_data.get("active_test_count", 30)
    text = update.message.text.strip().upper()
    clean = re.sub(r'[^ABCD]', '', text)

    if len(clean) != q_count:
        await update.message.reply_text(
            f"⚠️ {len(clean)} ta javob yubordingiz, {q_count} ta kerak.\n\nQaytadan yuboring."
        )
        return True

    answer_key = db.get_answer_key(test_id)
    if not answer_key:
        await update.message.reply_text("⚠️ Kalit hali kiritilmagan.")
        return True

    key = re.sub(r'[^ABCD]', '', answer_key.upper())
    correct = sum(1 for u, k in zip(clean, key) if u == k)
    wrong = q_count - correct
    percent = round((correct / q_count) * 100)

    if percent >= 85: baho = "🏆 Ajoyib!"
    elif percent >= 70: baho = "👍 Yaxshi!"
    elif percent >= 50: baho = "📚 Qoniqarli"
    else: baho = "💪 Ko'proq mashq kerak"

    # Xato javoblar tahlili
    wrong_details = []
    for i, (u, k) in enumerate(zip(clean, key)):
        if u != k:
            wrong_details.append(f"  {i+1}-savol: Siz {u} ✗  →  To'g'ri: {k} ✓")

    result = (
        f"📊 Natija: {test_id and db.get_pdf_test(test_id) and db.get_pdf_test(test_id).get('title','')}\n"
        f"{'─'*25}\n"
        f"✅ To'g'ri: {correct}/{q_count}\n"
        f"❌ Xato:   {wrong}/{q_count}\n"
        f"📈 Foiz:   {percent}%\n"
        f"🎯 Baho:   {baho}\n"
    )

    if wrong_details:
        result += f"\n❌ Xato javoblar ({wrong} ta):\n"
        result += "\n".join(wrong_details[:20])
        if wrong > 20:
            result += f"\n  ... va yana {wrong-20} ta xato"

    db.save_pdf_result(uid, test_id, correct, q_count, clean)
    context.user_data.pop("waiting_answers_for", None)
    context.user_data.pop("active_test_count", None)

    kb = [
        [InlineKeyboardButton("📝 Yana test", callback_data="menu_tests")],
        [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_main")],
    ]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))
    return True

# ═══════════════════════════════════════════
#  QO'LLANMALAR
# ═══════════════════════════════════════════
async def menu_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if not is_approved(uid) and not is_premium(uid):
        kb = [[InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium"), InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("💎 Qo'llanmalar faqat premium uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    guides = db.get_all_guides()
    if not guides:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Hozircha qo'llanmalar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")] for g in guides]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
    await query.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guide = db.get_guide(int(query.data.split("_")[1]))
    if not guide:
        return
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_guides")]]
    await query.edit_message_text(f"📖 {guide['title']}\n\n{guide['content']}"[:4000], reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  VIDEOLAR
# ═══════════════════════════════════════════
async def menu_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if not is_approved(uid) and not is_premium(uid):
        kb = [[InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium"), InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("💎 Videolar faqat premium uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    videos = db.get_all_videos()
    if not videos:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Hozircha videolar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(f"▶️ {v['title']}", callback_data=f"video_{v['id']}")] for v in videos]
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])
    await query.edit_message_text("🎬 Video darslar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    video = db.get_video(int(query.data.split("_")[1]))
    if not video:
        return
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_videos")]]
    await query.edit_message_text(f"🎬 {video['title']}\n\n{video['description']}\n\n🔗 {video['url']}", reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  NATIJALAR
# ═══════════════════════════════════════════
async def menu_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    results = db.get_user_pdf_results(query.from_user.id)
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
    if not results:
        await query.edit_message_text("Hali test yechmagansiz.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = "📊 Natijalaringiz:\n\n"
    for r in results:
        pct = round(r['correct']/r['total']*100) if r['total'] else 0
        text += f"📝 {r['test_title']}: {r['correct']}/{r['total']} ({pct}%)\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  ADMIN: TESTLAR BOSHQARUVI
# ═══════════════════════════════════════════
async def admin_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tests = db.get_all_pdf_tests()
    kb = [[InlineKeyboardButton("➕ Yangi test qo'shish", callback_data="admin_add_pdf")]]
    for t in tests:
        free = "🆓" if t.get("is_free") else "💎"
        kb.append([
            InlineKeyboardButton(f"{free} {t['title']}", callback_data=f"admin_test_view_{t['id']}"),
        ])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await query.edit_message_text("📝 Testlar boshqaruvi:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[3])
    test = db.get_pdf_test(test_id)
    if not test:
        return
    results = db.get_test_results(test_id)
    free = "🆓 Bepul" if test.get("is_free") else "💎 Premium"
    text = (
        f"📝 {test['title']}\n"
        f"{'─'*20}\n"
        f"❓ Savollar: {test['question_count']} ta\n"
        f"🔑 Kalit: {test['answer_key']}\n"
        f"📌 Turi: {free}\n"
        f"👥 Yechganlar: {len(results)} ta\n"
    )
    is_free = test.get("is_free", 0)
    toggle_text = "💎 Premiumga o'tkazish" if is_free else "🆓 Bepulga o'tkazish"
    kb = [
        [InlineKeyboardButton(toggle_text, callback_data=f"admin_test_toggle_{test_id}")],
        [InlineKeyboardButton("📊 Natijalar", callback_data=f"admin_test_results_{test_id}")],
        [InlineKeyboardButton("🗑 O'chirish", callback_data=f"admin_test_delete_{test_id}")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_tests")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[3])
    results = db.get_test_results(test_id)
    test = db.get_pdf_test(test_id)
    if not results:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data=f"admin_test_view_{test_id}")]]
        await query.edit_message_text("Hali hech kim yechmagan.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = f"📊 {test['title']} — natijalar:\n\n"
    for r in results[:20]:
        pct = round(r['correct']/r['total']*100)
        text += f"👤 {r['first_name']}: {r['correct']}/{r['total']} ({pct}%)\n"
    kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data=f"admin_test_view_{test_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[3])
    test = db.get_pdf_test(test_id)
    new_val = 0 if test.get("is_free") else 1
    db.set_test_free(test_id, new_val)
    await admin_test_view(update, context)

async def admin_test_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[3])
    kb = [
        [InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"admin_test_delete_confirm_{test_id}")],
        [InlineKeyboardButton("❌ Yo'q", callback_data=f"admin_test_view_{test_id}")],
    ]
    await query.edit_message_text("Testni o'chirishni tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(kb))

async def admin_test_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[4])
    db.delete_pdf_test(test_id)
    await admin_tests(update, context)

# ═══════════════════════════════════════════
#  ADMIN: FOYDALANUVCHILAR
# ═══════════════════════════════════════════
async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = [
        [InlineKeyboardButton("👥 Barchasi", callback_data="admin_users_all")],
        [InlineKeyboardButton("✅ Tasdiqlangan", callback_data="admin_users_approved")],
        [InlineKeyboardButton("👑 Premium", callback_data="admin_users_premium")],
        [InlineKeyboardButton("⏳ Kutayotgan", callback_data="admin_users_pending")],
        [InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")],
    ]
    await query.edit_message_text("👥 Foydalanuvchilar:", reply_markup=InlineKeyboardMarkup(kb))

async def admin_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    filter_type = query.data.split("_")[2]
    users = db.get_users_by_status(filter_type if filter_type != "all" else None)
    text = f"👥 Foydalanuvchilar ({len(users)} ta):\n\n"
    kb_users = []
    for u in users[:20]:
        status_icon = {"approved":"✅","premium":"👑","pending":"⏳","rejected":"❌","new":"🆕"}.get(u['status'],"👤")
        text += f"{status_icon} {u['first_name']} — {u['status']}\n"
        kb_users.append([InlineKeyboardButton(f"{status_icon} {u['first_name']}", callback_data=f"admin_user_{u['user_id']}")])
    kb_users.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_users")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb_users))

async def admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split("_")[2])
    user = db.get_user(target_id)
    if not user:
        return
    status = user['status']
    exp = db.get_premium_expiry(target_id)
    text = (
        f"👤 {user['first_name']}\n"
        f"🆔 {user['user_id']}\n"
        f"📛 @{user['username'] or 'yoq'}\n"
        f"📌 Status: {status}\n"
    )
    if exp:
        text += f"👑 Premium: {exp.strftime('%d.%m.%Y')} gacha\n"

    kb = []
    if status != "approved":
        kb.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_user_approve_{target_id}")])
    if status != "premium":
        kb.append([InlineKeyboardButton("👑 Premium berish (30 kun)", callback_data=f"admin_user_premium_{target_id}")])
    if status != "rejected":
        kb.append([InlineKeyboardButton("❌ Chiqarib yuborish", callback_data=f"admin_user_kick_{target_id}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_users_all")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    action = parts[3]
    target_id = int(parts[4])

    if action == "approve":
        db.set_user_status(target_id, "approved")
        await context.bot.send_message(chat_id=target_id, text="✅ Kirish tasdiqlandi! /start bosing.")
        await query.answer("✅ Tasdiqlandi!", show_alert=True)
    elif action == "premium":
        expiry = datetime.now() + timedelta(days=PREMIUM_KUN)
        db.set_premium(target_id, expiry)
        await context.bot.send_message(chat_id=target_id, text=f"👑 Premium berildi! {expiry.strftime('%d.%m.%Y')} gacha. /start bosing.")
        await query.answer("👑 Premium berildi!", show_alert=True)
    elif action == "kick":
        db.set_user_status(target_id, "rejected")
        await context.bot.send_message(chat_id=target_id, text="❌ Botdan foydalanish huquqingiz bekor qilindi.")
        await query.answer("❌ Chiqarib yuborildi!", show_alert=True)

    # Yangilangan profilni ko'rsatish
    context.user_data["_refresh"] = True
    query.data = f"admin_user_{target_id}"
    await admin_user_detail(update, context)

# ═══════════════════════════════════════════
#  ADMIN: TO'LOV SO'ROVLARI
# ═══════════════════════════════════════════
async def admin_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payments = db.get_pending_payments()
    if not payments:
        kb = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]]
        await query.edit_message_text("Hozircha kutayotgan to'lovlar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = f"💎 To'lov so'rovlari: {len(payments)} ta\n\nKo'rish uchun foydalanuvchini tanlang:"
    kb = []
    for p in payments:
        kb.append([InlineKeyboardButton(f"💳 {p['first_name']}", callback_data=f"admin_user_{p['user_id']}")])
    kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════
#  ADMIN: CONTENT QO'SHISH
# ═══════════════════════════════════════════
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    data = query.data

    if data == "admin_add_pdf":
        context.user_data["admin_action"] = "waiting_pdf_title"
        await query.edit_message_text("📝 Test nomini yozing:\n(Masalan: Ona tili — 1-variant)\n\nBekor: /admin")

    elif data == "admin_guides":
        guides = db.get_all_guides()
        kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="admin_add_guide")]]
        for g in guides:
            kb.append([InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"admin_guide_del_{g['id']}")])
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
        await query.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "admin_add_guide":
        context.user_data["admin_action"] = "add_guide_title"
        await query.edit_message_text("📚 Qo'llanma sarlavhasini yozing:")

    elif data.startswith("admin_guide_del_"):
        guide_id = int(data.split("_")[3])
        db.delete_guide(guide_id)
        await query.answer("O'chirildi!", show_alert=True)
        query.data = "admin_guides"
        await admin_callback(update, context)

    elif data == "admin_videos":
        videos = db.get_all_videos()
        kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="admin_add_video")]]
        for v in videos:
            kb.append([InlineKeyboardButton(f"▶️ {v['title']}", callback_data=f"admin_video_del_{v['id']}")])
        kb.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")])
        await query.edit_message_text("🎬 Videolar:", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "admin_add_video":
        context.user_data["admin_action"] = "add_video_title"
        await query.edit_message_text("🎬 Video sarlavhasini yozing:")

    elif data.startswith("admin_video_del_"):
        video_id = int(data.split("_")[3])
        db.delete_video(video_id)
        await query.answer("O'chirildi!", show_alert=True)
        query.data = "admin_videos"
        await admin_callback(update, context)

    elif data == "admin_stats":
        s = db.get_stats()
        await query.edit_message_text(
            f"📊 Statistika:\n\n"
            f"👥 Jami: {s['total_users']}\n"
            f"✅ Tasdiqlangan: {s['approved_users']}\n"
            f"👑 Premium: {s['premium_users']}\n"
            f"⏳ Kutayotgan: {s['pending_users']}\n"
            f"📝 Testlar: {s['total_pdf_tests']}\n"
            f"📚 Qo'llanmalar: {s['total_guides']}\n"
            f"🎬 Videolar: {s['total_videos']}\n"
            f"🏆 Jami natijalar: {s['total_results']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="admin_back")]])
        )

    elif data == "admin_broadcast":
        context.user_data["admin_action"] = "broadcast_message"
        await query.edit_message_text("📢 Xabar matnini yozing (barcha tasdiqlangan foydalanuvchilarga yuboriladi):\n\nBekor: /admin")

    elif data == "admin_back":
        await show_admin_menu(update, context)

async def handle_pdf_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_action") != "waiting_pdf_file":
        return
    file_id = update.message.document.file_id
    context.user_data["new_pdf_file_id"] = file_id
    context.user_data["admin_action"] = "waiting_pdf_key"
    count = context.user_data.get("new_pdf_count", 30)
    await update.message.reply_text(f"✅ PDF qabul qilindi!\n\nEndi {count} ta javob kalitini yozing:\nMasalan: ABCDABCD... ({count} ta harf)")

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return False
    action = context.user_data.get("admin_action", "")
    text = update.message.text.strip() if update.message and update.message.text else ""

    if action == "waiting_pdf_title":
        context.user_data["new_pdf_title"] = text
        context.user_data["admin_action"] = "waiting_pdf_count"
        await update.message.reply_text(f"✅ Nom: {text}\n\nNechta savol? (Masalan: 30)")

    elif action == "waiting_pdf_count":
        try:
            count = int(text)
            context.user_data["new_pdf_count"] = count
            context.user_data["admin_action"] = "waiting_pdf_is_free"
            kb = [
                [InlineKeyboardButton("🆓 Bepul", callback_data="pdf_type_free")],
                [InlineKeyboardButton("💎 Premium", callback_data="pdf_type_premium")],
            ]
            await update.message.reply_text(f"Savollar: {count} ta\n\nTest turi:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif action == "waiting_pdf_key":
        title = context.user_data.get("new_pdf_title", "")
        count = context.user_data.get("new_pdf_count", 30)
        file_id = context.user_data.get("new_pdf_file_id", "")
        is_free = context.user_data.get("new_pdf_is_free", 0)
        clean_key = re.sub(r'[^ABCD]', '', text.upper().replace(" ", "").replace(",", ""))
        if len(clean_key) != count:
            await update.message.reply_text(f"⚠️ {len(clean_key)} ta harf, {count} ta kerak. Qaytadan:")
            return True
        db.add_pdf_test(title, file_id, count, clean_key, is_free)
        context.user_data.clear()
        free_text = "🆓 Bepul" if is_free else "💎 Premium"
        await update.message.reply_text(f"✅ Test qo'shildi!\n📝 {title}\n❓ {count} savol\n{free_text}\n\n/admin")

    elif action == "add_guide_title":
        context.user_data["new_guide_title"] = text
        context.user_data["admin_action"] = "add_guide_content"
        await update.message.reply_text("Qo'llanma matnini yozing:")

    elif action == "add_guide_content":
        db.add_guide(context.user_data.get("new_guide_title", ""), text)
        context.user_data.clear()
        await update.message.reply_text("✅ Qo'llanma qo'shildi! /admin")

    elif action == "add_video_title":
        context.user_data["new_video_title"] = text
        context.user_data["admin_action"] = "add_video_desc"
        await update.message.reply_text("Video tavsifini yozing:")

    elif action == "add_video_desc":
        context.user_data["new_video_desc"] = text
        context.user_data["admin_action"] = "add_video_url"
        await update.message.reply_text("Video havolasini yozing (YouTube link):")

    elif action == "add_video_url":
        db.add_video(context.user_data.get("new_video_title", ""), context.user_data.get("new_video_desc", ""), text)
        context.user_data.clear()
        await update.message.reply_text("✅ Video qo'shildi! /admin")

    elif action == "broadcast_message":
        users = db.get_users_by_status("approved") + db.get_users_by_status("premium")
        sent = 0
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['user_id'], text=f"📢 Xabar:\n\n{text}")
                sent += 1
            except:
                pass
        context.user_data.clear()
        await update.message.reply_text(f"✅ Xabar {sent} ta foydalanuvchiga yuborildi.")

    else:
        return False
    return True

async def pdf_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    is_free = 1 if query.data == "pdf_type_free" else 0
    context.user_data["new_pdf_is_free"] = is_free
    context.user_data["admin_action"] = "waiting_pdf_file"
    await query.edit_message_text("✅ Tanlandi!\n\nEndi PDF faylni yuboring:")

# ═══════════════════════════════════════════
#  UMUMIY HANDLER
# ═══════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # To'lov cheki
    if await handle_payment_proof(update, context):
        return
    # Test javoblari
    if await handle_test_answers(update, context):
        return
    # Admin xabarlari
    await handle_admin_message(update, context)

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    kb = [
        [InlineKeyboardButton("📋 Bot haqida ma'lumot", callback_data="about_bot")],
        [InlineKeyboardButton("🆓 Bepul sinab ko'rish", callback_data="free_tests")],
        [InlineKeyboardButton("💎 Premium olish", callback_data="buy_premium")],
        [InlineKeyboardButton("📨 To'liq kirish so'rovi", callback_data="request_access")],
    ]
    await query.edit_message_text(
        f"👋 Salom, {user.first_name}!\n\nQuyidagilardan birini tanlang:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data.clear()
    await show_admin_menu(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(about_bot, pattern="^about_bot$"))
    app.add_handler(CallbackQueryHandler(free_tests_menu, pattern="^free_tests$"))
    app.add_handler(CallbackQueryHandler(buy_premium, pattern="^buy_premium$"))
    app.add_handler(CallbackQueryHandler(send_payment_proof, pattern="^send_payment_proof$"))
    app.add_handler(CallbackQueryHandler(payment_action, pattern="^pay_(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(request_access, pattern="^request_access$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern=r"^(approve|reject)_\d+$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))

    app.add_handler(CallbackQueryHandler(menu_tests, pattern="^menu_tests$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test, pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_test_prompt, pattern=r"^submit_test_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_guides, pattern="^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide, pattern=r"^guide_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_videos, pattern="^menu_videos$"))
    app.add_handler(CallbackQueryHandler(show_video, pattern=r"^video_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_results, pattern="^menu_results$"))

    app.add_handler(CallbackQueryHandler(admin_tests, pattern="^admin_tests$"))
    app.add_handler(CallbackQueryHandler(admin_test_view, pattern=r"^admin_test_view_d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_results, pattern=r"^admin_test_results_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_toggle, pattern=r"^admin_test_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_delete, pattern=r"^admin_test_delete_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_test_delete_confirm, pattern=r"^admin_test_delete_confirm_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_users, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_users_list, pattern="^admin_users_(all|approved|premium|pending)$"))
    app.add_handler(CallbackQueryHandler(admin_user_detail, pattern=r"^admin_user_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_user_action, pattern=r"^admin_user_(approve|premium|kick)_\d+$"))
    app.add_handler(CallbackQueryHandler(admin_payments, pattern="^admin_payments$"))
    app.add_handler(CallbackQueryHandler(pdf_type_callback, pattern="^pdf_type_(free|premium)$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
