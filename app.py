import os
import threading
import uuid
import fitz
from pdf2docx import Converter
from gtts import gTTS
import google.generativeai as genai
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ------------------ إعداد السيرفر ------------------
app = Flask(__name__)
@app.route('/')
def home(): return "All-in-One Bot is Live!"

# ------------------ المتغيرات ------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_KEY = os.environ.get("GOOGLE_API_KEY")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ------------------ Gemini (مع إضافة التعليمات) ------------------
model = None
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # ضفنا هنا الـ System Instruction عشان الإجابات تعجبك
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        system_instruction="أنت 'دحيح'. إجاباتك مختصرة جداً، علمية، وفي نقاط واضحة."
    )

# ------------------ أوامر البوت ------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً يا دحيح! 🤖\nأرسل نص للدردشة أو PDF للتحويل والترجمة.")

# ------------------ الرسائل النصية والصوت ------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model:
        await update.message.reply_text("❌ Gemini API غير مفعلة.")
        return

    user_text = update.message.text
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = model.generate_content(user_text)
        res_text = response.text if response.text else "ما قدرت أطلع رد."

        # إرسال النص
        await update.message.reply_text(res_text[:4096])

        # الصوت (Voice Note)
        audio_name = f"{uuid.uuid4()}.ogg"
        tts = gTTS(text=res_text[:500], lang='ar')
        tts.save(audio_name)
        with open(audio_name, "rb") as audio:
            await update.message.reply_voice(audio)
        os.remove(audio_name)

    except Exception as e:
        await update.message.reply_text(f"❌ حصل خطأ:\n{str(e)}")

# ------------------ استقبال ومعالجة PDF ------------------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("❌ أرسل ملف PDF فقط.")
        return

    pdf_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}_{doc.file_name}")
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(pdf_path)
    context.user_data["current_file"] = pdf_path

    keyboard = [
        [InlineKeyboardButton("ترجمة النص 🇸🇩", callback_data="translate")],
        [InlineKeyboardButton("تحويل لـ Word 📝", callback_data="word")]
    ]
    await update.message.reply_text(f"📄 الملف: {doc.file_name}\nماذا نفعل؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pdf_path = context.user_data.get("current_file")

    if not pdf_path or not os.path.exists(pdf_path):
        await query.edit_message_text("❌ الملف غير موجود.")
        return

    if query.data == "word":
        await query.edit_message_text("🔄 جاري التحويل...")
        docx_path = pdf_path.replace(".pdf", ".docx")
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        with open(docx_path, "rb") as f:
            await query.message.reply_document(f)
        os.remove(docx_path)

    elif query.data == "translate":
        await query.edit_message_text("🔄 جاري الترجمة...")
        doc = fitz.open(pdf_path)
        text = "".join([page.get_text() for page in doc])
        doc.close()
        res = model.generate_content(f"ترجم النص التالي بأسلوب علمي مبسط: {text[:3000]}")
        await query.message.reply_text(res.text[:4096])

# ------------------ التشغيل ------------------
def main():
    if not BOT_TOKEN: return
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
