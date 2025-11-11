import re
from datetime import datetime, timedelta
from typing import Any
from telegram.ext import JobQueue
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import BadRequest
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from utils.database import db  # ✅ Using Mongo now
from models.global_ban import GlobalBan  # ✅ Pydantic model version

# ====== CONFIG ======
GROUP_ID = -1002677839849
CHANNEL_ID = -1002875695805
GROUP_URL = "https://t.me/ThePhantom_Troupe"
CHANNEL_URL = "https://t.me/ThePhantom_Troupe_Auction"

# ====== RARITY MAP ======
RARITY_MAP = {
    "🔵": "Common",
    "🔴": "Medium",
    "🟠": "Rare",
    "🟡": "Legendary",
    "💮": "Exclusive",
    "🔮": "Limited",
    "🎐": "Celestial",
}

# ====== HELPERS ======
def safe_split(data: str | None, sep: str = "_", index: int | None = None) -> str | list[str]:
    if not data or sep not in data:
        return "" if index is not None else []
    parts = data.split(sep)
    return parts[index] if index is not None and len(parts) > index else parts

def is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return chat and chat.type == "private"

# ====== SAFE REPLY HELPER ======
async def safe_reply(update: Update, text: str, **kwargs):
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    elif update.callback_query:
        return await update.callback_query.message.reply_text(text, **kwargs)
    else:
        print("⚠️ No valid message or callback found for reply.")

# ====== GLOBAL BAN CHECK ======
async def is_globally_banned(user_id: int) -> bool:
    """Check if a user is globally banned (MongoDB version)."""
    banned = await db["global_bans"].find_one({"user_id": int(user_id)})
    return banned is not None

# ====== MEMBERSHIP CHECK ======
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        member_group = await context.bot.get_chat_member(GROUP_ID, user_id)
        member_channel = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return member_group.status not in ("left", "kicked") and member_channel.status not in ("left", "kicked")
    except Exception:
        return False

# ====== ADD COMMAND ======
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        await safe_reply(
            update,
            "⚠️ Please use this command in my DM.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Open DM", url=f"t.me/{context.bot.username}")]
            ]),
        )
        return

    user = update.effective_user
    if not user:
        return

    # ✅ Global Ban Check
    if await is_globally_banned(user.id):
        await safe_reply(update, "🚫 You are globally banned from using this bot.")
        return

    # ✅ Membership Check
    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_add")],
        ]
        await safe_reply(
            update,
            "<b>⚠️ You need to join our main group and channel to use this feature.</b>\n\n"
            "<b>Join both using the buttons below, then click 'Try Again'!</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ✅ Proceed if allowed
    keyboard = [
        [InlineKeyboardButton("👩‍🦰 Waifu", callback_data="type_waifu")],
        [InlineKeyboardButton("🧑‍🦱 Husbando", callback_data="type_husbando")],
    ]
    await safe_reply(
        update,
        "Choose what you want to add 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ====== TYPE SELECTION ======
async def type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if await is_globally_banned(user.id):
        await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    context.user_data["type"] = safe_split(query.data, "_", 1)
    keyboard = [
        [
            InlineKeyboardButton("🔵", callback_data="rarity_🔵"),
            InlineKeyboardButton("🔴", callback_data="rarity_🔴"),
            InlineKeyboardButton("🟠", callback_data="rarity_🟠"),
        ],
        [
            InlineKeyboardButton("🟡", callback_data="rarity_🟡"),
            InlineKeyboardButton("💮", callback_data="rarity_💮"),
            InlineKeyboardButton("🔮", callback_data="rarity_🔮"),
        ],
        [InlineKeyboardButton("🎐", callback_data="rarity_🎐")],
    ]
    await query.edit_message_text(
        f"Now select the rarity for your {context.user_data['type']}:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ====== RARITY SELECTION ======
async def rarity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if await is_globally_banned(user.id):
        await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    rarity_symbol = safe_split(query.data, "_", 1)
    context.user_data["rarity"] = rarity_symbol
    context.user_data["rarity_name"] = RARITY_MAP.get(rarity_symbol, "Unknown")

    msg_type = context.user_data.get("type", "waifu").capitalize()
    rarity_name = context.user_data["rarity_name"]

    bot_name = "@Waifu_Grabber_Bot" if msg_type.lower() == "waifu" else "@Husbando_Grabber_Bot"
    response_text = (
        f"✨ <b>Rarity Selected!</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💎 <b>Rarity:</b> {rarity_name} {rarity_symbol}\n"
        f"🏷️ <b>Type:</b> {msg_type}\n\n"
        f"📦 <b>Now send the {msg_type}</b> from your collection of this rarity!\n"
        f"🔗 <b>Source:</b> {bot_name}\n\n"
        f"Or type /cancel to stop this submission."
    )
    await query.edit_message_text(text=response_text, parse_mode="HTML")

# ====== RECHECK MEMBERSHIP ======
async def recheck_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await add_command(update, context)

# ====== CANCEL COMMAND ======
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_chat(update):
        return

    user = update.effective_user
    if await is_globally_banned(user.id):
        await safe_reply(update, "🚫 You are globally banned from using this bot.")
        return

    if context.user_data:
        context.user_data.clear()
        await safe_reply(update, "❌ Your submission process has been cancelled.")
    else:
        await safe_reply(update, "⚠️ You don’t have any ongoing submission to cancel.")

# ====== HANDLERS ======
add_handlers = [
    CommandHandler("add", add_command),
    CallbackQueryHandler(type_selection, pattern="^type_"),
    CallbackQueryHandler(rarity_selection, pattern="^rarity_"),
    CallbackQueryHandler(recheck_membership, pattern="^recheck_add"),
    CommandHandler("cancel", cancel_command),
]