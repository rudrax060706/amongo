from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import db
from config import (
    WELCOME_MESSAGE,
    WELCOME_VIDEO_ID,
    GROUP_URL,
    CHANNEL_URL,
    LOG_GROUP_ID,
)
from utils.logger import log_user_start, escape_markdown


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # ====== Global Ban Check ======
    banned = await db.global_bans.find_one({"user_id": str(user.id)})
    if banned:
        if update.message:
            await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return

    # ====== Upsert User in MongoDB ======
    existing_user = await db.users.find_one({"user_id": user.id})
    is_new_user = False

    if not existing_user:
        new_user = {
            "user_id": user.id,
            "full_name": user.full_name or "Unknown",
            "username": user.username,
            "created_at": datetime.utcnow(),
            "last_seen": datetime.utcnow(),
        }
        await db.users.insert_one(new_user)
        is_new_user = True
    else:
        await db.users.update_one(
            {"user_id": user.id},
            {"$set": {"last_seen": datetime.utcnow()}}
        )

    # ====== Inline Buttons ======
    keyboard = [
        [
            InlineKeyboardButton("📢 Group", url=GROUP_URL),
            InlineKeyboardButton("🧿 Channel", url=CHANNEL_URL),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_video(
        chat_id=chat.id,
        video=WELCOME_VIDEO_ID,
        caption=WELCOME_MESSAGE,
        parse_mode="MarkdownV2",
        reply_markup=reply_markup,
    )

    # ====== Logging (only for new users) ======
    if is_new_user:
        log_text = (
            f"📥 **New User Started Bot**\n"
            f"👤 Name: {escape_markdown(user.full_name or 'Unknown')}\n"
            f"🆔 ID: `{user.id}`\n"
            f"💬 Username: @{escape_markdown(user.username) if user.username else 'N/A'}\n"
            f"🕒 Time: {escape_markdown(datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'))}\n"
            f"📍 Chat Type: {escape_markdown(chat.type)}"
        )
        await log_user_start(context, log_text)