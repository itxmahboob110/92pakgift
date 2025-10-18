import os
import logging
import json
from datetime import datetime, date
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- Configuration (Environment Variables se load hongi) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
CHANNEL_ID_1 = os.environ.get("CHANNEL_ID_1") # Telegram Channel ID/Username
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://chat.whatsapp.com/defaultlink") # WhatsApp Link
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))
GIFT_CODE = os.environ.get("GIFT_CODE", "92pak")

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Data Handling (Pichla Non-persistent Data System) ---
user_data = {}
# ... (load_data and save_data functions remain the same as before) ...
# Note: For simplicity and continuity, keeping the non-persistent data functions.
def load_data():
    global user_data, GIFT_CODE
    try:
        if os.path.exists("data.json"):
            with open("data.json", "r") as f:
                data = json.load(f)
                user_data = data.get("user_data", {})
                GIFT_CODE = data.get("GIFT_CODE", os.environ.get("GIFT_CODE", "92pak"))
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def save_data():
    global user_data, GIFT_CODE
    try:
        with open("data.json", "w") as f:
            json.dump({"user_data": user_data, "GIFT_CODE": GIFT_CODE}, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user(user_id):
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "total_invites": 0,
            "available_invites": 0,
            "last_claimed_date": "1970-01-01",
            "channels_verified": False, # New field for initial verification status
        }
    return user_data[user_id_str]

async def check_subscription(bot: Bot, user_id: int, chat_id: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

# --- Custom Keyboards ---

async def get_main_keyboard(user_id):
    """Generates the main command buttons."""
    referral_link = f"https://t.me/@{os.environ.get('BOT_USERNAME')}?start={user_id}"
    
    keyboard = [
        [InlineKeyboardButton("🔗 Reffer Link (Doston Ko Invite Karein)", url=referral_link)],
        [
            InlineKeyboardButton("📊 Total Reffers (Status Dekhein)", callback_data='status'),
            InlineKeyboardButton("🎁 Claim Gift Code", callback_data='claim')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_verification_keyboard():
    """Generates the initial channel verification buttons."""
    keyboard = [
        [InlineKeyboardButton("✅ Telegram Channel Join Karein", url=f"https://t.me/{CHANNEL_ID_1.replace('@', '')}")],
        [InlineKeyboardButton("🌐 WhatsApp Channel Join Karein", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("☑️ Verification Confirm Karein", callback_data='verify_check')]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command, registers user, and tracks referrals."""
    user_id = update.effective_user.id
    user_data_entry = get_user(user_id)
    
    # Set bot username for referral link in the first run if not set
    if 'BOT_USERNAME' not in os.environ:
        bot_info = await context.bot.get_me()
        os.environ['BOT_USERNAME'] = bot_info.username

    # Referral Tracking Logic
    if context.args and context.args[0].isdigit():
        referrer_id = context.args[0]
        referrer_id_str = str(referrer_id)
        if referrer_id_str != str(user_id) and user_data_entry.get("referrer_tracked") is None:
            referrer_data = get_user(referrer_id)
            referrer_data["total_invites"] += 1
            referrer_data["available_invites"] += 1
            user_data_entry["referrer_tracked"] = referrer_id
            await context.bot.send_message(
                referrer_id, 
                f"🎉 Mubarak! Aapke invite link se **{update.effective_user.first_name}** join hua hai. Ab aapke paas **{referrer_data['available_invites']}** available invites hain."
            )
            save_data()
            
    if user_data_entry['channels_verified']:
        await send_main_menu(update, context)
    else:
        await send_verification_step(update, context)


async def send_verification_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the initial verification step with buttons."""
    text = (
        "**Asslam-o-Alaikum everyone !!**\n"
        "🥳 **WELCOME TO OUR FREE GIFT CODE BOT**\n\n"
        "Peelay Zaroori **Verification** Karein taake aap aagay badh saken:"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=get_verification_keyboard(),
        parse_mode='Markdown'
    )


async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the welcome message and main menu keyboard."""
    user_id = update.effective_user.id
    user_data_entry = get_user(user_id)
    
    welcome_text = (
        "**KhushAamdeed !!**\n\n"
        "Aapko yahan pr daily **92Pak** kay Giftcodes Mila Karen Gay.🎁\n"
        "Requirments Yeh hai Keh Aapko **2 Bandy Invite** Karne Hoon Gay !!\n\n"
        f"Aapkay paas abhi **{user_data_entry['available_invites']}** invites available hain."
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        reply_markup=await get_main_keyboard(user_id),
        parse_mode='Markdown'
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if query.data == 'verify_check':
        # Channel Verification Logic
        is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1)
        
        # NOTE: WhatsApp verification is manual/assumed. We'll proceed if TG is joined.
        # Agar aap doosra TG channel add karen to yahan logic badal dein.
        
        if is_ch1_joined:
            user['channels_verified'] = True
            save_data()
            await query.edit_message_text(
                "✅ **Verification Kamyab!** Ab aap Gift Code haasil kar sakte hain. Aagay badhein.",
                parse_mode='Markdown'
            )
            await send_main_menu(update, context)
        else:
            await query.edit_message_text(
                "❌ **Verification Nakam!** Aapne Telegram Channel join nahi kiya hai ya bot ko dobara start/verify karna hoga.",
                reply_markup=get_verification_keyboard(),
                parse_mode='Markdown'
            )

    elif query.data == 'status':
        # Status Logic (using existing logic but formatted better)
        is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1)
        
        claim_status = ""
        invites_needed = 2
        
        if user["available_invites"] >= invites_needed:
             claim_status = "**Mubarak!** Aap code claim karne ke liye tayyar hain. '🎁 Claim Gift Code' button dabayein."
        else:
            remaining = invites_needed - user["available_invites"]
            claim_status = f"**Agla Code:** Aapko mazeed **{remaining}** invites ki zaroorat hai."

        status_message = (
            f"📊 **Aapka Referral Status**\n"
            "-----------------------------------\n"
            f"👥 Total Invites: **{user['total_invites']}**\n"
            f"💰 Available Invites for Claim: **{user['available_invites']}**\n\n"
            f"**Claim Status:** {claim_status}\n"
            "-----------------------------------\n"
            f"({datetime.now().strftime('%H:%M:%S')})"
        )
        
        await query.edit_message_text(
            status_message,
            reply_markup=await get_main_keyboard(user_id),
            parse_mode='Markdown'
        )

    elif query.data == 'claim':
        # Claim Logic (using existing logic)
        today_str = date.today().isoformat()
        invites_needed = 2

        if not user['channels_verified']:
             await query.edit_message_text(
                "❌ **Pehle Verification:** Code claim karne se pehle zaroori channels join aur verify karein.",
                reply_markup=get_verification_keyboard(),
                parse_mode='Markdown'
            )
             return

        if user["last_claimed_date"] == today_str:
            await query.edit_message_text(
                "⏳ **Ruk Jayiye:** Aap aaj ka code pehle hi claim kar chuke hain. Aap rozana sirf aik code claim kar sakte hain."
            )
            return

        if user["available_invites"] < invites_needed:
            remaining = invites_needed - user["available_invites"]
            await query.edit_message_text(
                f"❌ **Na-mukammal:** Aapke paas abhi sirf {user['available_invites']} available invites hain. Mazeed **{remaining}** doston ko invite karein."
            )
            return

        # Successful Claim
        user["available_invites"] -= invites_needed
        user["last_claimed_date"] = today_str
        global GIFT_CODE
        
        message = (
            "🎉 **Mubarak ho! Aapka Gift Code!** 🎉\n\n"
            f"Aapne kamyabi se **{invites_needed}** invites istemaal kar ke code claim kar liya hai.\n\n"
            f"🎮 **Aapka Gift Code (Daily Code):** `{GIFT_CODE}`\n\n"
            "--------------------------\n"
            f"🎁 **Agla Code:** Agla code aap kal ({user['available_invites']} invites baqi hain) ya jab bhi aapke paas **2 naye invites** jama hon, tab claim kar sakte hain."
        )
        await query.edit_message_text(message, parse_mode='Markdown')
        await context.bot.send_message(
            ADMIN_ID,
            f"✅ CLAIMED: User {query.from_user.full_name} ({user_id}) ne aaj ka code claim kar liya. Remaining invites: {user['available_invites']}"
        )
        save_data()
        await send_main_menu(update, context) # Send back to main menu


# ... (error_handler and unknown remain the same) ...
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update '%s' caused error '%s'", update, context.error)
    if update and update.effective_user and update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 Error in Bot: Update {update.update_id} caused error: {context.error}"
            )
        except:
             pass

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text.startswith('/'):
        await update.message.reply_text("Maaf kijiye, main is command ko nahi samajh paya. Menu ke liye /start type karein.")
    else:
         # Handle unrecognised messages by sending to main menu if verified
         user = get_user(update.effective_user.id)
         if user['channels_verified']:
             await send_main_menu(update, context)


async def setcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (setcode_command remains the same) ...
    global GIFT_CODE
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Aapke paas yeh command istemaal karne ki permission nahi hai.")
        return

    if not context.args:
        await update.message.reply_text(f"❌ Istemaal: `/setcode <NEW_CODE>`. Current code hai: `{GIFT_CODE}`")
        return

    new_code = " ".join(context.args)
    GIFT_CODE = new_code
    save_data()
    
    await update.message.reply_text(
        f"✅ **Success!** Naya Daily Gift Code set kar diya gaya hai: `{GIFT_CODE}`"
    )

def main() -> None:
    if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID_1 or not WEBHOOK_URL:
        logger.error("❌ Zaroori Environment Variables set nahi hain. Kripya .env file ya Render settings check karein. WHATSAPP_LINK optional hai.")
        return
        
    load_data()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("setcode", setcode_command))
    application.add_handler(filters.UpdateType.CALLBACK_QUERY, handle_callback_query)
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown)) # Handles general text messages
    
    application.add_error_handler(error_handler)

    # Run with Webhook for Render
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL,
    )
    logger.info("Bot started successfully in Webhook mode (Render compatible).")

if __name__ == "__main__":
    main()
