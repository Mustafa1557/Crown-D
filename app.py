import os
import threading
import uuid
import fitz  # للـ PDF
from docx import Document  # للـ Word
from pptx import Presentation  # للـ PowerPoint
from pdf2docx import Converter
from gtts import gTTS
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- إعداد السيرفر ---
app = Flask(__name__)
@app.route('/')
def home(): return "Tools Bot with Admin Monitor is Live!"

# --- المتغيرات المخفية ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID") # تأكد من وضع الـ ID في راندر
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- دالة إرسال تنبيه للمشرف ---
async def notify_admin(context, message):
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"📢 تنبيه المراقبة:\n{message}")
        except:
            print("خطأ: تأكد من صحة ADMIN_ID وأنك بدأت محادثة مع البوت.")

# --- وظيفة استخراج النص ---
def get_text_from_any(file_path):
    ext = file_path.lower()
    text = ""
    try:
        if ext.endswith('.pdf'):
            doc = fitz.open(file_path)
            text = "".join([page.get_text() for page in doc])
            doc.close()
        elif ext.endswith('.docx'):
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext.endswith(('.pptx', '.ppt')):
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text += shape.text + " "
    except:
        pass
    return text

# --- أوامر البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"أهلاً {user.first_name}! 🛠️\nأرسل ملف (PDF, Word, PPT) لتحويله.")
    # تنبيه المشرف عند دخول مستخدم جديد
    await notify_admin(context, f"المستخدم {user.first_name} (@{user.username}) بدأ استخدام البوت.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user = update.effective_user
    file_ext = doc.file_name.lower().split('.')[-1]
    
    if file_ext not in ['pdf', 'docx', 'pptx', 'ppt']:
        await update.message.reply_text("❌ أقبل فقط PDF, Word, PowerPoint.")
        return

    pdf_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_{doc.file_name}")
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    context.user_data["current_file"] = pdf_path

    # تنبيه المشرف عند رفع ملف
    await notify_admin(context, f"قام {user.first_name} برفع ملف: {doc.file_name}")

    keyboard = [[InlineKeyboardButton("تحويل لصوت 🎧", callback_data="audio")]]
    if file_ext == 'pdf':
        keyboard.append([InlineKeyboardButton("تحويل لـ Word 📝", callback_data="word")])
    
    await update.message.reply_text(f"📄 تم استلام الملف. ماذا نفعل؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    file_path = context.user_data.get("current_file")
    
    if not file_path or not os.path.exists(file_path): return

    if query.data == "audio":
        await query.edit_message_text("🔄 جاري التحويل لصوت...")
        text = get_text_from_any(file_path)
        if text.strip():
            audio_path = f"{uuid.uuid4()}.ogg"
            tts = gTTS(text=text[:1000], lang='ar')
            tts.save(audio_path)
            with open(audio_path, "rb") as voice:
                await query.message.reply_voice(voice)
            os.remove(audio_path)
            await notify_admin(context, f"✅ نجح {user.first_name} في تحويل نص لصوت.")
        else:
            await query.message.reply_text("❌ لم أجد نصاً.")

    elif query.data == "word":
        await query.edit_message_text("🔄 جاري التحويل لـ Word...")
        docx_path = file_path.replace('.pdf', '.docx')
        cv = Converter(file_path)
        cv.convert(docx_path)
        cv.close()
        with open(docx_path, "rb") as f:
            await query.message.reply_document(f)
        os.remove(docx_path)
        await notify_admin(context, f"✅ نجح {user.first_name} في تحويل PDF لـ Word.")

def main():
    if not BOT_TOKEN: return
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
