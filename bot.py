import os
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from flask import Flask
import threading

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()

# Data store
referrals = {}

# Flask for Render keep-alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running fine!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

# --- Handlers ---

@router.message(F.text == "/start")
async def start_command(message: Message):
    args = message.text.split()
    referrer = None

    if len(args) > 1:
        referrer = args[1]

    user_id = str(message.from_user.id)
    if user_id not in referrals:
        referrals[user_id] = {"referrals": [], "referrer": None}

    if referrer and referrer != user_id:
        if referrer not in referrals:
            referrals[referrer] = {"referrals": [], "referrer": None}
        if user_id not in referrals[referrer]["referrals"]:
            referrals[referrer]["referrals"].append(user_id)
            referrals[user_id]["referrer"] = referrer
            await message.answer(f"🎉 You were referred by <b>{referrer}</b>!")
        else:
            await message.answer("⚠️ Already referred by this user.")
    elif referrer == user_id:
        await message.answer("⚠️ You can't refer yourself!")

    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await message.answer(
        f"👋 Welcome {message.from_user.first_name}!\n"
        f"Your referral link:\n{link}\n\n"
        f"💰 Total referrals: {len(referrals[user_id]['referrals'])}"
    )

@router.message(F.text == "/help")
async def help_command(message: Message):
    await message.answer(
        "🧠 Commands:\n"
        "/start - Get your referral link\n"
        "/help - Show this message\n"
        "/stats - View your referral stats"
    )

@router.message(F.text == "/stats")
async def stats_command(message: Message):
    user_id = str(message.from_user.id)
    if user_id not in referrals:
        await message.answer("❌ You haven't started the bot yet. Use /start.")
        return

    ref_count = len(referrals[user_id]["referrals"])
    await message.answer(f"📊 You have {ref_count} referrals!")

# Register router
dp.include_router(router)

async def main():
    print("🤖 Bot running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(main())
