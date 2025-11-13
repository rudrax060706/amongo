from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from handlers.add_command import is_globally_banned
from utils.database import db  # <-- using Motor async client
from config import GROUP_ID, CHANNEL_ID, GROUP_URL, CHANNEL_URL, RARITY_MAP


# ================= HELPER FUNCTIONS =================

async def has_started_bot(user_id: int) -> bool:
    """Check if user has started the bot."""
    user = await db.users.find_one({"_id": str(user_id)})
    return user is not None


async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is in both group and channel."""
    try:
        member_group = await context.bot.get_chat_member(GROUP_ID, user_id)
        member_channel = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return (
            member_group.status not in ("left", "kicked")
            and member_channel.status not in ("left", "kicked")
        )
    except Exception:
        return False


async def check_user_status(user_id: int) -> str:
    """Check global ban and bot start status."""
    if await db.global_bans.find_one({"user_id": str(user_id)}):
        return "banned"
    

# ================= MAIN COMMAND HANDLER =================

async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main /myitems command."""
    if update.message is None:
        return
    user = update.effective_user

    # 1️⃣ Check global ban and bot start
    status = await check_user_status(user.id)
    if status == "banned":
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return

    # 2️⃣ Membership check
    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_items")],
        ]
        await update.message.reply_text(
            "<b>⚠️ You must join our main group and channel to use this feature.</b>\n\n"
            "Once you've joined both, click <b>'Try Again'</b>!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # 3️⃣ Show category menu
    await show_category_selection(update, context)


# ================= TRY AGAIN CALLBACK =================

async def recheck_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user

    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_items")],
        ]
        await query.edit_message_text(
            "<b>⚠️ You still need to join our group and channel.</b>\n\n"
            "Join both, then click <b>'Try Again'</b>!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await show_category_selection(update, context, from_callback=True)


# ================= CATEGORY MENU =================

async def show_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    user_id = str(update.effective_user.id)
    now = datetime.utcnow()

    waifu_count = await db.submissions.count_documents({
        "type": "waifu",
        "user_id": user_id,
        "status": "approved",
        "expires_at": {"$gt": now}
    })
    husbando_count = await db.submissions.count_documents({
        "type": "husbando",
        "user_id": user_id,
        "status": "approved",
        "expires_at": {"$gt": now}
    })

    keyboard = []
    if waifu_count:
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if husbando_count:
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    text = "Choose a category:" if (waifu_count or husbando_count) else "<b>You have no ongoing items.</b>"

    if from_callback:
        await update.callback_query.edit_message_text(text, parse_mode="HTML",
                                                      reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    else:
        await update.message.reply_text(text, parse_mode="HTML",
                                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)


# ================= TYPE SELECTION =================

async def type_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    _, _, category = query.data.split("_")
    keyboard = [
        [
            InlineKeyboardButton("🌟 View All (Default)", callback_data=f"view_all_{category}_1"),
            InlineKeyboardButton("🎯 Filter by Rarity", callback_data=f"filter_rarity_{category}")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await query.edit_message_text(
        f"<b>Selected category:</b> {category.capitalize()}\nChoose how you want to view items:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================= VIEW ALL HANDLER =================

async def view_all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user

    data = query.data.split("_")
    category = data[2]
    page = int(data[3]) if len(data) > 3 else 1
    items_per_page = 10
    now = datetime.utcnow()

    cursor = db.submissions.find({
        "type": category,
        "user_id": str(user.id),
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id", 1)

    results = await cursor.to_list(None)
    total_items = len(results)
    start, end = (page - 1) * items_per_page, page * items_per_page
    current_items = results[start:end]

    if not current_items:
        await query.edit_message_text(f"No ongoing {category} auctions found.")
        return

    items_list = ""
    for item in current_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown anime")
        msg_id = item.get("channel_message_id")
        channel_id = str(item.get("channel_id", ""))
        if channel_id.startswith("-100"):
            link = f"https://t.me/c/{channel_id[4:]}/{msg_id}"
        else:
            link = f"{CHANNEL_URL}/{msg_id}"

        emoji = next((k for k, v in RARITY_MAP.items() if v == item.get("rarity_name")), "⭐")
        items_list += f"{emoji} <a href='{link}'>{item.get('_id')}. {name}</a> ({anime})\n"

    total_pages = (total_items + items_per_page - 1) // items_per_page
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⏮️ Prev", callback_data=f"view_all_{category}_{page-1}"))
    if end < total_items:
        nav_buttons.append(InlineKeyboardButton("Next ⏭️", callback_data=f"view_all_{category}_{page+1}"))

    buttons = []
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"select_type_{category}"),
        InlineKeyboardButton("🗑️ Delete", callback_data="delete")
    ])

    await query.edit_message_text(
        f"<b>💫 All {category.capitalize()} Auctions</b>\nPage {page}/{total_pages}\n\n{items_list}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= RARITY FILTER HANDLERS =================

async def filter_rarity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user

    _, _, category = query.data.split("_")
    now = datetime.utcnow()
    cursor = db.submissions.find({
        "type": category,
        "user_id": str(user.id),
        "status": "approved",
        "expires_at": {"$gt": now}
    }, {"rarity_name": 1})

    rarities = {item["rarity_name"] async for item in cursor if item.get("rarity_name")}
    if not rarities:
        await query.edit_message_text(f"<b>You have no ongoing {category} items.</b>", parse_mode="HTML")
        return

    keyboard = []
    row = []
    for emoji, name in RARITY_MAP.items():
        if name in rarities:
            row.append(InlineKeyboardButton(emoji, callback_data=f"select_rarity_{category}_{emoji}_1"))
            if len(row) >= 3:
                keyboard.append(row)
                row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"select_type_{category}")])

    await query.edit_message_text(
        f"<b>Filter {category.capitalize()} by Rarity:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def rarity_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = update.effective_user

    data = query.data.split("_")
    category = data[2]
    emoji = data[3]
    page = int(data[4]) if len(data) > 4 else 1
    rarity_name = RARITY_MAP.get(emoji, "Unknown")

    now = datetime.utcnow()
    cursor = db.submissions.find({
        "type": category,
        "user_id": str(user.id),
        "rarity_name": rarity_name,
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id", 1)

    results = await cursor.to_list(None)
    total_items = len(results)
    items_per_page = 10
    start, end = (page - 1) * items_per_page, page * items_per_page
    current_items = results[start:end]

    if not current_items:
        await query.edit_message_text(
            f"No ongoing {category} found with rarity {rarity_name} ({emoji})."
        )
        return

    items_list = ""
    for item in current_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown anime")
        msg_id = item.get("channel_message_id")
        channel_id = str(item.get("channel_id", ""))
        if channel_id.startswith("-100"):
            link = f"https://t.me/c/{channel_id[4:]}/{msg_id}"
        else:
            link = f"{CHANNEL_URL}/{msg_id}"
        items_list += f"• <a href='{link}'>{item.get('_id')}. {name}</a> ({anime})\n"

    total_pages = (total_items + items_per_page - 1) // items_per_page
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⏮️ Prev", callback_data=f"select_rarity_{category}_{emoji}_{page-1}"))
    if end < total_items:
        nav_buttons.append(InlineKeyboardButton("Next ⏭️", callback_data=f"select_rarity_{category}_{emoji}_{page+1}"))

    buttons = []
    if nav_buttons:
        buttons.append(nav_buttons)
    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"filter_rarity_{category}"),
        InlineKeyboardButton("🗑️ Delete", callback_data="delete")
    ])

    await query.edit_message_text(
        f"{emoji} <b>{rarity_name}</b> {category.capitalize()}s\nPage {page}/{total_pages}\n\n{items_list}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ================= BACK & DELETE =================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user_id = str(update.effective_user.id)
    now = datetime.utcnow()

    keyboard = []
    if await db.submissions.count_documents({"type": "waifu", "user_id": user_id, "status": "approved", "expires_at": {"$gt": now}}):
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if await db.submissions.count_documents({"type": "husbando", "user_id": user_id, "status": "approved", "expires_at": {"$gt": now}}):
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    if not keyboard:
        await query.edit_message_text("<b>No ongoing auctions available.</b>", parse_mode="HTML")
        return

    await query.edit_message_text("Choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.delete_message()


# ================= HANDLER LIST =================

myitems_handlers = [
    CommandHandler("myitems", items_command),
    CallbackQueryHandler(recheck_items, pattern="^recheck_items$"),
    CallbackQueryHandler(type_selection_handler, pattern="^select_type_"),
    CallbackQueryHandler(view_all_handler, pattern="^view_all_"),
    CallbackQueryHandler(filter_rarity_handler, pattern="^filter_rarity_"),
    CallbackQueryHandler(rarity_selection_handler, pattern="^select_rarity_"),
    CallbackQueryHandler(back_handler, pattern="^back$"),
    CallbackQueryHandler(delete_menu_handler, pattern="^delete$"),
]
