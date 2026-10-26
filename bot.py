import os
import asyncio
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client

# دریافت متغیرهای امنیتی از تنظیمات سرور
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# وب‌سرور سبک برای روشن نگه داشتن ۲۴ ساعته سرور
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Spotify Mini App Bot is Alive!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    web_app.run(host="0.0.0.0", port=port)

# دستورات ربات تلگرام
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # ذخیره اطلاعات اولیه تلگرام کاربر در دیتابیس
    supabase.table("users").upsert({
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name
    }).execute()
    
    contact_btn = KeyboardButton("📱 تایید و ارسال شماره تماس", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"سلام {user.first_name} عزیز! به مینی‌اپ موزیک خوش آمدید 🎵\n\n"
        "برای ساخت پروفایل اختصاصی، لطفاً دکمه زیر را لمس کنید:",
        reply_markup=reply_markup
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = update.effective_user.id
    
    supabase.table("users").update({
        "phone_number": contact.phone_number
    }).eq("telegram_id", user_id).execute()
    
    context.user_data["waiting_for_email"] = True
    await update.message.reply_text(
        "✅ شماره تماس شما ثبت شد.\n\n"
        "حالا لطفاً آدرس ایمیل خود را ارسال کنید تا حساب کاربری‌تان کامل شود:",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get("waiting_for_email"):
        if "@" in text and "." in text:
            supabase.table("users").update({
                "email": text
            }).eq("telegram_id", user_id).execute()
            
            context.user_data["waiting_for_email"] = False
            await update.message.reply_text(
                "🎉 تبریک! پروفایل شما با موفقیت تکمیل شد.\n"
                "اطلاعات شما در سرور ذخیره شد و آماده ورود به مینی‌اپ هستید."
            )
        else:
            await update.message.reply_text("❌ فرمت ایمیل صحیح نیست. لطفاً یک ایمیل معتبر وارد کنید:")

def main():
    # اجرای وب‌سرور در پس‌زمینه
    threading.Thread(target=run_web, daemon=True).start()
    
    # سازگاری با Python 3.14 در سرور Render
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # اجرای ربات تلگرام
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
