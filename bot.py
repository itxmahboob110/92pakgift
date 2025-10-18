import os
import logging
from flask import Flask, request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from uuid import uuid4

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Environment vars
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# In-memory data (for demo — use DB for production)
users = {}
referrals = {}
gift_codes = {"code": "FREE92PAK", "remaining": 100}
admin_id = None  # Set your Telegram ID here

# ---- Telegram Bot Application ----
application = Application.builder().token(BOT_TOKEN).build()


# ---------------- Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users[user_id] = {"ref": None, "invites": 0, "verified": False}

    text = (
        "Assalam O Alaikum! Umeed karta hoon keh aap khairiyat se honge 🌙\n\n"
        "*✨ Welcome To Our 92Pak Free Gift Code Bot ✨*"
    )
    keyboard = [
        [
            InlineKeyboardButton("📢 Join Telegram Channel", url="https://t.me/YourChannel"),
        ],
        [
            InlineKeyboardButton("💬 Join WhatsApp Channel", url="https://chat.whatsapp.com/YourGroup"),
        ],
        [
            InlineKeyboardButton("✅ Verify", callback_data="verify"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    users[user_id]["verified"] = True

    ref_code = str(uuid4())[:8]
    referrals[user_id] = {"code": ref_code, "count": 0}

    text = (
        "🎉 *KhushAmdeed!!*\n\n"
        "92Pak Free Gift Code Bot jo aapko daily free gift codes provide karta hai.\n"
        "Lekin aapko daily *2 members invite* karne honge gift code ke liye.\n\n"
        f"📲 *Your Refer Code:* `{ref_code}`"
    )
    keyboard = [
        [
            InlineKeyboardButton("👥 My Refers", callback_data="refers"),
            InlineKeyboardButton("🎁 Claim", callback_data="claim"),
        ],
        [
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def refers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    count = referrals.get(user_id, {}).get("count", 0)
    await query.answer()
    await query.edit_message_text(f"👥 You have invited *{count}* members.", parse_mode="Markdown")


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    ref = referrals.get(user_id, {})

    if ref.get("count", 0) >= 2:
        if gift_codes["remaining"] > 0:
            gift_codes["remaining"] -= 1
            code = gift_codes["code"]
            await query.edit_message_text(
                f"🎁 *Congratulations!*\nYour gift code is: `{code}`",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Sorry, all gift codes have been claimed!")
    else:
        remaining = 2 - ref.get("count", 0)
        await query.edit_message_text(
            f"⚠️ You need {remaining} more invites to claim your gift code!"
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    remaining = gift_codes["remaining"]
    await query.answer()
    await query.edit_message_text(
        f"📊 Remaining gift codes: *{remaining}*", parse_mode="Markdown"
    )


# ---------------- Admin Commands ----------------
async def set_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Access denied.")
        return
    try:
        code = context.args[0]
        limit = int(context.args[1])
        gift_codes["code"] = code
        gift_codes["remaining"] = limit
        await update.message.reply_text(f"🎁 Gift code set to {code} for {limit} users.")
    except:
        await update.message.reply_text("Usage: /set_gift <code> <limit>")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != admin_id:
        await update.message.reply_text("Access denied.")
        return
    msg = " ".join(context.args)
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e:
            logger.warning(f"Cannot send to {uid}: {e}")
    await update.message.reply_text("✅ Broadcast sent.")


# ---------------- Handlers ----------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(verify, pattern="^verify$"))
application.add_handler(CallbackQueryHandler(refers, pattern="^refers$"))
application.add_handler(CallbackQueryHandler(claim, pattern="^claim$"))
application.add_handler(CallbackQueryHandler(status, pattern="^status$"))
application.add_handler(CommandHandler("set_gift", set_gift))
application.add_handler(CommandHandler("broadcast", broadcast))


# ---------------- Flask Webhook ----------------
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


@app.route("/")
async def index():
    return "92Pak Referral Bot is Running 🚀"


if __name__ == "__main__":
    import asyncio

    async def run():
        await application.initialize()
        await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        await application.start()
        print("Bot is live on Render with Webhook ✅")
        await asyncio.Event().wait()

    asyncio.run(run())
