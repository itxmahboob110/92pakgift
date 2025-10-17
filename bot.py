import asyncio
import datetime
import os
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME_RAW = os.getenv("CHANNEL_USERNAME")
WHATSAPP_LINK = os.getenv("WHATSAPP_LINK")
ADMIN_ID_STR = os.getenv("ADMIN_ID")

if CHANNEL_USERNAME_RAW:
    if "t.me/" in CHANNEL_USERNAME_RAW:
        CHANNEL_USERNAME = CHANNEL_USERNAME_RAW.split("t.me/")[-1]
    else:
        CHANNEL_USERNAME = CHANNEL_USERNAME_RAW.lstrip("@")
else:
    CHANNEL_USERNAME = None

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables")
if not CHANNEL_USERNAME:
    raise ValueError("CHANNEL_USERNAME is not set in environment variables")
if not WHATSAPP_LINK:
    raise ValueError("WHATSAPP_LINK is not set in environment variables")
if not ADMIN_ID_STR:
    raise ValueError("ADMIN_ID is not set in environment variables")

ADMIN_ID = int(ADMIN_ID_STR)
DAILY_CODE = os.getenv("DAILY_CODE", "")

bot = Bot(token=BOT_TOKEN)
router = Router()

verified_users = set()
referrals = {}
user_data = {}

@router.message(CommandStart())
async def start_cmd(msg: Message, command: CommandObject):
    uid = msg.from_user.id
    ref = command.args
    
    print(f"📥 /start command received from user {uid}")
    print(f"   Referral parameter: {ref}")
    
    if ref and ref != str(uid):
        referrals.setdefault(ref, []).append(uid)
        print(f"✅ Referral tracked: User {uid} was referred by {ref}")
        print(f"   Total referrals for {ref}: {len(referrals[ref])}")
    elif ref == str(uid):
        print(f"⚠️ User {uid} tried to refer themselves - ignored")
    else:
        print(f"ℹ️ User {uid} started bot without referral")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Telegram Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton(text="💬 Join WhatsApp Channel", url=WHATSAPP_LINK)],
        [InlineKeyboardButton(text="✅ Verify & Continue", callback_data="verify")]
    ])
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={uid}"
    print(f"   Generated referral link: {referral_link}")
    
    await msg.answer(
        f"👋 Hey {msg.from_user.first_name}!\n\n"
        f"To get your daily gift code:\n"
        f"1️⃣ Join both channels below\n"
        f"2️⃣ Invite 2 friends using your personal link\n\n"
        f"Your invite link 👇\n"
        f"<code>{referral_link}</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "verify")
async def verify_channels(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    try:
        member = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.answer("❌ You haven't joined the Telegram channel yet!", show_alert=True)
            return
    except Exception as e:
        await callback.answer(f"⚠️ Channel verification failed: {e}", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I have joined WhatsApp Channel", callback_data="whatsapp_done")]
    ])
    await callback.message.answer(
        "✅ Telegram channel joined confirmed!\n\n"
        "Now click below once you've joined the WhatsApp channel:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data == "whatsapp_done")
async def whatsapp_done(callback: CallbackQuery):
    uid = callback.from_user.id
    verified_users.add(uid)
    
    bot_info = await bot.get_me()
    referral_link = f"https://t.me/{bot_info.username}?start={uid}"
    await callback.message.answer(
        "🎉 Verification complete!\n\n"
        "Now invite <b>2 friends</b> to get your daily gift code.\n"
        "Use this link:\n"
        f"<code>{referral_link}</code>\n\n"
        "Send /status anytime to check your progress.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(Command("status"))
async def status_cmd(msg: Message):
    user_id = msg.from_user.id
    if user_id not in verified_users:
        await msg.answer("⚠️ You must join both channels first! Use /start again.")
        return
    
    invited = len(referrals.get(str(user_id), []))
    today = datetime.date.today().strftime("%Y-%m-%d")
    last_claim = user_data.get(str(user_id))
    
    if invited >= 2:
        if last_claim == today:
            await msg.answer("✅ You've already claimed today's gift code.")
            return
        
        user_data[str(user_id)] = today
        await msg.answer(
            f"🎁 Congrats! You've qualified for today's gift code!\n\n"
            f"🎯 Today's Code: <b>{DAILY_CODE}</b>\n\nCome back tomorrow for the next one.",
            parse_mode="HTML"
        )
        referrals[str(user_id)] = []
    else:
        await msg.answer(f"👥 You've invited {invited}/2 friends.\nInvite 2 to get your daily code!")

@router.message(Command("setcode"))
async def set_code(msg: Message):
    global DAILY_CODE
    
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ You are not authorized.")
        return
    
    args = msg.text.split(maxsplit=1)
    if len(args) < 2:
        await msg.answer("Usage: /setcode NEWCODE")
        return
    
    new_code = args[1]
    DAILY_CODE = new_code
    await msg.answer(f"✅ Daily code updated to: {new_code}")

async def main():
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Bot running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
