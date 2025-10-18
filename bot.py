import os
import sqlite3
import hashlib
import logging
from flask import Flask, request, abort
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
import asyncio

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://wa.me/")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing!")

# Telegram bot init
bot = Bot(BOT_TOKEN)

# Flask app
app = Flask(__name__)

# Database setup
DB_PATH = "bot_data.sqlite"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            refer_code TEXT,
            referred_by TEXT,
            joined_channel INTEGER DEFAULT 0,
            invites INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_code TEXT,
            referee_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            valid_for INTEGER,
            set_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_db()

# Helper functions


def generate_ref_code(user_id):
    h = hashlib.sha1(f"REF{user_id}".encode()).hexdigest()[:8].upper()
    return f"R{h}"


def user_exists(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)


def register_user(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not user_exists(user.id):
        ref_code = generate_ref_code(user.id)
        c.execute("INSERT INTO users (user_id, username, first_name, refer_code) VALUES (?, ?, ?, ?)",
                  (user.id, user.username or "", user.first_name or "", ref_code))
    else:
        c.execute("UPDATE users SET username=?, first_name=?, last_seen=CURRENT_TIMESTAMP WHERE user_id=?",
                  (user.username or "", user.first_name or "", user.id))
    conn.commit()
    conn.close()


def set_referred(ref_code, referee_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE refer_code=?", (ref_code,))
    row = c.fetchone()
    if row:
        referrer_id = row[0]
        c.execute("SELECT 1 FROM referrals WHERE referrer_code=? AND referee_id=?", (ref_code, referee_id))
        if not c.fetchone():
            c.execute("INSERT INTO referrals (referrer_code, referee_id) VALUES (?, ?)", (ref_code, referee_id))
            c.execute("UPDATE users SET invites = invites + 1 WHERE user_id=?", (referrer_id,))
            c.execute("UPDATE users SET referred_by=? WHERE user_id=?", (ref_code, referee_id))
            conn.commit()
    conn.close()


def get_invites_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT invites FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, username, first_name, refer_code, invites, joined_channel, claimed FROM users WHERE user_id=?",
        (user_id,))
    row = c.fetchone()
    conn.close()
    return row


def get_current_code():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT code, valid_for, set_at FROM codes ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row


def set_code(code, valid_for):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO codes (code, valid_for) VALUES (?, ?)", (code, valid_for))
    conn.commit()
    conn.close()


# Keyboards
def make_start_keyboard(user):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Telegram Channel", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("Join WhatsApp Channel", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("Verify", callback_data=f"verify:{user.id}")]
    ])


def make_after_verify_keyboard(user_id):
    user = get_user_by_id(user_id)
    refer_code = user[3] if user else generate_ref_code(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start={refer_code}"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Refers ✅ ({get_invites_count(user_id)})", callback_data=f"shows_refs:{user_id}"),
            InlineKeyboardButton("Claim", callback_data=f"claim:{user_id}")
        ],
        [InlineKeyboardButton("Status", callback_data=f"status:{user_id}")],
        [InlineKeyboardButton("Share Referral Link", url=ref_link)]
    ])


# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    args = context.args

    if args:
        ref_code = args[0]
        logger.info(f"Referral start detected for user {user.id} with code {ref_code}")
        set_referred(ref_code, user.id)

    text = (
        "Assalam O Alaikum, Umeed Karta Hoon keh Aap Khairiyat Se Hon Gay 🌙\n\n"
        "<b>Welcome To Our 92Pak Free Gift Code Bot</b>\n\n"
        "Neechay diye gaye buttons se channel join karo aur verify karo."
    )
    await update.message.reply_html(text, reply_markup=make_start_keyboard(user))


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    await query.answer()

    if data.startswith("verify:"):
        target_user_id = int(data.split(":")[1])
        if user.id != target_user_id:
            await query.edit_message_text("Please press Verify in your own chat using /start.")
            return

        try:
            res = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
            if res.status in ("member", "creator", "administrator"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET joined_channel=1 WHERE user_id=?", (user.id,))
                conn.commit()
                conn.close()

                text = (
                    "KhushAmdeed !! 🎉\n\n"
                    "92Pak Free Gift Code Bot jo aapko Daily Free GiftCodes Provide Karta Hai.\n"
                    "Lekin aapko har din 2 members invite karne honge gift code ke liye."
                )
                await query.edit_message_text(text, reply_markup=make_after_verify_keyboard(user.id))
            else:
                await query.edit_message_text("Aap abhi channel join nahi karay. Pehlay channel join karein phir Verify karein.")
        except Exception as e:
            logger.exception("Error verifying membership")
            await query.edit_message_text("Verification mein error aaya. Bot ko channel ka admin bana kar phir try karein.")

    elif data.startswith("shows_refs:"):
        uid = int(data.split(":")[1])
        invites = get_invites_count(uid)
        await bot.send_message(chat_id=user.id, text=f"Total invites by you: {invites}")

    elif data.startswith("claim:"):
        uid = int(data.split(":")[1])
        user_row = get_user_by_id(uid)
        if not user_row:
            await bot.send_message(chat_id=user.id, text="Aap pehle /start karein.")
            return

        invites = user_row[4]
        claimed = user_row[6]
        if claimed:
            await bot.send_message(chat_id=user.id, text="Aap pehle hi apna gift code claim kar chukay hain.")
            return

        if invites >= 2:
            current = get_current_code()
            if current:
                code, valid_for, set_at = current
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET claimed=1 WHERE user_id=?", (uid,))
                conn.commit()
                conn.close()
                await bot.send_message(chat_id=user.id, text=f"🎁 Aapka Gift Code: {code}\nValid for: {valid_for} users\nSet at: {set_at}")
            else:
                await bot.send_message(chat_id=user.id, text="Aaj ke liye koi gift code set nahi hai.")
        else:
            remaining = 2 - invites
            await bot.send_message(chat_id=user.id, text=f"Aapko abhi {remaining} aur invites chahiye gift code claim karne ke liye.")

    elif data.startswith("status:"):
        uid = int(data.split(":")[1])
        user_row = get_user_by_id(uid)
        if not user_row:
            await bot.send_message(chat_id=user.id, text="Koi data nahi mila.")
            return
        invites = user_row[4]
        joined = "Yes" if user_row[5] else "No"
        claimed = "Yes" if user_row[6] else "No"
        await bot.send_message(chat_id=user.id, text=f"📊 Status:\nJoined channel: {joined}\nInvites: {invites}\nClaimed: {claimed}")


# Admin commands
def is_admin(uid): return uid == ADMIN_ID


async def setcode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setcode <CODE> <valid_for>")
        return
    code = context.args[0]
    valid_for = int(context.args[1])
    set_code(code, valid_for)
    await update.message.reply_text(f"✅ New code set: {code} valid for {valid_for} users.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE joined_channel=1")
    joined = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE claimed=1")
    claimed = c.fetchone()[0]
    conn.close()
    await update.message.reply_text(f"📈 Stats:\nTotal users: {total}\nJoined: {joined}\nClaimed: {claimed}")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    rows = c.fetchall()
    conn.close()
    fails = 0
    for (uid,) in rows:
        try:
            await bot.send_message(chat_id=uid, text=msg)
        except:
            fails += 1
    await update.message.reply_text(f"Broadcast sent ✅ | Failures: {fails}")


# Application setup
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callback_query_handler))
application.add_handler(CommandHandler("setcode", setcode_cmd))
application.add_handler(CommandHandler("stats", stats_cmd))
application.add_handler(CommandHandler("broadcast", broadcast_cmd))


@app.route("/", methods=["GET"])
def home():
    return "92Pak Bot is Running ✅"


@app.route("/webhook", methods=["POST"])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        await application.process_update(update)
        return "ok"
    else:
        abort(403)


async def set_webhook():
    if WEBHOOK_URL:
        await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
        logger.info(f"Webhook set to {WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    asyncio.run(set_webhook())
    app.run(host="0.0.0.0", port=PORT)
