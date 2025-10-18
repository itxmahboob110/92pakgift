import os
import sqlite3
import hashlib
import logging
from flask import Flask, request, abort
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
)
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram import __version__ as ptb_version
import requests

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME")  # without @
CHANNEL_ID = os.environ.get("CHANNEL_ID")    # e.g. @YourChannel or -1001234567890
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://wa.me/")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://your-service.onrender.com/webhook
PORT = int(os.environ.get("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable required")

bot = Bot(BOT_TOKEN)
app = Flask(__name__)

# --- Database setup ---
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

# --- Helpers ---
def user_exists(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def register_user(user):
    # user is telegram.User
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not user_exists(user.id):
        refer_code = generate_ref_code(user.id)
        c.execute("INSERT INTO users (user_id, username, first_name, refer_code) VALUES (?, ?, ?, ?)",
                  (user.id, user.username or "", user.first_name or "", refer_code))
        conn.commit()
    else:
        # update username/first_name
        c.execute("UPDATE users SET username=?, first_name=?, last_seen=CURRENT_TIMESTAMP WHERE user_id=?",
                  (user.username or "", user.first_name or "", user.id))
        conn.commit()
    conn.close()

def generate_ref_code(user_id):
    # deterministic unique code
    raw = f"REF{user_id}"
    # optionally hash shorter
    h = hashlib.sha1(raw.encode()).hexdigest()[:8].upper()
    return f"R{h}"

def set_referred(ref_code, referee_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # find referrer user
    c.execute("SELECT user_id FROM users WHERE refer_code=?", (ref_code,))
    row = c.fetchone()
    if row:
        referrer_id = row[0]
        # record referral if not exist
        c.execute("SELECT 1 FROM referrals WHERE referrer_code=? AND referee_id=?", (ref_code, referee_id))
        if not c.fetchone():
            c.execute("INSERT INTO referrals (referrer_code, referee_id) VALUES (?, ?)", (ref_code, referee_id))
            # increment invites for referrer
            c.execute("UPDATE users SET invites = invites + 1 WHERE user_id=?", (referrer_id,))
            # mark referee's referred_by
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
    c.execute("SELECT user_id, username, first_name, refer_code, invites, joined_channel, claimed FROM users WHERE user_id=?", (user_id,))
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

# --- Telegram interaction helpers ---
def make_start_keyboard(user):
    kb = [
        [InlineKeyboardButton("Join Telegram Channel", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton("Join WhatsApp Channel", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("Verify", callback_data=f"verify:{user.id}")]
    ]
    return InlineKeyboardMarkup(kb)

def make_after_verify_keyboard(user_id):
    user = get_user_by_id(user_id)
    refer_code = user[3] if user else generate_ref_code(user_id)
    # Referral link
    ref_link = f"https://t.me/{BOT_USERNAME}?start={refer_code}"
    kb = [
        [
            InlineKeyboardButton(f"Refers ✅ ({get_invites_count(user_id)})", callback_data=f"shows_refs:{user_id}"),
            InlineKeyboardButton("Claim", callback_data=f"claim:{user_id}")
        ],
        [InlineKeyboardButton("Status", callback_data=f"status:{user_id}")],
        [InlineKeyboardButton("Share Referral Link", url=ref_link)]
    ]
    return InlineKeyboardMarkup(kb)

# --- Flask route for webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return "OK"
    else:
        abort(403)

# --- Dispatcher and handlers ---
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# /start handler
def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    register_user(user)

    # handle start payload (referral)
    args = context.args
    if args:
        ref_code = args[0]
        # If URL encodes like REF..., accept both R... and raw.
        logger.info(f"User {user.id} started with payload {ref_code}")
        set_referred(ref_code, user.id)

    # Send welcome message (bold welcome)
    text = ("Assalam O Alaikum, Umeed Karta Hoon keh Aap Khairiyat Se Hon Gay\n\n"
            "<b>Welcome To Our 92Pak Free Gift Code Bot</b>\n\n"
            "Neechay diye gaye buttons se channel join karo aur verify karo.")
    keyboard = make_start_keyboard(user)
    message.reply_html(text, reply_markup=keyboard)

# callback query handler for verify, claim, status, shows_refs
def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user
    query.answer()

    if data.startswith("verify:"):
        # verify channel membership
        target_user_id = int(data.split(":",1)[1])
        # check whether the user clicking is same as target OR allow others (but safer to use same)
        if user.id != target_user_id:
            query.edit_message_text("Please press Verify in your own chat using /start.")
            return

        try:
            # Check membership status
            res = bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
            status = res.status  # "member", "left", "kicked", "administrator", "creator"
            logger.info(f"Channel membership status for {user.id}: {status}")
            if status in ("member", "creator", "administrator"):
                # mark joined_channel
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET joined_channel=1 WHERE user_id=?", (user.id,))
                conn.commit()
                conn.close()

                # send after-verify interface
                text = ("KhushAmdeed !!\n\n"
                        "92Pak Free Gift Code Bot jo aapko Daily Free GiftCodes Provide Karta Hai.\n"
                        "But aapko daily 2 members invite karne honge gift code kay liye.")
                keyboard = make_after_verify_keyboard(user.id)
                query.edit_message_text(text, reply_markup=keyboard)
            else:
                query.edit_message_text("Aap abhi channel join nahi karay. Pehlay channel join karein phir Verify karein.")
        except Exception as e:
            logger.exception("Error checking chat member")
            query.edit_message_text("Verification mein error aaya. Ensure bot is member of the channel and try again.")

    elif data.startswith("shows_refs:"):
        uid = int(data.split(":",1)[1])
        invites = get_invites_count(uid)
        bot.send_message(chat_id=user.id, text=f"Total invites by you: {invites}")

    elif data.startswith("claim:"):
        uid = int(data.split(":",1)[1])
        user_row = get_user_by_id(uid)
        if not user_row:
            bot.send_message(chat_id=user.id, text="Aap pehle /start karein.")
            return
        invites = user_row[4]
        claimed = user_row[6]
        if claimed:
            bot.send_message(chat_id=user.id, text="Aap pehle hi apna gift code claim kar chukay hain.")
            return
        if invites >= 2:
            # give code if available
            current = get_current_code()
            if current:
                code, valid_for, set_at = current
                # mark user as claimed
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET claimed=1 WHERE user_id=?", (uid,))
                # decrement valid_for if tracking usage
                conn.commit()
                conn.close()
                bot.send_message(chat_id=user.id, text=f"Congrats! Aapka gift code: {code}\nValid for: {valid_for} users (set on {set_at})")
            else:
                bot.send_message(chat_id=user.id, text="Aaj ke liye koi gift code set nahi hai. Admin se rabta karein.")
        else:
            remaining = 2 - invites
            bot.send_message(chat_id=user.id, text=f"Aapko abhi {remaining} aur invites chahiye gift code claim karne ke liye.")

    elif data.startswith("status:"):
        uid = int(data.split(":",1)[1])
        user_row = get_user_by_id(uid)
        if not user_row:
            bot.send_message(chat_id=user.id, text="Koi data nahi mila.")
            return
        invites = user_row[4]
        joined = "Yes" if user_row[5] else "No"
        claimed = "Yes" if user_row[6] else "No"
        bot.send_message(chat_id=user.id, text=f"Status:\nJoined channel: {joined}\nInvites: {invites}\nClaimed: {claimed}")

# Admin commands
def is_admin(user_id):
    return user_id == ADMIN_ID

def setcode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        update.message.reply_text("Unauthorized.")
        return
    args = context.args
    if len(args) < 2:
        update.message.reply_text("Usage: /setcode <CODE> <valid_for_count>")
        return
    code = args[0]
    try:
        valid_for = int(args[1])
    except:
        update.message.reply_text("valid_for must be integer.")
        return
    set_code(code, valid_for)
    update.message.reply_text(f"New code set: {code} valid for {valid_for} users.")

def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        update.message.reply_text("Unauthorized.")
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
    update.message.reply_text(f"Stats:\nTotal users started: {total}\nJoined channel: {joined}\nCodes claimed: {claimed}")

def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        update.message.reply_text("Unauthorized.")
        return
    # message after command
    if context.args:
        text = " ".join(context.args)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        rows = c.fetchall()
        conn.close()
        failures = 0
        for (uid,) in rows:
            try:
                bot.send_message(chat_id=uid, text=text)
            except Exception as e:
                failures += 1
        update.message.reply_text(f"Broadcast sent. Failures: {failures}")
    else:
        update.message.reply_text("Usage: /broadcast <message>")

# register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(callback_query_handler))
dispatcher.add_handler(CommandHandler("setcode", setcode_cmd))
dispatcher.add_handler(CommandHandler("stats", stats_cmd))
dispatcher.add_handler(CommandHandler("broadcast", broadcast_cmd))

# optional ping
@app.route("/", methods=["GET"])
def index():
    return "92Pak Bot is running."

# --- On startup set webhook if WEBHOOK_URL provided ---
def set_webhook():
    if WEBHOOK_URL:
        url = WEBHOOK_URL
        try:
            bot.set_webhook(url)
            logger.info(f"Webhook set to {url}")
        except Exception as e:
            logger.exception("Failed to set webhook")

if __name__ == "__main__":
    # only when running directly (Render will run via gunicorn)
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
