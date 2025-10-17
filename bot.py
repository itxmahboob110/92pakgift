import asyncio
import datetime
import json
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME_RAW = os.getenv("CHANNEL_USERNAME")
WHATSAPP_LINK = os.getenv("WHATSAPP_LINK")
ADMIN_ID_STR = os.getenv("ADMIN_ID")
DAILY_CODE = os.getenv("DAILY_CODE", "")

if not BOT_TOKEN or not CHANNEL_USERNAME_RAW or not WHATSAPP_LINK or not ADMIN_ID_STR:
    raise ValueError("Missing environment variables in .env")

ADMIN_ID = int(ADMIN_ID_STR)
CHANNEL_USERNAME = CHANNEL_USERNAME_RAW.replace("https://t.me/", "").lstrip("@")

# JSON database file
DB_FILE = "data.json"

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2)

data = load_data()

bot = Bot(token=BOT_TOKEN)
router = Router()

# -------------------- Start Command --------------------
@router.message(CommandStart())
async def start_cmd(msg: Message):
    uid = str(msg.from_user.id)
    args = msg.text.split()
    ref = None
    if len(args) > 1:
        ref = args[1]

    # Initialize user data if not present
    if uid not in data:
        data[uid] = {
            "total_referrals": 0,
            "used_referrals": 0,
            "last_claim": None
        }

    # Referral tracking
    if ref and ref != uid:
        if ref in data:
            data[ref]["total_referrals"] += 1
        else:
            data[ref] = {
                "total_referrals": 1,
                "used_referrals": 0,
                "last_claim": None
            }
        save_data(data)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Telegram Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="💬 Join WhatsApp Channel", url=WHATSAPP_LINK)],
        [InlineKeyboardButton(text="✅ Verify & Continue", callback_data="verify")]
    ])

    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={uid}"

    await msg.answer(
        f"👋 <b>Hey {msg.from_user.first_name}!</b>\n\n"
        f"Welcome to your daily gift bot 🎁\n"
        f"Join both channels and verify below to continue.\n\n"
        f"Your Invite Link 👇\n<code>{referral_link}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# -------------------- Verification --------------------
@router.callback_query(F.data == "verify")
async def verify_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.answer("❌ Join the Telegram channel first!", show_alert=True)
            return
    except Exception as e:
        await callback.answer(f"⚠️ Verification failed: {e}", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I have joined WhatsApp", callback_data="whatsapp_done")]
    ])
    await callback.message.answer(
        "✅ Telegram verification done!\nNow confirm WhatsApp join:",
        reply_markup=kb
    )
    await callback.answer()

# -------------------- WhatsApp Done --------------------
@router.callback_query(F.data == "whatsapp_done")
async def whatsapp_done(callback: CallbackQuery):
    await callback.message.answer(
        "🎉 Verification Complete!\n\n"
        "Invite 2 friends using your referral link to unlock your daily gift.\n\n"
        "Type /status anytime to see your progress.",
        parse_mode="HTML"
    )
    await callback.answer()

# -------------------- Status Command --------------------
@router.message(Command("status"))
async def status_cmd(msg: Message):
    uid = str(msg.from_user.id)
    if uid not in data:
        await msg.answer("⚠️ Please use /start first.")
        return

    total = data[uid]["total_referrals"]
    used = data[uid]["used_referrals"]
    available = total - used
    last_claim = data[uid]["last_claim"]

    await msg.answer(
        f"💎 <b>Your Premium Referral Dashboard</b> 💎\n\n"
        f"👤 <b>Total Invites:</b> {total}\n"
        f"🎁 <b>Gift Codes Claimed:</b> {used}\n"
        f"💰 <b>Available Referrals:</b> {available}\n"
        f"📅 <b>Last Claim:</b> {last_claim or '—'}\n\n"
        f"Use /claim to get your gift code if you have 2 or more available referrals.",
        parse_mode="HTML"
    )

# -------------------- Claim Command --------------------
@router.message(Command("claim"))
async def claim_cmd(msg: Message):
    uid = str(msg.from_user.id)
    if uid not in data:
        await msg.answer("⚠️ Please use /start first.")
        return

    today = datetime.date.today().strftime("%Y-%m-%d")
    total = data[uid]["total_referrals"]
    used = data[uid]["used_referrals"]
    available = total - used

    if available < 2:
        await msg.answer("👥 You need at least 2 available referrals to claim your gift!")
        return

    if data[uid]["last_claim"] == today:
        await msg.answer("✅ You've already claimed today's gift. Come back tomorrow!")
        return

    data[uid]["used_referrals"] += 2
    data[uid]["last_claim"] = today
    save_data(data)

    await msg.answer(
        "🎉 Processing your gift code...\n✨ Verified referrals found!\n\n"
        f"🎯 <b>Your Code:</b> <code>{DAILY_CODE}</code>\n\n"
        "Keep inviting friends to earn more free codes!",
        parse_mode="HTML"
    )

# -------------------- Admin: Set Code --------------------
@router.message(Command("setcode"))
async def set_code(msg: Message):
    global DAILY_CODE
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ Unauthorized.")
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Usage: /setcode NEWCODE")
        return

    DAILY_CODE = parts[1]
    await msg.answer(f"✅ Daily code updated to: <b>{DAILY_CODE}</b>", parse_mode="HTML")

# -------------------- Admin: Stats --------------------
@router.message(Command("stats"))
async def admin_stats(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    total_users = len(data)
    total_referrals = sum(u["total_referrals"] for u in data.values())
    total_claims = sum(u["used_referrals"] // 2 for u in data.values())

    await msg.answer(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔗 Total Referrals: {total_referrals}\n"
        f"🎁 Total Claims: {total_claims}",
        parse_mode="HTML"
    )

# -------------------- Run Bot --------------------
async def main():
    dp = Dispatcher()
    dp.include_router(router)
    print("🤖 Bot is now running (Premium Edition)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
