import os
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNELS = ["@YourChannel1", "@YourChannel2"]
DATA_FILE = "data.json"
ADMIN_ID = 123456789  # 👈 apna Telegram numeric ID yahan daalo (get it from @userinfobot)
# ----------------------------------------

# 🗂️ Data Handling
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({"gift_code": "92pak", "users": {}}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# 🔁 Daily Reset
async def daily_reset():
    while True:
        now = datetime.now()
        next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        await asyncio.sleep((next_reset - now).total_seconds())
        data = load_data()
        for user_id in data["users"]:
            data["users"][user_id]["invites_today"] = 0
        save_data(data)
        print("✅ Daily invites reset complete")

# 🚀 START Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = str(update.effective_user.id)
    data = load_data()

    # 🧠 Ensure user in DB
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "invites_today": 0,
            "joined": False,
            "referred_users": []
        }

    # 🧾 Referral logic
    if args:
        referrer = args[0]
        if referrer != user_id and referrer in data["users"]:
            # Only count if this user is NEW for that referrer
            if user_id not in data["users"][referrer].get("referred_users", []):
                data["users"][referrer]["referred_users"].append(user_id)
                data["users"][referrer]["invites_today"] += 1

                # Check reward threshold
                if data["users"][referrer]["invites_today"] >= 2:
                    gift = data["gift_code"]
                    await context.bot.send_message(
                        chat_id=referrer,
                        text=f"🎁 Congratulations! Your gift code: {gift}"
                    )
                    data["users"][referrer]["invites_today"] = 0

    save_data(data)

    # 📢 Ask to join channels
    buttons = [
        [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNELS[0][1:]}")],
        [InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNELS[1][1:]}")],
        [InlineKeyboardButton("✅ I Joined", callback_data="joined")]
    ]
    await update.message.reply_text(
        "👇 Join both channels to continue:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ✅ JOIN Verification
async def joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    data = load_data()

    joined_all = True
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch, int(user_id))
            if member.status not in ["member", "administrator", "creator"]:
                joined_all = False
        except:
            joined_all = False

    if joined_all:
        data["users"][user_id]["joined"] = True
        save_data(data)
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await query.message.reply_text(
            f"✅ Verified!\nYour referral link:\n{link}\n\nInvite 2 *new* friends (who never used bot before) to earn your next gift code 🎁"
        )
    else:
        await query.message.reply_text("❌ You must join both channels first!")

# 🔐 ADMIN: Change Gift Code
async def setcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    if len(context.args) == 0:
        await update.message.reply_text("Usage: `/setcode <new_gift_code>`", parse_mode="Markdown")
        return

    new_code = context.args[0]
    data = load_data()
    data["gift_code"] = new_code
    save_data(data)

    await update.message.reply_text(f"✅ Gift code updated to: `{new_code}`", parse_mode="Markdown")

# ⚙️ Main App
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(joined, pattern="joined"))
app.add_handler(CommandHandler("setcode", setcode))

# Run both bot + daily reset
async def main():
    task1 = asyncio.create_task(app.run_polling())
    task2 = asyncio.create_task(daily_reset())
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    asyncio.run(main())
