# my_items_handler_list.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from utils.database import db
from models.tables import Submission
from config import BOT_USERNAME  # your bot username without @

# ---------------------------
# /myitems command
# ---------------------------
async def myitems(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send buttons to select Waifu or Husbando"""
    keyboard = [
        [
            InlineKeyboardButton("Waifu", callback_data="myitems_type:waifu"),
            InlineKeyboardButton("Husbando", callback_data="myitems_type:husbando"),
        ]
    ]
    await update.message.reply_text(
        "Select type:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------------------
# Handle type selection
# ---------------------------
async def myitems_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    selected_type = query.data.split(":")[1]  # "waifu" or "husbando"

    # Fetch user submissions of this type
    submissions_cursor = db.submissions.find({
        "user_id": user_id,
        "type": selected_type,
        "status": "approved",
        "is_expired": False
    })
    submissions = await submissions_cursor.to_list(length=100)

    if not submissions:
        # Show message with button to start DM with bot
        keyboard = [
            [
                InlineKeyboardButton(
                    "Add your first item", 
                    url=f"https://t.me/{BOT_USERNAME}?start=add"
                )
            ]
        ]
        await query.edit_message_text(
            f"You have no {selected_type} items yet.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Build message
    msg = f"Your {selected_type} items:\n\n"
    for sub in submissions:
        bid = sub.get("current_bid") or sub.get("base_bid") or 0
        msg += f"• {sub.get('waifu_name') or sub.get('anime_name')} — Current Bid: {bid}\n"

    await query.edit_message_text(msg)

# ---------------------------
# Handler list (like photo_handlers)
# ---------------------------
myitems_handlers = [
    CommandHandler("myitems", myitems),
    CallbackQueryHandler(myitems_type_handler, pattern=r"^myitems_type:")
]
