import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- Telegram Bot Setup ---
application = ApplicationBuilder().token(BOT_TOKEN).build()

# --- Flask App for Webhook ---
app = Flask(__name__)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Join Telegram Channel", url="https://t.me/YourChannelLink")],
        [InlineKeyboardButton("💬 Join WhatsApp Channel", url="https://chat.whatsapp.com/YourWhatsAppInvite")],
        [InlineKeyboardButton("✅ Verify & Get Gift Code", callback_data="verify")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎉 **Welcome!**\n\nJoin both channels and then verify to get your **Free Gift Code** 🎁",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 Please invite *2 friends* using your unique referral link.\n\nOnce they join, you'll get your gift code automatically!",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use /start to begin and claim your free gift code 🎁")

# --- Handlers registration ---
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CallbackQueryHandler(verify, pattern="verify"))

# --- Flask Webhook Route ---
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

@app.route("/")
def home():
    return "92Pak Telegram Bot Running 🚀"

# --- Run the bot ---
if __name__ == "__main__":
    import asyncio

    async def main():
        await application.initialize()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        await application.start()
        print("✅ Webhook connected to Telegram.")

        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port)

    asyncio.run(main())

