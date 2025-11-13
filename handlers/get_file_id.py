from telegram import Update
from telegram.ext import ContextTypes

OWNER_ID = 7562158122  # 🔹 replace with your Telegram user ID

async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send back the file_id when the owner sends a media file."""
    message = update.effective_message
    user_id = update.effective_user.id

    # Only owner can use
    if user_id != OWNER_ID:
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        await message.reply_text(f"📸 Photo file_id:\n`{file_id}`", parse_mode="Markdown")

    elif message.video:
        file_id = message.video.file_id
        await message.reply_text(f"🎥 Video file_id:\n`{file_id}`", parse_mode="Markdown")

    elif message.animation:
        file_id = message.animation.file_id
        await message.reply_text(f"🎬 Animation file_id:\n`{file_id}`", parse_mode="Markdown")

    elif message.document:
        file_id = message.document.file_id
        await message.reply_text(f"📁 Document file_id:\n`{file_id}`", parse_mode="Markdown")

    else:
        await message.reply_text("⚠️ Send a photo, video, or document.")
