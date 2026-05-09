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
ADMIN_ID = 12345678  # <--- تأكد من وضع رقم الـ ID الخاص بك هنا
DOWNLOAD_DIR = "downloads"

async def notify_admin(context, message):
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📢 تقرير المراقبة:\n{message}")
        except: pass

def cleanup(file_path):
    try:
        if os.path.exists(file_path): os.remove(file_path)
    except: pass

# --- وظائف البوت المعدلة ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_name = user.first_name
    
    # إشعار للأدمن بتفاصيل المستخدم الجديد
    admin_msg = (f"👤 مستخدم جديد دخل البوت:\n"
                 f"🔹 الاسم: {user_name}\n"
                 f"🔹 اليوزر: @{user.username if user.username else 'لا يوجد'}\n"
                 f"🔹 الـ ID: `{user.id}`")
    await notify_admin(context, admin_msg)
    
    # الرد على المستخدم باسمه هو وليس اسمك
    await update.message.reply_text(f"مرحباً يا {user_name}! 👋\nأرسل لي ملف PDF وسأقوم بمعالجته لك فوراً.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user = update.message.from_user
    
    if not doc.file_name.lower().endswith('.pdf'):
        await update.message.reply_text("عذراً، أقبل ملفات PDF فقط.")
        return
    
    # إخطار الإدارة بالملف المرفوع
    await notify_admin(context, f"📥 {user.first_name} أرسل ملفاً:\n📄 {doc.file_name}")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    pdf_path = os.path.join(DOWNLOAD_DIR, doc.file_name)
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    context.user_data['current_file'] = pdf_path

    keyboard = [[InlineKeyboardButton("Word 📝", callback_data='word')],
                [InlineKeyboardButton("صوت 🎙️", callback_data='audio')],
                [InlineKeyboardButton("ترجمة 🇸🇩", callback_data='translate')],
                [InlineKeyboardButton("دمج 📂", callback_data='merge')]]
    await update.message.reply_text("الملف جاهز! ماذا تريد أن أفعل؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    pdf_path = context.user_data.get('current_file')

    # مراقبة ضغطات الأزرار
    await notify_admin(context, f"⚙️ {user.first_name} اختار عملية: {query.data}")

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
            await query.message.reply_text("✅ تمت الترجمة بنجاح.")
        except:
            await query.message.reply_text("فشلت الترجمة، قد يكون الملف محمياً أو كبيراً جداً.")

    elif query.data == 'word' and pdf_path:
        await query.edit_message_text("🔄 جاري التحويل لوورد...")
        try:
            docx_path = pdf_path.replace('.pdf', '.docx')
            cv = Converter(pdf_path)
            cv.convert(docx_path); cv.close()
            await query.message.reply_document(document=open(docx_path, 'rb'))
            cleanup(docx_path)
        except Exception as e:
            await query.message.reply_text(f"خطأ في التحويل: {e}")

    elif query.data == 'audio' and pdf_path:
        await query.edit_message_text("🎧 جاري تحويل النص لصوت...")
        try:
            doc = fitz.open(pdf_path)
            text = "".join([page.get_text() for page in doc])
            tts = gTTS(text=text[:2000], lang='en')
            audio_path = pdf_path.replace('.pdf', '.mp3')
            tts.save(audio_path)
            await query.message.reply_audio(audio=open(audio_path, 'rb'))
            cleanup(audio_path)
        except Exception as e:
            await query.message.reply_text(f"خطأ في الصوت: {e}")

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
