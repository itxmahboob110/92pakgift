import os
import logging
import json
from datetime import datetime, date
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.error import BadRequest
from collections import defaultdict # Naya import for better data handling

# --- Configuration (Environment Variables se load hongi) ---
# Naye code mein Data store karne ke liye variables ki zaroorat nahin
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
# CHANNEL_ID_1 ab NUMERICAL ID (-100...) for VERIFICATION
CHANNEL_ID_1 = os.environ.get("CHANNEL_ID_1") 
# CHANNEL_USERNAME ab USERNAME (@...) for BUTTON LINK
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME") 
WHATSAPP_LINK = os.environ.get("WHATSAPP_LINK", "https://chat.whatsapp.com/defaultlink") 

# Initial Gift Code
GIFT_CODE = os.environ.get("GIFT_CODE", "92pak")

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Data Store (In-Memory Dictionary) ---
# NOTE: Render restart hone par data loss hoga. Yeh sirf testing ke liye hai.
user_data = defaultdict(lambda: {
    "total_invites": 0,
    "available_invites": 0,
    "last_claimed_date": "1970-01-01",
    "channels_verified": False,
    "referrer_tracked": None # Track if a referral has been credited
})

# --- CORE VERIFICATION FUNCTION (ROBUST) ---
async def check_subscription(bot: Bot, user_id: int, chat_id: str) -> bool:
    """Checks if the user is a member of the given channel."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    
    except BadRequest as e:
        error_msg = str(e).lower()
        if 'user not found' in error_msg or 'user not participant' in error_msg or 'chat not found' in error_msg:
            logger.warning(f"⚠️ VERIFICATION FAILED (User/Chat issue) for {user_id} in {chat_id}: {e}")
            return False
        
        logger.error(f"🚨 CRITICAL BADREQUEST ERROR: {e}")
        return False
        
    except Exception as e:
        logger.error(f"🚨 UNEXPECTED ERROR during verification for {user_id}: {e}")
        return False
        
# --- Custom Keyboards ---
async def get_main_keyboard(context, user_id):
    """Generates the main command buttons."""
    # Bot username is needed for referral link
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
    """Generates the initial channel verification buttons."""
    # CHANNEL_USERNAME ka istemaal
    telegram_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}" 
    
    keyboard = [
        [InlineKeyboardButton("✅ Telegram Channel Join Karein", url=telegram_link)],
        [InlineKeyboardButton("🌐 WhatsApp Channel Join Karein", url=WHATSAPP_LINK)], 
        [InlineKeyboardButton("☑️ Verification Confirm Karein", callback_data='verify_check')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command, registers user, and tracks referrals."""
    user_id = update.effective_user.id
    user_data_entry = user_data[user_id] # Fetch user data
    
    # Store bot username in context.bot_data (safer than os.environ)
    if 'BOT_USERNAME' not in context.bot_data:
        bot_info = await context.bot.get_me()
        context.bot_data['BOT_USERNAME'] = bot_info.username

    # Referral Tracking Logic
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
        
        if referrer_id != user_id and user_data_entry["referrer_tracked"] is None:
            referrer_data = user_data[referrer_id]
            referrer_data["total_invites"] += 1
            referrer_data["available_invites"] += 1
            user_data_entry["referrer_tracked"] = referrer_id
            
            await context.bot.send_message(
                referrer_id, 
                f"🎉 Mubarak! Aapke invite link se **{update.effective_user.first_name}** join hua hai. Ab aapke paas **{referrer_data['available_invites']}** available invites hain."
            )
            
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
    user_data_entry = user_data[user_id]
    
    welcome_text = (
        "**KhushAamdeed !!**\n\n"
        "Aapko yahan pr daily **92Pak** kay Giftcodes Mila Karen Gay.🎁\n"
        "Requirments Yeh hai Keh Aapko **2 Bandy Invite** Karne Hoon Gay !!\n\n"
        f"Aapkay paas abhi **{user_data_entry['available_invites']}** invites available hain."
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_text,
        reply_markup=await get_main_keyboard(context, user_id),
        parse_mode='Markdown'
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles button clicks."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = user_data[user_id]
    
    # 🚨 FIX 1: If/elif structure theek ki gayi hai.
    # Verification check hamesha 'if' se shuru hona chahiye.
    if query.data == 'verify_check':
        # Final Verification Logic with Safety Override
        logger.info(f"➡️ VERIFY CHECK initiated by user {user_id}")
        is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1) 
        
        # Safety Override: Verification hamesha grant ho jayegi for testing
        user['channels_verified'] = True 
        
        if is_ch1_joined:
            # Agar API call kamyab ho to yeh message milega
            logger.info(f"🟢 VERIFICATION SUCCESS for user {user_id}")
            message_text = "✅ **Verification Kamyab!** Aapne zaroori channels join kar liye hain. Aagay badhein."
        else:
            # Agar API call fail ho to yeh message milega (Bot ab stuck nahi hoga)
            logger.info(f"🔴 VERIFICATION FAILED by API for user {user_id} but granting access for testing.")
            message_text = "⚠️ **Verification Nakam!** (Lekin aap aagay badh sakte hain) Zaroor check karein ke aapne channel join kiya hai. Aagay badhein."

        await query.edit_message_text(
            message_text,
            parse_mode='Markdown'
        )
        
        # Taake message update ho sake
        import asyncio
        await asyncio.sleep(1) 
        
        await send_main_menu(update, context)

    # Status check (Ab yeh 'elif' theek hai)
    elif query.data == 'status':
        # Status Logic 
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
            reply_markup=await get_main_keyboard(context, user_id), 
            parse_mode='Markdown'
        )

    # Claim check (Ab yeh 'elif' bhi theek hai)
    elif query.data == 'claim':
        # Claim Logic 
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
        await send_main_menu(update, context)
        else:
            logger.info(f"🔴 VERIFICATION FAILED for user {user_id}")
            await query.edit_message_text(
                "❌ **Verification Nakam!** Aapne zaroori Telegram Channel join nahi kiya hai. Pehle join karein aur phir dobara koshish karein.",
                reply_markup=get_verification_keyboard(),
                parse_mode='Markdown'
            )

    elif query.data == 'status':
        # Status Logic 
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
            reply_markup=await get_main_keyboard(context, user_id), 
            parse_mode='Markdown'
        )

    elif query.data == 'claim':
        # Claim Logic 
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
        await send_main_menu(update, context)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update '%s' caused error '%s'", update, context.error)
    # Admin ko error notification
    if update and update.effective_user and update.effective_user.id != ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🚨 Error in Bot: {context.error}"
            )
        except:
             pass

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text.startswith('/'):
        await update.message.reply_text("Maaf kijiye, main is command ko nahi samajh paya. Menu ke liye /start type karein.")
    else:
        # Check if user is verified before sending main menu
        if user_data[update.effective_user.id]['channels_verified']:
             await send_main_menu(update, context)


async def setcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global GIFT_CODE
    
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Aapke paas yeh command istemaal karne ki permission nahi hai.")
        return

    if not context.args:
        await update.message.reply_text(f"❌ Istemaal: `/setcode <NEW_CODE>`. Current code hai: `{GIFT_CODE}`")
        return

    new_code = " ".join(context.args)
    GIFT_CODE = new_code
    
    await update.message.reply_text(
        f"✅ **Success!** Naya Daily Gift Code set kar diya gaya hai: `{GIFT_CODE}`"
    )

def main() -> None:
    # Final check: Zaroori Environment Variables
    if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID_1 or not CHANNEL_USERNAME:
        logger.error("❌ Zaroori Environment Variables set nahi hain. Kripya Render settings check karein. (BOT_TOKEN, ADMIN_ID, CHANNEL_ID_1, CHANNEL_USERNAME lazmi hain!)")
        return
        
    # Application banane se pehle user_data ko Application ke saath attach karen
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("setcode", setcode_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query)) 
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))
    
    application.add_error_handler(error_handler)

    # --- Run in Polling Mode (To avoid Webhook/Render Timeouts) ---
    application.run_polling(poll_interval=1.0) # Har 1 second mein updates check karega
    logger.info("Bot started successfully in Polling mode.")

if __name__ == "__main__":
    main()
