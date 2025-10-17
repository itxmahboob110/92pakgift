import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask, request
import asyncio

# === Load environment variable ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN not found in environment variables!")

# === Initialize bot and dispatcher ===
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Flask App for Webhook ===
app = Flask(__name__)

# === Webhook route ===
@app.route(f"/{TOKEN}", methods=["POST"])
async def telegram_webhook():
    update = Update.model_validate(await request.get_json())
    await dp.feed_update(bot, update)
    return "OK", 200

# === Test route ===
@app.route("/", methods=["GET"])
def index():
    return "Bot is running successfully on Render!", 200

# === Basic command handler ===
from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text == "/start")
async def start_handler(message: Message):
    ...

    await message.answer("🎉 Welcome! Your bot is live and working perfectly on Render.")

@dp.message(commands=["help"])
async def help_command(message: types.Message):
    await message.answer("Here are your available commands:\n/start - Start bot\n/help - Help info")

# === Main setup ===
async def on_startup():
    webhook_url = f"{os.getenv('RENDER_EXTERNAL_URL')}/{TOKEN}"
    await bot.set_webhook(webhook_url)
    print(f"✅ Webhook set: {webhook_url}")

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()
    print("❌ Webhook removed and bot stopped.")

def run():
    loop = asyncio.get_event_loop()
    loop.create_task(on_startup())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

if __name__ == "__main__":
    run()
