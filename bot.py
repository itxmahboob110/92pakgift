# bot.py
import os
import time
import json
import logging
from threading import Thread
from flask import Flask, request
import telebot

# ------------- Config / Logging -------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # required
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "").replace("https://t.me/", "").lstrip("@")
WHATSAPP_LINK = os.getenv("WHATSAPP_LINK", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DAILY_CODE = os.getenv("DAILY_CODE", "92PAK-GIFT")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")  # Render provides this automatically

if not TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN not set. Add it in Render environment variables.")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")

if not CHANNEL_USERNAME:
    logger.critical("CHANNEL_USERNAME not set.")
    raise SystemExit("Missing CHANNEL_USERNAME")

if not WHATSAPP_LINK:
    logger.critical("WHATSAPP_LINK not set.")
    raise SystemExit("Missing WHATSAPP_LINK")

if ADMIN_ID == 0:
    logger.critical("ADMIN_ID not set or invalid.")
    raise SystemExit("Missing ADMIN_ID")

# ------------- Data storage (simple JSON) -------------
DB_FILE = "data.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "all_users": []}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.exception("Failed to load DB file, starting fresh.")
        return {"users": {}, "all_users": []}

def save_data(d):
    try:
        with open(DB_FILE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        logger.exception("Failed to save DB file.")

db = load_data()

# ensure structure
db.setdefault("users", {})
db.setdefault("all_users", [])

# ------------- Bot init and Flask -------------
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/{TOKEN}"
if WEBHOOK_HOST:
    WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}"
    WEBHOOK_URL = f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}"
else:
    WEBHOOK_URL = None

# ------------- Utility helpers -------------
def ensure_user_record(uid: int):
    s = str(uid)
    if s not in db["users"]:
        db["users"][s] = {
            "total_referrals": 0,
            "used_referrals": 0,
            "last_claim": None
        }
        if s not in db["all_users"]:
            db["all_users"].append(s)
        save_data(db)

def get_available_referrals(uid: int):
    rec = db["users"].get(str(uid), {"total_referrals": 0, "used_referrals": 0})
    return rec["total_referrals"] - rec["used_referrals"]

def send_admin_message(text: str):
    try:
        bot.send_message(ADMIN_ID, text)
    except Exception:
        logger.exception("Failed to send admin message.")

# ------------- Telegram handlers (logic) -------------
@bot.message_handler(commands=["start"])
def handle_start(message):
    uid = message.from_user.id
    text_parts = message.text.split()
    ref = None
    if len(text_parts) > 1:
        ref = text_parts[1]

    ensure_user_record(uid)

    # track referral (if exists and not self-ref)
    if ref and ref != str(uid):
        if ref not in db["users"]:
            db["users"][ref] = {"total_referrals": 1, "used_referrals": 0, "last_claim": None}
            if ref not in db["all_users"]:
                db["all_users"].append(ref)
        else:
            db["users"][ref]["total_referrals"] += 1
        save_data(db)
        logger.info(f"Referral: user {uid} referred by {ref}")

    # reply with invite + buttons
    invite_link = f"https://t.me/{bot.get_me().username}?start={uid}"
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("📢 Join Telegram Channel", url=f"https://t.me/{CHANNEL_USERNAME}"))
    keyboard.add(telebot.types.InlineKeyboardButton("💬 Join WhatsApp Channel", url=WHATSAPP_LINK))
    keyboard.add(telebot.types.InlineKeyboardButton("✅ Verify & Continue", callback_data="verify"))

    bot.send_message(uid,
                     f"👋 Hey {message.from_user.first_name}!\n\n"
                     f"Join both channels then click Verify to continue.\n\n"
                     f"Your invite link:\n`{invite_link}`",
                     reply_markup=keyboard,
                     parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "verify")
def handle_verify(call):
    user_id = call.from_user.id
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        status = member.status
        if status not in ["member", "administrator", "creator"]:
            bot.answer_callback_query(call.id, "❌ You haven't joined the Telegram channel yet!", show_alert=True)
            return
    except Exception as e:
        logger.exception("Channel verification failed")
        bot.answer_callback_query(call.id, "⚠️ Channel verification failed. Make sure the channel exists and bot is added as admin.", show_alert=True)
        return

    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("✅ I have joined WhatsApp", callback_data="whatsapp_done"))
    bot.send_message(user_id, "✅ Telegram verified. Now confirm WhatsApp join:", reply_markup=kb)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "whatsapp_done")
def handle_whatsapp_done(call):
    user_id = call.from_user.id
    ensure_user_record(user_id)
    bot.send_message(user_id, "🎉 Verification complete! Invite 2 friends to claim the daily code. Use /status and /claim to check.")
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=["status"])
def handle_status(message):
    uid = message.from_user.id
    ensure_user_record(uid)
    rec = db["users"][str(uid)]
    total = rec["total_referrals"]
    used = rec["used_referrals"]
    available = total - used
    bot.send_message(uid,
                     f"💎 Your Referral Dashboard 💎\n\n"
                     f"👤 Total Invites: {total}\n"
                     f"🎁 Codes Claimed (used referrals): {used}\n"
                     f"🔓 Available Referrals: {available}\n"
                     f"📅 Last Claim: {rec.get('last_claim') or '—'}\n\n"
                     f"Use /claim to redeem (2 referrals per code).")

@bot.message_handler(commands=["claim"])
def handle_claim(message):
    uid = message.from_user.id
    ensure_user_record(uid)
    rec = db["users"][str(uid)]
    available = rec["total_referrals"] - rec["used_referrals"]
    today = time.strftime("%Y-%m-%d")

    if available < 2:
        bot.send_message(uid, "👥 You need at least 2 available referrals to claim a code.")
        return

    if rec.get("last_claim") == today:
        bot.send_message(uid, "✅ You've already claimed today's code. Come back tomorrow.")
        return

    # consume referrals
    rec["used_referrals"] += 2
    rec["last_claim"] = today
    save_data(db)

    bot.send_message(uid, f"🎉 Congrats! Your daily code:\n`{DAILY_CODE}`", parse_mode="Markdown")

# ------------- Admin commands -------------
@bot.message_handler(commands=["setcode"])
def handle_setcode(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ You are not authorized.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /setcode NEWCODE")
        return
    global DAILY_CODE
    DAILY_CODE = parts[1].strip()
    bot.reply_to(message, f"✅ Daily code updated to: `{DAILY_CODE}`", parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
def handle_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    total_users = len(db["all_users"])
    total_referrals = sum(u["total_referrals"] for u in db["users"].values())
    total_claims = sum(u.get("used_referrals",0)//2 for u in db["users"].values())
    bot.reply_to(message,
                 f"📊 Bot Stats\n\n👥 Users: {total_users}\n🔗 Total Referrals: {total_referrals}\n🎁 Total Claims: {total_claims}")

@bot.message_handler(commands=["broadcast"])
def handle_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /broadcast Your message here")
        return
    text = parts[1]
    sent = 0
    # rate limit: 30 msgs / sec -> we'll send with small sleep to be safe
    for uid in list(db["all_users"]):
        try:
            bot.send_message(int(uid), text)
            sent += 1
            time.sleep(0.075)  # ~13 msgs/sec safe
        except Exception:
            continue
    bot.reply_to(message, f"✅ Broadcast complete. Attempted: {len(db['all_users'])}, Sent: {sent}")

# ------------- Webhook endpoints for Render -------------
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_post():
    # Telegram will POST updates here
    try:
        json_str = request.get_data().decode("utf-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception:
        logger.exception("Failed to process incoming webhook update.")
    return "", 200

@app.route("/", methods=["GET"])
def set_webhook():
    # Called once to set the webhook on startup (Render will hit /)
    if not WEBHOOK_URL:
        return "RENDER_EXTERNAL_URL not set. Set it in Render env vars.", 500

    try:
        bot.remove_webhook()
    except Exception:
        pass

    ok = bot.set_webhook(url=WEBHOOK_URL)
    if ok:
        logger.info(f"Webhook set to: {WEBHOOK_URL}")
        return "Webhook set successfully ✅", 200
    else:
        logger.error("Failed to set webhook.")
        return "Failed to set webhook", 500

# ------------- Run app -------------
if __name__ == "__main__":
    # ensure webhook removed (prevents conflict if previous polling instance existed)
    try:
        bot.remove_webhook()
    except Exception:
        pass

    logger.info("Starting Flask app (Render webhook mode)...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
