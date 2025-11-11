from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    MessageHandler,
    filters,
)
from utils.database import db  # MongoDB async client
from .add_command import is_private_chat, RARITY_MAP
from config import LOG_GROUP_ID


# ====== BASE BID HANDLER ======
async def handle_base_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return
    if not context.user_data.get("awaiting_bid"):
        return  # Ignore if not expecting a bid

    user = update.message.from_user
    text = update.message.text.strip()

    # Validate numeric input
    if not text.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid number for base bid.")
        return

    base_bid = int(text)
    context.user_data["base_bid"] = base_bid
    context.user_data.pop("awaiting_bid", None)

    # Retrieve previous submission (temporary data)
    submission_data = {
        "user_id": user.id,
        "user_name": user.first_name or "N/A",
        "username": f"@{user.username}" if user.username else None,
        "type": context.user_data.get("type"),
        "rarity": context.user_data.get("rarity"),
        "rarity_name": RARITY_MAP.get(context.user_data.get("rarity"), "Unknown"),
        "anime_name": context.user_data.get("anime_name"),
        "waifu_name": context.user_data.get("waifu_name"),
        "optional_tag": context.user_data.get("optional_tag"),
        "caption": context.user_data.get("caption"),
        "file_id": context.user_data.get("file_id"),
        "submitted_time": datetime.utcnow(),
        "base_bid": base_bid,
        "status": "pending",
    }

    # Save submission to MongoDB
    result = await db["submissions"].insert_one(submission_data)
    item_id = str(result.inserted_id)

    # Build log message
    log_caption = (
        f"📩 <b>New {context.user_data['type'].capitalize()} Submission</b>\n\n"
        f"🆔 <b>Item ID:</b> <code>{item_id}</code>\n"
        f"👤 <b>Name:</b> {user.first_name}\n"
        f"🔗 <b>Username:</b> @{user.username if user.username else 'N/A'}\n"
        f"🎬 <b>Anime:</b> {context.user_data['anime_name']}\n"
        f"💞 <b>{context.user_data['type'].capitalize()}:</b> {context.user_data['waifu_name']}\n"
        f"💎 <b>Rarity:</b> {RARITY_MAP.get(context.user_data['rarity'])} {context.user_data['rarity']}\n"
        f"💰 <b>Base Bid:</b> {base_bid}\n"
        f"🏷️ <b>Tag:</b> {context.user_data['optional_tag']}\n"
        f"⏰ <b>Submitted:</b> {datetime.now().strftime('%d %B %Y • %I:%M %p')}"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{item_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{item_id}"),
        ]
    ]

    # Send to logs group
    try:
        await context.bot.send_photo(
            chat_id=int(LOG_GROUP_ID),
            photo=context.user_data["file_id"],
            caption=log_caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        await update.message.reply_text("⚠️ Unable to send to log group. Check LOG_GROUP_ID or bot permissions.")

    await update.message.reply_text("✅ Sent to the owner for approval!")

    # Clear temporary data
    context.user_data.clear()


# ====== HANDLERS LIST ======
bid_handlers = [
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_base_bid),
]