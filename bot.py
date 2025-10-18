# save as bot.py
import os
import logging
import asyncio
from datetime import date, datetime
from collections import defaultdict

from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest

# -------------------------
# Logging
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# -------------------------
# Env / Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID")) if os.environ.get("ADMIN_ID") else None
CHANNEL_ID_RAW = os.environ.get("CHANNEL_ID")  # must be numeric like -1001234567890
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@YourChannel")
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://chat.whatsapp.com/defaultlink")
GIFT_CODE = os.environ.get("GIFT_CODE", "92pak")

# Validate channel id to int if possible
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW) if CHANNEL_ID_RAW is not None else None
except Exception:
    CHANNEL_ID = None

# In-memory user store (for demonstration)
user_data = defaultdict(lambda: {
    "channels_verified": False,
    "available_invites": 0,
    "total_invites": 0,
    "last_claimed_date": "1970-01-01",
    "referrer": None
})

# -------------------------
# Helper: safe get_chat_member with timeout
async def is_member_of_channel(bot: Bot, user_id: int, chat_id) -> bool:
    """
    Returns True if user is member/admin/creator of chat_id.
    Uses timeout so request doesn't hang forever.
    """
    try:
        # give short timeout so Render logs don't hang; adjust if needed
        coro = bot.get_chat_member(chat_id, user_id)
        member = await asyncio.wait_for(coro, timeout=4.0)
        logger.info(f"Checked membership user={user_id} chat={chat_id} -> {member.status}")
        return member.status in ("member", "administrator", "creator")
    except asyncio.TimeoutError:
        logger.warning("Timeout while checking membership (Telegram slow).")
        return False
    except BadRequest as e:
        # common reasons: chat not found, user not found, bot not admin/allowed
        logger.warning(f"BadRequest when checking membership: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking membership: {e}")
        return False

# -------------------------
# Keyboards
def verification_keyboard():
    tg_link = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    kb = [
        [InlineKeyboardButton("✅ Join Telegram Channel", url=tg_link)],
        [InlineKeyboardButton("🌐 Join WhatsApp (Link)", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("☑️ I have joined — Verify", callback_data="verify_check")],
    ]
    return InlineKeyboardMarkup(kb)

def main_menu_keyboard(bot_username: str, user_id: int):
    ref = f"https://t.me/{bot_username}?start={user_id}"
    kb = [
        [InlineKeyboardButton("🔗 Invite Friends (Referral)", url=ref)],
        [InlineKeyboardButton("🎁 Claim Gift Code", callback_data="claim")],
    ]
    return InlineKeyboardMarkup(kb)

# -------------------------
# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    data = user_data[uid]

    # track bot username for referral
    if "bot_username" not in context.bot_data:
        me = await context.bot.get_me()
        context.bot_data["bot_username"] = me.username

    # handle start with referral (e.g., /start 12345)
    if context.args and context.args[0].isdigit():
        refid = int(context.args[0])
        if refid != uid and data["referrer"] is None:
            user_data[refid]["total_invites"] += 1
            user_data[refid]["available_invites"] += 1
            data["referrer"] = refid
            try:
                await context.bot.send_message(
                    chat_id=refid,
                    text=f"🎉 A new user joined using your link! Total available invites: {user_data[refid]['available_invites']}"
                )
            except Exception as e:
                logger.warning(f"Couldn't notify referrer {refid}: {e}")

    # If verified, send main menu; else send verification prompt
    if data["channels_verified"]:
        await send_main_menu(update, context)
    else:
        await send_verification_prompt(update, context)

async def send_verification_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Assalam-o-Alaikum!\n\n"
        "Welcome — pehle Telegram channel join karain, phir Verify button dabayein.\n\n"
        "➡️ Only Telegram verification required. WhatsApp link bhi nichay hai."
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=verification_keyboard(),
        parse_mode="Markdown"
    )

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bot_username = context.bot_data.get("bot_username", (await context.bot.get_me()).username)
    kb = main_menu_keyboard(bot_username, uid)
    msg = (
        f"Khushamdeed!\n\n"
        f"Aap verified hain. Available invites: {user_data[uid]['available_invites']}\n\n"
        "Use the buttons below."
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=kb)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = user_data[uid]

    if query.data == "verify_check":
        # Basic pre-check
        if CHANNEL_ID is None:
            await query.edit_message_text(
                "❌ Bot configuration error: CHANNEL_ID invalid. Admin ko notify karo."
            )
            logger.error("CHANNEL_ID is not set correctly (must be numeric -100...)")
            return

        # Check membership with timeout
        joined = await is_member_of_channel(context.bot, uid, CHANNEL_ID)
        if joined:
            data["channels_verified"] = True
            logger.info(f"User {uid} verified successfully.")
            await query.edit_message_text("✅ Verification successful! Aap ab access le sakte hain.")
            # small pause then send menu
            await asyncio.sleep(0.8)
            await send_main_menu(update, context)
        else:
            await query.edit_message_text(
                "❌ Verification failed. Ensure you have joined the Telegram channel (and use the same Telegram account). Agar bot channel ka admin nahi hai to admin check karein.",
                reply_markup=verification_keyboard()
            )

    elif query.data == "claim":
        today = date.today().isoformat()
        if not data["channels_verified"]:
            await query.edit_message_text("❌ Pehle verification complete karein.", reply_markup=verification_keyboard())
            return
        if data["available_invites"] < 2:
            await query.edit_message_text(f"❌ Aapko 2 invites chahiye. Abhi: {data['available_invites']}")
            return
        if data["last_claimed_date"] == today:
            await query.edit_message_text("⏳ Aaj ka code pehle hi claim ho chuka hai.")
            return

        data["available_invites"] -= 2
        data["last_claimed_date"] = today
        # send code privately
        await query.edit_message_text(f"🎉 Aapka code: `{GIFT_CODE}`\n\nAgla code kal ya jab 2 invites jama hon.")
        # notify admin
        try:
            await context.bot.send_message(ADMIN_ID, f"User {query.from_user.full_name} ({uid}) claimed today's code.")
        except Exception as e:
            logger.warning(f"Could not notify admin: {e}")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # respond to unknown commands
    if update.message and update.message.text and update.message.text.startswith('/'):
        await update.message.reply_text("Unknown command. Use /start to open menu.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")
    # notify admin quietly
    try:
        if ADMIN_ID:
            await context.bot.send_message(ADMIN_ID, f"Bot error: {context.error}")
    except Exception:
        pass

# -------------------------
# Main
def main():
    # config checks before starting
    if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID_RAW or not CHANNEL_USERNAME:
        logger.error("Missing required environment variables: BOT_TOKEN, ADMIN_ID, CHANNEL_ID, CHANNEL_USERNAME")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(error_handler)

    logger.info("Starting bot (polling mode).")
    app.run_polling(poll_interval=1.0)

if __name__ == "__main__":
    main()
