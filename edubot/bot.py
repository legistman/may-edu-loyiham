import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from database import Database

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# .env dan token va admin ID
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "YOUR_TELEGRAM_ID_HERE"))

db = Database()

# ConversationHandler holatlari
TAKING_TEST, WAITING_ANSWER = range(2)


# ─────────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────

def is_approved(user_id: int) -> bool:
    return db.is_user_approved(user_id)

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ─────────────────────────────────────────────
#  /start — Boshlash
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name

    db.add_user(user_id, username, user.first_name)

    if is_admin(user_id):
        await update.message.reply_text(
            f"👋 Xush kelibsiz, Admin!\n\n"
            f"🔧 Admin paneli: /admin\n"
            f"📊 Statistika: /stats"
        )
        return

    status = db.get_user_status(user_id)

    if status == "approved":
        await show_main_menu(update, context)
    elif status == "pending":
        await update.message.reply_text(
            "⏳ Sizning so'rovingiz ko'rib chiqilmoqda.\n"
            "Admin tasdiqlashini kuting."
        )
    else:
        # Yangi foydalanuvchi — so'rov yuborish
        keyboard = [[InlineKeyboardButton("📨 Kirish so'rovi yuborish", callback_data="request_access")]]
        await update.message.reply_text(
            f"👋 Salom, {user.first_name}!\n\n"
            f"Bu bot o'quv materiallar va testlar uchun.\n"
            f"Foydalanish uchun admin ruxsati kerak.\n\n"
            f"👇 Quyidagi tugmani bosing:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Testlar", callback_data="menu_tests")],
        [InlineKeyboardButton("📚 Qo'llanmalar", callback_data="menu_guides")],
        [InlineKeyboardButton("🎬 Video darslar", callback_data="menu_videos")],
        [InlineKeyboardButton("📊 Mening natijalarim", callback_data="menu_results")],
    ]
    text = (
        "📌 Asosiy menyu\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
#  KIRISH SO'ROVI
# ─────────────────────────────────────────────

async def request_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    status = db.get_user_status(user.id)
    if status == "pending":
        await query.edit_message_text("⏳ So'rovingiz allaqachon yuborilgan. Kuting.")
        return
    if status == "approved":
        await show_main_menu(update, context)
        return

    db.set_user_status(user.id, "pending")

    # Adminga xabar
    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user.id}"),
        ]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🔔 Yangi kirish so'rovi!\n\n"
            f"👤 Ism: {user.first_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📛 Username: @{user.username or 'yoq'}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await query.edit_message_text(
        "✅ So'rovingiz adminga yuborildi!\n"
        "Tasdiqlangandan so'ng xabar olasiz."
    )


# ─────────────────────────────────────────────
#  ADMIN: TASDIQLASH / RAD ETISH
# ─────────────────────────────────────────────

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    data = query.data
    action, user_id_str = data.split("_", 1)
    target_user_id = int(user_id_str)

    if action == "approve":
        db.set_user_status(target_user_id, "approved")
        await query.edit_message_text(f"✅ Foydalanuvchi {target_user_id} tasdiqlandi.")
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🎉 Tabriklaymiz! Botdan foydalanishga ruxsat berildi.\n/start bosing."
        )
    elif action == "reject":
        db.set_user_status(target_user_id, "rejected")
        await query.edit_message_text(f"❌ Foydalanuvchi {target_user_id} rad etildi.")
        await context.bot.send_message(
            chat_id=target_user_id,
            text="😔 Afsuski, so'rovingiz rad etildi."
        )


# ─────────────────────────────────────────────
#  ADMIN PANEL
# ─────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return

    keyboard = [
        [InlineKeyboardButton("📝 Test qo'shish", callback_data="admin_add_test")],
        [InlineKeyboardButton("📚 Qo'llanma qo'shish", callback_data="admin_add_guide")],
        [InlineKeyboardButton("🎬 Video qo'shish", callback_data="admin_add_video")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
    ]
    await update.message.reply_text(
        "🔧 Admin Panel\n\nNimani qilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
#  TESTLAR BO'LIMI
# ─────────────────────────────────────────────

async def menu_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_approved(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    tests = db.get_all_tests()
    if not tests:
        await query.edit_message_text(
            "📝 Hozircha testlar yo'q.\n\n"
            "⬅️ /start — Asosiy menyu"
        )
        return

    keyboard = []
    for test in tests:
        keyboard.append([InlineKeyboardButton(
            f"📝 {test['title']}",
            callback_data=f"start_test_{test['id']}"
        )])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])

    await query.edit_message_text(
        "📝 Testlar ro'yxati\n\nQaysi testni boshlaysiz?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_approved(user_id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    test_id = int(query.data.split("_")[2])
    questions = db.get_test_questions(test_id)

    if not questions:
        await query.edit_message_text("❌ Bu testda savollar yo'q.")
        return

    # Test holatini saqlaymiz
    context.user_data["test_id"] = test_id
    context.user_data["questions"] = questions
    context.user_data["current_q"] = 0
    context.user_data["answers"] = []

    await send_question(update, context, query.message)


async def send_question(update, context, message):
    questions = context.user_data["questions"]
    current = context.user_data["current_q"]
    total = len(questions)

    if current >= total:
        await finish_test(update, context, message)
        return

    q = questions[current]
    keyboard = [
        [InlineKeyboardButton(f"A) {q['option_a']}", callback_data="ans_A")],
        [InlineKeyboardButton(f"B) {q['option_b']}", callback_data="ans_B")],
        [InlineKeyboardButton(f"C) {q['option_c']}", callback_data="ans_C")],
        [InlineKeyboardButton(f"D) {q['option_d']}", callback_data="ans_D")],
    ]

    text = (
        f"📝 Savol {current + 1}/{total}\n\n"
        f"❓ {q['question']}"
    )

    try:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if "questions" not in context.user_data:
        await query.edit_message_text("❌ Test topilmadi. /start bosing.")
        return

    answer = query.data.split("_")[1]  # A, B, C, D
    context.user_data["answers"].append(answer)
    context.user_data["current_q"] += 1

    await send_question(update, context, query.message)


async def finish_test(update, context, message):
    questions = context.user_data["questions"]
    answers = context.user_data["answers"]
    test_id = context.user_data["test_id"]
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id

    correct = 0
    result_text = "📊 Test natijalari:\n\n"

    for i, (q, ans) in enumerate(zip(questions, answers)):
        is_correct = ans.upper() == q["correct_answer"].upper()
        if is_correct:
            correct += 1
            icon = "✅"
        else:
            icon = "❌"
        result_text += f"{icon} {i+1}. To'g'ri javob: {q['correct_answer']}, Sizning javobingiz: {ans}\n"

    total = len(questions)
    percent = round((correct / total) * 100) if total > 0 else 0

    result_text += (
        f"\n─────────────────\n"
        f"✅ To'g'ri: {correct}/{total}\n"
        f"📈 Natija: {percent}%\n"
    )

    if percent >= 85:
        result_text += "🏆 Ajoyib natija!"
    elif percent >= 60:
        result_text += "👍 Yaxshi natija!"
    else:
        result_text += "📚 Ko'proq o'qish kerak."

    # Natijani bazaga saqlash
    db.save_result(user_id, test_id, correct, total)

    keyboard = [
        [InlineKeyboardButton("📝 Yana test", callback_data="menu_tests")],
        [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_main")],
    ]

    context.user_data.clear()

    try:
        await message.edit_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        await message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
#  QO'LLANMALAR
# ─────────────────────────────────────────────

async def menu_guides(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_approved(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    guides = db.get_all_guides()
    if not guides:
        keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("📚 Hozircha qo'llanmalar yo'q.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for g in guides:
        keyboard.append([InlineKeyboardButton(f"📖 {g['title']}", callback_data=f"guide_{g['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])

    await query.edit_message_text("📚 Qo'llanmalar:", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    guide_id = int(query.data.split("_")[1])
    guide = db.get_guide(guide_id)

    if not guide:
        await query.edit_message_text("❌ Qo'llanma topilmadi.")
        return

    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_guides")]]
    text = f"📖 {guide['title']}\n\n{guide['content']}"

    # Telegram 4096 belgi limiti
    if len(text) > 4000:
        text = text[:4000] + "...\n\n(Qolgan qism keyingi xabarda)"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
#  VIDEO DARSLAR
# ─────────────────────────────────────────────

async def menu_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_approved(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    videos = db.get_all_videos()
    if not videos:
        keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]
        await query.edit_message_text("🎬 Hozircha video darslar yo'q.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for v in videos:
        keyboard.append([InlineKeyboardButton(f"▶️ {v['title']}", callback_data=f"video_{v['id']}")])
    keyboard.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")])

    await query.edit_message_text("🎬 Video darslar:", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    video_id = int(query.data.split("_")[1])
    video = db.get_video(video_id)

    if not video:
        await query.edit_message_text("❌ Video topilmadi.")
        return

    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="menu_videos")]]
    text = (
        f"🎬 {video['title']}\n\n"
        f"📝 {video['description']}\n\n"
        f"🔗 {video['url']}"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
#  NATIJALAR
# ─────────────────────────────────────────────

async def menu_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    results = db.get_user_results(user_id)
    keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]]

    if not results:
        await query.edit_message_text(
            "📊 Siz hali hech qanday test yechmagansiz.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    text = "📊 Sizning natijalaringiz:\n\n"
    for r in results:
        pct = round((r['correct'] / r['total']) * 100) if r['total'] > 0 else 0
        text += f"📝 {r['test_title']}: {r['correct']}/{r['total']} ({pct}%)\n"

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────
#  ADMIN: CONTENT QO'SHISH (oddiy usul)
# ─────────────────────────────────────────────

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.answer("❌ Ruxsat yo'q!", show_alert=True)
        return

    data = query.data

    if data == "admin_users":
        users = db.get_all_users()
        text = f"👥 Foydalanuvchilar: {len(users)} ta\n\n"
        for u in users[:20]:
            text += f"• {u['first_name']} (@{u['username']}) — {u['status']}\n"
        await query.edit_message_text(text)

    elif data == "admin_stats":
        stats = db.get_stats()
        text = (
            f"📊 Statistika:\n\n"
            f"👥 Jami foydalanuvchilar: {stats['total_users']}\n"
            f"✅ Tasdiqlangan: {stats['approved_users']}\n"
            f"⏳ Kutayotgan: {stats['pending_users']}\n"
            f"📝 Testlar: {stats['total_tests']}\n"
            f"📚 Qo'llanmalar: {stats['total_guides']}\n"
            f"🎬 Videolar: {stats['total_videos']}\n"
        )
        await query.edit_message_text(text)

    elif data == "admin_add_test":
        context.user_data["admin_action"] = "add_test_title"
        await query.edit_message_text(
            "📝 Yangi test yaratish\n\n"
            "Test nomini yozing:\n"
            "(Bekor qilish: /admin)"
        )

    elif data == "admin_add_guide":
        context.user_data["admin_action"] = "add_guide_title"
        await query.edit_message_text(
            "📚 Yangi qo'llanma\n\n"
            "Qo'llanma sarlavhasini yozing:\n"
            "(Bekor qilish: /admin)"
        )

    elif data == "admin_add_video":
        context.user_data["admin_action"] = "add_video_title"
        await query.edit_message_text(
            "🎬 Yangi video\n\n"
            "Video sarlavhasini yozing:\n"
            "(Bekor qilish: /admin)"
        )


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin xabarlarini qayta ishlash"""
    if not is_admin(update.effective_user.id):
        return

    action = context.user_data.get("admin_action", "")
    text = update.message.text

    # TEST QO'SHISH
    if action == "add_test_title":
        context.user_data["new_test_title"] = text
        context.user_data["admin_action"] = "add_test_done"
        db.add_test(text)
        test_id = db.get_last_test_id()
        context.user_data["current_test_id"] = test_id
        context.user_data["admin_action"] = "add_question"
        context.user_data["question_num"] = 1
        await update.message.reply_text(
            f"✅ Test yaratildi: '{text}'\n\n"
            f"Endi 1-savolni quyidagi formatda yozing:\n\n"
            f"Savol matni\n"
            f"A) Variant\n"
            f"B) Variant\n"
            f"C) Variant\n"
            f"D) Variant\n"
            f"To'g'ri javob: A\n\n"
            f"Tugatish uchun: /done"
        )

    elif action == "add_question":
        try:
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
            question_text = lines[0]
            opt_a = lines[1].lstrip("Aa)").strip()
            opt_b = lines[2].lstrip("Bb)").strip()
            opt_c = lines[3].lstrip("Cc)").strip()
            opt_d = lines[4].lstrip("Dd)").strip()
            correct = lines[5].split(":")[-1].strip().upper()

            test_id = context.user_data["current_test_id"]
            db.add_question(test_id, question_text, opt_a, opt_b, opt_c, opt_d, correct)
            num = context.user_data["question_num"]
            context.user_data["question_num"] = num + 1

            await update.message.reply_text(
                f"✅ {num}-savol qo'shildi!\n\n"
                f"Keyingi savolni yozing yoki /done bosing."
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ Format xato! Qaytadan yozing:\n\n"
                f"Savol matni\n"
                f"A) ...\nB) ...\nC) ...\nD) ...\n"
                f"To'g'ri javob: A"
            )

    # QO'LLANMA QO'SHISH
    elif action == "add_guide_title":
        context.user_data["new_guide_title"] = text
        context.user_data["admin_action"] = "add_guide_content"
        await update.message.reply_text(
            f"✅ Sarlavha: '{text}'\n\n"
            f"Endi qo'llanma matnini yozing:"
        )

    elif action == "add_guide_content":
        title = context.user_data.get("new_guide_title", "")
        db.add_guide(title, text)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Qo'llanma qo'shildi: '{title}'")

    # VIDEO QO'SHISH
    elif action == "add_video_title":
        context.user_data["new_video_title"] = text
        context.user_data["admin_action"] = "add_video_desc"
        await update.message.reply_text("Video tavsifini yozing:")

    elif action == "add_video_desc":
        context.user_data["new_video_desc"] = text
        context.user_data["admin_action"] = "add_video_url"
        await update.message.reply_text("Video havolasini (URL) yozing:")

    elif action == "add_video_url":
        title = context.user_data.get("new_video_title", "")
        desc = context.user_data.get("new_video_desc", "")
        db.add_video(title, desc, text)
        context.user_data.clear()
        await update.message.reply_text(f"✅ Video qo'shildi: '{title}'")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    context.user_data.clear()
    await update.message.reply_text("✅ Tugallandi! /admin — Admin panel")


# ─────────────────────────────────────────────
#  ASOSIY
# ─────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("done", done_command))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(request_access, pattern="^request_access$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(menu_tests, pattern="^menu_tests$"))
    app.add_handler(CallbackQueryHandler(start_test, pattern="^start_test_"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^ans_[ABCD]$"))
    app.add_handler(CallbackQueryHandler(menu_guides, pattern="^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide, pattern="^guide_"))
    app.add_handler(CallbackQueryHandler(menu_videos, pattern="^menu_videos$"))
    app.add_handler(CallbackQueryHandler(show_video, pattern="^video_"))
    app.add_handler(CallbackQueryHandler(menu_results, pattern="^menu_results$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    # Matn xabarlari (admin uchun)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
