import os
import logging
from collections import defaultdict
from datetime import datetime, date
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import BadRequest
import asyncio

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
CHANNEL_ID_1 = os.environ.get("CHANNEL_ID_1")  # NUMERIC (-100...)
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")  # @username
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://chat.whatsapp.com/defaultlink")
GIFT_CODE = os.environ.get("GIFT_CODE", "92pak")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

user_data = defaultdict(lambda: {
    "total_invites": 0,
    "available_invites": 0,
    "last_claimed_date": "1970-01-01",
    "channels_verified": False,
    "referrer_tracked": None
})


# --- VERIFY MEMBERSHIP ---
async def check_subscription(bot: Bot, user_id: int, chat_id: str) -> bool:
    try:
        logger.info(f"🔍 Checking membership: user={user_id}, chat_id={chat_id}")
        member = await bot.get_chat_member(chat_id, user_id)
        logger.info(f"✅ Member status: {member.status}")
        return member.status in ['member', 'administrator', 'creator']
    except BadRequest as e:
        logger.warning(f"⚠️ Verification error (BadRequest): {e}")
        return False
    except Exception as e:
        logger.error(f"🚨 Unexpected verification error: {e}")
        return False


# --- KEYBOARDS ---
async def get_main_keyboard(context, user_id):
    if 'BOT_USERNAME' not in context.bot_data:
        bot_info = await context.bot.get_me()
        context.bot_data['BOT_USERNAME'] = bot_info.username
    referral_link = f"https://t.me/{context.bot_data['BOT_USERNAME']}?start={user_id}"
    keyboard = [
        [InlineKeyboardButton("🔗 Reffer Link (Doston Ko Invite Karein)", url=referral_link)],
        [
            InlineKeyboardButton("📊 Total Reffers (Status Dekhein)", callback_data='status'),
            InlineKeyboardButton("🎁 Claim Gift Code", callback_data='claim')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_verification_keyboard():
    telegram_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    keyboard = [
        [InlineKeyboardButton("✅ Telegram Channel Join Karein", url=telegram_link)],
        [InlineKeyboardButton("🌐 WhatsApp Channel Join Karein", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("☑️ Verification Confirm Karein", callback_data='verify_check')]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_entry = user_data[user_id]

    if 'BOT_USERNAME' not in context.bot_data:
        bot_info = await context.bot.get_me()
        context.bot_data['BOT_USERNAME'] = bot_info.username

    # Referral Logic
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        if referrer_id != user_id and user_data_entry["referrer_tracked"] is None:
            referrer_data = user_data[referrer_id]
            referrer_data["total_invites"] += 1
            referrer_data["available_invites"] += 1
            user_data_entry["referrer_tracked"] = referrer_id
            await context.bot.send_message(
                referrer_id,
                f"🎉 Mubarak! Aapke invite link se **{update.effective_user.first_name}** join hua hai.\n"
                f"Aapke paas ab **{referrer_data['available_invites']}** available invites hain."
            )

    if user_data_entry['channels_verified']:
        await send_main_menu(update, context)
    else:
        await send_verification_step(update, context)


async def send_verification_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "**Asslam-o-Alaikum everyone !!**\n"
        "🥳 **WELCOME TO OUR FREE GIFT CODE BOT**\n\n"
        "Zaroori **Verification** karein taake aap aagay badh saken:"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=get_verification_keyboard(),
        parse_mode='Markdown'
    )


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data_entry = user_data[user_id]
    welcome_text = (
        "**KhushAamdeed !!**\n\n"
        "Yahan aapko daily **92Pak** kay Gift Codes milain gay. 🎁\n"
        "Requirments: **2 banday invite** karne zaroori hain!\n\n"
        f"Aapke paas abhi **{user_data_entry['available_invites']}** invites available hain."
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        reply_markup=await get_main_keyboard(context, user_id),
        parse_mode='Markdown'
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = user_data[user_id]

    if query.data == 'verify_check':
        logger.info(f"➡️ VERIFY CHECK started for user {user_id}")
        is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1)

        if is_ch1_joined:
            user['channels_verified'] = True
            logger.info(f"🟢 VERIFICATION SUCCESS for {user_id}")
            message_text = "✅ **Verification Kamyab!** Aapne zaroori channels join kar liye hain. Aagay badhein."
            await query.edit_message_text(message_text, parse_mode='Markdown')
            await asyncio.sleep(1)
            await send_main_menu(update, context)
        else:
            logger.info(f"🔴 VERIFICATION FAILED for {user_id}")
            await query.edit_message_text(
                "❌ **Verification Nakam!** Pehle channel join karein phir dobara try karein.",
                reply_markup=get_verification_keyboard(),
                parse_mode='Markdown'
            )

    elif query.data == 'status':
        invites_needed = 2
        if user["available_invites"] >= invites_needed:
            claim_status = "**Mubarak!** Aap code claim kar sakte hain!"
        else:
            remaining = invites_needed - user["available_invites"]
            claim_status = f"**Agla Code:** Mazeed **{remaining}** invites chahiye."

        status_message = (
            f"📊 **Referral Status**\n"
            f"👥 Total Invites: **{user['total_invites']}**\n"
            f"💰 Available Invites: **{user['available_invites']}**\n\n"
            f"{claim_status}\n({datetime.now().strftime('%H:%M:%S')})"
        )
        await query.edit_message_text(
            status_message,
            reply_markup=await get_main_keyboard(context, user_id),
            parse_mode='Markdown'
        )

    elif query.data == 'claim':
        today_str = date.today().isoformat()
        invites_needed = 2

        if not user['channels_verified']:
            await query.edit_message_text(
                "❌ Pehle verification complete karein.",
                reply_markup=get_verification_keyboard(),
                parse_mode='Markdown'
            )
            return

        if user["last_claimed_date"] == today_str:
            await query.edit_message_text(
                "⏳ Aaj ka code pehle hi claim ho chuka hai."
            )
            return

        if user["available_invites"] < invites_needed:
            remaining = invites_needed - user["available_invites"]
            await query.edit_message_text(
                f"❌ Sirf {user['available_invites']} invites hain. {remaining} aur chahiye."
            )
            return

        user["available_invites"] -= invites_needed
        user["last_claimed_date"] = today_str
        global GIFT_CODE

        message = (
            "🎉 **Mubarak ho!**\n"
            f"🎮 **Aapka Gift Code:** `{GIFT_CODE}`\n\n"
            "Agla code aap kal ya 2 naye invites milne par claim kar sakte hain."
        )
        await query.edit_message_text(message, parse_mode='Markdown')
        await context.bot.send_message(
            ADMIN_ID,
            f"✅ CLAIMED: User {query.from_user.full_name} ({user_id}) ne code claim kar liya."
        )
        await send_main_menu(update, context)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"❌ Error: {context.error}")
    if update and update.effective_user and update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 Error in Bot: {context.error}"
            )
        except:
            pass


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text.startswith('/'):
        await update.message.reply_text("Maaf kijiye, yeh command samajh nahi aayi. /start likhein.")
    else:
        if user_data[update.effective_user.id]['channels_verified']:
            await send_main_menu(update, context)


async def setcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GIFT_CODE
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Aapke paas yeh command istemaal karne ki permission nahi hai.")
        return
    if not context.args:
        await update.message.reply_text(f"❌ Istemaal: `/setcode <NEW_CODE>`. Current: `{GIFT_CODE}`", parse_mode='Markdown')
        return
    new_code = " ".join(context.args)
    GIFT_CODE = new_code
    await update.message.reply_text(f"✅ Naya code set: `{GIFT_CODE}`", parse_mode='Markdown')


def main():
    if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID_1 or not CHANNEL_USERNAME:
        logger.error("❌ Environment variables missing! (BOT_TOKEN, ADMIN_ID, CHANNEL_ID_1, CHANNEL_USERNAME required)")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("setcode", setcode_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    application.add_error_handler(error_handler)

    application.run_polling(poll_interval=1.0)
    logger.info("✅ Bot started successfully.")


if __name__ == "__main__":
    main()
