import logging, os, re, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (Application, CommandHandler, CallbackQueryHandler,
                          MessageHandler, filters, ContextTypes)
from database import Database

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
db       = Database()
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "7869342062"))
TZ        = ZoneInfo("Asia/Tashkent")
WEBAPP_BASE = "https://legistman.github.io/may-edu-loyiham"

WEBAPP_URL = "https://legistman.github.io/LEGISTMAN-WEB-APP"  # GitHub Pages URL

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

    if is_admin(user.id):
        db.add_user(user.id, user.username or "", user.first_name, user.first_name)
        await show_welcome(update, context); return

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
    if update.effective_user:
        uid = update.effective_user.id
    elif update.callback_query:
        uid = update.callback_query.from_user.id
    else:
        return
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

    if uid == ADMIN_ID:
        header = (
            f"🔧 Admin panel\n"
            f"👤 {fn}\n\n"
            f"{goal}"
        )
    elif prem:
        header = (
            f"👑 Xush kelibsiz, {fn}!\n"
            f"PRO obuna: {exp_str(uid)} gacha aktiv ✅\n\n"
            f"{goal}"
        )
    else:
        header = f"👋 Xush kelibsiz, {fn}!\n\n{goal}"
    if badge_str: header += f"\n{badge_str}"

    # Foydalanuvchi ma'lumotlarini Web App ga uzatish
    import base64, json as _json
    wa_data = {
        "full_name":  fn,
        "is_pro":     prem,
        "is_admin":   bool(uid == ADMIN_ID),
        "pro_until":  exp_str(uid) if prem else "",
        "tests_done": len(results),
        "best_ball":  round(max((r.get("correct",0)*3.1 for r in results), default=0), 1),
        "goal_done":  done_today,
        "badges":     badges,
        "is_new":     False,
        "pro_price":  S("pro_price","349 000"),
        "card_num":   S("card_number","9860 3501 4876 2387"),
        "card_own":   S("card_owner","Mallayev Ozodbek"),
        "tests":      [{"id":t["id"],"title":t["title"],"is_free":t.get("is_free",0),
                         "time_limit":t.get("time_limit",30),"question_count":t.get("question_count",30)}
                        for t in db.get_all_pdf_tests()],
        "guides":     [{"id":g["id"],"title":g["title"],"is_free":g.get("is_free",1)}
                        for g in db.get_all_guides()],
    }
    encoded = base64.b64encode(_json.dumps(wa_data, ensure_ascii=True).encode()).decode()
    # start_param ni URL ga qo'shamiz - Telegram Web App qo'llab-quvvatlaydi
    wa_url  = f"{WEBAPP_URL}?d={encoded}"

    kb = [[InlineKeyboardButton("🌐 LEGISTMAN — Ilovani ochish",
                                web_app=WebAppInfo(url=wa_url))]]

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
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📱 Bot haqida to'liq tanishtirish",
                web_app=WebAppInfo(url=WEBAPP_URL))],
            [back("back_welcome")],
        ]))

# ═══════════════════════════════════════════════════════
#  BEPUL MENYU
# ═══════════════════════════════════════════════════════
async def free_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = [
        [InlineKeyboardButton("📝 TESTLAR",          callback_data="free_tests")],
        [InlineKeyboardButton("📚 QO'LLANMALAR",     callback_data="free_guides")],
        [InlineKeyboardButton("📊 Statistika",       callback_data="user_stats")],
        [InlineKeyboardButton("👑 PRO olish",         callback_data="buy_pro")],
        [InlineKeyboardButton("📩 Adminga murojaat", callback_data="contact_admin")],
        [back("back_welcome")],
    ]
    await q.edit_message_text("🆓 Bepul bo'lim", reply_markup=InlineKeyboardMarkup(kb))

async def free_tests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    # Barcha testlar ko'rinadi — bepul ham, PRO ham
    all_tests = db.get_all_pdf_tests()
    kb = []
    for t in all_tests:
        if t.get("is_free"):
            kb.append([InlineKeyboardButton(f"🆓 {t['title']}", callback_data=f"pdf_test_{t['id']}")])
        else:
            kb.append([InlineKeyboardButton(f"🔒 {t['title']}", callback_data=f"pro_locked_{t['id']}")])
    if not all_tests:
        kb.append([InlineKeyboardButton("👑 PRO olish", callback_data="buy_pro")])
    kb.append([back("free_menu")])
    await q.edit_message_text(
        "📝 Testlar ro'yxati\n\n🆓 Bepul  |  🔒 PRO obuna kerak",
        reply_markup=InlineKeyboardMarkup(kb))

async def pro_locked_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bepul foydalanuvchi PRO testga kirishga uringanda marketing xabari"""
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    if is_pro(uid) or is_approved(uid):
        # Aslida PRO — to'g'ri testga yo'naltirish
        test_id = int(q.data.replace("pro_locked_", ""))
        q.data  = f"pdf_test_{test_id}"
        await show_pdf_test(update, context)
        return
    price = S("pro_price","349 000")
    msg = (
        "🔒 Bu test PRO obuna uchun\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Siz hozircha bepul versiyadan foydalanmoqdasiz.\n\n"
        "❌ Bepul versiyada:\n"
        "• Faqat cheklangan testlar\n"
        "• Xato tahlilisiz natija\n"
        "• To'g'ri javoblar ko'rsatilmaydi\n\n"
        "✅ PRO obuna bilan:\n"
        "• Barcha testlarga to'liq kirish\n"
        "• Har bir xato savol ko'rsatiladi\n"
        "• To'g'ri javoblar kaliti beriladi\n"
        "• Shaxsiy reyting va tahlil\n"
        "• Barcha qo'llanmalar\n\n"
        f"💰 Narx: atigi {price} so'm / 30 kun\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Huquq sohasida professional bo'lish\n"
        "uchun eng to'g'ri qaror! ⚖️"
    )
    await q.edit_message_text(
        msg,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 PRO obuna olish", callback_data="buy_pro")],
            [InlineKeyboardButton("⬅️ Orqaga",          callback_data="free_tests")],
        ]))

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
            [InlineKeyboardButton("📸 Chek yuboraman", callback_data="pro_send_proof")],
            [back("back_welcome")],
        ]))

async def pro_send_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_proof"
    await q.edit_message_text(
        "📸 PRO to'lov chekini yuboring (rasm yoki fayl).\n\nBekor: /start")

# ═══════════════════════════════════════════════════════
#  SAHOVAT
# ═══════════════════════════════════════════════════════
async def sahovat_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    card  = S("sahovat_card", S("card_number","9860 3501 4876 2387"))
    owner = S("sahovat_owner", S("card_owner","Mallayev Ozodbek"))
    stats = db.get_sahovat_stats()
    cnt   = stats["confirmed_count"]
    await q.edit_message_text(
        f"🤲 Sahovat — Ezgu amal\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❤️ Har bir to'lovning 50% og'ir betob bolalar\n"
        f"va mehribonlik uyiga yo'naltiriladi.\n\n"
        f"💳 Karta:\n`{card}`\n"
        f"👤 Egasi: {owner}\n\n"
        f"🕊 Jami tasdiqlangan sahovat: {cnt} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Yaxshilik qiling — dunyoni yoritaylik! ✨",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "📱 Sahovat haqida batafsil",
                web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton("🤲 Sahovat qilish",  callback_data="sahovat_amount")],
            [InlineKeyboardButton("📊 Hisobot",         callback_data="sahovat_report")],
            [back("back_welcome")],
        ]))

async def sahovat_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi niyatini tanlaydi"""
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🤲 Niyatingizni tanlang:\n\n"
        "📖 Qo'llanma uchun — qo'llanma olish va yaxshilikka sherik bo'lish\n"
        "❤️ Faqat ehson — 100% og'ir betob bolalar va mehribonlik uyiga",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Qo'llanma uchun", callback_data="sah_niyat_guide")],
            [InlineKeyboardButton("❤️ Faqat ehson",     callback_data="sah_niyat_ehson")],
            [back("sahovat_info")],
        ]))

async def sahovat_niyat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    niyat = "guide" if "guide" in q.data else "ehson"
    context.user_data["sahovat_type"] = niyat

    if niyat == "guide":
        await q.edit_message_text(
            "📖 Qo'llanma uchun sahovat\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Siz to'lagan mablag' ikki qismga bo'linadi:\n\n"
            "🏥 50% — Og'ir betob bolalar va mehribonlik\n"
            "   uyiga to'liq ehson qilinadi\n\n"
            "✍️ 50% — Tunlari uxlamay tayyorlangan\n"
            "   qo'llanmaning qalam haqi bo'ladi\n\n"
            "Shu tariqa siz ham ilm olib, ham savobga\n"
            "sherik bo'lasiz. Har ikki niyat ham go'zal! 🌟\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Miqdorni tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("5 000 so'm",  callback_data="sah_amt_5000"),
                 InlineKeyboardButton("10 000 so'm", callback_data="sah_amt_10000")],
                [InlineKeyboardButton("20 000 so'm", callback_data="sah_amt_20000"),
                 InlineKeyboardButton("50 000 so'm", callback_data="sah_amt_50000")],
                [InlineKeyboardButton("✏️ Boshqa miqdor", callback_data="sah_amt_custom")],
                [back("sahovat_amount")],
            ]))
    else:
        await q.edit_message_text(
            "❤️ Faqat ehson\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Siz to'lagan mablag'ning:\n\n"
            "🏥 100% — Og'ir betob bolalar va mehribonlik\n"
            "   uyiga to'liq ehson qilinadi\n\n"
            "Bu sof niyat bilan qilingan sadaqa —\n"
            "hech qanday manfaat kutmasdan!\n\n"
            "Rasululloh ﷺ aytdilar:\n"
            "«Sadaqa mol-mulkni kamaytirmaydi»\n"
            "( Muslim, 2588 ) 🌙\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💰 Miqdorni tanlang:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("5 000 so'm",  callback_data="sah_amt_5000"),
                 InlineKeyboardButton("10 000 so'm", callback_data="sah_amt_10000")],
                [InlineKeyboardButton("20 000 so'm", callback_data="sah_amt_20000"),
                 InlineKeyboardButton("50 000 so'm", callback_data="sah_amt_50000")],
                [InlineKeyboardButton("✏️ Boshqa miqdor", callback_data="sah_amt_custom")],
                [back("sahovat_amount")],
            ]))

async def sahovat_amount_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    card    = S("sahovat_card", S("card_number","9860 3501 4876 2387"))
    owner   = S("sahovat_owner", S("card_owner","Mallayev Ozodbek"))
    amt_key = q.data.replace("sah_amt_","")
    amounts = {"5000":"5 000","10000":"10 000","20000":"20 000","50000":"50 000"}
    amount  = amounts.get(amt_key,"")
    niyat   = context.user_data.get("sahovat_type","guide")
    foiz    = "50% xayriya / 50% qalam haqi" if niyat == "guide" else "100% xayriya"
    context.user_data["sahovat_amount"] = amount
    context.user_data["step"] = "waiting_sahovat_proof"
    await q.edit_message_text(
        f"✅ Miqdor: {amount} so'm\n"
        f"💡 Taqsimot: {foiz}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 Kartaga o'tkazing:\n`{card}`\n"
        f"👤 Egasi: {owner}\n"
        f"💰 Miqdor: {amount} so'm\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"O'tkazib bo'lgach chekni shu yerga yuboring 📸",
        parse_mode="Markdown")

async def sahovat_amount_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O'zingiz miqdor kiritish"""
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "waiting_sahovat_custom_amount"
    await q.edit_message_text(
        "✏️ Sahovat miqdorini yozing (so'mda):\n\n"
        "Masalan: 15 000\n\nBekor: /start")

async def sahovat_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eski tugma uchun — to'g'ridan miqdor tanlashga yo'naltiradi"""
    q = update.callback_query; await q.answer()
    await sahovat_amount(update, context)

async def sahovat_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    uid  = q.from_user.id
    reports = db.get_sahovat_reports(5)
    stats   = db.get_sahovat_stats()
    total_confirmed = stats["confirmed_count"]
    if not reports:
        text = (
            "📊 Sahovat hisoboti\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Jami tasdiqlangan: {total_confirmed} ta\n\n"
            "Oylik hisobotlar har oy oxirida chop etiladi. 🤝"
        )
    else:
        text = f"📊 Sahovat hisoboti\n━━━━━━━━━━━━━━━━━━━━━━━━\n✅ Jami: {total_confirmed} ta\n\n"
        for r in reports:
            text += (
                f"📅 {r['period']}\n"
                f"💰 Yig'ildi: {r['total_sum']} so'm\n"
                f"🏥 Xayriya: {r['charity_sum']} so'm\n"
                f"✍️ Qalam haqi: {r['author_sum']} so'm\n"
                f"👥 Donorlar: {r['donors_count']} kishi\n"
            )
            if r.get('note'):
                text += f"📝 {r['note']}\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    kb = [
        [InlineKeyboardButton("🔄 Yangilash", callback_data="sahovat_report")],
    ]
    if is_admin(uid):
        kb.append([InlineKeyboardButton("🗑 Hisobotlarni tozalash", callback_data="sah_clear_reports")])
    kb.append([back("sahovat_info")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def sah_clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin hisobotlarni tozalaydi"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    await q.edit_message_text(
        "⚠️ Barcha sahovat hisobotlarini o'chirishni tasdiqlaysizmi?\n\n"
        "Bu amal qaytarib bo'lmaydi!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, o'chirish", callback_data="sah_clear_confirm"),
             InlineKeyboardButton("❌ Bekor",         callback_data="sahovat_report")],
        ]))

async def sah_clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hisobotlarni tasdiqlash bilan tozalash"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db.conn.execute("DELETE FROM sahovat_reports")
    db.conn.commit()
    await q.answer("✅ Hisobotlar tozalandi!", show_alert=True)
    await sahovat_report(update, context)

async def sahovat_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sahovat to'lovini tasdiqlaydi yoki rad etadi"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts  = q.data.split("_")   # sah_ok_PAYID_UID  yoki sah_no_PAYID_UID
    action = parts[1]
    pay_id = int(parts[2])
    uid    = int(parts[3])
    cap    = q.message.caption or q.message.text or ""
    u    = db.get_user(uid)
    name = uname(u) if u else str(uid)

    if action == "ok":
        db.confirm_sahovat_payment(pay_id)

        # Haftalik hisobotni qayta hisoblash (type bo'yicha)
        from datetime import datetime, timedelta
        now      = datetime.now()
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        period   = f"{(now - timedelta(days=6)).strftime('%d.%m')}–{now.strftime('%d.%m.%Y')}"
        stats    = db.get_weekly_sahovat_stats()
        # Haftalik hisobotni yangilash
        db.conn.execute("DELETE FROM sahovat_reports WHERE period=?", (period,))
        db.conn.commit()
        total_str   = f"{stats['grand_total']:,}".replace(",", " ")
        charity_str = f"{stats['total_charity']:,}".replace(",", " ")
        author_str  = f"{stats['total_author']:,}".replace(",", " ")
        db.add_sahovat_report(period, total_str, charity_str, author_str, stats["donors_cnt"])

        # Admin xabarini yangilash
        new_cap = cap + "\n\n✅ Tasdiqlandi! Rahmat ❤️"
        kb_admin = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💬 {name} ga xabar yuborish",
                                 callback_data=f"sah_reply_{uid}")]
        ])
        try:
            await q.edit_message_caption(new_cap, reply_markup=kb_admin)
        except:
            await q.edit_message_text(new_cap, reply_markup=kb_admin)

        # Foydalanuvchiga motivatsion xabar
        pay_row  = db.conn.execute(
            "SELECT payment_type FROM sahovat_payments WHERE id=?", (pay_id,)).fetchone()
        ptype    = pay_row["payment_type"] if pay_row else "guide"
        if ptype == "ehson":
            xayriya_qism = "❤️ To'lovingiz 100% og'ir betob bolalar\nva mehribonlik uyiga yo'naltirildi."
        else:
            xayriya_qism = "❤️ To'lovingizning 50% og'ir betob bolalar\nva mehribonlik uyiga yo'naltirildi."
        motivatsion = (
            f"🤲 Sahovat to'lovingiz tasdiqlandi!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Assalomu alaykum, {name}! 👋\n\n"
            f"Bugun Siz oddiy bir ish qilmadingiz —\n"
            f"Siz birovning hayotiga nur olib kirdingiz. 🌟\n\n"
            f"{xayriya_qism}\n\n"
            f"💡 Bilasizmi?\n"
            f"Rasululloh ﷺ aytdilar:\n"
            f"«Sadaqa mol-mulkni kamaytirmaydi»\n"
            f"(Muslim, 2588)\n\n"
            f"Siz bugun savobga sherik bo'ldingiz —\n"
            f"bu savob, in sha Alloh, Qiyomat kuni\n"
            f"Sizning tarozingizda bo'ladi. 🌙\n\n"
            f"Dunyoni yaxshilar o'zgartiradi.\n"
            f"Siz o'sha yaxshilardansiz! ✨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🙏 Legistman jamoasi nomidan katta rahmat!"
        )
        try:
            await context.bot.send_message(uid, motivatsion)
        except: pass
    else:
        db.reject_sahovat_payment(pay_id)
        try:
            await q.edit_message_caption(cap + "\n\n❌ Rad etildi.")
        except:
            await q.edit_message_text(cap + "\n\n❌ Rad etildi.")
        try:
            await context.bot.send_message(
                uid,
                "😔 Sahovat to'lovingiz tasdiqlanmadi.\n"
                "Iltimos adminga murojaat qiling.")
        except: pass

async def sahovat_edit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sahovat miqdorini tahrirlaydi"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts  = q.data.split("_")  # sah_edit_PAYID_UID
    pay_id = int(parts[2])
    uid    = int(parts[3])
    context.user_data["step"]             = "sah_admin_edit_amount"
    context.user_data["edit_pay_id"]      = pay_id
    context.user_data["edit_pay_uid"]     = uid
    context.user_data["edit_msg_id"]      = q.message.message_id
    context.user_data["edit_msg_caption"] = q.message.caption or q.message.text or ""
    await q.answer()
    await context.bot.send_message(
        q.from_user.id,
        f"✏️ To'lov #{pay_id} uchun haqiqiy miqdorni yozing (so'mda):\n\n"
        f"Masalan: 20 000\n\nBekor: /admin")

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

    # Ketma-ketlik tekshiruvi — birinchi ishlanmagan testni topamiz (ASC tartibda)
    all_tests_list = db.get_all_pdf_tests_asc()
    first_undone = None
    for t_check in all_tests_list:
        if t_check["id"] == test_id:
            break
        if not db.user_completed_test(uid, t_check["id"]):
            first_undone = t_check
            break
    if first_undone:
        fu_title = first_undone["title"]
        fu_id    = first_undone["id"]
        await q.edit_message_text(
            f"⚠️ Ketma-ketlik buzildi!\n\n"
            f"Bu testni ishlash uchun avval:\n"
            f"📝 {fu_title!r} testini yeching.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📝 {fu_title}", callback_data=f"pdf_test_{fu_id}")],
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
                    "⏰ Vaqt tugadi!",
                    chat_id=chat_id, message_id=msg_id)
            except: pass
            # Foydalanuvchiga alohida eslatma xabari
            try:
                await ctx.bot.send_message(
                    chat_id,
                    f"⏰ Test vaqti tugadi!\n\n"
                    f"Javobingiz qabul qilinmadi.\n"
                    f"Qaytadan urinib ko'ring! 💪",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Qaytadan ishlash", callback_data="free_tests")]
                    ]))
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
        togri = ", ".join(f"{i+1}-{k}" for i, k in enumerate(key))
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
        # Bepul foydalanuvchiga marketing — faqat xato SONI
        marketing = (
            f"📊 Natija tahlili:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ Xato javoblar soni: {wrong} ta\n\n"
            f"Qaysi savollarda xato qilganingizni\n"
            f"va to'g'ri javoblarni bilmoqchimisiz?\n\n"
            f"👑 PRO obuna bilan:\n"
            f"✅ Har bir xato savol ko'rsatiladi\n"
            f"✅ To'g'ri javoblar kaliti beriladi\n"
            f"✅ Batafsil tahlil taqdim etiladi\n"
            f"✅ Barcha testlar + qo'llanmalar\n\n"
            f"💰 {S('pro_price','349 000')} so'm / 30 kun\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ Bilim — kelajagingizga investitsiya!"
        )
        await update.message.reply_text(
            marketing,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 PRO obuna — javoblarni ko'rish!", callback_data="buy_pro")],
            ]))

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
    tests = db.get_all_pdf_tests()  # Barcha testlar ko'rinadi
    kb = []
    for t in tests:
        if t.get("is_free") or prem:
            kb.append([InlineKeyboardButton(
                f"{'🆓' if t.get('is_free') else '👑'} {t['title']}",
                callback_data=f"my_result_{t['id']}")])
        else:
            kb.append([InlineKeyboardButton(
                f"🔒 {t['title']}",
                callback_data=f"stat_locked_{t['id']}")])
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

async def stat_locked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bepul foydalanuvchi PRO statistikasiga kirishga uringanda"""
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🔒 Bu statistika faqat PRO obuna uchun\n\n"
        "👑 PRO obuna bilan:\n"
        "✅ Barcha testlar bo'yicha shaxsiy statistika\n"
        "✅ Xato tahlili va to'g'ri javoblar\n"
        "✅ Ommaviy reyting\n\n"
        f"💰 {S('pro_price','349 000')} so'm / 30 kun",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👑 PRO olish", callback_data="buy_pro")],
            [back("my_results")],
        ]))

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

async def sahovat_reply_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin sahovat tasdiqlangandan keyin foydalanuvchiga fayl+xabar yuboradi"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    tid  = int(q.data.replace("sah_reply_", ""))
    u    = db.get_user(tid)
    name = uname(u) if u else str(tid)
    context.user_data["step"]             = "sahovat_reply"
    context.user_data["reply_to_uid"]     = tid
    context.user_data["reply_to_name"]    = name
    await context.bot.send_message(
        q.from_user.id,
        f"📨 {name} ga xabar va/yoki qo'llanma yuboring:\n\n"
        f"• Matn yozsangiz — xabar yuboriladi\n"
        f"• Fayl (PDF) yuborsangiz — fayl biriktiriladi\n"
        f"• Avval fayl, keyin matn yozsangiz — ikkalasi ham yuboriladi\n\n"
        f"Bekor: /admin"
    )

# ═══════════════════════════════════════════════════════
#  ADMIN PANEL
# ═══════════════════════════════════════════════════════
async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📝 Testlar",            callback_data="adm_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar",       callback_data="adm_guides")],
        [InlineKeyboardButton("👥 Foydalanuvchilar",   callback_data="adm_users")],
        [InlineKeyboardButton("💎 To'lov so'rovlari",  callback_data="adm_payments")],
        [InlineKeyboardButton("🤲 Sahovat to'lovlari", callback_data="adm_sahovat")],
        [InlineKeyboardButton("📊 Sahovat hisoboti",   callback_data="adm_sah_report")],
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
    badges, cnt = db.get_user_badges(tid)
    text = (
        f"👤 {uname(u)}\n🆔 {u['user_id']}\n"
        f"📛 @{u['username'] or 'yoq'}\n"
        f"📌 Status: {u['status']}\n"
        f"📊 Yechgan testlar: {cnt} ta\n"
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
    kb.append([InlineKeyboardButton("🗑 Barcha ma'lumotlarni tozalash", callback_data=f"aua_wipe_{tid}")])
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
    elif action == "wipe":
        db.wipe_user(tid)
        try: await context.bot.send_message(tid, "🗑 Barcha ma'lumotlaringiz o'chirildi. /start bosib qayta boshlang.")
        except: pass
        msg = "🗑 Barcha ma'lumotlar o'chirildi!"
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

async def adm_reregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user.id):
        await q.answer("Ruxsat yo'q!", show_alert=True); return
    tid = int(q.data.split("_")[2])
    u   = db.get_user(tid)
    name = uname(u) if u else str(tid)
    try:
        await context.bot.send_message(
            tid,
            "📢 Admin so'rovi:\n\n"
            "✍️ Iltimos, asl ismingiz va familiyangizni to'liq kiriting.\n\n"
            "📝 Masalan: Mallayev Ozodbek",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Ismimni yangilash", callback_data="re_register")]
            ]))
        await q.answer("✅ So'rov yuborildi!", show_alert=True)
        # Xabarni yangilash — admin ko'rsin
        cap = q.message.text or ""
        try:
            await q.edit_message_text(
                cap + f"\n\n♻️ Qayta ro'yxat so'rovi yuborildi → {name}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"💬 {name} ga xabar yuborish",
                                         callback_data=f"reply_{tid}")]
                ]))
        except: pass
    except:
        await q.answer("❌ Xabar yuborib bo'lmadi.", show_alert=True)

async def adm_sahovat_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    pays = db.get_pending_sahovat_payments()
    stats = db.get_sahovat_stats()
    kb = []
    for p in pays:
        name = p.get("full_name") or p.get("first_name") or str(p["user_id"])
        kb.append([InlineKeyboardButton(
            f"🤲 {name}",
            callback_data=f"aud_{p['user_id']}")])
    kb.append([back("adm_back")])
    text = (
        f"🤲 Sahovat to'lovlari\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Kutayotgan: {len(pays)} ta\n"
        f"✅ Jami tasdiqlangan: {stats['confirmed_count']} ta"
    )
    await q.edit_message_text(
        text if pays else "✅ Kutayotgan sahovat to'lovlari yo'q.\n"
                          f"Jami tasdiqlangan: {stats['confirmed_count']} ta",
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

async def adm_sah_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    donors = db.get_confirmed_donors(30)

    if not donors:
        await q.edit_message_text(
            "📊 Sahovat hisoboti\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Hozircha tasdiqlangan sahovat yo'q.",
            reply_markup=InlineKeyboardMarkup([[back("adm_back")]]))
        return

    # Jami hisob
    total = 0; ehson_sum = 0; guide_sum = 0
    for d in donors:
        try: val = int(str(d["amount"]).replace(" ","").replace(",",""))
        except: val = 0
        total += val
        if d["payment_type"] == "ehson":
            ehson_sum += val
        else:
            guide_sum += val

    charity = ehson_sum + guide_sum // 2
    author  = guide_sum - guide_sum // 2

    def fmt(v): return f"{v:,}".replace(",", " ")

    text = (
        f"📊 Sahovat hisoboti\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Jami: {fmt(total)} so'm\n"
        f"🏥 Ehson uchun: {fmt(charity)} so'm\n"
        f"✍️ Qalam haqi: {fmt(author)} so'm\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    kb = []
    for d in donors:
        name  = d.get("full_name") or d.get("first_name") or str(d["user_id"])
        amt   = d["amount"] or "?"
        ptype = "📖" if d["payment_type"] == "guide" else "❤️"
        date  = str(d["created_at"])[:10]
        kb.append([InlineKeyboardButton(
            f"{ptype} {name} — {amt} so'm ({date})",
            callback_data=f"sah_donor_{d['id']}")])

    kb.append([InlineKeyboardButton("🔄 Yangilash",          callback_data="adm_sah_report")])
    kb.append([InlineKeyboardButton("🗑 Hisobotni tozalash", callback_data="adm_sah_clear")])
    kb.append([back("adm_back")])
    await q.edit_message_text(text + f"👥 Donorlar ({len(donors)} ta):",
                              reply_markup=InlineKeyboardMarkup(kb))

async def adm_sah_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    await q.edit_message_text(
        "⚠️ Barcha tasdiqlangan sahovat ma'lumotlarini tozalashni tasdiqlaysizmi?\n\n"
        "Bu amal qaytarib bo'lmaydi!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Ha, tozalash", callback_data="adm_sah_clear_ok"),
             InlineKeyboardButton("❌ Bekor",        callback_data="adm_sah_report")],
        ]))

async def adm_sah_clear_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db.conn.execute("DELETE FROM sahovat_reports")
    db.conn.execute("UPDATE sahovat_payments SET status='cleared' WHERE status='confirmed'")
    db.conn.commit()
    await q.answer("✅ Hisobot tozalandi!", show_alert=True)
    await adm_sah_report(update, context)

async def adm_sah_donor_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Donor tafsiloti + miqdorni tahrirlash"""
    q = update.callback_query; await q.answer()
    pay_id = int(q.data.split("_")[2])
    row = db.conn.execute("""
        SELECT s.*, u.first_name, u.full_name, u.username
        FROM sahovat_payments s JOIN users u ON s.user_id=u.user_id
        WHERE s.id=?""", (pay_id,)).fetchone()
    if not row:
        await q.answer("Topilmadi!", show_alert=True); return
    row  = dict(row)
    name = row.get("full_name") or row.get("first_name") or str(row["user_id"])
    ptype = "📖 Qo'llanma uchun" if row["payment_type"] == "guide" else "❤️ Faqat ehson"
    date  = str(row["created_at"])[:16]
    try:
        val     = int(str(row["amount"]).replace(" ","").replace(",",""))
        if row["payment_type"] == "guide":
            xayriya = f"{val//2:,}".replace(",", " ")
            qalam   = f"{val - val//2:,}".replace(",", " ")
            taqsim  = f"🏥 Ehson: {xayriya} so'm\n✍️ Qalam haqi: {qalam} so'm"
        else:
            taqsim = f"🏥 Ehson: {row['amount']} so'm (100%)"
    except:
        taqsim = "—"

    await q.edit_message_text(
        f"🧾 Donor tafsiloti\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {name}\n"
        f"🆔 {row['user_id']}\n"
        f"📛 @{row['username'] or 'yoq'}\n"
        f"🎯 Niyat: {ptype}\n"
        f"💰 Miqdor: {row['amount']} so'm\n"
        f"📅 Sana: {date}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{taqsim}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Miqdorni tahrirlash",
                                 callback_data=f"sah_edit_donor_{pay_id}")],
            [back("adm_sah_report")],
        ]))

async def sahovat_edit_donor_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin donor miqdorini tahrirlaydi (hisobot ichidan)"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    pay_id = int(q.data.split("_")[3])
    context.user_data["step"]        = "sah_donor_edit_amount"
    context.user_data["edit_pay_id"] = pay_id
    await context.bot.send_message(
        q.from_user.id,
        f"✏️ #{pay_id} donor uchun yangi miqdorni yozing (so'mda):\n\n"
        f"Masalan: 20 000\n\nBekor: /admin")

async def adm_add_sah_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    context.user_data["step"] = "sah_report_period"
    await q.edit_message_text(
        "📅 Hisobot davri yozing:\n\n"
        "Masalan: Aprel 2025  yoki  01.04–30.04.2025\n\n"
        "Bekor: /admin")
async def adm_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q     = update.callback_query; await q.answer()
    price = S("pro_price","349 000"); card = S("card_number"); owner = S("card_owner")
    ch    = S("channel","@legistman")
    sm    = db.get_start_message()
    photo = "✅ Bor" if sm and sm.get("photo_id") else "❌ Yo'q"
    sah_card = S("sahovat_card","—"); sah_owner = S("sahovat_owner","—")
    sah_pct  = S("sahovat_percent","10")
    await q.edit_message_text(
        f"⚙️ Sozlamalar\n{'━'*22}\n"
        f"💰 PRO narx: {price} so'm\n💳 Karta: {card}\n"
        f"👤 Egasi: {owner}\n📢 Kanal: {ch}\n🖼 Start rasmi: {photo}\n"
        f"{'━'*22}\n"
        f"🤲 Sahovat karta: {sah_card}\n"
        f"👤 Sahovat egasi: {sah_owner}\n"
        f"💡 Xayriya foizi: {sah_pct}%",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Narxni o'zgartirish",    callback_data="set_price")],
            [InlineKeyboardButton("💳 Karta raqami",           callback_data="set_card")],
            [InlineKeyboardButton("👤 Karta egasi",            callback_data="set_owner")],
            [InlineKeyboardButton("📢 Kanal username",         callback_data="set_channel")],
            [InlineKeyboardButton("📝 Start xabarini tahrirlash", callback_data="set_starttext")],
            [InlineKeyboardButton("🖼 Start rasmi yuklash",    callback_data="set_startphoto")],
            [InlineKeyboardButton("🗑 Start rasmini o'chirish", callback_data="set_startphoto_del")],
            [InlineKeyboardButton("━━━ SAHOVAT ━━━",           callback_data="adm_settings")],
            [InlineKeyboardButton("💳 Sahovat kartasi",        callback_data="set_sah_card")],
            [InlineKeyboardButton("👤 Sahovat karta egasi",    callback_data="set_sah_owner")],
            [InlineKeyboardButton("💡 Xayriya foizi (%)",      callback_data="set_sah_percent")],
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

    # DB dan pending_step ni olish
    if not step:
        try:
            row = db.conn.execute("SELECT pending_step FROM users WHERE user_id=?", (uid,)).fetchone()
            if row and row[0]:
                step = row[0]
                context.user_data["step"] = step
        except: pass

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

    # Sahovat cheki
    if step == "waiting_sahovat_proof":
        user    = update.effective_user
        u       = db.get_user(uid)
        name    = uname(u) if u else user.first_name
        amount  = context.user_data.get("sahovat_amount", "")
        niyat   = context.user_data.get("sahovat_type", "guide")
        niyat_t = "📖 Qo'llanma" if niyat == "guide" else "❤️ Ehson"
        foiz_t  = "50% xayriya / 50% qalam haqi" if niyat == "guide" else "100% xayriya"
        db.add_sahovat_payment(uid, amount, niyat)
        pay_id = db.conn.execute(
            "SELECT id FROM sahovat_payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (uid,)).fetchone()["id"]
        context.user_data.clear()
        await update.message.reply_text(
            "🤲 Sahovat cheki qabul qilindi!\n\n"
            "Admin ko'rib chiqadi va tasdiqlaydi. ❤️")
        amt_txt = f"{amount} so'm" if amount else "ko'rsatilmagan"
        kb = [
            [InlineKeyboardButton("✅ Tasdiqlash",       callback_data=f"sah_ok_{pay_id}_{uid}"),
             InlineKeyboardButton("❌ Rad etish",        callback_data=f"sah_no_{pay_id}_{uid}")],
            [InlineKeyboardButton("✏️ Miqdorni tahrirlash", callback_data=f"sah_edit_{pay_id}_{uid}")],
        ]
        await context.bot.send_photo(
            ADMIN_ID, photo[-1].file_id,
            caption=f"🤲 Yangi sahovat!\n\n"
                    f"👤 {name}\n🆔 {uid}\n📛 @{user.username or 'yoq'}\n"
                    f"💰 Miqdor: {amt_txt}\n"
                    f"🎯 Niyat: {niyat_t}\n"
                    f"💡 Taqsimot: {foiz_t}",
            reply_markup=InlineKeyboardMarkup(kb))
        return

    # Start rasmi (admin)
    if step == "set_startphoto" and is_admin(uid):
        db.update_start_message(photo_id=photo[-1].file_id)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ Start rasmi yangilandi!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Sozlamalarga", callback_data="adm_settings")]]))
        return

# ═══════════════════════════════════════════════════════
#  PDF HANDLERI
# ═══════════════════════════════════════════════════════
async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    step = context.user_data.get("step","")
    doc  = update.message.document
    if not doc: return
    if step == "sahovat_reply":
        # Admin fayl yubordi — matnini kutamiz
        context.user_data["sahovat_reply_file"] = doc.file_id
        tid  = context.user_data.get("reply_to_uid")
        name = context.user_data.get("reply_to_name","")
        await update.message.reply_text(
            f"✅ Fayl qabul qilindi!\n\n"
            f"Endi {name} ga yuboriladigan xabar matnini yozing.\n"
            f"(Faqat fayl yuborish uchun '.' yozing)\n\nBekor: /admin")
        return
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
    if not update.message or not update.message.text: return
    uid  = update.effective_user.id
    step = context.user_data.get("step","")
    txt  = (update.message.text or "").strip()

    # ── ADMIN steplari — kanaldan mustaqil ──────────────────────────────
    if is_admin(uid):
        if step == "sah_donor_edit_amount":
            pay_id = context.user_data.get("edit_pay_id")
            context.user_data.clear()
            db.update_sahovat_amount(pay_id, txt)
            await update.message.reply_text(
                f"✅ #{pay_id} donor miqdori {txt} so'm ga yangilandi!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Hisobotga qaytish", callback_data="adm_sah_report")],
                ]))
            return

        if step == "sah_admin_edit_amount":
            pay_id  = context.user_data.get("edit_pay_id")
            pay_uid = context.user_data.get("edit_pay_uid")
            msg_id  = context.user_data.get("edit_msg_id")
            old_cap = context.user_data.get("edit_msg_caption","")
            context.user_data.clear()
            db.conn.execute("UPDATE sahovat_payments SET amount=? WHERE id=?", (txt, pay_id))
            db.conn.commit()
            new_cap = re.sub(r"💰 Miqdor:.*", f"💰 Miqdor: {txt} so'm ✏️", old_cap) if "Miqdor:" in old_cap else old_cap + f"\n💰 Miqdor: {txt} so'm ✏️"
            kb = [
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"sah_ok_{pay_id}_{pay_uid}"),
                 InlineKeyboardButton("❌ Rad etish",  callback_data=f"sah_no_{pay_id}_{pay_uid}")],
                [InlineKeyboardButton("✏️ Miqdorni tahrirlash", callback_data=f"sah_edit_{pay_id}_{pay_uid}")],
            ]
            try:
                await context.bot.edit_message_caption(chat_id=ADMIN_ID, message_id=msg_id, caption=new_cap, reply_markup=InlineKeyboardMarkup(kb))
            except:
                try:
                    await context.bot.edit_message_text(chat_id=ADMIN_ID, message_id=msg_id, text=new_cap, reply_markup=InlineKeyboardMarkup(kb))
                except: pass
            await update.message.reply_text(f"✅ Miqdor {txt} so'm ga yangilandi!")
            return

        if step == "admin_reply":
            tid  = context.user_data.get("reply_to_uid")
            name = context.user_data.get("reply_to_name","")
            context.user_data.clear()
            if tid:
                try:
                    await context.bot.send_message(tid, f"📬 Admin javobi:\n{'━'*22}\n{txt}")
                    await update.message.reply_text(
                        f"✅ Javob yuborildi → {name}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]))
                except:
                    await update.message.reply_text("❌ Xabar yuborib bo'lmadi.")
            return

        if step == "sahovat_reply":
            tid      = context.user_data.get("reply_to_uid")
            name     = context.user_data.get("reply_to_name","")
            file_id  = context.user_data.get("sahovat_reply_file")
            caption_txt = "" if txt == "." else f"📬 Admin xabari:\n{'━'*22}\n{txt}"
            context.user_data.clear()
            try:
                if file_id:
                    await context.bot.send_document(tid, file_id, caption=caption_txt or None)
                else:
                    await context.bot.send_message(tid, f"📬 Admin xabari:\n{'━'*22}\n{txt}")
                await update.message.reply_text(
                    f"✅ Yuborildi → {name}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]))
            except:
                await update.message.reply_text("❌ Yuborib bo'lmadi.")
            return

        if step == "sah_report_period":
            context.user_data["sah_rep_period"] = txt
            context.user_data["step"] = "sah_report_total"
            await update.message.reply_text(f"✅ Davr: {txt}\n\n💰 Jami yig'ilgan summani yozing:\nMasalan: 850 000")
            return

        if step == "sah_report_total":
            context.user_data["sah_rep_total"] = txt
            context.user_data["step"] = "sah_report_donors"
            await update.message.reply_text(f"✅ Jami: {txt} so'm\n\n👥 Sahovat qilganlar sonini yozing:\nMasalan: 12")
            return

        if step == "sah_report_donors":
            context.user_data["sah_rep_donors"] = txt
            context.user_data["step"] = "sah_report_note"
            await update.message.reply_text(f"✅ Donorlar: {txt} kishi\n\n📝 Izoh yozing (ixtiyoriy):\n'-' bosing o'tkazib yuborish uchun")
            return

        if step == "sah_report_note":
            note   = "" if txt == "-" else txt
            period = context.user_data.get("sah_rep_period","")
            total  = context.user_data.get("sah_rep_total","")
            donors = context.user_data.get("sah_rep_donors","0")
            try:
                val     = int(total.replace(" ","").replace(",",""))
                charity = f"{val//2:,}".replace(",", " ")
                author  = f"{val - val//2:,}".replace(",", " ")
            except:
                charity = total; author = total
            db.add_sahovat_report(period, total, charity, author, int(donors) if donors.isdigit() else 0, note)
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Hisobot saqlandi!\n\n📅 {period}\n💰 Jami: {total} so'm\n🏥 Ehson: {charity} so'm\n✍️ Qalam haqi: {author} so'm\n👥 {donors} kishi",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Hisobotlar", callback_data="adm_sah_report")],
                    [InlineKeyboardButton("🔧 Admin", callback_data="adm_back")],
                ]))
            return

        if step == "broadcast":
            users = db.get_users_by_status(None)
            sent  = 0
            for u in users:
                if u["status"] in ("approved","pro"):
                    try:
                        await context.bot.send_message(
                            u["user_id"], f"📢\n\n{txt}",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("✍️ Asl ismim bilan qayta ro'yxatdan o'tish", callback_data="re_register")]
                            ]))
                        sent += 1
                    except: pass
            context.user_data.clear()
            await update.message.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]))
            return

        if step == "admin_reply_all":
            uid2 = context.user_data.get("reply_all_uid")
            name = context.user_data.get("reply_all_name","")
            context.user_data.clear()
            if uid2:
                try:
                    await context.bot.send_message(uid2, f"📬 Admin javobi:\n{'━'*22}\n{txt}")
                    await update.message.reply_text(f"✅ Yuborildi → {name}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]))
                except:
                    await update.message.reply_text("❌ Yuborib bo'lmadi.")
            return

        if step in ("set_sah_card","set_sah_owner","set_sah_percent"):
            key_map = {"set_sah_card":"sahovat_card","set_sah_owner":"sahovat_owner","set_sah_percent":"sahovat_percent"}
            db.set_setting(key_map[step], txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Sahovat sozlamasi yangilandi: {txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Sozlamalar", callback_data="adm_settings")]]))
            return

        if step in ("set_price","set_card","set_owner","set_channel"):
            key_map = {"set_price":"pro_price","set_card":"card_number","set_owner":"card_owner","set_channel":"channel"}
            db.set_setting(key_map[step], txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Yangilandi: {txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Sozlamalar", callback_data="adm_settings")]]))
            return

        if step == "set_starttext":
            sm = db.get_start_message()
            if sm:
                db.update_start_message(text=txt)
            else:
                db.conn.execute("INSERT INTO start_message (text,photo_id) VALUES (?,'')", (txt,))
                db.conn.commit()
            context.user_data.clear()
            await update.message.reply_text("✅ Start xabari yangilandi!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Sozlamalar", callback_data="adm_settings")]]))
            return

        # Admin PDF test yaratish steplari
        if step == "pdf_title":
            context.user_data["pdf_title"] = txt
            context.user_data["step"] = "pdf_count"
            await update.message.reply_text(f"✅ Nom: {txt}\n\nNechta savol? (Masalan: 30)")
            return

        if step == "pdf_count":
            try:
                n = int(txt)
                context.user_data["pdf_count"] = n
                context.user_data["step"] = "pdf_time"
                await update.message.reply_text(f"✅ Savollar soni: {n}\n\nVaqt chegarasi (daqiqada)? Masalan: 30")
            except:
                await update.message.reply_text("Raqam kiriting. Masalan: 30")
            return

        if step == "pdf_time":
            try:
                t = int(txt)
                context.user_data["pdf_time"] = t
                context.user_data["step"] = "pdf_type_select"
                kb = [[
                    InlineKeyboardButton("🆓 Bepul", callback_data="adm_pdf_free"),
                    InlineKeyboardButton("👑 PRO",   callback_data="adm_pdf_pro"),
                ]]
                await update.message.reply_text(
                    f"✅ Vaqt: {t} daqiqa\n\nTest turi:",
                    reply_markup=InlineKeyboardMarkup(kb))
            except:
                await update.message.reply_text("Raqam kiriting. Masalan: 30")
            return

        if step == "pdf_key":
            n     = context.user_data.get("pdf_count", 30)
            clean = re.sub(r"[^ABCD]", "", txt.upper())
            if len(clean) != n:
                await update.message.reply_text(f"⚠️ {len(clean)} ta harf kiritdingiz, {n} ta kerak.\nQaytadan yuboring:")
                return
            title   = context.user_data.get("pdf_title","")
            file_id = context.user_data.get("pdf_file_id","")
            is_free = context.user_data.get("pdf_is_free", 0)
            t_limit = context.user_data.get("pdf_time", 30)
            db.add_pdf_test(title, file_id, n, clean, is_free, t_limit)
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Test qo'shildi!\n📝 {title}\n❓ {n} savol\n⏱ {t_limit} daqiqa",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Testlarga", callback_data="adm_tests")],
                    [InlineKeyboardButton("🔧 Admin",     callback_data="adm_back")],
                ]))
            # Barcha foydalanuvchilarga bildirishnoma
            all_users = db.get_all_users()
            sent = 0
            for u in all_users:
                if u["status"] in ("approved","pro","new") and u.get("full_name"):
                    try:
                        await context.bot.send_message(
                            u["user_id"],
                            f"🔔 Yangi test qo'shildi!\n\n📝 {title}\n❓ {n} ta savol\n⏱ Vaqt: {t_limit} daqiqa\n\nHoziroq ishlang! 👇",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("📝 Testga o'tish", callback_data="free_tests")]
                            ]))
                        sent += 1
                    except: pass
            if sent:
                await update.message.reply_text(f"📢 {sent} ta foydalanuvchiga xabar yuborildi.")
            return

        if step == "rename_test":
            tid = context.user_data["edit_id"]
            db.update_pdf_test(tid, title=txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Test nomi yangilandi: {txt}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Testni ko'rish", callback_data=f"atv_{tid}")],
                    [InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")],
                ]))
            return

        if step == "update_key":
            n     = context.user_data.get("edit_cnt", 30)
            clean = re.sub(r"[^ABCD]", "", txt.upper())
            if len(clean) != n:
                await update.message.reply_text(f"⚠️ {len(clean)} ta harf, {n} ta kerak. Qaytadan:"); return
            tid = context.user_data["edit_id"]
            db.update_pdf_test(tid, answer_key=clean)
            context.user_data.clear()
            await update.message.reply_text("✅ Javob kaliti yangilandi!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Testni ko'rish", callback_data=f"atv_{tid}")],
                    [InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")],
                ]))
            return

        if step == "update_time":
            try:
                t   = int(txt)
                tid = context.user_data["edit_id"]
                db.update_pdf_test(tid, time_limit=t)
                context.user_data.clear()
                await update.message.reply_text(f"✅ Vaqt {t} daqiqaga yangilandi!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📝 Testni ko'rish", callback_data=f"atv_{tid}")],
                        [InlineKeyboardButton("🔧 Admin panel",    callback_data="adm_back")],
                    ]))
            except:
                await update.message.reply_text("Raqam kiriting. Masalan: 45")
            return

        if step == "add_guide_title":
            context.user_data["guide_title"] = txt
            context.user_data["step"]        = "waiting_guide_file"
            await update.message.reply_text(
                f"✅ Sarlavha: {txt}\n\n"
                "📄 Endi PDF faylni yuboring\n"
                "(qo'llanma fayli):")
            return

    # ── FOYDALANUVCHI steplari ──────────────────────────────────────────
    # Ro'yxatdan o'tish
    if step == "waiting_fullname":
        if len(txt.split()) < 2:
            await update.message.reply_text("To'liq ism va familiyangizni kiriting.\nMasalan: Mallayev Ozodbek"); return
        db.add_user(uid, update.effective_user.username or "", update.effective_user.first_name, txt)
        is_re = context.user_data.get("re_register", False)
        context.user_data.clear()
        try:
            tg_name = update.effective_user.first_name or ""
            tg_user = update.effective_user.username or "yoq"
            prefix  = "♻️ Qayta ro'yxat!" if is_re else "🆕 Yangi a'zo!"
            await context.bot.send_message(
                ADMIN_ID,
                prefix + "\n" + "━"*20 + "\n"
                f"👤 Kiritilgan ism: {txt}\n"
                f"📱 Telegram ismi: {tg_name}\n"
                f"🆔 ID: {uid}\n"
                f"📛 @{tg_user}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"💬 {txt} ga xabar yuborish", callback_data=f"reply_{uid}")],
                    [InlineKeyboardButton("♻️ Qayta ro'yxatdan o'tkazish", callback_data=f"adm_reregister_{uid}")],
                ]))
        except: pass
        if is_re:
            await update.message.reply_text(
                f"✅ Rahmat, {txt}!\n\nIsmingiz yangilandi. 🎉",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]]))
        else:
            await show_welcome(update, context)
        return

    # Test javoblari
    if step == "waiting_answers":
        await handle_test_answers(update, context); return

    # Sahovat — o'z miqdorini kiritish
    if step == "waiting_sahovat_custom_amount":
        context.user_data["sahovat_amount"] = txt
        context.user_data["step"] = "waiting_sahovat_proof"
        card  = S("sahovat_card", S("card_number","9860 3501 4876 2387"))
        owner = S("sahovat_owner", S("card_owner","Mallayev Ozodbek"))
        niyat = context.user_data.get("sahovat_type","guide")
        foiz  = "50% xayriya / 50% qalam haqi" if niyat == "guide" else "100% xayriya"
        await update.message.reply_text(
            f"✅ Miqdor: {txt} so'm\n💡 Taqsimot: {foiz}\n\n"
            f"💳 Kartaga o'tkazing:\n`{card}`\n👤 Egasi: {owner}\n\n"
            f"O'tkazib bo'lgach chekni shu yerga yuboring 📸",
            parse_mode="Markdown")
        return

    # To'lov cheki (fayl) — PRO
    if step == "waiting_proof":
        doc = update.message.document
        if doc:
            u    = db.get_user(uid)
            name = uname(u) if u else update.effective_user.first_name
            context.user_data.clear()
            await update.message.reply_text("✅ Chek qabul qilindi!\n\nAdmin 24 soat ichida ko'rib chiqadi. 🙏")
            kb = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok_{uid}"),
                   InlineKeyboardButton("❌ Rad etish",  callback_data=f"pay_no_{uid}")]]
            await context.bot.send_document(
                ADMIN_ID, doc.file_id,
                caption=f"💎 Yangi to'lov (fayl)!\n\n👤 {name}\n🆔 {uid}\n📛 @{update.effective_user.username or 'yoq'}",
                reply_markup=InlineKeyboardMarkup(kb))
            db.add_payment_request(uid)
        else:
            await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return

    # Sahovat cheki (fayl)
    if step == "waiting_sahovat_proof":
        doc = update.message.document
        if doc:
            u      = db.get_user(uid)
            name   = uname(u) if u else update.effective_user.first_name
            amount = context.user_data.get("sahovat_amount", "")
            niyat  = context.user_data.get("sahovat_type", "guide")
            niyat_t = "📖 Qo'llanma" if niyat == "guide" else "❤️ Ehson"
            foiz_t  = "50% xayriya / 50% qalam haqi" if niyat == "guide" else "100% xayriya"
            db.add_sahovat_payment(uid, amount, niyat)
            pay_id = db.conn.execute(
                "SELECT id FROM sahovat_payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (uid,)).fetchone()["id"]
            context.user_data.clear()
            await update.message.reply_text("🤲 Sahovat cheki qabul qilindi!\n\nAdmin ko'rib chiqadi. ❤️")
            amt_txt = f"{amount} so'm" if amount else "ko'rsatilmagan"
            kb = [
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"sah_ok_{pay_id}_{uid}"),
                 InlineKeyboardButton("❌ Rad etish",  callback_data=f"sah_no_{pay_id}_{uid}")],
                [InlineKeyboardButton("✏️ Miqdorni tahrirlash", callback_data=f"sah_edit_{pay_id}_{uid}")],
            ]
            await context.bot.send_document(
                ADMIN_ID, doc.file_id,
                caption=f"🤲 Yangi sahovat (fayl)!\n\n👤 {name}\n🆔 {uid}\n📛 @{update.effective_user.username or 'yoq'}\n💰 Miqdor: {amt_txt}\n🎯 Niyat: {niyat_t}\n💡 {foiz_t}",
                reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text("Iltimos rasm yoki fayl yuboring.")
        return

    # Murojaat
    if step == "waiting_contact":
        back_cb = context.user_data.get("contact_back","free_menu")
        u    = db.get_user(uid)
        name = uname(u) if u else str(uid)
        context.user_data.clear()
        await context.bot.send_message(
            ADMIN_ID,
            f"📩 Yangi murojaat!\n{'━'*22}\n👤 {name}\n🆔 {uid}\n📛 @{update.effective_user.username or 'yoq'}\n{'━'*22}\n💬 {txt}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"↩️ {name} ga javob", callback_data=f"reply_{uid}")]]))
        await update.message.reply_text(
            "✅ Murojaatingiz adminga yuborildi! 🙏\n\nAdmin 24 soat ichida ko'rib chiqadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Yana murojaat", callback_data="contact_admin")],
                [InlineKeyboardButton("🏠 Menyuga qaytish", callback_data=back_cb)],
            ]))
        return

# ═══════════════════════════════════════════════════════
#  CALLBACK HANDLER (qolganlar)
# ═══════════════════════════════════════════════════════
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query; await q.answer()
    data = q.data

    # Admin menyu
    if data == "adm_back":           await show_admin_menu(update, context)
    elif data == "re_register":
        uid2 = q.from_user.id
        context.user_data["step"] = "waiting_fullname"
        context.user_data["re_register"] = True
        await q.edit_message_text(
            "✍️ Iltimos, asl ismingiz va familiyangizni to'liq kiriting:\n\n"
            "📝 Masalan: Mallayev Ozodbek\n\n"
            "Bu ma'lumot faqat bot ichida ishlatiladi.")
    elif data == "sahovat_amount":        await sahovat_amount(update, context)
    elif data.startswith("sah_niyat_"):   await sahovat_niyat_selected(update, context)
    elif data == "sah_amt_custom":        await sahovat_amount_custom(update, context)
    elif data.startswith("sah_amt_"):     await sahovat_amount_selected(update, context)
    elif data.startswith("adm_reregister_"):
        pass  # alohida handler tomonidan ushlanadi
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
    elif data == "adm_sahovat":      await adm_sahovat_payments(update, context)
    elif data == "adm_sah_report":         await adm_sah_report(update, context)
    elif data == "adm_sah_clear":          await adm_sah_clear(update, context)
    elif data == "adm_sah_clear_ok":       await adm_sah_clear_ok(update, context)
    elif data.startswith("sah_edit_donor_"):await sahovat_edit_donor_amount(update, context)
    elif data.startswith("sah_donor_"):      await adm_sah_donor_detail(update, context)
    elif data.startswith("sah_edit_"):      await sahovat_edit_amount(update, context)
    elif data.startswith("del_sah_report_"):
        if not is_admin(q.from_user.id): return
        rid = int(data.split("_")[-1])
        db.delete_sahovat_report(rid)
        await adm_sah_report(update, context)
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
    elif data in ("guide_type_free", "guide_type_pro"):
        is_free   = 1 if data == "guide_type_free" else 0
        g_title   = context.user_data.get("guide_title","")
        g_content = context.user_data.get("guide_content","")
        g_file_id = context.user_data.get("guide_file_id","")
        db.add_guide(g_title, g_content, is_free, g_file_id)
        context.user_data.clear()
        kb = [[InlineKeyboardButton("📚 Qo'llanmalarga", callback_data="adm_guides"),
               InlineKeyboardButton("🔧 Admin", callback_data="adm_back")]]
        label = "Bepul" if is_free else "PRO"
        await q.edit_message_text(
            f"✅ Muvaffaqiyatli! Qo'llanma qo'shildi ({label})",
            reply_markup=InlineKeyboardMarkup(kb))
        # Barcha foydalanuvchilarga bildirishnoma
        all_users = db.get_all_users()
        sent = 0
        for u in all_users:
            if u.get("full_name"):
                try:
                    await context.bot.send_message(
                        u["user_id"],
                        f"📚 Yangi qo'llanma qo'shildi!\n\n"
                        f"📖 {g_title}\n"
                        f"{'🆓 Bepul' if is_free else '👑 PRO obuna'}\n\n"
                        f"Hoziroq o'qing! 👇",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(
                                "📚 Qo'llanmalarga o'tish",
                                callback_data="free_guides" if is_free else "pro_guides")]
                        ]))
                    sent += 1
                except: pass
        await context.bot.send_message(ADMIN_ID, f"📢 {sent} ta foydalanuvchiga xabar yuborildi.")

    # PDF test type
    elif data in ("pdf_type_free", "adm_pdf_free"):
        context.user_data["pdf_is_free"] = 1
        context.user_data["step"] = "waiting_pdf_file"
        await q.edit_message_text(
            "✅ 🆓 Bepul tanlandi!\n\n"
            "📄 Endi PDF faylni yuboring:")
    elif data in ("pdf_type_pro", "adm_pdf_pro"):
        context.user_data["pdf_is_free"] = 0
        context.user_data["step"] = "waiting_pdf_file"
        await q.edit_message_text(
            "✅ 👑 PRO tanlandi!\n\n"
            "📄 Endi PDF faylni yuboring:")

    # Sozlamalar
    elif data == "set_startphoto_del":
        db.update_start_message(photo_id="")
        await q.answer("✅ Rasm o'chirildi!", show_alert=True)
        await adm_settings(update, context)
    elif data in ("set_price","set_card","set_owner","set_channel","set_starttext","set_startphoto",
                  "set_sah_card","set_sah_owner","set_sah_percent"):
        hints = {
            "set_price":      "💰 Yangi narxni yozing (masalan: 349 000):",
            "set_card":       "💳 Yangi karta raqamini yozing:",
            "set_owner":      "👤 Yangi karta egasi ismini yozing:",
            "set_channel":    "📢 Yangi kanal username yozing (masalan: @legistman):",
            "set_starttext":  "📝 Yangi start xabari matnini yozing:",
            "set_startphoto": "🖼 Start uchun rasm yuboring:",
            "set_sah_card":   "💳 Sahovat kartasi raqamini yozing:",
            "set_sah_owner":  "👤 Sahovat karta egasi ismini yozing:",
            "set_sah_percent":"💡 Mehribonlik uyiga beriladigan foizni yozing (masalan: 10):",
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
async def send_weekly_report(context: ContextTypes.DEFAULT_TYPE):
    """Har juma 20:00 da kanalga haftalik hisobot yuboriladi"""
    from datetime import datetime, timedelta
    now    = datetime.now()
    stats  = db.get_weekly_sahovat_stats()
    if stats["donors_cnt"] == 0:
        return  # Bu hafta hech kim sahovat qilmagan — yuborma
    ch     = S("channel","@legistman")
    period = f"{(now - timedelta(days=6)).strftime('%d.%m')}–{now.strftime('%d.%m.%Y')}"

    def fmt(v): return f"{v:,}".replace(",", " ")

    text = (
        f"📊 Haftalik sahovat hisoboti\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {period}\n\n"
        f"👥 Jami donorlar: {stats['donors_cnt']} kishi\n"
        f"💰 Jami yig'ildi: {fmt(stats['grand_total'])} so'm\n\n"
    )
    if stats["guide_cnt"]:
        text += (
            f"📖 Qo'llanma uchun: {stats['guide_cnt']} kishi\n"
            f"   Yig'ildi: {fmt(stats['guide_total'])} so'm\n\n"
        )
    if stats["ehson_cnt"]:
        text += (
            f"❤️ Faqat ehson: {stats['ehson_cnt']} kishi\n"
            f"   Yig'ildi: {fmt(stats['ehson_total'])} so'm\n\n"
        )
    text += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏥 Og'ir betob bolalar +\n"
        f"   Mehribonlik uyiga: {fmt(stats['total_charity'])} so'm\n"
        f"✍️ Qalam haqi: {fmt(stats['total_author'])} so'm\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Sahovat qilganlarga Alloh baraka bersin! 🤲\n"
        f"Siz ham qo'shilishingiz mumkin 👉 @legistman_bot"
    )
    try:
        await context.bot.send_message(ch, text)
    except Exception as e:
        await context.bot.send_message(ADMIN_ID,
            f"⚠️ Haftalik hisobot kanalga yuborilmadi:\n{e}")

async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Web App dan kelgan ma'lumotlarni qayta ishlash"""
    import json as _json
    uid  = update.effective_user.id
    raw  = update.message.web_app_data.data
    try:
        data   = _json.loads(raw)
        action = data.get("action","")
    except:
        return

    # Ro'yxatdan o'tish
    if action == "register":
        full_name = data.get("full_name","").strip()
        if len(full_name.split()) >= 2:
            db.add_user(uid, update.effective_user.username or "",
                        update.effective_user.first_name, full_name)
            # Adminga bildirishnoma
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🆕 Yangi a'zo!\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 {full_name}\n🆔 {uid}\n"
                    f"📛 @{update.effective_user.username or 'yoq'}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(f"💬 {full_name} ga xabar",
                                             callback_data=f"reply_{uid}")
                    ]]))
            except: pass
            await show_welcome(update, context)

    # Testlar
    elif action == "open_tests":
        prem = is_pro(uid)
        if prem:
            context.user_data["from_webapp"] = True
            # Fake callback query orqali pro_tests_list ga yo'naltirish
            await update.message.reply_text(
                "📝 Testlar:",
                reply_markup=InlineKeyboardMarkup([
                    *[[InlineKeyboardButton(
                        f"{'🆓' if t.get('is_free') else '👑'} {t['title']}",
                        callback_data=f"pdf_test_{t['id']}"
                    )] for t in db.get_all_pdf_tests()],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]
                ]))
        else:
            await update.message.reply_text(
                "📝 Bepul testlar:",
                reply_markup=InlineKeyboardMarkup([
                    *[[InlineKeyboardButton(
                        f"{'🆓' if t.get('is_free') else '🔒'} {t['title']}",
                        callback_data=f"pdf_test_{t['id']}" if t.get('is_free') else f"pro_locked_{t['id']}"
                    )] for t in db.get_all_pdf_tests()],
                    [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]
                ]))

    # Qo'llanmalar
    elif action == "open_guides":
        prem = is_pro(uid)
        guides = db.get_all_guides() if prem else db.get_free_guides()
        await update.message.reply_text(
            "📚 Qo'llanmalar:",
            reply_markup=InlineKeyboardMarkup([
                *[[InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")] for g in guides],
                [InlineKeyboardButton("🏠 Bosh menyu", callback_data="back_welcome")]
            ]))

    # Statistika
    elif action == "open_stats":
        await update.message.reply_text(
            "📊 Statistika:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Shaxsiy natijalar", callback_data="my_results")],
                [InlineKeyboardButton("🏆 Ommaviy reyting",   callback_data="public_rating")],
                [InlineKeyboardButton("🏠 Bosh menyu",        callback_data="back_welcome")],
            ]))

    # Bot haqida
    elif action == "open_about":
        context.user_data.clear()
        from telegram import Update as _U
        class FakeQuery:
            from_user = update.effective_user
            message   = update.message
            data      = "about_bot"
            async def answer(self): pass
            async def edit_message_text(self, *a, **kw):
                await update.message.reply_text(*a, **kw)
        update.callback_query = FakeQuery()
        await about_bot(update, context)
        update.callback_query = None

    # Adminga murojaat
    elif action == "open_contact":
        prem    = is_pro(uid)
        back_cb = "pro_menu" if prem else "free_menu"
        context.user_data["step"]         = "waiting_contact"
        context.user_data["contact_back"] = back_cb
        await update.message.reply_text(
            "📩 Adminga murojaat\n\n"
            "✍️ Murojaatingizni yozing:")

    # Sahovat
    elif action == "open_sahovat":
        await update.message.reply_text(
            "🤲 Sahovat",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🤲 Sahovat qilish", callback_data="sahovat_info")
            ]]))

    # Admin statistikasi
    elif action == "get_admin_stats":
        if uid != ADMIN_ID: return
        stats = {
            "total_users":  len(db.get_all_users()),
            "pro_users":    sum(1 for u in db.get_all_users() if u.get("status")=="pro"),
            "today_users":  db.get_today_users_count() if hasattr(db,'get_today_users_count') else 0,
            "total_tests":  len(db.get_all_pdf_tests()),
            "total_results": db.get_total_results_count() if hasattr(db,'get_total_results_count') else 0,
        }
        await update.message.reply_text(
            f"📊 Admin statistikasi:\n"
            f"👥 Jami foydalanuvchilar: {stats['total_users']}\n"
            f"👑 PRO obunalilar: {stats['pro_users']}\n"
            f"📝 Jami testlar: {stats['total_tests']}")

    # PRO to'lov cheki
    elif action == "send_proof_pro":
        context.user_data["step"] = "waiting_proof"
        # DB ga ham saqlaymiz - Web App yopilganda ham ishlaydi
        try:
            db.conn.execute("UPDATE users SET pending_step=? WHERE user_id=?", ("waiting_proof", uid))
            db.conn.commit()
        except: pass
        card = S("card_number","9860 3501 4876 2387")
        owner = S("card_owner","Mallayev Ozodbek")
        await update.message.reply_text(
            f"💳 PRO obuna to'lovi\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Karta: `{card}`\n"
            f"Egasi: {owner}\n\n"
            f"💰 Miqdor: {S('pro_price','349 000')} so'm\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📸 To'lov chekini (screenshot) shu yerga yuboring:",
            parse_mode="Markdown")

    # Sahovat cheki
    elif action == "send_proof_sahovat":
        context.user_data["step"] = "waiting_sahovat_proof"
        try:
            db.conn.execute("UPDATE users SET pending_step=? WHERE user_id=?", ("waiting_sahovat_proof", uid))
            db.conn.commit()
        except: pass
        card = S("card_number","9860 3501 4876 2387")
        owner = S("card_owner","Mallayev Ozodbek")
        await update.message.reply_text(
            f"🤲 Sahovat to'lovi\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Karta: `{card}`\n"
            f"Egasi: {owner}\n\n"
            f"💰 Istalgan miqdor\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📸 To'lov chekini (screenshot) shu yerga yuboring:",
            parse_mode="Markdown")

    # Yangi test saqlash (Web App admin panelidan)
    elif action == "add_test_full":
        if uid != ADMIN_ID: return
        name      = data.get("name","").strip()
        time_l    = int(data.get("time", 30))
        is_free   = int(data.get("is_free", 0))
        key       = data.get("key","").upper()
        questions = data.get("questions", [])
        if not name or not key:
            await update.message.reply_text("⚠️ Test nomi yoki kalit yo'q!")
            return
        # Savol matnlarini birlashtirish
        q_text = ""
        q_text = ""
        for i, q in enumerate(questions):
            q_text += str(i+1)+". "+q.get("text","")+chr(10)
        # DB ga saqlash - file_id bo'sh (savollar matnda)
        db.add_pdf_test(name, "", len(questions) or len(key), key, is_free, time_l)
        # Barcha foydalanuvchilarga xabar
        all_users = db.get_all_users()
        sent = 0
        for u in all_users:
            if u.get("full_name"):
                try:
                    await context.bot.send_message(
                        u["user_id"],
                        f"📝 Yangi test qo'shildi!\n\n"
                        f"📌 {name}\n"
                        f"{'🆓 Bepul' if is_free else '👑 PRO obuna'}\n\n"
                        f"Hoziroq ishlang! 👇",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("📝 Testlar", callback_data="free_menu" if is_free else "pro_menu")
                        ]]))
                    sent += 1
                except: pass
        await update.message.reply_text(
            f"✅ Test saqlandi!\n"
            f"📌 {name}\n"
            f"❓ {len(questions)} ta savol\n"
            f"🔑 Kalit: {key}\n"
            f"📢 {sent} ta foydalanuvchiga xabar yuborildi.")

    # Yangi qo'llanma saqlash (Web App admin panelidan)
    elif action == "add_guide":
        if uid != ADMIN_ID: return
        name    = data.get("name","").strip()
        is_free = int(data.get("is_free", 1))
        if not name:
            await update.message.reply_text("⚠️ Qo'llanma nomi yo'q!")
            return
        context.user_data["step"]           = "waiting_guide_file"
        context.user_data["guide_title"]    = name
        context.user_data["guide_is_free"]  = is_free
        await update.message.reply_text(
            f"✅ Nom: {name}\n"
            f"Tur: {'Bepul' if is_free else 'PRO'}\n\n"
            f"📄 Endi PDF faylni yuboring:")

    # PRO olish
    elif action == "buy_pro":
        await update.message.reply_text(
            "👑 PRO obuna",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 To'lov qilish", callback_data="buy_pro")
            ]]))

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
    app.add_handler(CallbackQueryHandler(buy_pro,          pattern=r"^buy_pro$"))
    app.add_handler(CallbackQueryHandler(pro_send_proof,   pattern=r"^pro_send_proof$"))
    app.add_handler(CallbackQueryHandler(payment_action,  pattern=r"^pay_(ok|no)_\d+$"))
    app.add_handler(CallbackQueryHandler(sahovat_info,           pattern=r"^sahovat_info$"))
    app.add_handler(CallbackQueryHandler(sahovat_amount,         pattern=r"^sahovat_amount$"))
    app.add_handler(CallbackQueryHandler(sahovat_niyat_selected, pattern=r"^sah_niyat_(guide|ehson)$"))
    app.add_handler(CallbackQueryHandler(sahovat_amount_custom,  pattern=r"^sah_amt_custom$"))
    app.add_handler(CallbackQueryHandler(sahovat_amount_selected,pattern=r"^sah_amt_\d+$"))
    app.add_handler(CallbackQueryHandler(sahovat_report,         pattern=r"^sahovat_report$"))
    app.add_handler(CallbackQueryHandler(sahovat_proof,          pattern=r"^sahovat_proof$"))
    app.add_handler(CallbackQueryHandler(sahovat_payment_action, pattern=r"^sah_(ok|no)_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(sah_clear_reports,      pattern=r"^sah_clear_reports$"))
    app.add_handler(CallbackQueryHandler(adm_sah_clear,          pattern=r"^adm_sah_clear$"))
    app.add_handler(CallbackQueryHandler(adm_sah_clear_ok,       pattern=r"^adm_sah_clear_ok$"))
    app.add_handler(CallbackQueryHandler(sah_clear_confirm,      pattern=r"^sah_clear_confirm$"))
    app.add_handler(CallbackQueryHandler(sahovat_edit_amount,    pattern=r"^sah_edit_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(sahovat_reply_prompt,   pattern=r"^sah_reply_\d+$"))
    app.add_handler(CallbackQueryHandler(contact_admin,          pattern=r"^contact_admin$"))
    app.add_handler(CallbackQueryHandler(admin_reply_prompt,     pattern=r"^reply_\d+$"))
    app.add_handler(CallbackQueryHandler(adm_reregister,         pattern=r"^adm_reregister_\d+$"))

    # Testlar
    app.add_handler(CallbackQueryHandler(pro_locked_test,    pattern=r"^pro_locked_\d+$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test,      pattern=r"^pdf_test_\d+$"))
    app.add_handler(CallbackQueryHandler(submit_prompt,      pattern=r"^submit_\d+$"))
    app.add_handler(CallbackQueryHandler(show_guide,         pattern=r"^guide_\d+$"))

    # Statistika
    app.add_handler(CallbackQueryHandler(user_stats,         pattern=r"^user_stats$"))
    app.add_handler(CallbackQueryHandler(my_results,         pattern=r"^my_results$"))
    app.add_handler(CallbackQueryHandler(stat_locked,         pattern=r"^stat_locked_\d+$"))
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
    app.add_handler(CallbackQueryHandler(adm_user_action, pattern=r"^aua_(ok|prem|unprem|kick|reset|wipe)_\d+$"))

    # Qolgan callbacklar
    app.add_handler(CallbackQueryHandler(cb_handler))

    # Fayllar va rasmlar
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))
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
        # Har juma soat 20:00 da haftalik sahovat hisoboti
        app.job_queue.run_daily(
            send_weekly_report,
            time=dtime(hour=20, minute=0),
            days=(4,),   # 4 = juma (0=dushanba)
            name="weekly_sahovat_report")

    print("✅ Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
