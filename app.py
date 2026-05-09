import os
import threading
import fitz
from flask import Flask
from gtts import gTTS
from pdf2docx import Converter
from PyPDF2 import PdfMerger
from deep_translator import GoogleTranslator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- الإعدادات ---
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = 8168754101  # <--- ضيف الـ ID بتاعك هنا يا مصطفى
DOWNLOAD_DIR = "downloads"

async def notify_admin(context, message):
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📢 مراقبة:\n{message}")
        except: pass

def cleanup(file_path):
    try:
        if os.path.exists(file_path): os.remove(file_path)
    except: pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await notify_admin(context, f"مستخدم ضغط /start: {user.first_name} (@{user.username})")
    await update.message.reply_text("أهلاً مصطفى! أرسل ملف PDF وسأعالجُه لك.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'): return
    
    user = update.message.from_user
    await notify_admin(context, f"📥 استلام ملف: {doc.file_name}\nمن: {user.first_name} (@{user.username})")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    context.user_data['current_file'] = pdf_path

    keyboard = [[InlineKeyboardButton("Word 📝", callback_data='word')],
                [InlineKeyboardButton("صوت 🎙️", callback_data='audio')],
                [InlineKeyboardButton("ترجمة 🇸🇩", callback_data='translate')],
                [InlineKeyboardButton("دمج 📂", callback_data='merge')]]
    await update.message.reply_text("اختر المهمة:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    pdf_path = context.user_data.get('current_file')

    await notify_admin(context, f"⚙️ {user.first_name} اختار مهمة: {query.data}")

    if query.data == 'translate' and pdf_path:
        await query.edit_message_text("🇸🇩 جاري الترجمة...")
        try:
            doc = fitz.open(pdf_path)
            full_text = "".join([page.get_text() for page in doc])
            translator = GoogleTranslator(source='auto', target='ar')
            chunks = [full_text[i:i+2000] for i in range(0, len(full_text), 2000)]
            for chunk in chunks:
                if chunk.strip():
                    await query.message.reply_text(translator.translate(chunk))
            await query.message.reply_text("✅ تمت الترجمة.")
        except:
            await query.message.reply_text("خطأ في الترجمة.")

    elif query.data == 'word' and pdf_path:
        await query.edit_message_text("🔄 جاري التحويل...")
        docx_path = pdf_path.replace('.pdf', '.docx')
        cv = Converter(pdf_path)
        cv.convert(docx_path); cv.close()
        await query.message.reply_document(document=open(docx_path, 'rb'))
        cleanup(docx_path)

    elif query.data == 'audio' and pdf_path:
        await query.edit_message_text("🎧 جاري التحويل لصوت...")
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        tts = gTTS(text=text[:2000], lang='en')
        audio_path = pdf_path.replace('.pdf', '.mp3')
        tts.save(audio_path)
        await query.message.reply_audio(audio=open(audio_path, 'rb'))
        cleanup(audio_path)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    if not TOKEN: return
    app_tg = Application.builder().token(TOKEN).build()
    app_tg.add_handler(CommandHandler("start", start))
    app_tg.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app_tg.add_handler(CallbackQueryHandler(button_callback))
    app_tg.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
