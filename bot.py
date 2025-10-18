import os
import logging
import json
from datetime import datetime, date
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# --- Configuration (Environment Variables se load hongi) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))  # Apna User ID yahaan daalein
CHANNEL_ID_1 = os.environ.get("CHANNEL_ID_1") # Pehle Telegram Channel ka ID
CHANNEL_ID_2 = os.environ.get("CHANNEL_ID_2") # Dusre Telegram Channel/Group ka ID
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8080))
# Initial gift code, jo admin badal sakta hai
GIFT_CODE = os.environ.get("GIFT_CODE", "92pak")

# Non-persistent data store (WARNING: Restart hone par data loss hoga)
# Production ke liye PostgreSQL ya koi persistent database istemaal karein.
user_data = {}

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def load_data():
    """Load data from a non-persistent way (just for demonstration)."""
    global user_data, GIFT_CODE
    try:
        if os.path.exists("data.json"):
            with open("data.json", "r") as f:
                data = json.load(f)
                user_data = data.get("user_data", {})
                GIFT_CODE = data.get("GIFT_CODE", os.environ.get("GIFT_CODE", "92pak"))
        logger.info("Data loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading data: {e}")

def save_data():
    """Save data to a non-persistent way (just for demonstration)."""
    global user_data, GIFT_CODE
    try:
        with open("data.json", "w") as f:
            json.dump({"user_data": user_data, "GIFT_CODE": GIFT_CODE}, f, indent=4)
        logger.info("Data saved successfully.")
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user(user_id):
    """Initializes user data if it doesn't exist."""
    user_id_str = str(user_id)
    if user_id_str not in user_data:
        user_data[user_id_str] = {
            "is_joined_channel_1": False,
            "is_joined_channel_2": False,
            "total_invites": 0,
            "available_invites": 0,  # Invites available for daily claim
            "last_claimed_date": "1970-01-01",
        }
    return user_data[user_id_str]

async def check_subscription(bot: Bot, user_id: int, chat_id: str) -> bool:
    """Checks if the user is a member of the given channel."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        # Status 'member', 'administrator', 'creator' sab theek hain.
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription for {user_id} in {chat_id}: {e}")
        return False

# --- Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles /start command, registers user, and tracks referrals."""
    user_id = update.effective_user.id
    user_data_entry = get_user(user_id)
    referrer_id = None
    
    # 1. Referral Logic
    if context.args and context.args[0].isdigit():
        referrer_id = context.args[0]
        referrer_id_str = str(referrer_id)
        
        # Self-referral check
        if referrer_id_str == str(user_id):
            referrer_id = None # Ignore self-referral
        elif referrer_id_str in user_data and user_data_entry.get("referrer_tracked") is None:
            # Track referral and reward referrer
            referrer_data = get_user(referrer_id)
            referrer_data["total_invites"] += 1
            referrer_data["available_invites"] += 1
            user_data_entry["referrer_tracked"] = referrer_id # To prevent multiple tracking
            await context.bot.send_message(
                referrer_id, 
                f"🎉 Mubarak! Aapke invite link se ek naya user ({update.effective_user.full_name}) join hua hai. Ab aapke paas {referrer_data['available_invites']} available invites hain."
            )
            save_data()

    # 2. Initial Instructions
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
    
    message = (
        f"Assalam-o-Alaikum, {update.effective_user.first_name}!\n\n"
        "Gift Code haasil karne ke liye in aasan steps ko poora karein:\n\n"
        "**Step 1: Channels Join Karein (Zaroori)**\n"
        f"1. Hamara **Telegram Channel 1** join karein: [Channel 1 Link](https://t.me/{CHANNEL_ID_1.replace('@', '')})\n"
        f"2. Hamara **Telegram Channel 2** join karein: [Channel 2 Link](https://t.me/{CHANNEL_ID_2.replace('@', '')})\n\n"
        "(Note: Bot dono channels ki membership verify karega.)\n\n"
        "**Step 2: Doston ko Invite Karein**\n"
        "Gift Code claim karne ke liye, aapko kam se kam **2 doston** ko invite karna hoga.\n"
        "Aapka unique invite link yeh hai:\n"
        f"`{referral_link}`\n\n"
        "**Step 3: Code Claim Karein**\n"
        "Jab aap steps poore kar lein, toh `/claim` command istemaal karein.\n\n"
        "**Apna Status Dekhne ke liye:** `/status` command istemaal karein."
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user's current status and progress."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Check current channel subscription status
    is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1)
    is_ch2_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_2)

    # Update local data (for easier tracking, though not strictly needed here)
    user["is_joined_channel_1"] = is_ch1_joined
    user["is_joined_channel_2"] = is_ch2_joined
    save_data()

    # Calculate remaining invites
    invites_needed = 2
    
    channel_status = (
        f"✅ Channel 1: {'Joined' if is_ch1_joined else '❌ Not Joined'}\n"
        f"✅ Channel 2: {'Joined' if is_ch2_joined else '❌ Not Joined'}\n"
    )
    
    claim_status = ""
    if is_ch1_joined and is_ch2_joined:
        claim_status = (
            f"**Invites Status**:\n"
            f"👥 Total Invites: **{user['total_invites']}**\n"
            f"🎁 Available Invites for Claim: **{user['available_invites']}**\n"
        )
        if user["available_invites"] >= invites_needed:
             claim_status += "\n**Mubarak!** Aap code claim karne ke liye tayyar hain. `/claim` type karein."
        else:
            remaining = invites_needed - user["available_invites"]
            claim_status += f"\n**Agla Code:** Aapko mazeed **{remaining}** invites ki zaroorat hai."
    else:
        claim_status = "\n**CODE CLAIM NAHI HO SAKTA:** Pehle dono channels join karein (Step 1)."
        
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"

    message = (
        f"**👤 Aapka Status:**\n"
        "--------------------------\n"
        f"{channel_status}"
        f"--------------------------\n"
        f"{claim_status}\n"
        f"--------------------------\n"
        f"Aapka Invite Link: `{referral_link}`\n\n"
        f"({datetime.now().strftime('%H:%M:%S')})"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allows user to claim the gift code based on daily invites."""
    user_id = update.effective_user.id
    user = get_user(user_id)
    today_str = date.today().isoformat()
    invites_needed = 2

    # 1. Channels Verification
    is_ch1_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_1)
    is_ch2_joined = await check_subscription(context.bot, user_id, CHANNEL_ID_2)

    if not (is_ch1_joined and is_ch2_joined):
        await update.message.reply_text(
            "❌ **Na-mukammal:** Code claim karne ke liye, aapko pehle dono channels (Telegram Channel 1 aur 2) join karne honge. Phir `/claim` karein.",
            parse_mode='Markdown'
        )
        return

    # 2. Daily Claim Check
    if user["last_claimed_date"] == today_str:
        await update.message.reply_text(
            "⏳ **Ruk Jayiye:** Aap aaj ka code pehle hi claim kar chuke hain. Aap rozana sirf aik code claim kar sakte hain."
        )
        return

    # 3. Invite Count Check
    if user["available_invites"] < invites_needed:
        remaining = invites_needed - user["available_invites"]
        await update.message.reply_text(
            f"❌ **Na-mukammal:** Aapke paas abhi sirf {user['available_invites']} available invites hain. Mazeed **{remaining}** doston ko invite karein."
        )
        return

    # 4. Successful Claim
    user["available_invites"] -= invites_needed
    user["last_claimed_date"] = today_str
    
    global GIFT_CODE
    
    message = (
        "🎉 **Mubarak ho! Aapka Gift Code!** 🎉\n\n"
        f"Aapne kamyabi se **{invites_needed}** invites istemaal kar ke code claim kar liya hai.\n\n"
        f"🎮 **Aapka Gift Code (Daily Code):** `{GIFT_CODE}`\n\n"
        "--------------------------\n"
        f"🎁 **Agla Code:** Agla code aap kal ({user['available_invites']} invites baqi hain) ya jab bhi aapke paas **2 naye invites** jama hon, tab claim kar sakte hain. Apni link share karte rahein!"
    )
    await update.message.reply_text(message, parse_mode='Markdown')
    await context.bot.send_message(
        ADMIN_ID,
        f"✅ CLAIMED: User {update.effective_user.full_name} ({user_id}) ne aaj ka code claim kar liya. Remaining invites: {user['available_invites']}"
    )
    save_data()


async def setcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only command to change the daily gift code."""
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to admin."""
    logger.error("Update '%s' caused error '%s'", update, context.error)
    if update and update.effective_user and update.effective_user.id != ADMIN_ID:
        await context.bot.send_message(
            ADMIN_ID,
            f"🚨 Error in Bot: Update {update.update_id} caused error: {context.error}"
        )
    
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles unknown commands."""
    await update.message.reply_text("Maaf kijiye, main is command ko nahi samajh paya. Zaroori commands ke liye `/start` type karein.")

# --- Main Setup ---

def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN or not ADMIN_ID or not CHANNEL_ID_1 or not CHANNEL_ID_2 or not WEBHOOK_URL:
        logger.error("❌ Zaroori Environment Variables set nahi hain. Kripya .env file ya Render settings check karein.")
        return

    # Data load (non-persistent)
    load_data()
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("claim", claim_command))
    application.add_handler(CommandHandler("setcode", setcode_command))
    
    # Unknown commands (must be last)
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    # Error handler
    application.add_error_handler(error_handler)

    # --- Run with Webhook for Render ---
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="",
        webhook_url=WEBHOOK_URL,
    )
    logger.info("Bot started successfully in Webhook mode (Render compatible).")


if __name__ == "__main__":
    main()
