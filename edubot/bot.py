import logging
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
db = Database()

def is_approved(user_id): return db.is_user_approved(user_id)
def is_admin(user_id): return user_id == ADMIN_ID

async def start(update, context):
    user = update.effective_user
    db.add_user(user.id, user.username or "", user.first_name)
    if is_admin(user.id):
        await update.message.reply_text("Admin panel: /admin")
        return
    status = db.get_user_status(user.id)
    if status == "approved":
        await show_main_menu(update, context)
    elif status == "pending":
        await update.message.reply_text("Sorovingiz kutilmoqda...")
    else:
        kb = [[InlineKeyboardButton("Kirish sorovi yuborish", callback_data="request_access")]]
        await update.message.reply_text(f"Salom, {user.first_name}! Ruxsat uchun tugmani bosing:", reply_markup=InlineKeyboardMarkup(kb))

async def show_main_menu(update, context):
    kb = [
        [InlineKeyboardButton("Testlar", callback_data="menu_tests")],
        [InlineKeyboardButton("Qollanmalar", callback_data="menu_guides")],
        [InlineKeyboardButton("Video darslar", callback_data="menu_videos")],
        [InlineKeyboardButton("Mening natijalarim", callback_data="menu_results")],
    ]
    text = "Asosiy menyu:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def request_access(update, context):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    status = db.get_user_status(user.id)
    if status == "pending":
        await query.edit_message_text("Sorovingiz kutilmoqda...")
        return
    if status == "approved":
        await show_main_menu(update, context)
        return
    db.set_user_status(user.id, "pending")
    kb = [[InlineKeyboardButton("Tasdiqlash", callback_data=f"approve_{user.id}"), InlineKeyboardButton("Rad etish", callback_data=f"reject_{user.id}")]]
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"Yangi sorov!\nIsm: {user.first_name}\nID: {user.id}\nUsername: @{user.username or 'yoq'}", reply_markup=InlineKeyboardMarkup(kb))
    await query.edit_message_text("Sorovingiz adminga yuborildi! Kuting.")

async def admin_action(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    action, uid = query.data.split("_", 1)
    target = int(uid)
    if action == "approve":
        db.set_user_status(target, "approved")
        await query.edit_message_text(f"Tasdiqlandi: {target}")
        await context.bot.send_message(chat_id=target, text="Ruxsat berildi! /start bosing.")
    else:
        db.set_user_status(target, "rejected")
        await query.edit_message_text(f"Rad etildi: {target}")
        await context.bot.send_message(chat_id=target, text="Sorovingiz rad etildi.")

async def admin_panel(update, context):
    if not is_admin(update.effective_user.id):
        return
    kb = [
        [InlineKeyboardButton("PDF Test yuklash", callback_data="admin_add_pdf")],
        [InlineKeyboardButton("Qollanma qoshish", callback_data="admin_add_guide")],
        [InlineKeyboardButton("Video qoshish", callback_data="admin_add_video")],
        [InlineKeyboardButton("Foydalanuvchilar", callback_data="admin_users")],
        [InlineKeyboardButton("Statistika", callback_data="admin_stats")],
    ]
    await update.message.reply_text("Admin Panel:", reply_markup=InlineKeyboardMarkup(kb))

async def menu_tests(update, context):
    query = update.callback_query
    await query.answer()
    if not is_approved(query.from_user.id):
        await query.answer("Ruxsat yoq!", show_alert=True)
        return
    tests = db.get_all_pdf_tests()
    if not tests:
        kb = [[InlineKeyboardButton("Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Hozircha testlar yoq.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = []
    for t in tests:
        kb.append([InlineKeyboardButton(f"{t['title']} ({t.get('question_count',30)} savol)", callback_data=f"pdf_test_{t['id']}")])
    kb.append([InlineKeyboardButton("Orqaga", callback_data="back_main")])
    await query.edit_message_text("Testlar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_pdf_test(update, context):
    query = update.callback_query
    await query.answer()
    if not is_approved(query.from_user.id):
        return
    test_id = int(query.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    if not test:
        await query.edit_message_text("Test topilmadi.")
        return
    q_count = test.get("question_count", 30)
    context.user_data["active_test_id"] = test_id
    context.user_data["active_test_count"] = q_count
    await context.bot.send_document(
        chat_id=query.message.chat_id,
        document=test["file_id"],
        caption=f"{test['title']}\n\nSavollar: {q_count} ta\n\nTestni yechib, javoblaringizni yuboring:\n{q_count} ta harf ketma-ket\nMasalan: ABCDABCD..."
    )
    kb = [[InlineKeyboardButton("Javob yuboraman", callback_data=f"submit_test_{test_id}")]]
    await context.bot.send_message(chat_id=query.message.chat_id, text="Testni yechib bolgach:", reply_markup=InlineKeyboardMarkup(kb))

async def submit_test_prompt(update, context):
    query = update.callback_query
    await query.answer()
    test_id = int(query.data.split("_")[2])
    test = db.get_pdf_test(test_id)
    q_count = test.get("question_count", 30) if test else 30
    context.user_data["waiting_answers_for"] = test_id
    context.user_data["active_test_count"] = q_count
    await query.edit_message_text(f"Javoblaringizni yuboring!\n\n{q_count} ta harf ketma-ket:\nMasalan: ABCDABCDABCD...")

async def handle_test_answers(update, context):
    user_id = update.effective_user.id
    test_id = context.user_data.get("waiting_answers_for")
    if not test_id:
        await handle_admin_message(update, context)
        return
    q_count = context.user_data.get("active_test_count", 30)
    text = update.message.text.strip().upper()
    clean = re.sub(r'[^ABCD]', '', text)
    if len(clean) != q_count:
        await update.message.reply_text(f"Xato! {len(clean)} ta javob, {q_count} ta kerak. Qaytadan yuboring.")
        return
    answer_key = db.get_answer_key(test_id)
    if not answer_key:
        await update.message.reply_text("Kalit hali kiritilmagan. Admin tez orada kiritadi.")
        return
    key = re.sub(r'[^ABCD]', '', answer_key.upper())
    if len(key) != q_count:
        await update.message.reply_text("Kalit xato. Admin bilan bogling.")
        return
    correct = sum(1 for u, k in zip(clean, key) if u == k)
    wrong = q_count - correct
    percent = round((correct / q_count) * 100)
    if percent >= 85: baho = "Ajoyib! 🏆"
    elif percent >= 70: baho = "Yaxshi! 👍"
    elif percent >= 50: baho = "Qoniqarli 📚"
    else: baho = "Mashq kerak 💪"
    
    wrong_list = [f"{i+1}: {u} (togri: {k})" for i,(u,k) in enumerate(zip(clean,key)) if u!=k]
    
    result = f"📊 Natija\n{'─'*20}\nTogri: {correct}/{q_count}\nXato: {wrong}/{q_count}\nFoiz: {percent}%\nBaho: {baho}\n"
    if wrong_list and wrong <= 15:
        result += "\nXato javoblar:\n" + "\n".join(wrong_list)
    
    db.save_pdf_result(user_id, test_id, correct, q_count, clean)
    context.user_data.pop("waiting_answers_for", None)
    context.user_data.pop("active_test_count", None)
    
    kb = [[InlineKeyboardButton("Boshqa test", callback_data="menu_tests"), InlineKeyboardButton("Asosiy menyu", callback_data="back_main")]]
    await update.message.reply_text(result, reply_markup=InlineKeyboardMarkup(kb))

async def menu_guides(update, context):
    query = update.callback_query
    await query.answer()
    if not is_approved(query.from_user.id):
        return
    guides = db.get_all_guides()
    if not guides:
        kb = [[InlineKeyboardButton("Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Hozircha qollanmalar yoq.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(g['title'], callback_data=f"guide_{g['id']}")] for g in guides]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="back_main")])
    await query.edit_message_text("Qollanmalar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_guide(update, context):
    query = update.callback_query
    await query.answer()
    guide = db.get_guide(int(query.data.split("_")[1]))
    if not guide:
        return
    kb = [[InlineKeyboardButton("Orqaga", callback_data="menu_guides")]]
    text = f"{guide['title']}\n\n{guide['content']}"
    await query.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup(kb))

async def menu_videos(update, context):
    query = update.callback_query
    await query.answer()
    if not is_approved(query.from_user.id):
        return
    videos = db.get_all_videos()
    if not videos:
        kb = [[InlineKeyboardButton("Orqaga", callback_data="back_main")]]
        await query.edit_message_text("Hozircha videolar yoq.", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton(v['title'], callback_data=f"video_{v['id']}")] for v in videos]
    kb.append([InlineKeyboardButton("Orqaga", callback_data="back_main")])
    await query.edit_message_text("Video darslar:", reply_markup=InlineKeyboardMarkup(kb))

async def show_video(update, context):
    query = update.callback_query
    await query.answer()
    video = db.get_video(int(query.data.split("_")[1]))
    if not video:
        return
    kb = [[InlineKeyboardButton("Orqaga", callback_data="menu_videos")]]
    await query.edit_message_text(f"{video['title']}\n\n{video['description']}\n\n{video['url']}", reply_markup=InlineKeyboardMarkup(kb))

async def menu_results(update, context):
    query = update.callback_query
    await query.answer()
    results = db.get_user_pdf_results(query.from_user.id)
    kb = [[InlineKeyboardButton("Orqaga", callback_data="back_main")]]
    if not results:
        await query.edit_message_text("Hali test yechmagansiz.", reply_markup=InlineKeyboardMarkup(kb))
        return
    text = "Natijalaringiz:\n\n"
    for r in results:
        pct = round(r['correct']/r['total']*100) if r['total'] else 0
        text += f"{r['test_title']}: {r['correct']}/{r['total']} ({pct}%)\n"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def admin_callback(update, context):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    data = query.data
    if data == "admin_add_pdf":
        context.user_data["admin_action"] = "waiting_pdf_title"
        await query.edit_message_text("Test nomini yozing:\n(Masalan: Ona tili 1-variant)\n\nBekor: /admin")
    elif data == "admin_add_guide":
        context.user_data["admin_action"] = "add_guide_title"
        await query.edit_message_text("Qollanma sarlavhasini yozing:")
    elif data == "admin_add_video":
        context.user_data["admin_action"] = "add_video_title"
        await query.edit_message_text("Video sarlavhasini yozing:")
    elif data == "admin_users":
        users = db.get_all_users()
        text = f"Foydalanuvchilar: {len(users)} ta\n\n"
        for u in users[:20]:
            text += f"• {u['first_name']} — {u['status']}\n"
        await query.edit_message_text(text)
    elif data == "admin_stats":
        s = db.get_stats()
        await query.edit_message_text(f"Statistika:\n\nJami: {s['total_users']}\nTasdiqlangan: {s['approved_users']}\nKutayotgan: {s['pending_users']}\nTestlar: {s['total_pdf_tests']}\nQollanmalar: {s['total_guides']}\nVideolar: {s['total_videos']}")

async def handle_pdf_upload(update, context):
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_action") != "waiting_pdf_file":
        return
    file_id = update.message.document.file_id
    context.user_data["new_pdf_file_id"] = file_id
    context.user_data["admin_action"] = "waiting_pdf_key"
    count = context.user_data.get("new_pdf_count", 30)
    await update.message.reply_text(f"PDF qabul qilindi!\n\nEndi {count} ta javob kalitini yozing:\nMasalan: ABCDABCD... ({count} ta harf)")

async def handle_admin_message(update, context):
    if not is_admin(update.effective_user.id):
        return
    action = context.user_data.get("admin_action", "")
    text = update.message.text.strip() if update.message.text else ""
    
    if action == "waiting_pdf_title":
        context.user_data["new_pdf_title"] = text
        context.user_data["admin_action"] = "waiting_pdf_count"
        await update.message.reply_text(f"Nom: {text}\n\nNechta savol? (Masalan: 30)")
    
    elif action == "waiting_pdf_count":
        try:
            count = int(text)
            context.user_data["new_pdf_count"] = count
            context.user_data["admin_action"] = "waiting_pdf_file"
            await update.message.reply_text(f"Savollar: {count} ta\n\nEndi PDF faylni yuboring!")
        except:
            await update.message.reply_text("Faqat raqam yozing. Masalan: 30")
    
    elif action == "waiting_pdf_key":
        title = context.user_data.get("new_pdf_title", "")
        count = context.user_data.get("new_pdf_count", 30)
        file_id = context.user_data.get("new_pdf_file_id", "")
        clean_key = re.sub(r'[^ABCD]', '', text.upper().replace(" ","").replace(",",""))
        if len(clean_key) != count:
            await update.message.reply_text(f"Xato! {len(clean_key)} ta, {count} ta kerak. Qaytadan:")
            return
        db.add_pdf_test(title, file_id, count, clean_key)
        context.user_data.clear()
        await update.message.reply_text(f"Test qoshildi!\nNom: {title}\nSavollar: {count} ta\n\n/admin")
    
    elif action == "add_guide_title":
        context.user_data["new_guide_title"] = text
        context.user_data["admin_action"] = "add_guide_content"
        await update.message.reply_text("Qollanma matnini yozing:")
    
    elif action == "add_guide_content":
        db.add_guide(context.user_data.get("new_guide_title",""), text)
        context.user_data.clear()
        await update.message.reply_text("Qollanma qoshildi!")
    
    elif action == "add_video_title":
        context.user_data["new_video_title"] = text
        context.user_data["admin_action"] = "add_video_desc"
        await update.message.reply_text("Video tavsifini yozing:")
    
    elif action == "add_video_desc":
        context.user_data["new_video_desc"] = text
        context.user_data["admin_action"] = "add_video_url"
        await update.message.reply_text("Video havolasini yozing:")
    
    elif action == "add_video_url":
        db.add_video(context.user_data.get("new_video_title",""), context.user_data.get("new_video_desc",""), text)
        context.user_data.clear()
        await update.message.reply_text("Video qoshildi!")

async def done_command(update, context):
    if not is_admin(update.effective_user.id):
        return
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. /admin")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CallbackQueryHandler(request_access, pattern="^request_access$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(menu_tests, pattern="^menu_tests$"))
    app.add_handler(CallbackQueryHandler(show_pdf_test, pattern="^pdf_test_"))
    app.add_handler(CallbackQueryHandler(submit_test_prompt, pattern="^submit_test_"))
    app.add_handler(CallbackQueryHandler(menu_guides, pattern="^menu_guides$"))
    app.add_handler(CallbackQueryHandler(show_guide, pattern="^guide_"))
    app.add_handler(CallbackQueryHandler(menu_videos, pattern="^menu_videos$"))
    app.add_handler(CallbackQueryHandler(show_video, pattern="^video_"))
    app.add_handler(CallbackQueryHandler(menu_results, pattern="^menu_results$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_test_answers))
    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
