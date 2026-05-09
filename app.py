import os
import uuid
import threading
import asyncio
import fitz
from docx import Document
from gtts import gTTS
from deep_translator import GoogleTranslator
from langdetect import detect
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# =========================================
# Flask Server
# =========================================
app = Flask(__name__)
@app.route('/')
def home():
    return "Multi-Option Translator Bot is Live ✅"

# =========================================
# إعدادات البوت
# =========================================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================
# وظائف مساعدة (Helpers)
# =========================================
def cleanup(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except:
        pass

def extract_text(path):
    text = ""
    try:
        if path.lower().endswith(".pdf"):
            with fitz.open(path) as pdf:
                for page in pdf:
                    text += page.get_text()
        elif path.lower().endswith(".docx"):
            doc = Document(path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif path.lower().endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        print(f"Extract error: {e}")
        return ""
    return text.strip()

def split_text(text, size=3000):
    return [text[i:i+size] for i in range(0, len(text), size)]

async def process_translation(text):
    """دالة موحدة لمعالجة الترجمة لتجنب التكرار"""
    if not text: return ""
    translator = GoogleTranslator(source="auto", target="ar")
    translated_result = ""
    chunks = split_text(text, 2500)
    # نترجم أول 10 قطع فقط (حوالي 25 ألف حرف) لضمان السرعة
    for chunk in chunks[:10]:
        if chunk.strip():
            translated = await asyncio.to_thread(translator.translate, chunk)
            translated_result += translated + "\n\n"
    return translated_result

# =========================================
# الأوامر واستقبال الملفات
# =========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"مرحباً يا {update.effective_user.first_name} 👋\nأرسل ملفك وسأعطيك خيارات الترجمة والصوت.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_size > 15 * 1024 * 1024:
        await update.message.reply_text("❌ الملف كبير جداً (الحد 15MB).")
        return

    file_name = f"{uuid.uuid4()}_{doc.file_name}"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)
    context.user_data["file_path"] = file_path

    keyboard = [
        [InlineKeyboardButton("🌍 خيارات الترجمة بالعربي", callback_data="choose_trans")],
        [InlineKeyboardButton("🎧 صوت إنجليزي (Medical)", callback_data="audio_en")],
        [InlineKeyboardButton("📄 استخراج النص", callback_data="extract")]
    ]
    await update.message.reply_text("✅ تم استلام الملف، ماذا نفعل؟", reply_markup=InlineKeyboardMarkup(keyboard))

# =========================================
# معالجة الأزرار (Logic)
# =========================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    path = context.user_data.get("file_path")

    if not path:
        await query.message.reply_text("❌ انتهت الجلسة أو حذف الملف.")
        return

    try:
        # --- 1. اختيار طريقة الترجمة ---
        if query.data == "choose_trans":
            keyboard = [
                [InlineKeyboardButton("📄 إرسال كملف TXT", callback_data="trans_as_file")],
                [InlineKeyboardButton("💬 إرسال كرسائل نصية", callback_data="trans_as_text")]
            ]
            await query.edit_message_text("كيف تريد استلام الترجمة؟", reply_markup=InlineKeyboardMarkup(keyboard))
            return # نخرج عشان ننتظر ضغطة الزر الجاية

        # --- 2. الترجمة كملف ---
        elif query.data == "trans_as_file":
            await query.edit_message_text("⏳ جاري الترجمة وتحضير الملف...")
            text = await asyncio.to_thread(extract_text, path)
            translated = await process_translation(text)
            
            out_path = path.replace(".pdf", "_ar.txt").replace(".docx", "_ar.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(translated)
            await query.message.reply_document(document=open(out_path, "rb"), caption="✅ ملف الترجمة العربي.")
            cleanup(out_path)

        # --- 3. الترجمة كرسائل ---
        elif query.data == "trans_as_text":
            await query.edit_message_text("⏳ جاري الترجمة والإرسال نصياً...")
            text = await asyncio.to_thread(extract_text, path)
            translated = await process_translation(text)
            chunks = split_text(translated, 3500)
            for chunk in chunks[:5]:
                await query.message.reply_text(chunk)
            await query.message.reply_text("✅ تمت الترجمة النصية.")

        # --- 4. استخراج النص ---
        elif query.data == "extract":
            await query.edit_message_text("📄 جاري الاستخراج...")
            text = await asyncio.to_thread(extract_text, path)
            chunks = split_text(text, 3500)
            for chunk in chunks[:3]:
                await query.message.reply_text(chunk)

        # --- 5. الصوت الإنجليزي ---
        elif query.data == "audio_en":
            await query.edit_message_text("🎧 جاري إنشاء الصوت الإنجليزي...")
            text = await asyncio.to_thread(extract_text, path)
            try: detected = detect(text[:500])
            except: detected = "en"
            
            if detected != "en":
                translator = GoogleTranslator(source="auto", target="en")
                text = await asyncio.to_thread(translator.translate, text[:2500])

            audio_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp3")
            tts = gTTS(text=text[:4000], lang="en", slow=False)
            tts.save(audio_path)
            with open(audio_path, "rb") as f:
                await query.message.reply_audio(audio=f)
            cleanup(audio_path)

    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {e}")
    
    # التنظيف النهائي للملف الأصلي (فقط عند انتهاء العمليات وليس عند اختيار النوع)
    if query.data in ["trans_as_file", "trans_as_text", "extract", "audio_en"]:
        finally_cleanup(path, context)

def finally_cleanup(path, context):
    cleanup(path)
    context.user_data.pop("file_path", None)

def main():
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    if not TOKEN: return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
