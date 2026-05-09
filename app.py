import os
import threading
import fitz  # PyMuPDF
from flask import Flask
from gtts import gTTS
from pdf2docx import Converter
from PyPDF2 import PdfMerger
from googletrans import Translator
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- 1. إعداد Flask لضمان استمرارية السيرفر على Render ---
app = Flask(__name__)
translator = Translator()

@app.route('/')
def home():
    return "Bot is Running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. إعدادات البوت والملفات ---
TOKEN = os.environ.get('BOT_TOKEN')
DOWNLOAD_DIR = "downloads"

def cleanup(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً مصطفى! 🎓\n"
        "أرسل لي ملف PDF وسأقوم بمعالجته لك.\n"
        "ملاحظة: للدمج أرسل ملفين ثم اختر دمج."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("الرجاء إرسال ملف بصيغة PDF فقط.")
        return

    msg = await update.message.reply_text("⏳ جاري تحميل الملف...")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    
    context.user_data['current_file'] = pdf_path

    keyboard = [
        [InlineKeyboardButton("تحويل لـ Word 📝", callback_data='word')],
        [InlineKeyboardButton("قراءة المحتوى بصوت 🎙️", callback_data='audio')],
        [InlineKeyboardButton("ترجمة للعربية 🇸🇩", callback_data='translate')],
        [InlineKeyboardButton("دمج الملفات المرفوعة 📂", callback_data='merge')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.edit_text("الملف جاهز! اختر ماذا تريد أن أفعل:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pdf_path = context.user_data.get('current_file')

    if not pdf_path or not os.path.exists(pdf_path):
        if query.data != 'merge':
            await query.edit_message_text("عذراً، الملف غير موجود. أرسله مرة أخرى.")
            return

    if query.data == 'word':
        await query.edit_message_text("🔄 جاري التحويل لـ Word...")
        docx_path = pdf_path.replace('.pdf', '.docx')
        try:
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            await query.message.reply_document(document=open(docx_path, 'rb'))
            cleanup(docx_path)
        except Exception as e:
            await query.message.reply_text(f"خطأ في التحويل: {str(e)}")

    elif query.data == 'audio':
        await query.edit_message_text("🎧 جاري استخراج النص وتحويله لصوت...")
        try:
            doc = fitz.open(pdf_path)
            text = "".join([page.get_text() for page in doc])
            if text.strip():
                tts = gTTS(text=text[:3000], lang='en')
                audio_path = pdf_path.replace('.pdf', '.mp3')
                tts.save(audio_path)
                await query.message.reply_audio(audio=open(audio_path, 'rb'))
                cleanup(audio_path)
            else:
                await query.message.reply_text("الملف فارغ!")
        except Exception as e:
            await query.message.reply_text(f"خطأ في الصوت: {str(e)}")

    elif query.data == 'translate':
        await query.edit_message_text("🇸🇩 جاري الترجمة للعربية...")
        try:
            doc = fitz.open(pdf_path)
            text = "".join([page.get_text() for page in doc])
            translated = translator.translate(text[:3000], dest='ar')
            await query.message.reply_text(f"**الترجمة:**\n\n{translated.text}")
        except Exception as e:
            await query.message.reply_text("فشلت الترجمة، حاول لاحقاً.")

    elif query.data == 'merge':
        await query.edit_message_text("🔄 جاري دمج كل ملفات الـ PDF المرفوعة...")
        try:
            merger = PdfMerger()
            pdf_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.pdf')]
            if len(pdf_files) < 2:
                await query.message.reply_text("أرسل ملفين على الأقل للدمج.")
                return
            for f in sorted(pdf_files):
                merger.append(os.path.join(DOWNLOAD_DIR, f))
            merged_path = os.path.join(DOWNLOAD_DIR, "merged_by_bot.pdf")
            merger.write(merged_path)
            merger.close()
            await query.message.reply_document(document=open(merged_path, 'rb'))
            # تنظيف المجلد بعد الدمج
            for f in pdf_files: cleanup(os.path.join(DOWNLOAD_DIR, f))
            cleanup(merged_path)
        except Exception as e:
            await query.message.reply_text(f"خطأ في الدمج: {str(e)}")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    if not TOKEN: return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
