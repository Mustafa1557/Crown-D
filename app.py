import os
import threading
import fitz  # PyMuPDF
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
    return "Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

TOKEN = os.environ.get('BOT_TOKEN')
DOWNLOAD_DIR = "downloads"

def cleanup(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً مصطفى! أرسل ملف PDF وسأعالجُه لك.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'):
        return
    
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
    pdf_path = context.user_data.get('current_file')

    if query.data == 'translate' and pdf_path:
        await query.edit_message_text("🇸🇩 جاري الترجمة...")
        try:
            doc = fitz.open(pdf_path)
            text = "".join([page.get_text() for page in doc])
            # المكتبة الجديدة مستقرة جداً
            translated = GoogleTranslator(source='auto', target='ar').translate(text[:2000])
            await query.message.reply_text(f"**الترجمة:**\n\n{translated}")
        except Exception as e:
            await query.message.reply_text("خطأ في الترجمة.")

    elif query.data == 'word' and pdf_path:
        await query.edit_message_text("🔄 جاري التحويل...")
        docx_path = pdf_path.replace('.pdf', '.docx')
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        await query.message.reply_document(document=open(docx_path, 'rb'))
        cleanup(docx_path)

    elif query.data == 'audio' and pdf_path:
        await query.edit_message_text("🎧 جاري تحويل الصوت...")
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
