import os
import threading
import fitz  # PyMuPDF
from flask import Flask
from gtts import gTTS
from pdf2docx import Converter
from PyPDF2 import PdfMerger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- إعداد Flask للحفاظ على السيرفر حياً ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Alive!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- متغيرات البيئة ---
TOKEN = os.environ.get('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً مصطفى! أرسل ملف PDF وسأقوم بمعالجته لك.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("عذراً، أنا أتعامل مع ملفات PDF فقط حالياً.")
        return

    await update.message.reply_text("جاري تحميل الملف...")
    pdf_path = f"downloads/{doc.file_name}"
    os.makedirs("downloads", exist_ok=True)
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    
    # حفظ المسار في بيانات المستخدم
    context.user_data['last_file'] = pdf_path
    
    keyboard = [
        [InlineKeyboardButton("تحويل إلى Word 📝", callback_data='word')],
        [InlineKeyboardButton("استخراج نص وصوت 🎙️", callback_data='audio')],
        [InlineKeyboardButton("ترجمة المحتوى Arabic 🔄", callback_data='translate')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("ماذا تريد أن أفعل بهذا الملف؟", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    pdf_path = context.user_data.get('last_file')

    if not pdf_path or not os.path.exists(pdf_path):
        await query.edit_message_text("انتهت جلسة الملف، يرجى إرساله مرة أخرى.")
        return

    if data == 'word':
        await query.edit_message_text("جاري التحويل إلى Word... قد يستغرق ذلك دقيقة.")
        docx_path = pdf_path.replace('.pdf', '.docx')
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        await query.message.reply_document(document=open(docx_path, 'rb'))
        
    elif data == 'audio':
        await query.edit_message_text("جاري استخراج النص وتحويله لصوت...")
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        if text.strip():
            tts = gTTS(text=text[:2000], lang='en') # نأخذ أول 2000 حرف للتجربة
            audio_path = pdf_path.replace('.pdf', '.mp3')
            tts.save(audio_path)
            await query.message.reply_audio(audio=open(audio_path, 'rb'))
        else:
            await query.message.reply_text("لم أجد نصاً قابلاً للقراءة في الملف.")

def main():
    threading.Thread(target=run_flask).start()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()
