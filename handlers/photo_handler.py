import re
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from utils.database import db  # MongoDB async client
from models.tables import Submission
from .add_command import is_private_chat, is_member, RARITY_MAP, GROUP_URL, CHANNEL_URL


# ====== PHOTO HANDLER ======
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles photo submissions and stores them in MongoDB."""
    if not is_private_chat(update):
        return
    if not update.message or not update.message.photo:
        return

    user = update.message.from_user
    if not user:
        return

    # ✅ Membership check
    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_add")],
        ]
        await update.message.reply_text(
            "<b>⚠️ You need to join our main group and channel to use this feature.</b>\n\n"
            "<b>Join both using the buttons below, then click 'Try Again'!</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    caption = update.message.caption or ""

    # ✅ Ensure previous steps completed
    if not context.user_data.get("type") or not context.user_data.get("rarity"):
        await update.message.reply_text("⚠️ Please start again using /add.")
        return

    selected_type = context.user_data["type"]
    selected_rarity = context.user_data["rarity"]

    # --- Validation ---
    if "waifu" in caption.lower() and selected_type != "waifu":
        await update.message.reply_text("❌ You selected Husbando, but this looks like a Waifu.")
        return
    if "husbando" in caption.lower() and selected_type != "husbando":
        await update.message.reply_text("❌ You selected Waifu, but this looks like a Husbando.")
        return

    found_rarity = next((emoji for emoji in RARITY_MAP if emoji in caption), None)
    if not found_rarity:
        await update.message.reply_text(f"⚠️ Please include a rarity emoji in your caption (like {selected_rarity}).")
        return
    if found_rarity != selected_rarity:
        await update.message.reply_text(
            f"❌ You selected rarity {selected_rarity} ({RARITY_MAP.get(selected_rarity, 'Unknown')}), "
            f"but your caption has {found_rarity} ({RARITY_MAP.get(found_rarity, 'Unknown')})."
        )
        return

    # --- Extract Info ---
    lines = [line.strip() for line in caption.strip().split("\n") if line.strip()]
    anime_name = "Unknown"
    waifu_name = "Unknown"
    optional_tag = "—"

    if len(lines) > 1:
        anime_name = re.sub(r"\s*\d+\/\d+\.?\s*$", "", lines[1]).strip()
    if len(lines) > 2:
        waifu_line = lines[2].strip()
        parts = waifu_line.split(":")
        if len(parts) > 1:
            waifu_name = parts[1].split("x1")[0].strip()
        else:
            waifu_name = waifu_line
    if len(lines) > 3:
        possible_tag = lines[-1]
        if "RARITY" not in possible_tag.upper():
            optional_tag = possible_tag

    file_id = update.message.photo[-1].file_id

    # ✅ Create Submission instance
    submission = Submission(
        user_id=str(user.id),
        username=user.username or None,
        user_name=user.full_name,
        type=selected_type,
        rarity=selected_rarity,
        rarity_name=RARITY_MAP.get(selected_rarity, "Unknown"),
        caption=caption,
        anime_name=anime_name,
        waifu_name=waifu_name,
        optional_tag=optional_tag,
        file_id=file_id,
        submitted_time=datetime.utcnow(),
        status="draft",  # not yet finalized
    )

    # ✅ Insert into MongoDB
    result = await db["submissions"].insert_one(submission.dict(by_alias=True))
    submission_id = str(result.inserted_id)

    # ✅ Store temporarily for next step
    context.user_data.update({
        "submission_id": submission_id,
        "type": selected_type,
        "rarity": selected_rarity,
        "rarity_name": RARITY_MAP.get(selected_rarity, "Unknown"),
        "caption": caption,
        "anime_name": anime_name,
        "waifu_name": waifu_name,
        "optional_tag": optional_tag,
        "file_id": file_id,
        "awaiting_bid": True,  # waiting for bid next
    })

    await update.message.reply_text(
        "💰 Please enter the <b>base bid</b> for this item (in numbers only):\n\n"
        "Or type /cancel to stop this submission.",
        parse_mode="HTML",
    )


# ====== HANDLERS LIST ======
photo_handlers = [
    MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo),
]
