import os
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import asyncio
from datetime import datetime, timedelta

# 🔧 Config
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNELS = ["@YourChannel1", "@YourChannel2"]
GIFT_CODE = "92pak"
DATA_FILE = "data.json"

# 🗂️ Data Load / Save
def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# 🔁 Daily Reset (simple version)
async def daily_reset():
    while True:
        now = datetime.now()
        next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        sleep_time = (next_reset - now).total_seconds()
        await asyncio.sleep(sleep_time)
        data = load_data()
        for user_id in data:
            data[user_id]["invites_today"] = 0
        save_data(data)
        print("✅ Daily invites reset")

# 🚀 Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user_id = str(update.effective_user.id)
    data = load_data()

    # Handle referral
    if args:
        referrer = args[0]
        if referrer != user_id:
            if referrer not in data:
                data[referrer] = {"invites_today": 0, "joined": False}
            data[referrer]["invites_today"] = data[referrer].get("invites_today", 0) + 1

            if data[referrer]["invites_today"] >= 2:
                await context.bot.send_message(
                    chat_id=referrer, text=f"🎁 Your gift code: {GIFT_CODE}"
                )
                data[referrer]["invites_today"] = 0

    # Save user info
    if user_id not in data:
        data[user_id] = {"invites_today": 0, "joined": False}
    save_data(data)

    # Ask to join channels
    buttons = [
        [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{CHANNELS[0][1:]}")],
        [InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{CHANNELS[1][1:]}")],
        [InlineKeyboardButton("✅ I Joined", callback_data="joined")],
    ]
    await update.message.reply_text(
        "👇 Join both channels to continue:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = load_data()

    joined_all = True
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                joined_all = False
        except:
            joined_all = False

    if joined_all:
        data[str(user_id)]["joined"] = True
        save_data(data)
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        await query.message.reply_text(
            f"✅ Verified! Your referral link:\n{link}\n\nInvite 2 friends daily to earn your next gift code 🎁"
        )
    else:
        await query.message.reply_text("❌ You must join both channels first!")

# ⚙️ Main App
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(joined, pattern="joined"))

# Run both bot + daily reset
async def main():
    task1 = asyncio.create_task(app.run_polling())
    task2 = asyncio.create_task(daily_reset())
    await asyncio.gather(task1, task2)

if __name__ == "__main__":
    asyncio.run(main())
