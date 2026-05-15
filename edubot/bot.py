import logging, os, re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo('Asia/Tashkent')
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
db = Database()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "123456789"))

def S(key):        return db.get_setting(key) or ""

CHANNEL = "@legistman"  # Majburiy kanal

async def check_channel(uid, bot):
    """Foydalanuvchi kanalga a'zo ekanini tekshirish"""
    try:
        member = await bot.get_chat_member(CHANNEL, uid)
        return member.status not in ("left", "kicked", "banned")
    except:
        return True  # Xato bo'lsa ruxsat ber
def is_admin(uid): return uid == ADMIN_ID

def is_pro(uid):
    u = db.get_user(uid)
    if not u or u["status"] != "pro": return False
    exp = db.get_pro_expiry(uid)
    if not exp or datetime.now(TASHKENT) > exp:
        db.set_user_status(uid, "approved")
        return False
    return True

def is_approved(uid):
    return db.get_user_status(uid) in ("approved", "pro")

def exp_str(uid):
    exp = db.get_pro_expiry(uid)
    return exp.strftime("%d.%m.%Y") if exp else "?"

def uname(u):
    return u.get("full_name") or u.get("first_name") or "Foydalanuvchi"

def back_btn(cb): return InlineKeyboardButton("⬅️ Orqaga", callback_data=cb)

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

    # Kanalga a'zolikni tekshirish
    if not await check_channel(user.id, context.bot):
        kb = [[InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL.lstrip('@')}")],
              [InlineKeyboardButton("✅ A'zo bo'ldim, tekshirish", callback_data="check_join")]]
        await update.message.reply_text(
            f"⚠️ Botdan foydalanish uchun avval\n"
            f"{CHANNEL} kanaliga a'zo bo'ling!\n\n"
            f"A'zo bo'lgach '✅ A'zo bo'ldim' tugmasini bosing.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    ex = db.get_user(user.id)
    if ex and ex.get("full_name"):
        await show_welcome(update, context)
        return

    # Yangi foydalanuvchi — start xabarini ko'rsatib, ism so'raymiz
    context.user_data["step"] = "waiting_fullname"
    sm = db.get_start_message()
    text = sm["text"] if sm else "Xush kelibsiz!"
    photo_id = sm.get("photo_id","") if sm else ""

    kb = [[InlineKeyboardButton("✍️ Ro'yxatdan o'tish", callback_data="do_register")]]
    if photo_id:
        await update.message.reply_photo(
            photo=photo_id, caption=text,
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def do_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_fullname"
    await q.edit_message_text(
        "✍️ Ismingiz va familiyangizni to'liq kiriting:\n\n"
        "📝 Masalan: Mallayev Ozodbek"
    ) if not update.callback_query.message.photo else \
    await context.bot.send_message(
        q.from_user.id,
        "✍️ Ismingiz va familiyangizni to'liq kiriting:\n\n"
        "📝 Masalan: Mallayev Ozodbek"
    )

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanalga a'zolikni qayta tekshirish"""
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if await check_channel(uid, context.bot):
        ex = db.get_user(uid)
        if ex and ex.get("full_name"):
            await show_welcome(update, context)
        else:
            context.user_data["step"] = "waiting_fullname"
            sm = db.get_start_message()
            intro = sm["text"] if sm else "Xush kelibsiz!"
            reg_text = intro + "\n\n✍️ Ismingiz va familiyangizni to'liq kiriting:\n📝 Masalan: Mallayev Ozodbek"
            if sm and sm.get("photo_id"):
                await context.bot.send_photo(uid, photo=sm["photo_id"], caption=reg_text)
                await q.delete_message()
            else:
                await q.edit_message_text(reg_text)
    else:
        kb = [[InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL.lstrip('@')}")],
              [InlineKeyboardButton("✅ A'zo bo'ldim, tekshirish", callback_data="check_join")]]
        await q.answer("Hali a'zo bo'lmadingiz!", show_alert=True)

async def show_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    u    = db.get_user(uid)
    fn   = uname(u) if u else ""
    prem = is_pro(uid)

    if prem:
        header = (
            f"👑 Xush kelibsiz, {fn}!\n\n"
            f"👑 PRO obuna: {exp_str(uid)} gacha aktiv ✅\n\n"
            f"Barcha imkoniyatlar sizga ochiq 🎓"
        )
    else:
        header = (
            f"👋 Xush kelibsiz, {fn}!\n\n"
            f"📌 LEGISTMAN BOT — huquqiy bilimlar platformasi"
        )

    if prem:
        kb = [
            [InlineKeyboardButton("👑 PRO bo'lim",   callback_data="pro_menu")],
            [InlineKeyboardButton("📩 Adminga murojaat",  callback_data="contact_admin")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("ℹ️ Bot haqida ma'lumot", callback_data="about_bot")],
            [InlineKeyboardButton("🆓 Bepul versiya",        callback_data="free_menu")],
            [InlineKeyboardButton("👑 PRO versiya",      callback_data="pro_info")],
            [InlineKeyboardButton("📩 Adminga murojaat",     callback_data="contact_admin")],
        ]

    full_header = header + header2
    if update.callback_query:
        await update.callback_query.edit_message_text(full_header, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(full_header, reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT HAQIDA
# ═══════════════════════════════════════════════════════════════════════════════
async def about_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[back_btn("back_welcome")]]
    await q.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 LEGISTMAN BOT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 @legistman kanalining rasmiy o'quv boti\n\n"
        "Bu bot orqali siz:\n\n"
        "⚖️ Huquq sohasidagi bilimlaringizni\n"
        "   testlar orqali sinab ko'rasiz\n\n"
        "📚 Tizimli va amaliy huquqiy\n"
        "   qo'llanmalar bilan o'rganasiz\n\n"
        "📊 Har bir test bo'yicha batafsil\n"
        "   tahlil va reyting ko'rasiz 🏆\n\n"
        "💡 Bilim — kelajakka eng yaxshi investitsiya!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 Bot yaratuvchisi: @legistman_uz",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  BEPUL MENYU
# ═══════════════════════════════════════════════════════════════════════════════
async def free_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("📝 TESTLAR",          callback_data="free_tests")],
        [InlineKeyboardButton("📚 QO'LLANMALAR",     callback_data="free_guides")],
        [InlineKeyboardButton("👑 PRO obuna olish",   callback_data="buy_pro")],
        [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        [back_btn("back_welcome")],
    ]
    await q.edit_message_text("🆓 Bepul bo'lim", reply_markup=InlineKeyboardMarkup(kb))

async def free_tests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_free_pdf_tests()
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    if not tests:
        kb.append([InlineKeyboardButton("👑 PRO obuna olish", callback_data="buy_pro")])
    kb.append([back_btn("free_menu")])
    await q.edit_message_text(
        "📝 Bepul testlar:" if tests else "⏳ Hozircha bepul testlar yo'q.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def free_guides_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    guides = db.get_free_guides()
    kb = []
    for g in guides:
        kb.append([InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")])
    if not guides:
        kb.append([InlineKeyboardButton("👑 PRO obuna olish", callback_data="buy_pro")])
    kb.append([back_btn("free_menu")])
    await q.edit_message_text(
        "📚 Bepul qo'llanmalar:" if guides else "⏳ Hozircha bepul qo'llanmalar yo'q.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  PREMIUM INFO & MENYU
# ═══════════════════════════════════════════════════════════════════════════════
async def pro_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    price = S("pro_price"); days = S("pro_days")
    kb = [
        [InlineKeyboardButton("💳 To'lov qilish", callback_data="buy_pro")],
        [back_btn("back_welcome")],
    ]
    await q.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 PRO OBUNA\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "PRO a'zo bo'lsangiz:\n\n"
        "✅ Barcha testlarga kirish\n"
        "✅ Har bir xato tahlili + to'g'ri javoblar\n"
        "✅ Barcha huquqiy qo'llanmalar\n"
        "✅ Shaxsiy reyting va statistika\n"
        "✅ Yangi materiallar birinchi bo'lib\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n\n"
        "🎯 Bilimingizni professional darajaga olib chiqing!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def pro_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    kb = [
        [InlineKeyboardButton("📝 Testlar",              callback_data="menu_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",         callback_data="menu_guides")],
        [InlineKeyboardButton("📊 Statistika",           callback_data="user_stats")],
        [InlineKeyboardButton("📩 Adminga murojaat",     callback_data="contact_admin")],
        [back_btn("back_welcome")],
    ]
    await q.edit_message_text(
        f"👑 PRO bo'lim\n\n👑 PRO obuna: {exp_str(uid)} gacha aktiv",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  TO'LOV
# ═══════════════════════════════════════════════════════════════════════════════
async def buy_pro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if is_pro(uid):
        await q.answer("Siz allaqachon PRO foydalanuvchisiz!", show_alert=True)
        return
    price = S("pro_price"); card = S("card_number"); owner = S("card_owner"); days = S("pro_days")
    kb = [
        [InlineKeyboardButton("✅ Chek yuboraman", callback_data="send_payment_proof")],
        [back_btn("pro_info")],
    ]
    await q.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 TO'LOV MA'LUMOTLARI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Narx: {price} so'm / {days} kun\n\n"
        f"Karta raqami:\n`{card}`\n"
        f"Karta egasi: {owner}\n\n"
        "📋 Qadamlar:\n"
        f"1️⃣ Kartaga {price} so'm o'tkering\n"
        "2️⃣ To'lov chekini (screenshot) saqlang\n"
        "3️⃣ Quyidagi tugmani bosib chekni yuboring\n"
        "4️⃣ Admin 24 soat ichida ko'rib chiqadi ✅\n\n"
        "⚡️ Tasdiqlangach PRO obuna darhol yoqiladi!",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def send_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_payment_proof"
    await q.edit_message_text(
        "📸 To'lov chekini yuboring\n\n"
        "Rasm yoki screenshot ko'rinishida yuboring.\n\nBekor: /start"
    )

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat document (PDF/fayl) ko'rinishidagi cheklar uchun — rasmlar handle_photo_upload da"""
    if context.user_data.get("step") != "waiting_payment_proof": return False
    user = update.effective_user
    doc  = update.message.document
    if not doc:
        await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return True
    context.user_data.clear()
    await update.message.reply_text("✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏")
    u    = db.get_user(user.id)
    name = uname(u) if u else user.first_name
    kb   = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{user.id}"),
        InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_no_{user.id}"),
    ]]
    cap = f"💎 Yangi to'lov (fayl)!\n\n👤 {name}\n🆔 {user.id}\n📛 @{user.username or 'yoq'}"
    await context.bot.send_document(ADMIN_ID, doc.file_id, caption=cap, reply_markup=InlineKeyboardMarkup(kb))
    db.add_payment_request(user.id)
    return True

async def payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    action, tid = q.data.split("_")[1], int(q.data.split("_")[2])
    days = int(S("pro_days") or "30")
    old  = q.message.caption or q.message.text or ""
    if action == "ok":
        exp = datetime.now(TASHKENT) + timedelta(days=days)
        db.set_pro(tid, exp)
        try: await q.edit_message_caption(old + f"\n\n✅ Tasdiqlandi! {exp.strftime('%d.%m.%Y')} gacha")
        except: await q.edit_message_text(old + "\n\n✅ Tasdiqlandi!")
        await context.bot.send_message(
            tid,
            f"🎉 PRO OBUNA FAOLLASHTIRILDI!\n\n"
            f"👑 {days} kun — {exp.strftime('%d.%m.%Y')} gacha\n\n"
            f"Barcha imkoniyatlar sizga ochiq! /start bosing. 🚀"
        )
    else:
        try: await q.edit_message_caption(old + "\n\n❌ Rad etildi.")
        except: await q.edit_message_text(old + "\n\n❌ Rad etildi.")
        await context.bot.send_message(tid, "😔 To'lovingiz tasdiqlanmadi.")

# ═══════════════════════════════════════════════════════════════════════════════
#  MUROJAAT
# ═══════════════════════════════════════════════════════════════════════════════
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid  = q.from_user.id
    back = "pro_menu" if is_pro(uid) else "free_menu"
    context.user_data["step"]         = "waiting_contact_msg"
    context.user_data["contact_back"] = back
    await q.edit_message_text(
        "📩 Adminga murojaat\n\n"
        "Fikr-mulohaza yoki takliflaringiz uchun:\n\n"
        "💬 @legistman_uz — to'g'ridan-to'g'ri yozing\n\n"
        "✍️ Yoki murojaatingizni shu yerga yozing,\n"
        "admin 24 soat ichida ko'rib chiqadi:",
        reply_markup=InlineKeyboardMarkup([[back_btn(back)]])
    )

async def admin_reply_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    target_id = int(q.data.replace("reply_", ""))
    u    = db.get_user(target_id)
    name = uname(u) if u else str(target_id)
    context.user_data["step"]          = "admin_reply"
    context.user_data["reply_to_uid"]  = target_id
    context.user_data["reply_to_name"] = name
    await q.edit_message_text(f"✍️ {name} ga javob yozing:\n\nBekor: /admin")



# ═══════════════════════════════════════════════════════════════════════════════
#  TESTLAR
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid) or is_approved(uid)
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = []
    for t in tests:
        ic = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{ic} {t['title']}", callback_data=f"pdf_test_{t['id']}")])
    kb.append([back_btn("pro_menu")])
    await q.edit_message_text(
        "📝 Testlar:" if tests else "⏳ Testlar yo'q.",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_pdf_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; test_id = int(q.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    if not test: return
    if not test.get("is_free") and not is_approved(uid):
        kb = [[InlineKeyboardButton("👑 PRO obuna olish", callback_data="buy_pro"), back_btn("free_menu")]]
        await q.edit_message_text("⭐️ Bu test faqat PRO a'zolar uchun.", reply_markup=InlineKeyboardMarkup(kb))
        return
    n = test.get("question_count", 30)
    context.user_data["step"] = "active_test"
    context.user_data["tid"]  = test_id
    context.user_data["tcnt"] = n

    # Faylni yuborish — protect_content=True (forward va yuklab olish taqiqlangan)
    await context.bot.send_document(
        q.message.chat_id,
        test["file_id"],
        caption=f"📝 {test['title']}\n❓ Savollar: {n} ta\n\nTestni yechib bo'lgach javob yuboring.",
        protect_content=True
    )

    kb = [[InlineKeyboardButton("✏️ Javob yuboraman", callback_data=f"submit_test_{test_id}")]]
    await context.bot.send_message(q.message.chat_id, "Tayyor bo'ldingizmi?", reply_markup=InlineKeyboardMarkup(kb))

async def submit_test_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    test_id = int(q.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    n = test.get("question_count", 30) if test else 30
    import time
    context.user_data["step"]       = "waiting_answers"
    context.user_data["tid"]        = test_id
    context.user_data["tcnt"]       = n
    context.user_data["test_start"] = time.time()
    t_limit = int(S("test_time_limit") or "30")
    await q.edit_message_text(
        f"✏️ {n} ta javobni yuboring!\n\n"
        f"Faqat harflar ketma-ket (ABCD):\n"
        f"Masalan: ABCDABCD...\n\n(Jami {n} ta harf)"
    )

async def handle_test_answers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") != "waiting_answers": return False
    uid = update.effective_user.id
    test_id = context.user_data["tid"]; n = context.user_data["tcnt"]
    clean = re.sub(r"[^ABCD]", "", update.message.text.strip().upper())
    if len(clean) != n:
        await update.message.reply_text(f"⚠️ {len(clean)} ta javob, {n} ta kerak. Qaytadan:")
        return True
    key = re.sub(r"[^ABCD]", "", (db.get_answer_key(test_id) or "").upper())
    if not key:
        await update.message.reply_text("⚠️ Kalit kiritilmagan. Adminga murojaat qiling.")
        return True
    correct = sum(u == k for u, k in zip(clean, key))
    wrong   = n - correct
    ball    = round(correct * 3.1, 1)
    max_b   = round(n * 3.1, 1)
    pct     = round(correct / n * 100)
    if pct >= 85:   baho = "🏆 Ajoyib!"
    elif pct >= 70: baho = "👍 Yaxshi!"
    elif pct >= 50: baho = "📚 Qoniqarli"
    else:           baho = "💪 Ko'proq mashq kerak"

    test_obj     = db.get_pdf_test(test_id)
    is_free_test = test_obj.get("is_free", 0) if test_obj else 0
    prem_user    = is_pro(uid)

    db.save_pdf_result(uid, test_id, correct, n, clean)
    context.user_data.clear()

    result = (
        f"📊 Test natijasi\n{'─'*26}\n"
        f"📋 Jami savollar:    {n} ta\n"
        f"✅ To'g'ri javoblar: {correct} ta\n"
        f"❌ Xato javoblar:    {wrong} ta\n"
        f"🏅 Ball: {ball} / {max_b}\n"
        f"📈 Foiz: {pct}%\n"
        f"🎯 {baho}\n"
    )

    if is_free_test and not prem_user:
        # Bepul test — tahlilsiz, premium jalbi
        result += (
            f"\n{'─'*26}\n"
            f"💡 Batafsil tahlilni ko'rish uchun:\n\n"
            f"👑 PRO obuna obuna oling va:\n"
            f"• Har bir xato savolni bilib oling\n"
            f"• To'g'ri javoblar ro'yxatini oling\n"
            f"• Professional tahlil oling\n\n"
            f"🎯 Natijangizni yanada yaxshilang!"
        )
        kb = [
            [InlineKeyboardButton("📝 Yana test",  callback_data="free_tests")],
            [InlineKeyboardButton("📊 Statistika", callback_data="user_stats")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")],
        ]
    else:
        # Premium test — to'liq tahlil
        xato_lines = [
            f"  {i+1}-savol: Siz ❌{u}  →  To'g'ri ✅{k}"
            for i, (u, k) in enumerate(zip(clean, key)) if u != k
        ]
        togri_list = "\n".join(f"  {i+1}–{k}" for i, k in enumerate(key))
        if xato_lines:
            result += f"\n{'─'*26}\n❌ Xato savollar ({wrong} ta):\n" + "\n".join(xato_lines[:30])
        result += f"\n\n{'─'*26}\n✅ To'g'ri javoblar kaliti:\n{togri_list}"
        kb = [
            [InlineKeyboardButton("📝 Yana test",  callback_data="menu_tests")],
            [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")],
        ]

    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))

    # Bepul foydalanuvchiga ALOHIDA marketing xabari
    if is_free_test and not prem_user:
        price = S("pro_price")
        u     = db.get_user(uid)
        name  = (u.get("full_name") or u.get("first_name","")) if u else ""
        if pct >= 85:
            msg = (
                f"🏆 {name}, siz {pct}% natija ko'rsatdingiz!\n\n"
                f"Bu ajoyib! Lekin bilasizmi — xatolaringiz qayerda?\n\n"
                f"👑 PRO obuna foydalanuvchilar:\n"
                f"✅ Har bir xato savolini aniq ko'radi\n"
                f"🔑 To'g'ri javoblar kalitini oladi\n"
                f"📊 Barcha testlarga kiradi\n"
                f"📚 Maxsus qo'llanmalardan foydalanadi\n\n"
                f"💰 Atigi {price} so'm / 30 kun\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Bilimingizni to'liq namoyon eting! 🚀"
            )
        elif pct >= 50:
            msg = (
                f"📈 {name}, {pct}% — yaxshi natija!\n\n"
                f"Agar xatolaringizni bilsangiz,\n"
                f"keyingi safargi natija yanada yaxshi bo'ladi.\n\n"
                f"👑 PRO obuna bilan nima qo'shiladi:\n"
                f"🔍 Har bir xato savol ko'rsatiladi\n"
                f"✅ To'g'ri javoblar ro'yxati beriladi\n"
                f"📝 Barcha PRO testlar ochiladi\n"
                f"📚 Amaliy qo'llanmalar bilan mustahkamlash\n\n"
                f"💰 {price} so'm / 30 kun\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Xatolardan o'rganish — professionallik belgisi! 💡"
            )
        else:
            msg = (
                f"💪 {name}, har bir urinish sizni oldinga olib boradi!\n\n"
                f"Hozir {pct}% — lekin bu faqat boshlash.\n"
                f"Qaysi mavzularda kamchilik borligini bilib oling.\n\n"
                f"👑 PRO obuna — eng tez o'sish yo'li:\n"
                f"🔍 Xatolaringizni aniq ko'ring\n"
                f"📚 Qo'llanmalar bilan bilimingizni to'ldiring\n"
                f"📝 Cheksiz testlar bilan mashq qiling\n"
                f"🏆 O'z progressingizni kuzating\n\n"
                f"💰 {price} so'm / 30 kun\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Muvaffaqiyat tizimli tayyorgarlik natijasidir! 🎯"
            )
        mk = [[InlineKeyboardButton("👑 PRO obuna olish — hoziroq!", callback_data="buy_pro")]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(mk))

    return True

# ═══════════════════════════════════════════════════════════════════════════════
#  QO'LLANMALAR
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [[back_btn("pro_menu")]]
    await q.edit_message_text(
        "📚 Qo'llanmalar\n\n"
        "Siz PRO foydalanuvchisi hisoblanganingiz uchun\n"
        "@legistman_uz profili bilan bog'laning —\n"
        "sizni QO'LLANMA BAZA kanaliga qo'shib qo'yadi 📖",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1])
    g   = db.get_guide(gid)
    if not g: return
    uid       = q.from_user.id
    prem      = is_pro(uid)
    is_free_g = g.get("is_free", 1)
    back      = "free_guides" if is_free_g else "menu_guides"
    kb        = [[back_btn(back)]]
    file_id   = g.get("file_id","")

    if file_id:
        await context.bot.send_document(
            q.message.chat_id, file_id,
            caption=f"📖 {g['title']}",
            protect_content=True
        )
        await context.bot.send_message(q.message.chat_id, "👆", reply_markup=InlineKeyboardMarkup(kb))
    else:
        await q.edit_message_text(
            f"📖 {g['title']}\n\n{g['content']}"[:4000],
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # Bepul qo'llanmadan keyin alohida marketing xabari
    if is_free_g and not prem:
        price = S("pro_price")
        u     = db.get_user(uid)
        name  = (u.get("full_name") or u.get("first_name","")) if u else ""
        msg   = (
            f"📚 {name}, bu faqat bir namuna!\n\n"
            f"Bizning to'liq qo'llanmalar bazamizda:\n"
            f"📖 Huquqning barcha sohalari bo'yicha materiallar\n"
            f"🎯 BMBA imtihoniga maxsus tayyorgarlik\n"
            f"✅ Amaliy misollar va tahlillar\n"
            f"📝 Har bir mavzu bo'yicha test\n\n"
            f"👑 PRO obuna obuna bilan barchasiga kirish oching.\n\n"
            f"💰 {price} so'm / 30 kun\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Bilim — eng foydali investitsiya! 📈"
        )
        mk = [[InlineKeyboardButton("👑 PRO obuna — barchasini oching!", callback_data="buy_pro")]]
        await context.bot.send_message(q.message.chat_id, msg, reply_markup=InlineKeyboardMarkup(mk))

# ═══════════════════════════════════════════════════════════════════════════════
#  STATISTIKA (FOYDALANUVCHI)
# ═══════════════════════════════════════════════════════════════════════════════
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistika bosh menyusi"""
    q = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid)
    back = "pro_menu" if prem else "free_menu"
    kb   = [
        [InlineKeyboardButton("👤 Shaxsiy natijalar",  callback_data="my_results")],
        [InlineKeyboardButton("🏆 Ommaviy reyting",    callback_data="public_rating")],
        [InlineKeyboardButton("🎁 Do'st taklif qilish", callback_data="my_referral")],
        [back_btn(back)],
    ]
    await q.edit_message_text(
        "📊 Statistika bo'limi\n\n"
        "👤 Shaxsiy natijalar — faqat o'z natijalaringiz\n"
        "🏆 Ommaviy reyting — barcha ishtirokchilar reytingi",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def my_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Do'st taklif qilish bo'limi"""
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid)
    back = "user_stats"
    count  = db.get_referral_count(uid)
    needed = int(S("referral_needed") or "10")
    left   = max(0, needed - (count % needed))
    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
    text = (
        f"🎁 Do'st taklif qilish\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Siz taklif qilganlar: {count} ta\n"
        f"🎯 Keyingi sovg'a uchun: yana {left} ta\n\n"
        f"📌 Qoida:\n"
        f"{needed} ta do'stingiz botga qo'shilsa — sizga\n"
        f"7 kunlik PRO obuna sovg'a beriladi! 🎉\n\n"
        f"🔗 Sizning taklif havolangiz:\n"
        f"{ref_link}"
    )
    kb = [[back_btn(back)]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def my_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shaxsiy natijalar — har bir test bo'yicha alohida"""
    q   = update.callback_query; await q.answer()
    uid = q.from_user.id
    prem = is_pro(uid)
    back = "pro_menu" if prem else "free_menu"
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"📝 {t['title']}", callback_data=f"my_result_{t['id']}")])
    if not tests:
        kb.append([InlineKeyboardButton("📝 Testlarga o'tish", callback_data="menu_tests" if prem else "free_tests")])
    kb.append([back_btn("user_stats")])
    await q.edit_message_text(
        "👤 Shaxsiy natijalar\n\nQaysi test natijasini ko'rmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def my_result_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitta test bo'yicha shaxsiy natija"""
    q      = update.callback_query; await q.answer()
    uid    = q.from_user.id
    tid    = int(q.data.replace("my_result_", ""))
    t      = db.get_pdf_test(tid)
    if not t:
        await q.answer("Test topilmadi!", show_alert=True); return
    results = db.get_user_results_for_test(uid, tid)
    kb = [[back_btn("my_results")]]
    if not results:
        await q.edit_message_text(
            f"📝 {t['title']}\n\nBu testni hali yechmagansiz.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    # Eng yaxshi natija
    best = max(results, key=lambda x: x["correct"])
    last = results[0]
    max_b = round(t["question_count"] * 3.1, 1)
    text = (
        f"👤 Shaxsiy natija\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 {t['title']}\n"
        f"🔢 Jami urinish: {len(results)} marta\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Eng yaxshi natija:\n"
        f"  ✅ To'g'ri: {best['correct']}/{t['question_count']}\n"
        f"  🏅 Ball: {round(best['correct']*3.1,1)} / {max_b}\n"
        f"  📈 Foiz: {round(best['correct']/t['question_count']*100)}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Oxirgi urinish:\n"
        f"  ✅ To'g'ri: {last['correct']}/{t['question_count']}\n"
        f"  🏅 Ball: {round(last['correct']*3.1,1)} / {max_b}\n"
        f"  📈 Foiz: {round(last['correct']/t['question_count']*100)}%\n"
    )
    if len(results) > 1:
        text += f"━━━━━━━━━━━━━━━━━━━━━━\n📋 Barcha urinishlar:\n"
        for i, r in enumerate(results[:5]):
            ball = round(r["correct"]*3.1, 1)
            pct  = round(r["correct"]/t["question_count"]*100)
            date = str(r.get("taken_at",""))[:10]
            text += f"  {i+1}. {ball} ball ({pct}%) — {date}\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def public_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ommaviy reyting — test tanlash"""
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    prem = is_pro(uid)
    tests = db.get_all_pdf_tests() if prem else db.get_free_pdf_tests()
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"🏆 {t['title']}", callback_data=f"pub_rating_{t['id']}")])
    if not tests:
        kb.append([InlineKeyboardButton("📝 Testlarga o'tish", callback_data="menu_tests" if prem else "free_tests")])
    kb.append([back_btn("user_stats")])
    await q.edit_message_text(
        "🏆 Ommaviy reyting\n\nQaysi test reytingini ko'rmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def pub_rating_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitta test bo'yicha TOP 20 reyting"""
    q   = update.callback_query; await q.answer()
    tid = int(q.data.replace("pub_rating_", ""))
    t   = db.get_pdf_test(tid)
    if not t:
        await q.answer("Test topilmadi!", show_alert=True); return
    ratings = db.get_test_rating(tid)
    kb = [[back_btn("public_rating")]]
    if not ratings:
        await q.edit_message_text(
            f"🏆 {t['title']}\n\nHali hech kim bu testni yechmagan.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    medals = {0:"🥇", 1:"🥈", 2:"🥉"}
    max_b  = round(t["question_count"] * 3.1, 1)
    text   = (
        f"🏆 Ommaviy reyting\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 {t['title']}\n"
        f"👥 Ishtirokchilar: {len(ratings)} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    for i, r in enumerate(ratings[:20]):
        medal = medals.get(i, f"{i+1}.")
        ball  = round(r["correct"] * 3.1, 1)
        pct   = round(r["correct"] / r["total"] * 100) if r["total"] else 0
        name  = r.get("full_name") or r.get("first_name","?")
        text += f"{medal} {name} — {ball}/{max_b} ball ({pct}%)\n"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# Eski menu_results — user_stats ga yo'naltiradi
async def menu_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await user_stats(update, context)

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════════════════════════════
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar",            callback_data="adm_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",       callback_data="adm_guides")],
        [InlineKeyboardButton("👥 Foydalanuvchilar",   callback_data="adm_users")],
        [InlineKeyboardButton("👑 PRO obuna so'rovlari",  callback_data="adm_payments")],
        [InlineKeyboardButton("📊 Statistika/Reyting", callback_data="adm_stats")],
        [InlineKeyboardButton("🖼 Start xabari",       callback_data="adm_start_msg")],
        [InlineKeyboardButton("⚙️ Sozlamalar",         callback_data="adm_settings")],
        [InlineKeyboardButton("📢 Xabar yuborish",     callback_data="adm_broadcast")],
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

# ── TESTLAR BOSHQARUVI ───────────────────────────────────────────────────────
async def adm_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [
        [InlineKeyboardButton("➕ Yangi test",      callback_data="adm_test_add")],
        [InlineKeyboardButton("📦 Testlar arxivi",  callback_data="adm_archive")],
    ]
    for t in tests:
        ic = "🆓" if t.get("is_free") else "⭐️"
        kb.append([InlineKeyboardButton(f"{ic} {t['title']}", callback_data=f"atv_{t['id']}")])
    kb.append([back_btn("adm_back")])
    await q.edit_message_text("📝 Testlar boshqaruvi:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    if not t: return
    res = db.get_test_rating(tid)
    ic  = "🆓 Bepul" if t.get("is_free") else "👑 PRO obuna"
    tog = "👑 PROga o'tkazish" if t.get("is_free") else "🆓 Bepulga o'tkazish"
    text = (
        f"📝 {t['title']}\n{'─'*22}\n"
        f"❓ Savollar: {t['question_count']} ta\n"
        f"🔑 Kalit: {t['answer_key']}\n"
        f"📌 Turi: {ic}\n"
        f"👥 Yechganlar: {len(res)} ta"
    )
    kb = [
        [InlineKeyboardButton(f"🔄 {tog}",             callback_data=f"att_{tid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data=f"atn_{tid}")],
        [InlineKeyboardButton("🔑 Kalitni yangilash",   callback_data=f"atk_{tid}")],
        [InlineKeyboardButton("📊 Natijalar/Reyting",   callback_data=f"atr_{tid}")],
        [InlineKeyboardButton("🗑 O'chirish",            callback_data=f"atd_{tid}")],
        [back_btn("adm_tests")],
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_test_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    t   = db.get_pdf_test(tid)
    db.update_pdf_test(tid, is_free=0 if t.get("is_free") else 1)
    new_ic = "🆓 Bepulga o'tkazildi!" if not t.get("is_free") else "👑 PRO obunaga o'tkazildi!"
    await q.answer(new_ic, show_alert=True)
    q.data = f"atv_{tid}"; await adm_test_view(update, context)

async def adm_test_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1])
    res = db.get_test_rating(tid); t = db.get_pdf_test(tid)
    kb  = [[back_btn(f"atv_{tid}")]]
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
    tid = int(q.data.split("_")[1]); t = db.get_pdf_test(tid)
    kb  = [[InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"atdc_{tid}"),
            InlineKeyboardButton("❌ Bekor",         callback_data=f"atv_{tid}")]]
    await q.edit_message_text(
        f"⚠️ '{t['title']}' ni o'chirishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_test_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db.delete_pdf_test(int(q.data.split("_")[1]))
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_tests(update, context)

async def adm_test_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "pdf_title"
    await q.edit_message_text("📝 Yangi test nomi:\nBekor: /admin")

async def adm_test_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1]); t = db.get_pdf_test(tid)
    context.user_data["step"]    = "rename_test"
    context.user_data["edit_id"] = tid
    await q.edit_message_text(f"✏️ Yangi nom:\nHozirgi: {t['title']}\n\nBekor: /admin")

async def adm_test_newkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1]); t = db.get_pdf_test(tid)
    context.user_data["step"]     = "update_key"
    context.user_data["edit_id"]  = tid
    context.user_data["edit_cnt"] = t.get("question_count", 30)
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
    kb.append([back_btn("adm_back")])
    await q.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_guide_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1]); g = db.get_guide(gid)
    if not g: return
    ic  = "🆓 Bepul" if g.get("is_free") else "👑 PRO obuna"
    tog = "👑 PRO obunaga" if g.get("is_free") else "🆓 Bepulga"
    has_file = "✅ Fayl bor" if g.get("file_id") else "❌ Fayl yo'q"
    kb = [
        [InlineKeyboardButton(f"🔄 {tog} o'tkazish",    callback_data=f"agt_{gid}")],
        [InlineKeyboardButton("✏️ Nomini o'zgartirish",  callback_data=f"agn_{gid}")],
        [InlineKeyboardButton("📎 Faylni yangilash",     callback_data=f"agf_{gid}")],
        [InlineKeyboardButton("🗑 O'chirish",            callback_data=f"agd_{gid}")],
        [back_btn("adm_guides")],
    ]
    await q.edit_message_text(
        f"📖 {g['title']}\n{'─'*20}\n📌 Turi: {ic}\n📎 Fayl: {has_file}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_guide_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1]); g = db.get_guide(gid)
    db.update_guide(gid, is_free=0 if g.get("is_free") else 1)
    new_ic = "🆓 Bepulga o'tkazildi!" if g.get("is_free") else "👑 PRO obunaga o'tkazildi!"
    await q.answer(new_ic, show_alert=True)
    q.data = f"agv_{gid}"; await adm_guide_view(update, context)

async def adm_guide_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    gid = int(q.data.split("_")[1]); g = db.get_guide(gid)
    kb  = [[InlineKeyboardButton("✅ Ha", callback_data=f"agdc_{gid}"),
            InlineKeyboardButton("❌ Bekor", callback_data=f"agv_{gid}")]]
    await q.edit_message_text(
        f"'{g['title']}' ni o'chirishni tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_guide_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    db.delete_guide(int(q.data.split("_")[1]))
    await q.answer("✅ O'chirildi!", show_alert=True)
    await adm_guides(update, context)

# ── FOYDALANUVCHILAR ─────────────────────────────────────────────────────────
async def adm_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("👥 Barchasi",     callback_data="aul_all")],
        [InlineKeyboardButton("✅ Tasdiqlangan", callback_data="aul_approved")],
        [InlineKeyboardButton("👑 PRO obuna",      callback_data="aul_pro")],
        [InlineKeyboardButton("⏳ Kutayotgan",   callback_data="aul_pending")],
        [back_btn("adm_back")],
    ]
    await q.edit_message_text("👥 Foydalanuvchilar:", reply_markup=InlineKeyboardMarkup(kb))

async def adm_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ft    = q.data.split("_")[1]
    users = db.get_users_by_status(None if ft == "all" else ft)
    icons = {"approved":"✅","pro":"⭐️","pending":"⏳","rejected":"❌","new":"🆕"}
    kb    = []
    for u in users[:25]:
        ic = icons.get(u["status"],"👤")
        kb.append([InlineKeyboardButton(f"{ic} {uname(u)}", callback_data=f"aud_{u['user_id']}")])
    kb.append([back_btn("adm_users")])
    await q.edit_message_text(
        f"👥 {ft} — {len(users)} ta:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tid = int(q.data.split("_")[1]); u = db.get_user(tid)
    if not u: return
    exp  = db.get_pro_expiry(tid)
    text = (
        f"👤 {uname(u)}\n🆔 {u['user_id']}\n"
        f"📛 @{u['username'] or 'yoq'}\n📌 Status: {u['status']}\n"
    )
    if exp: text += f"👑 PRO obuna: {exp.strftime('%d.%m.%Y')} gacha\n"
    kb = []
    if u["status"] != "approved":
        kb.append([InlineKeyboardButton("✅ Tasdiqlash",             callback_data=f"aua_ok_{tid}")])
    if u["status"] != "pro":
        kb.append([InlineKeyboardButton("👑 PRO obuna berish (30 kun)", callback_data=f"aua_prem_{tid}")])
    if u["status"] == "pro":
        kb.append([InlineKeyboardButton("🚫 PRO obunadan chiqarish",   callback_data=f"aua_unprem_{tid}")])
    if u["status"] not in ("rejected","new"):
        kb.append([InlineKeyboardButton("🚫 Chiqarib yuborish",      callback_data=f"aua_kick_{tid}")])
    kb.append([InlineKeyboardButton("🔄 Qayta ro'yxatdan o'tkazish", callback_data=f"aua_reset_{tid}")])
    kb.append([back_btn("aul_all")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def adm_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, action, tid_str = q.data.split("_", 2)
    tid  = int(tid_str)
    days = int(S("pro_days") or "30")
    msg  = ""
    if action == "ok":
        db.set_user_status(tid, "approved")
        try: await context.bot.send_message(tid, "✅ Botdan foydalanishga ruxsat berildi! /start bosing.")
        except: pass
        msg = "✅ Tasdiqlandi!"
    elif action == "prem":
        exp = datetime.now(TASHKENT) + timedelta(days=days)
        db.set_pro(tid, exp)
        try: await context.bot.send_message(tid, f"👑 PRO obuna berildi! {exp.strftime('%d.%m.%Y')} gacha. /start bosing.")
        except: pass
        msg = "👑 PRO obuna berildi!"
    elif action == "unprem":
        db.remove_pro(tid)
        try: await context.bot.send_message(tid, "ℹ️ PRO obunangiz bekor qilindi.")
        except: pass
        msg = "PRO obuna olib tashlandi!"
    elif action == "kick":
        db.set_user_status(tid, "rejected")
        try: await context.bot.send_message(tid, "🚫 Botdan foydalanish huquqingiz bekor qilindi.")
        except: pass
        msg = "🚫 Chiqarib yuborildi!"
    elif action == "reset":
        db.reset_user(tid)
        try: await context.bot.send_message(tid, "🔄 Ma'lumotlaringiz o'chirildi.\n/start bosib qayta ro'yxatdan o'ting.")
        except: pass
        msg = "🔄 Qayta ro'yxatdan o'tkazildi!"
    elif action == "reset":
        db.reset_user(tid)
        try: await context.bot.send_message(tid, "🔄 Qayta ro'yxatdan o'tishingiz kerak. /start bosing.")
        except: pass
        msg = "🔄 Qayta ro'yxatga o'tkazildi!"
    await q.answer(msg, show_alert=True)
    q.data = f"aud_{tid}"; await adm_user_detail(update, context)

# ── TO'LOV SO'ROVLARI ────────────────────────────────────────────────────────
async def adm_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    pays = db.get_pending_payments()
    kb   = [[InlineKeyboardButton(f"💳 {uname(p)}", callback_data=f"aud_{p['user_id']}")] for p in pays]
    kb.append([back_btn("adm_back")])
    txt = f"💎 Kutayotgan to'lovlar: {len(pays)} ta" if pays else "✅ Kutayotgan to'lovlar yo'q."
    await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

# ── TESTLAR ARXIVI ───────────────────────────────────────────────────────────
async def adm_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    tests = db.get_all_pdf_tests()
    kb = [[back_btn("adm_tests")]]
    if not tests:
        await q.edit_message_text("Hali testlar yo'q.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb2 = []
    for t in tests:
        ic = "🆓" if t.get("is_free") else "⭐️"
        kb2.append([InlineKeyboardButton(f"{ic} {t['title']}", callback_data=f"arv_{t['id']}")])
    kb2.append([back_btn("adm_tests")])
    await q.edit_message_text("📦 Testlar arxivi — kalit ko'rish:", reply_markup=InlineKeyboardMarkup(kb2))

async def adm_archive_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    # arv_ID formatidan ID olish
    try:
        tid = int(q.data.replace("arv_", ""))
    except:
        await q.answer("Xato!", show_alert=True); return

    t = db.get_pdf_test(tid)
    if not t:
        await q.answer("Test topilmadi!", show_alert=True); return

    ic  = "🆓 Bepul" if t.get("is_free") else "👑 PRO obuna"
    key = t.get("answer_key", "")
    n   = t.get("question_count", len(key))

    # Kalitni tartibli ko'rsatish: 5 tadan qatorga ajratish
    rows = []
    for i in range(0, len(key), 5):
        chunk = key[i:i+5]
        row   = "  ".join(f"{i+j+1}.{c}" for j,c in enumerate(chunk))
        rows.append(row)
    kalit_text = "\n".join(rows)

    text = (
        f"🔑 Kalit arxivi\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 {t['title']}\n"
        f"📌 Turi: {ic}\n"
        f"❓ Savollar: {n} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ To'g'ri javoblar:\n\n"
        f"{kalit_text}"
    )

    kb = [
        [InlineKeyboardButton("📊 Reyting ko'rish", callback_data=f"atr_{tid}")],
        [InlineKeyboardButton("✏️ Tahrirlash",      callback_data=f"atv_{tid}")],
        [back_btn("adm_archive")],
    ]
    # 4096 dan oshmasligi uchun
    if len(text) > 4000:
        text = text[:4000] + "..."
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ── STATISTIKA / REYTING ─────────────────────────────────────────────────────
async def adm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    s   = db.get_stats()
    now = datetime.now(TASHKENT).strftime("%d.%m.%Y %H:%M")
    kb  = [
        [InlineKeyboardButton("🔄 Yangilash",                    callback_data="adm_stats")],
        [InlineKeyboardButton("🏆 Umumiy reyting",               callback_data="adm_rating_all")],
        [InlineKeyboardButton("📝 Test bo'yicha reyting",        callback_data="adm_rating_test")],
        [InlineKeyboardButton("👥 So'nggi a'zolar",             callback_data="adm_last_users")],
        [back_btn("adm_back")],
    ]
    await q.edit_message_text(
        "📊 Statistika\n" + "━"*24 + "\n" +
        f"🕐 {now}\n" + "━"*24 + "\n" +
        f"👥 Jami: {s['total_users']}\n" +
        f"✅ Tasdiqlangan: {s['approved_users']}\n" +
        f"👑 PRO obuna: {s['pro_users']}\n" +
        f"⏳ Kutayotgan: {s['pending_users']}\n" +
        f"🆕 Bugun: {s['today_users']}\n" +
        "━"*24 + "\n" +
        f"📝 Testlar: {s['total_pdf_tests']}\n" +
        f"📚 Qo'llanmalar: {s['total_guides']}\n" +
        f"🏆 Jami natijalar: {s['total_results']}\n" +
        f"📈 Bugungi natijalar: {s['today_results']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def adm_last_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    users = db.get_users_by_status(None)[:15]
    icons = {"approved":"✅","pro":"⭐️","pending":"⏳","rejected":"❌","new":"🆕"}
    parts = ["👥 So'nggi a'zolar:\n" + "━"*24]
    for u in users:
        ic   = icons.get(u["status"],"👤")
        name = uname(u)
        date = str(u.get("joined_at",""))[:10]
        parts.append(f"{ic} {name} (@{u['username'] or 'yoq'}) — {date}")
    kb = [[InlineKeyboardButton("⬅️ Statistika", callback_data="adm_stats")]]
    await q.edit_message_text("\n".join(parts), reply_markup=InlineKeyboardMarkup(kb))

async def adm_rating_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ratings = db.get_overall_rating()
    kb = [[back_btn("adm_stats")]]
    if not ratings:
        await q.edit_message_text("Hali natijalar yo'q.", reply_markup=InlineKeyboardMarkup(kb)); return
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
    kb.append([back_btn("adm_stats")])
    await q.edit_message_text("Qaysi test reytingini ko'rmoqchisiz?", reply_markup=InlineKeyboardMarkup(kb))

# ── START XABARI BOSHQARUVI ──────────────────────────────────────────────────
async def adm_start_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sm = db.get_start_message()
    has_photo = "✅ Rasm bor" if sm and sm.get("photo_id") else "❌ Rasm yo'q"
    kb = [
        [InlineKeyboardButton("✏️ Matnni o'zgartirish",  callback_data="sm_edit_text")],
        [InlineKeyboardButton("🖼 Rasm yuklash/o'zgartirish", callback_data="sm_edit_photo")],
        [InlineKeyboardButton("🗑 Rasmni o'chirish",     callback_data="sm_del_photo")],
        [InlineKeyboardButton("👁 Ko'rish (preview)",    callback_data="sm_preview")],
        [back_btn("adm_back")],
    ]
    await q.edit_message_text(
        f"🖼 Start xabari boshqaruvi\n\n{has_photo}\n\n"
        f"Matn: {(sm['text'][:100] + '...') if sm and len(sm['text'])>100 else (sm['text'] if sm else '')}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def sm_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    sm = db.get_start_message()
    if not sm:
        await q.answer("Start xabari yo'q!", show_alert=True); return
    kb = [[back_btn("adm_start_msg")]]
    if sm.get("photo_id"):
        await context.bot.send_photo(
            q.message.chat_id, sm["photo_id"],
            caption=sm["text"],
            reply_markup=InlineKeyboardMarkup(kb)
        )
    else:
        await context.bot.send_message(
            q.message.chat_id, sm["text"],
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ── SOZLAMALAR ───────────────────────────────────────────────────────────────
async def adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    price    = S("pro_price"); card = S("card_number"); owner = S("card_owner")
    t_limit  = S("test_time_limit") or "30"
    ref_need = S("referral_needed") or "10"
    sm       = db.get_start_message()
    has_photo = "✅ Rasm bor" if sm and sm.get("photo_id") else "❌ Rasm yo'q"
    kb = [
        [InlineKeyboardButton("💰 Narxni o'zgartirish",          callback_data="set_price")],
        [InlineKeyboardButton("💳 Karta raqamini o'zgartirish",   callback_data="set_card")],
        [InlineKeyboardButton("👤 Karta egasini o'zgartirish",    callback_data="set_owner")],
        [InlineKeyboardButton("⏱ Test vaqt chegarasi",           callback_data="set_testtime")],
        [InlineKeyboardButton("🎁 Referral soni (PRO uchun)",     callback_data="set_refcount")],
        [InlineKeyboardButton("📝 Start xabarini tahrirlash",     callback_data="set_starttext")],
        [InlineKeyboardButton("🖼 Start rasmini o'zgartirish",    callback_data="set_startphoto")],
        [InlineKeyboardButton("🗑 Start rasmini o'chirish",       callback_data="set_startphoto_del")],
        [back_btn("adm_back")],
    ]
    await q.edit_message_text(
        f"⚙️ Sozlamalar\n{'─'*22}\n"
        f"💰 PRO obuna narxi: {price} so'm / 30 kun\n"
        f"💳 Karta: {card}\n"
        f"👤 Egasi: {owner}\n"
        f"⏱ Test vaqt chegarasi: {t_limit} daqiqa\n"
        f"🎁 PRO uchun taklif soni: {ref_need} ta\n"
        f"🖼 Start rasmi: {has_photo}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ── BROADCAST ────────────────────────────────────────────────────────────────
async def adm_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "broadcast"
    await q.edit_message_text("📢 Xabar matnini yozing:\n\nBekor: /admin")

# ── PDF/GUIDE UPLOAD ─────────────────────────────────────────────────────────
async def handle_start_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start xabari uchun rasm"""
    if not is_admin(update.effective_user.id): return
    if context.user_data.get("step") != "set_startphoto": return
    photo = update.message.photo
    if not photo:
        await update.message.reply_text("Iltimos rasm (photo) yuboring.")
        return
    file_id = photo[-1].file_id
    db.update_start_message(photo_id=file_id)
    context.user_data.clear()
    kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
           InlineKeyboardButton("🔧 Admin panel",  callback_data="adm_back")]]
    await update.message.reply_text("✅ Start rasmi yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

async def handle_pdf_or_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    step = context.user_data.get("step","")
    if step == "waiting_pdf_file":
        context.user_data["pdf_file_id"] = update.message.document.file_id
        context.user_data["step"]        = "pdf_key"
        n = context.user_data.get("pdf_count", 30)
        await update.message.reply_text(
            f"✅ PDF qabul qilindi!\n\n{n} ta javob kalitini yozing (ABCD):"
        )
    elif step == "waiting_guide_file":
        context.user_data["guide_file_id"]  = update.message.document.file_id
        context.user_data["guide_content"]  = update.message.document.file_name or "PDF fayl"
        context.user_data["step"] = "add_guide_type"
        kb = [[InlineKeyboardButton("🆓 Bepul",    callback_data="guide_type_free"),
               InlineKeyboardButton("👑 PRO obuna", callback_data="guide_type_premium")]]
        await update.message.reply_text(
            f"✅ PDF qabul qilindi!\n\nQo'llanma turi:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    elif step == "sm_edit_photo":
        db.update_start_message(photo_id=update.message.document.file_id)
        context.user_data.clear()
        kb = [[back_btn("adm_start_msg")]]
        await update.message.reply_text("✅ Rasm yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha rasm xabarlari — to'lov cheki, start rasmi"""
    uid  = update.effective_user.id
    step = context.user_data.get("step","")

    # 1. To'lov cheki (har qanday foydalanuvchi)
    if step == "waiting_payment_proof":
        user  = update.effective_user
        photo = update.message.photo
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏"
        )
        u    = db.get_user(user.id)
        name = uname(u) if u else user.first_name
        kb = [[
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{user.id}"),
            InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_no_{user.id}"),
        ]]
        cap = (
            f"💎 Yangi to'lov so'rovi!\n\n"
            f"👤 {name}\n"
            f"🆔 {user.id}\n"
            f"📛 @{user.username or 'yoq'}"
        )
        await context.bot.send_photo(
            ADMIN_ID, photo[-1].file_id,
            caption=cap, reply_markup=InlineKeyboardMarkup(kb)
        )
        db.add_payment_request(user.id)
        return

    # 2. Start rasmi (faqat admin)
    if not is_admin(uid): return

    if step in ("sm_edit_photo", "set_startphoto"):
        photo_id = update.message.photo[-1].file_id
        db.update_start_message(photo_id=photo_id)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
               back_btn("adm_back")]]
        await update.message.reply_text("✅ Start rasmi yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  MATN XABARLARI
# ═══════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    step = context.user_data.get("step","")
    txt  = update.message.text.strip() if update.message and update.message.text else ""

    # Murojaat xabari
    if step == "waiting_contact_msg":
        back = context.user_data.get("contact_back","free_menu")
        u    = db.get_user(uid)
        name = uname(u) if u else str(uid)
        context.user_data.clear()
        # Adminga reply tugmasi bilan yuborish
        kb_admin = [[InlineKeyboardButton(f"↩️ {name} ga javob berish", callback_data=f"reply_{uid}")]]
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Yangi murojaat!\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {name}\n🆔 {uid}\n"
            f"📛 @{update.effective_user.username or 'yoq'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n💬 {txt}",
            reply_markup=InlineKeyboardMarkup(kb_admin)
        )
        # Foydalanuvchiga 2 ta tugma bilan javob
        kb = [
            [InlineKeyboardButton("📩 Yana murojaat yuborish", callback_data="contact_admin")],
            [InlineKeyboardButton("🏠 Menyuga qaytish",        callback_data=back)],
        ]
        await update.message.reply_text(
            "✅ Murojaatingiz adminga yuborildi! 🙏\n\nAdmin 24 soat ichida ko'rib chiqadi.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # Admin reply
    if step == "admin_reply" and is_admin(uid):
        target_id   = context.user_data.get("reply_to_uid")
        target_name = context.user_data.get("reply_to_name", "")
        context.user_data.clear()
        if not target_id:
            await update.message.reply_text("❌ Xato: foydalanuvchi topilmadi. /admin")
            return
        try:
            await context.bot.send_message(
                target_id,
                "📬 Admin javobi:\n━━━━━━━━━━━━━━━━━━━━━━\n" + txt
            )
            kb = [[InlineKeyboardButton("🔧 Admin panel", callback_data="adm_back")]]
            await update.message.reply_text(
                f"✅ Javob yuborildi → {target_name}",
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception:
            await update.message.reply_text(
                "❌ Xabar yuborib bo'lmadi. Foydalanuvchi botni bloklagan bo'lishi mumkin."
            )
        return

    if step == "waiting_payment_proof":
        await handle_payment_proof(update, context); return

    # Test javoblari
    if step == "waiting_answers":
        await handle_test_answers(update, context); return

    # Yangi foydalanuvchi ism
    if step == "waiting_fullname":
        if len(txt.split()) < 2:
            await update.message.reply_text(
                "To'liq ism va familiyangizni kiriting.\nMasalan: Mallayev Ozodbek"
            )
            return
        db.add_user(uid, update.effective_user.username or "", update.effective_user.first_name, txt)

        # Referral saqlash
        ref_id = context.user_data.get("ref_id")
        if ref_id and not db.referral_exists(uid):
            db.add_referral(ref_id, uid)
            ref_count = db.get_referral_count(ref_id)
            needed    = int(S("referral_needed") or "10")
            if ref_count >= needed and ref_count % needed == 0:
                # PRO obuna berish
                from datetime import timedelta
                exp = datetime.now(TASHKENT) + timedelta(days=7)
                db.set_pro(ref_id, exp)
                try:
                    await context.bot.send_message(
                        ref_id,
                        f"🎁 Tabrik! {needed} ta do'stingiz botga qo'shildi!\n\n"
                        f"Sovg'a sifatida sizga 7 kunlik PRO obuna berildi!\n"
                        f"👑 PRO obuna: {exp.strftime('%d.%m.%Y')} gacha aktiv"
                    )
                except: pass

        context.user_data.clear()
        # Adminga bildirishnoma
        try:
            uobj = update.effective_user
            await context.bot.send_message(
                ADMIN_ID,
                f"🆕 Yangi foydalanuvchi ro'yxatdan o'tdi!\n\n"
                f"👤 Ism-familiya: {txt}\n"
                f"🆔 ID: {uid}\n"
                f"📛 Username: @{uobj.username or 'yoq'}\n"
                f"📱 Telegram: {uobj.first_name}"
            )
        except: pass
        await show_welcome(update, context)
        return

    if not is_admin(uid): return

    # ── Admin amallar ──
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
                   InlineKeyboardButton("👑 PRO obuna", callback_data="pdf_type_premium")]]
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
        title   = context.user_data.get("pdf_title","")
        file_id = context.user_data.get("pdf_file_id","")
        is_free = context.user_data.get("pdf_is_free", 0)
        db.add_pdf_test(title, file_id, n, clean, is_free)
        context.user_data.clear()
        ic = "🆓 Bepul" if is_free else "👑 PRO obuna"
        kb = [[InlineKeyboardButton("📝 Testlarga",   callback_data="adm_tests"),
               InlineKeyboardButton("🔧 Admin panel", callback_data="adm_back")]]
        await update.message.reply_text(
            f"✅ Test qo'shildi!\n📝 {title}\n{ic}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif step == "rename_test":
        tid = context.user_data["edit_id"]
        db.update_pdf_test(tid, title=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📝 Testga qaytish", callback_data=f"atv_{tid}"),
               InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "update_key":
        n     = context.user_data.get("edit_cnt", 30)
        clean = re.sub(r"[^ABCD]", "", txt.upper())
        if len(clean) != n:
            await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:")
            return
        tid = context.user_data["edit_id"]
        db.update_pdf_test(tid, answer_key=clean)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📝 Testga qaytish", callback_data=f"atv_{tid}"),
               InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")]]
        await update.message.reply_text("✅ Kalit yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "add_guide_title":
        context.user_data["guide_title"] = txt
        context.user_data["step"]        = "waiting_guide_file"
        await update.message.reply_text(
            f"✅ Sarlavha: {txt}\n\nEndi PDF faylni yuboring:\n\nBekor: /admin"
        )

    elif step == "agn_edit":
        gid = context.user_data["edit_id"]
        db.update_guide(gid, title=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📖 Qo'llanmaga", callback_data=f"agv_{gid}"),
               InlineKeyboardButton("🔧 Admin panel", callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Nom yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "set_starttext":
        db.update_start_message(text=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
               InlineKeyboardButton("🔧 Admin panel",  callback_data="adm_back")]]
        await update.message.reply_text("✅ Start xabari yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "set_testtime":
        try:
            int(txt)
            db.set_setting("test_time_limit", txt)
            context.user_data.clear()
            kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"), back_btn("adm_back")]]
            await update.message.reply_text(f"✅ Vaqt chegarasi: {txt} daqiqa", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")

    elif step == "set_refcount":
        try:
            int(txt)
            db.set_setting("referral_needed", txt)
            context.user_data.clear()
            kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"), back_btn("adm_back")]]
            await update.message.reply_text(f"✅ Taklif soni: {txt} ta", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 10")

    elif step == "set_price":
        db.set_setting("pro_price", txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
               InlineKeyboardButton("🔧 Admin panel",  callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Narx yangilandi: {txt} so'm", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "set_card":
        db.set_setting("card_number", txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
               InlineKeyboardButton("🔧 Admin panel",  callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Karta yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "set_owner":
        db.set_setting("card_owner", txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings"),
               InlineKeyboardButton("🔧 Admin panel",  callback_data="adm_back")]]
        await update.message.reply_text(f"✅ Karta egasi yangilandi: {txt}", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "sm_edit_text":
        db.update_start_message(text=txt)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("🖼 Start xabariga", callback_data="adm_start_msg"),
               InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")]]
        await update.message.reply_text("✅ Start xabari yangilandi!", reply_markup=InlineKeyboardMarkup(kb))

    elif step == "broadcast":
        users = db.get_all_users(); sent = 0
        for u in users:
            if u["status"] in ("approved","pro"):
                try: await context.bot.send_message(u["user_id"], f"📢\n\n{txt}"); sent += 1
                except: pass
        context.user_data.clear()
        kb = [[InlineKeyboardButton("🔧 Admin panel", callback_data="adm_back")]]
        await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.", reply_markup=InlineKeyboardMarkup(kb))

# ═══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════════
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    data = q.data

    if   data == "adm_back":          await show_admin_menu(update, context)
    elif data == "adm_tests":          await adm_tests(update, context)
    elif data == "adm_guides":         await adm_guides(update, context)
    elif data == "adm_users":          await adm_users(update, context)
    elif data == "adm_payments":       await adm_payments(update, context)
    elif data == "adm_stats":          await adm_stats(update, context)
    elif data == "adm_settings":       await adm_settings(update, context)
    elif data == "adm_broadcast":      await adm_broadcast(update, context)
    elif data == "adm_rating_all":     await adm_rating_all(update, context)
    elif data == "adm_rating_test":    await adm_rating_test_list(update, context)
    elif data == "adm_test_add":       await adm_test_add_prompt(update, context)
    elif data == "adm_start_msg":      await adm_start_msg(update, context)
    elif data == "sm_preview":         await sm_preview(update, context)
    elif data == "sm_edit_text":
        context.user_data["step"] = "sm_edit_text"
        await q.edit_message_text("✏️ Yangi start xabari matnini yozing:\n\nBekor: /admin")
    elif data == "sm_edit_photo":
        context.user_data["step"] = "sm_edit_photo"
        await q.edit_message_text("🖼 Rasm yuboring (foto yoki PDF):\n\nBekor: /admin")
    elif data == "sm_del_photo":
        db.update_start_message(photo_id="")
        await q.answer("✅ Rasm o'chirildi!", show_alert=True)
        await adm_start_msg(update, context)
    elif data == "adm_guide_add":
        context.user_data["step"] = "add_guide_title"
        await q.edit_message_text("📚 Qo'llanma sarlavhasini yozing:\nBekor: /admin")

    elif data.startswith("pdf_type_"):
        is_free = 1 if data == "pdf_type_free" else 0
        context.user_data["pdf_is_free"] = is_free
        context.user_data["step"]        = "waiting_pdf_file"
        await q.edit_message_text("✅ Turi tanlandi!\n\nEndi PDF faylni yuboring:")

    elif data.startswith("guide_type_"):
        is_free = 1 if data == "guide_type_free" else 0
        db.add_guide(
            context.user_data.get("guide_title",""),
            context.user_data.get("guide_content",""),
            is_free,
            context.user_data.get("guide_file_id","")
        )
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📚 Qo'llanmalarga", callback_data="adm_guides"),
               InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")]]
        await q.edit_message_text("✅ Qo'llanma qo'shildi!", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("agv_"):   await adm_guide_view(update, context)
    elif data.startswith("agt_"):   await adm_guide_toggle(update, context)
    elif data.startswith("agd_"):   await adm_guide_delete(update, context)
    elif data.startswith("agdc_"):  await adm_guide_delete_ok(update, context)
    elif data.startswith("agn_"):
        gid = int(data.split("_")[1])
        context.user_data["step"]    = "agn_edit"
        context.user_data["edit_id"] = gid
        g = db.get_guide(gid)
        await q.edit_message_text(f"✏️ Yangi sarlavha:\nHozirgi: {g['title']}\nBekor: /admin")
    elif data.startswith("agf_"):
        gid = int(data.split("_")[1])
        context.user_data["step"]         = "waiting_guide_file"
        context.user_data["guide_title"]  = db.get_guide(gid)["title"]
        context.user_data["edit_guide_id"]= gid
        await q.edit_message_text("📎 Yangi PDF faylni yuboring:\n\nBekor: /admin")

    elif data.startswith("set_"):
        hints = {
            "set_price":      "💰 Yangi narxni yozing (masalan: 349 000):",
            "set_card":       "💳 Yangi karta raqamini yozing:",
            "set_owner":      "👤 Yangi karta egasi ismini yozing:",
            "set_starttext":  "📝 Yangi start xabari matnini yozing:",
            "set_startphoto": "🖼 Start uchun rasm yuboring:",
            "set_testtime":   "⏱ Test vaqt chegarasini daqiqalarda yozing (masalan: 30):",
            "set_refcount":   "🎁 PRO obuna uchun nechta do'st taklif qilish kerakligini yozing (masalan: 10):",
        }
        context.user_data["step"] = data
        await q.edit_message_text(hints.get(data,"Yangi qiymat:") + "\n\nBekor: /admin")

async def back_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await show_welcome(update, context)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
async def pro_expiry_reminder(context):
    """PRO tugashiga 3 kun qolganida eslatma"""
    from datetime import timedelta
    users = db.get_users_by_status("pro")
    for u in users:
        exp = db.get_pro_expiry(u["user_id"])
        if not exp: continue
        days_left = (exp - datetime.now(TASHKENT)).days
        if days_left == 3:
            try:
                await context.bot.send_message(
                    u["user_id"],
                    f"⏰ Eslatma!\n\n"
                    f"👑 PRO obunangiz {exp.strftime('%d.%m.%Y')} da tugaydi\n"
                    f"(3 kun qoldi)\n\n"
                    f"Uzilmaslik uchun yangilang! 👇",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👑 PRO obunani yangilash", callback_data="buy_pro")]
                    ])
                )
            except: pass

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))

    # Umumiy
    app.add_handler(CallbackQueryHandler(do_register,        pattern=r"^do_register$"))
    app.add_handler(CallbackQueryHandler(about_bot,          pattern=r"^about_bot$"))
    app.add_handler(CallbackQueryHandler(free_menu,          pattern=r"^free_menu$"))
    app.add_handler(CallbackQueryHandler(free_tests_list,    pattern=r"^free_tests$"))
    app.add_handler(CallbackQueryHandler(free_guides_list,   pattern=r"^free_guides$"))
    app.add_handler(CallbackQueryHandler(pro_info,       pattern=r"^pro_info$"))
    app.add_handler(CallbackQueryHandler(pro_menu,       pattern=r"^pro_menu$"))
    app.add_handler(CallbackQueryHandler(buy_pro,        pattern=r"^buy_pro$"))
    app.add_handler(CallbackQueryHandler(send_payment_proof, pattern=r"^send_payment_proof$"))
    app.add_handler(CallbackQueryHandler(payment_action,     pattern=r"^pay_(ok|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(contact_admin,      pattern=r"^contact_admin$"))
    app.add_handler(CallbackQueryHandler(admin_reply_prompt, pattern=r"^reply_\d+$"))
    app.add_handler(CallbackQueryHandler(back_welcome,       pattern=r"^back_welcome$"))
    app.add_handler(CallbackQueryHandler(check_join,          pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(my_referral,         pattern=r"^my_referral$"))

    # Testlar
    app.add_handler(CallbackQueryHandler(menu_tests,         pattern=r"^menu_tests$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test,      pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_test_prompt, pattern=r"^submit_test_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_guides,        pattern=r"^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide,         pattern=r"^guide_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_results,       pattern=r"^menu_results$"))
    app.add_handler(CallbackQueryHandler(user_stats,          pattern=r"^user_stats$"))
    app.add_handler(CallbackQueryHandler(my_results,          pattern=r"^my_results$"))
    app.add_handler(CallbackQueryHandler(my_result_detail,    pattern=r"^my_result_\d+$"))
    app.add_handler(CallbackQueryHandler(public_rating,       pattern=r"^public_rating$"))
    app.add_handler(CallbackQueryHandler(pub_rating_detail,   pattern=r"^pub_rating_\d+$"))

    # Admin testlar
    app.add_handler(CallbackQueryHandler(adm_tests,          pattern=r"^adm_tests$"))
    app.add_handler(CallbackQueryHandler(adm_test_view,      pattern=r"^atv_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_toggle,    pattern=r"^att_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_results,   pattern=r"^atr_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete,    pattern=r"^atd_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_delete_ok, pattern=r"^atdc_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_rename,    pattern=r"^atn_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_test_newkey,    pattern=r"^atk_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_archive,        pattern=r"^adm_archive$"))
    app.add_handler(CallbackQueryHandler(adm_archive_view,   pattern=r"^arv_\d+$"))

    # Admin foydalanuvchilar
    app.add_handler(CallbackQueryHandler(adm_users_list,   pattern=r"^aul_(all|approved|pro|pending)$"))
    app.add_handler(CallbackQueryHandler(adm_user_detail,  pattern=r"^aud_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_user_action,  pattern=r"^aua_(ok|prem|unprem|kick|reset)_\d+$"))

    # Admin umumiy
    app.add_handler(CallbackQueryHandler(cb_handler, pattern=r"^(adm_|pdf_type_|guide_type_|set_|agv_|agt_|agd_|agdc_|agn_|agf_|sm_|do_register)"))

    # Fayllar
    app.add_handler(MessageHandler(filters.Document.PDF,                   handle_pdf_or_guide))
    app.add_handler(MessageHandler(filters.Document.ALL & ~filters.Document.PDF, handle_pdf_or_guide))
    app.add_handler(MessageHandler(filters.PHOTO,                          handle_photo_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,        handle_message))

    # PRO eslatma (har kuni 10:00 da)
    job_queue = app.job_queue
    if job_queue:
        from datetime import time as dtime
        job_queue.run_daily(pro_expiry_reminder, time=dtime(hour=10, minute=0), name="pro_reminder")

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
