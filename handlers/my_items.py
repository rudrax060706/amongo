from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from handlers.add_command import is_globally_banned
from utils.database import db
from config import GROUP_ID, CHANNEL_ID, GROUP_URL, CHANNEL_URL, RARITY_MAP


# ------------------------------------------------
# Helper Functions
# ------------------------------------------------

async def has_started_bot(user_id: int) -> bool:
    user = await db.users.find_one({"user_id": user_id})
    return user is not None


async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        group = await context.bot.get_chat_member(GROUP_ID, user_id)
        channel = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return (
            group.status not in ("left", "kicked")
            and channel.status not in ("left", "kicked")
        )
    except Exception:
        return False


async def check_user_status(user_id: int) -> str:
    if await db.global_bans.find_one({"user_id": user_id}):
        return "banned"
    return "ok"


# ------------------------------------------------
# /myitems COMMAND
# ------------------------------------------------

async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user

    # 1. Check global ban
    if await is_globally_banned(user.id):
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return

    # 2. Check membership
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
            "Once done, tap <b>Try Again</b>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # 3. Show category menu
    await show_category_selection(update, context)


# ------------------------------------------------
# Try Again Button
# ------------------------------------------------

async def recheck_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
            "<b>⚠️ You still need to join both the group and channel.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await show_category_selection(update, context, from_callback=True)


# ------------------------------------------------
# Category Selection
# ------------------------------------------------

async def show_category_selection(update: Update, context, from_callback=False):
    user_id = update.effective_user.id
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
    if waifu_count > 0:
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if husbando_count > 0:
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    text = "Choose a category:" if keyboard else "<b>You have no ongoing items.</b>"

    if from_callback:
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )


# ------------------------------------------------
# Type Selection
# ------------------------------------------------

async def type_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    if await is_globally_banned(user.id):
        await query.edit_message_text("🚫 You are globally banned.")
        return

    _, _, category = query.data.split("_")

    keyboard = [
        [
            InlineKeyboardButton("🌟 View All", callback_data=f"view_all_{category}_1"),
            InlineKeyboardButton("🎯 Filter by Rarity", callback_data=f"filter_rarity_{category}")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    await query.edit_message_text(
        f"<b>Selected category:</b> {category.capitalize()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------------------------
# View All Items
# ------------------------------------------------

async def view_all_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data.split("_")

    category = data[2]
    page = int(data[3])
    items_per_page = 10
    now = datetime.utcnow()

    cursor = db.submissions.find({
        "type": category,
        "user_id": user.id,               # FIXED HERE
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id", 1)

    results = await cursor.to_list(None)
    total = len(results)

    start = (page - 1) * items_per_page
    end = page * items_per_page
    current_items = results[start:end]

    if not current_items:
        await query.edit_message_text(f"No ongoing {category}.")
        return

    # Build item list
    items_list = ""
    for item in current_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown")
        msg_id = item.get("channel_message_id")

        channel_id = str(item.get("channel_id", ""))
        if channel_id.startswith("-100"):
            link = f"https://t.me/c/{channel_id[4:]}/{msg_id}"
        else:
            link = f"{CHANNEL_URL}/{msg_id}"

        emoji = next((k for k, v in RARITY_MAP.items() if v == item.get("rarity_name")), "⭐")
        items_list += f"{emoji} <a href='{link}'>{item['_id']}. {name}</a> ({anime})\n"

    # Pagination
    total_pages = (total + items_per_page - 1) // items_per_page

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⏮ Prev", callback_data=f"view_all_{category}_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ⏭", callback_data=f"view_all_{category}_{page+1}"))

    keyboard = []
    if nav:
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton("⬅ Back", callback_data=f"select_type_{category}"),
        InlineKeyboardButton("🗑 Delete", callback_data="delete")
    ])

    await query.edit_message_text(
        f"<b>💫 All {category.capitalize()} Auctions</b>\n"
        f"Page {page}/{total_pages}\n\n{items_list}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------------------------
# Filter by Rarity
# ------------------------------------------------

async def filter_rarity_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    _, _, category = query.data.split("_")
    user = update.effective_user
    now = datetime.utcnow()

    cursor = db.submissions.find({
        "type": category,
        "user_id": user.id,                # FIXED HERE
        "status": "approved",
        "expires_at": {"$gt": now}
    }, {"rarity_name": 1})

    rarities = {item["rarity_name"] async for item in cursor if item.get("rarity_name")}

    if not rarities:
        await query.edit_message_text(f"<b>No {category} available.</b>", parse_mode="HTML")
        return

    keyboard = []
    row = []

    for emoji, name in RARITY_MAP.items():
        if name in rarities:
            row.append(InlineKeyboardButton(emoji, callback_data=f"select_rarity_{category}_{emoji}_1"))
            if len(row) == 3:
                keyboard.append(row)
                row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅ Back", callback_data=f"select_type_{category}")])

    await query.edit_message_text(
        f"<b>Filter {category.capitalize()} by Rarity</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------------------------
# Rarity Selection
# ------------------------------------------------

async def rarity_selection_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    data = query.data.split("_")

    category = data[2]
    emoji = data[3]
    page = int(data[4])

    rarity_name = RARITY_MAP.get(emoji)
    now = datetime.utcnow()

    cursor = db.submissions.find({
        "type": category,
        "user_id": user.id,                # FIXED HERE
        "rarity_name": rarity_name,
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id")

    results = await cursor.to_list(None)
    total = len(results)
    items_per_page = 10

    start = (page - 1) * items_per_page
    end = page * items_per_page
    current = results[start:end]

    if not current:
        await query.edit_message_text("No items found.")
        return

    items_list = ""
    for item in current:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown")
        msg_id = item.get("channel_message_id")

        channel_id = str(item.get("channel_id", ""))
        if channel_id.startswith("-100"):
            link = f"https://t.me/c/{channel_id[4:]}/{msg_id}"
        else:
            link = f"{CHANNEL_URL}/{msg_id}"

        items_list += f"• <a href='{link}'>{item['_id']}. {name}</a> ({anime})\n"

    total_pages = (total + items_per_page - 1) // items_per_page

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⏮ Prev", callback_data=f"select_rarity_{category}_{emoji}_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("Next ⏭", callback_data=f"select_rarity_{category}_{emoji}_{page+1}"))

    keyboard = []
    if nav:
        keyboard.append(nav)

    keyboard.append([
        InlineKeyboardButton("⬅ Back", callback_data=f"filter_rarity_{category}"),
        InlineKeyboardButton("🗑 Delete", callback_data="delete")
    ])

    await query.edit_message_text(
        f"{emoji} <b>{rarity_name}</b> {category.capitalize()}s\n"
        f"Page {page}/{total_pages}\n\n{items_list}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------------------------
# Back Button
# ------------------------------------------------

async def back_handler(update: Update, context):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    now = datetime.utcnow()

    keyboard = []
    if await db.submissions.count_documents({"type": "waifu", "user_id": user_id, "status": "approved", "expires_at": {"$gt": now}}):
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if await db.submissions.count_documents({"type": "husbando", "user_id": user_id, "status": "approved", "expires_at": {"$gt": now}}):
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    if not keyboard:
        await query.edit_message_text("<b>No ongoing auctions.</b>", parse_mode="HTML")
        return

    await query.edit_message_text(
        "Choose a category:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------------------------
# Delete Button
# ------------------------------------------------

async def delete_menu_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.delete_message()


# ------------------------------------------------
# Handlers Export
# ------------------------------------------------

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

