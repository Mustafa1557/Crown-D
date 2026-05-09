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
    return "Advanced Bot is Live ✅"

# =========================================
# إعدادات البوت
# =========================================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================
# وظائف مساعدة
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

# =========================================
# الرسالة الترحيبية
# =========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_msg = f"مرحباً يا {user.first_name} 👋\n\n📂 أرسل PDF / DOCX / TXT\nوسأقوم بترجمته أو تحويله لصوت إنجليزي فوراً."
    await update.message.reply_text(welcome_msg)

# =========================================
# استقبال الملفات
# =========================================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    
    # قيد الحجم (15MB)
    if doc.file_size > 15 * 1024 * 1024:
        await update.message.reply_text("❌ الملف كبير جداً. الحد الأقصى هو 15MB.")
        return

    allowed = [".pdf", ".docx", ".txt"]
    if not any(doc.file_name.lower().endswith(x) for x in allowed):
        await update.message.reply_text("❌ هذا النوع من الملفات غير مدعوم.")
        return

    file_name = f"{uuid.uuid4()}_{doc.file_name}"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)
    context.user_data["file_path"] = file_path

    keyboard = [
        [InlineKeyboardButton("🇸🇩 ترجمة وحفظ كملف", callback_data="translate_ar")],
        [InlineKeyboardButton("🎧 صوت إنجليزي (Medical)", callback_data="audio_en")],
        [InlineKeyboardButton("📄 استخراج النص", callback_data="extract")]
    ]
    await update.message.reply_text("✅ تم استلام الملف، اختر العملية:", reply_markup=InlineKeyboardMarkup(keyboard))

# =========================================
# معالجة الأزرار
# =========================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    path = context.user_data.get("file_path")

    if not path:
        await query.message.reply_text("❌ الملف غير موجود أو تم حذفه.")
        return

    try:
        # --- استخراج النص ---
        if query.data == "extract":
            await query.edit_message_text("📄 جاري استخراج النص...")
            text = await asyncio.to_thread(extract_text, path)
            if not text:
                await query.message.reply_text("❌ فشل استخراج النص.")
                return
            chunks = split_text(text, 3500)
            for chunk in chunks[:3]:
                await query.message.reply_text(chunk)

        # --- الترجمة وحفظ الملف ---
        elif query.data == "translate_ar":
            await query.edit_message_text("🌍 جاري الترجمة للعربية وحفظ الملف...")
            text = await asyncio.to_thread(extract_text, path)
            if not text: return

            translator = GoogleTranslator(source="auto", target="ar")
            translated_text = ""
            chunks = split_text(text, 2500)

            for chunk in chunks[:10]:
                if chunk.strip():
                    translated = await asyncio.to_thread(translator.translate, chunk)
                    translated_text += translated + "\n\n"

            # حفظ في ملف نصي وإرساله
            out_path = path.replace(".pdf", "_ar.txt").replace(".docx", "_ar.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            
            await query.message.reply_document(document=open(out_path, "rb"), caption="✅ ملف الترجمة جاهز.")
            cleanup(out_path)

        # --- صوت إنجليزي ---
        elif query.data == "audio_en":
            await query.edit_message_text("🎧 جاري إنشاء الصوت الإنجليزي...")
            text = await asyncio.to_thread(extract_text, path)
            if not text: return

            try:
                detected = detect(text[:1000])
            except:
                detected = "en"

            if detected != "en":
                translator = GoogleTranslator(source="auto", target="en")
                text = await asyncio.to_thread(translator.translate, text[:2500])

            audio_path = os.path.join(DOWNLOAD_DIR, f"{uuid.uuid4()}.mp3")
            tts = gTTS(text=text[:4000], lang="en", slow=False)
            tts.save(audio_path)
            
            with open(audio_path, "rb") as audio:
                await query.message.reply_audio(audio=audio, caption="✅ النطق الإنجليزي للمحاضرة.")
            cleanup(audio_path)

    except Exception as e:
        await query.message.reply_text(f"❌ حدث خطأ: {e}")

    # التنظيف النهائي للملف الأصلي (في آخر الـ callback)
    finally:
        cleanup(path)
        context.user_data.pop("file_path", None)

# =========================================
# التشغيل
# =========================================
def main():
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()
    
    if not TOKEN: return
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("✅ Bot is Optimized & Started")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
