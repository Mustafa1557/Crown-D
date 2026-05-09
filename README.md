import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- إعداد Flask لإبقاء السيرفر حياً ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Living!"

def run_flask():
    # Render بيستخدم بورت 10000 غالباً، بنقرأه من الـ ENV
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- كود البوت الأساسي ---

# جلب التوكن من الـ ENV في راندر
TOKEN = os.environ.get('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أهلاً يا مصطفى! بوت الملفات شغال وجاهز.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("استلمت الملف، جاري التجهيز...")
    # هنا هنضيف الدوال بتاعة الـ PDF والوورد والصوت لاحقاً

def main():
    # تشغيل Flask في Thread منفصل
    threading.Thread(target=run_flask).start()

    # تشغيل البوت
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
