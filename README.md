import os
import threading
import shutil
import fitz  # PyMuPDF
from flask import Flask
from gtts import gTTS
from pdf2docx import Converter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- 1. إعداد Flask لضمان استمرارية السيرفر ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running 24/7!"

def run_flask():
    # راندر بيمرر البورت تلقائياً في متغير PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- 2. إعدادات البوت والملفات ---
TOKEN = os.environ.get('BOT_TOKEN')
DOWNLOAD_DIR = "downloads"

# دالة لمسح الملفات بعد إرسالها لتوفير مساحة السيرفر
def cleanup(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً مصطفى! 🎓\n"
        "أرسل لي أي ملف PDF وسأقوم بتحويله لك إلى وورد أو ملف صوتي."
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("الرجاء إرسال ملف بصيغة PDF فقط.")
        return

    msg = await update.message.reply_text("⏳ جاري تحميل ومعالجة الملف...")
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    
    context.user_data['current_file'] = pdf_path

    keyboard = [
        [InlineKeyboardButton("تحويل لـ Word 📝", callback_data='word')],
        [InlineKeyboardButton("قراءة المحتوى بصوت 🎙️", callback_data='audio')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.edit_text("الملف جاهز! اختر ماذا تريد أن أفعل:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pdf_path = context.user_data.get('current_file')

    if not pdf_path or not os.path.exists(pdf_path):
        await query.edit_message_text("عذراً، الملف غير موجود. أرسله مرة أخرى.")
        return

    if query.data == 'word':
        await query.edit_message_text("🔄 جاري التحويل لـ Word... انتظر قليلاً.")
        docx_path = pdf_path.replace('.pdf', '.docx')
        try:
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            await query.message.reply_document(document=open(docx_path, 'rb'))
            cleanup(docx_path) # مسح الوورد بعد الإرسال
        except Exception as e:
            await query.message.reply_text(f"حدث خطأ أثناء التحويل: {str(e)}")

    elif query.data == 'audio':
        await query.edit_message_text("🎧 جاري تحويل النص إلى صوت (إنجليزي)...")
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            
            if text.strip():
                # تحويل أول 3000 حرف فقط لتفادي التأخير
                tts = gTTS(text=text[:3000], lang='en')
                audio_path = pdf_path.replace('.pdf', '.mp3')
                tts.save(audio_path)
                await query.message.reply_audio(audio=open(audio_path, 'rb'))
                cleanup(audio_path) # مسح الصوت بعد الإرسال
            else:
                await query.message.reply_text("لم أجد نصاً في هذا الملف!")
        except Exception as e:
            await query.message.reply_text(f"خطأ في الصوت: {str(e)}")

def main():
    # تشغيل سيرفر Flask في الخلفية
    threading.Thread(target=run_flask, daemon=True).start()

    # تشغيل البوت
    if not TOKEN:
        print("خطأ: BOT_TOKEN غير موجود في المتغيرات البيئية!")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("البوت يعمل الآن...")
    application.run_polling()

if __name__ == '__main__':
    main()
