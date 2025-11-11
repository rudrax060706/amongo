from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from handlers.add_command import is_globally_banned
from utils.database import db  # using Motor (async MongoDB client)
from bson import ObjectId
from config import GROUP_ID, CHANNEL_ID, GROUP_URL, CHANNEL_URL, RARITY_MAP


# ================= HELPER FUNCTIONS =================

async def has_started_bot(user_id: int) -> bool:
    """Check if user has started the bot."""
    user = await db.users.find_one({"id": user_id})
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
    """Check global ban and bot start status. Returns 'banned', 'not_started', or 'ok'."""
    if await db.global_bans.find_one({"user_id": str(user_id)}):
        return "banned"

    if not await has_started_bot(user_id):
        return "not_started"

    return "ok"


# ================= MAIN COMMAND HANDLER =================

async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main /items command."""
    if update.message is None:
        return
    user = update.effective_user

    # 1️⃣ Check global ban and bot start
    status = await check_user_status(user.id)
    if status == "banned":
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return
    if status == "not_started":
        keyboard = [[InlineKeyboardButton("▶️ Start Bot", url=f"https://t.me/{context.bot.username}?start=1")]]
        await update.message.reply_text(
            "<b>⚠️ You need to start the bot first!</b>\nClick below to start.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
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

    # 3️⃣ Show auction categories
    await show_category_selection(update, context)


# ================= TRY AGAIN CALLBACK =================

async def recheck_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggered when user clicks 'Try Again' — only checks membership."""
    query = update.callback_query
    if query is None or query.message is None:
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

    # ✅ User is now a member — show auction categories
    await show_category_selection(update, context, from_callback=True)


# ================= CATEGORY MENU FUNCTION =================

async def show_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False):
    """Displays Waifu / Husbando category options."""
    now = datetime.utcnow()
    waifu_count = await db.submissions.count_documents({
        "type": "waifu",
        "status": "approved",
        "expires_at": {"$gt": now}
    })
    husbando_count = await db.submissions.count_documents({
        "type": "husbando",
        "status": "approved",
        "expires_at": {"$gt": now}
    })

    keyboard = []
    if waifu_count > 0:
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if husbando_count > 0:
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    text = "Choose a category:" if (waifu_count or husbando_count) else "<b>No ongoing auctions available.</b>"

    if from_callback:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )


# ================= TYPE SELECTION =================

async def type_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
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
    if query.message:
        await query.edit_message_text(
            text=f"<b>Selected category:</b> {category.capitalize()}\nChoose how you want to view items:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ================= VIEW ALL HANDLER =================

async def view_all_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
            await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    data = query.data.split("_")
    category = data[2]
    page = int(data[3]) if len(data) > 3 else 1

    now = datetime.utcnow()
    cursor = db.submissions.find({
        "type": category,
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id", 1)

    results = [doc async for doc in cursor]
    total_items = len(results)
    items_per_page = 10
    start = (page - 1) * items_per_page
    end = start + items_per_page
    current_page_items = results[start:end]

    if not current_page_items:
        if query.message:
            await query.edit_message_text(f"No ongoing {category} auctions found.", parse_mode="HTML")
        return

    items_list = ""
    for item in current_page_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown anime")
        message_id = item.get("channel_message_id")
        channel_id = item.get("channel_id")
        if channel_id and str(channel_id).startswith("-100"):
            link = f"https://t.me/c/{str(channel_id)[4:]}/{message_id}"
        else:
            link = f"{CHANNEL_URL}/{message_id}"

        emoji = next((k for k, v in RARITY_MAP.items() if v == item.get("rarity_name")), "⭐")
        items_list += f"{emoji} <a href='{link}'>{item.get('_id')}. {name}</a> ({anime})\n"

    total_pages = (total_items + items_per_page - 1) // items_per_page
    buttons = []
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⏮️ Prev", callback_data=f"view_all_{category}_{page-1}"))
    if end < total_items:
        nav_buttons.append(InlineKeyboardButton("Next ⏭️", callback_data=f"view_all_{category}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"select_type_{category}"),
        InlineKeyboardButton("🗑️ Delete", callback_data="delete")
    ])

    if query.message:
        await query.edit_message_text(
            text=f"<b>💫 All {category.capitalize()} Auctions</b>\nPage {page}/{total_pages}\n\n{items_list}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# ================= FILTER BY RARITY =================

async def filter_rarity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
            await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    _, _, category = query.data.split("_")
    keyboard = [
        [
            InlineKeyboardButton("🔵", callback_data=f"select_rarity_{category}_🔵_1"),
            InlineKeyboardButton("🔴", callback_data=f"select_rarity_{category}_🔴_1"),
            InlineKeyboardButton("🟠", callback_data=f"select_rarity_{category}_🟠_1"),
        ],
        [
            InlineKeyboardButton("🟡", callback_data=f"select_rarity_{category}_🟡_1"),
            InlineKeyboardButton("💮", callback_data=f"select_rarity_{category}_💮_1"),
            InlineKeyboardButton("🔮", callback_data=f"select_rarity_{category}_🔮_1"),
        ],
        [InlineKeyboardButton("🎐", callback_data=f"select_rarity_{category}_🎐_1")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"select_type_{category}")]
    ]
    if query.message:
        await query.edit_message_text(
            text=f"<b>Filter {category.capitalize()} by Rarity:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ================= RARITY SELECTION =================

async def rarity_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
            await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    data = query.data.split("_")
    category = data[2]
    emoji = data[3]
    page = int(data[4]) if len(data) > 4 else 1
    rarity_name = RARITY_MAP.get(emoji, "Unknown")

    now = datetime.utcnow()
    cursor = db.submissions.find({
        "type": category,
        "rarity_name": rarity_name,
        "status": "approved",
        "expires_at": {"$gt": now}
    }).sort("_id", 1)

    results = [doc async for doc in cursor]
    total_items = len(results)
    items_per_page = 10
    start = (page - 1) * items_per_page
    end = start + items_per_page
    current_page_items = results[start:end]

    if not current_page_items:
        if query.message:
            await query.edit_message_text(
                f"No ongoing {category} found with rarity {rarity_name} ({emoji})."
            )
        return

    items_list = ""
    for item in current_page_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown anime")
        message_id = item.get("channel_message_id")
        channel_id = item.get("channel_id")
        if channel_id and str(channel_id).startswith("-100"):
            link = f"https://t.me/c/{str(channel_id)[4:]}/{message_id}"
        else:
            link = f"{CHANNEL_URL}/{message_id}"

        items_list += f"• <a href='{link}'>{item.get('_id')}. {name}</a> ({anime})\n"

    total_pages = (total_items + items_per_page - 1) // items_per_page
    buttons = []
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⏮️ Prev", callback_data=f"select_rarity_{category}_{emoji}_{page-1}"))
    if end < total_items:
        nav_buttons.append(InlineKeyboardButton("Next ⏭️", callback_data=f"select_rarity_{category}_{emoji}_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"select_type_{category}"),
        InlineKeyboardButton("🗑️ Delete", callback_data="delete")
    ])

    if query.message:
        await query.edit_message_text(
            text=f"{emoji} <b>{rarity_name}</b> {category.capitalize()}s\nPage {page}/{total_pages}\n\n{items_list}",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


# ================= BACK & DELETE =================

async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
            await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    now = datetime.utcnow()
    keyboard = []
    if await db.submissions.count_documents({"type": "waifu", "status": "approved", "expires_at": {"$gt": now}}) > 0:
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if await db.submissions.count_documents({"type": "husbando", "status": "approved", "expires_at": {"$gt": now}}) > 0:
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    if not keyboard and query.message:
        await query.edit_message_text("<b>No ongoing auctions available.</b>", parse_mode="HTML")
        return

    if query.message:
        await query.edit_message_text("Choose a category:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delete_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    user = update.effective_user

    if await is_globally_banned(user.id):
        if query.message:
            await query.edit_message_text("🚫 You are globally banned from using this bot.")
        return

    if query.message:
        await query.delete_message()


# ================= HANDLER LIST =================

items_handlers = [
    CommandHandler("items", items_command),
    CallbackQueryHandler(recheck_items, pattern="^recheck_items$"),
    CallbackQueryHandler(type_selection_handler, pattern="^select_type_"),
    CallbackQueryHandler(view_all_handler, pattern="^view_all_"),
    CallbackQueryHandler(filter_rarity_handler, pattern="^filter_rarity_"),
    CallbackQueryHandler(rarity_selection_handler, pattern="^select_rarity_"),
    CallbackQueryHandler(back_handler, pattern="^back$"),
    CallbackQueryHandler(delete_menu_handler, pattern="^delete$"),
]