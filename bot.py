import os
import asyncio
import threading
from flask import Flask, render_template, request, jsonify
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from supabase import create_client, Client

# مقادیر امنیتی با پیش‌فرض‌های ضدخطا
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://igeghcaikessmnwsahch.supabase.co").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_jWSURt-uHqUWp24bQ-kbkA_0MTZL8Mo").strip()
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://spotify-mini-app.onrender.com").strip()

# پاکسازی خودکار کاراکترهای اضافی احتمالی از ابتدای URL
if SUPABASE_URL.startswith("SUPABASE_URL="):
    SUPABASE_URL = SUPABASE_URL.split("=")[1].strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return render_template("index.html")

# API دریافت پلی‌لیست‌های کاربر
@web_app.route("/api/playlists", methods=["GET"])
def get_playlists():
    telegram_id = request.args.get("telegram_id")
    try:
        response = supabase.table("playlists").select("*").eq("telegram_id", telegram_id).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify([])

# API ثبت پلی‌لیست جدید
@web_app.route("/api/playlists", methods=["POST"])
def add_playlist():
    data = request.json
    print("Received playlist data:", data)  # چاپ اطلاعات در لاگ Render
    try:
        response = supabase.table("playlists").insert({
            "telegram_id": data.get("telegram_id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "cover_emoji": data.get("cover_emoji", "🎵")
        }).execute()
        print("Supabase insert response:", response)
        return jsonify({"success": True})
    except Exception as e:
        print("ERROR saving playlist:", str(e))  # چاپ خطای دقیق در لاگ
        return jsonify({"success": False, "error": str(e)})

def run_web():
    port = int(os.environ.get("PORT", 8000))
    web_app.run(host="0.0.0.0", port=port)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    try:
        supabase.table("users").upsert({
            "telegram_id": user.id,
            "username": user.username,
            "first_name": user.first_name
        }).execute()
    except Exception as e:
        print(f"Database Warning in start: {e}")
    
    contact_btn = KeyboardButton("📱 تایید و ارسال شماره تماس", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_btn]], resize_keyboard=True, one_time_keyboard=True)
    
    webapp_btn = InlineKeyboardButton(
        text="🎧 ورود مستقیم به مینی‌اپ اسپاتیفای",
        web_app=WebAppInfo(url=RENDER_EXTERNAL_URL)
    )
    inline_markup = InlineKeyboardMarkup([[webapp_btn]])
    
    await update.message.reply_text(
        f"سلام {user.first_name} عزیز! به مینی‌اپ موزیک خوش آمدید 🎵\n\n"
        "برای تکمیل ثبت‌نام، دکمه پایین صفحه (ارسال شماره تماس) را لمس کنید:",
        reply_markup=reply_markup
    )
    
    await update.message.reply_text(
        "همچنین می‌توانید همین الان محیط مینی‌اپ را باز کنید:",
        reply_markup=inline_markup
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = update.effective_user.id
    
    try:
        supabase.table("users").update({
            "phone_number": contact.phone_number
        }).eq("telegram_id", user_id).execute()
    except Exception as e:
        print(f"Database Warning in contact: {e}")
    
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
            try:
                supabase.table("users").update({
                    "email": text
                }).eq("telegram_id", user_id).execute()
            except Exception as e:
                print(f"Database Warning in email: {e}")
            
            context.user_data["waiting_for_email"] = False
            
            webapp_btn = InlineKeyboardButton(
                text="🎧 باز کردن مینی‌اپ اسپاتیفای",
                web_app=WebAppInfo(url=RENDER_EXTERNAL_URL)
            )
            inline_markup = InlineKeyboardMarkup([[webapp_btn]])
            
            await update.message.reply_text(
                "🎉 تبریک! پروفایل شما با موفقیت تکمیل شد.\n"
                "حالا می‌توانید وارد محیط اختصاصی مینی‌اپ شوید:",
                reply_markup=inline_markup
            )
        else:
            await update.message.reply_text("❌ فرمت ایمیل صحیح نیست. لطفاً یک ایمیل معتبر وارد کنید:")

def main():
    threading.Thread(target=run_web, daemon=True).start()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
