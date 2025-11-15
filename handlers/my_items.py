# myitems.py
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from handlers.add_command import is_globally_banned
from utils.database import db
from config import GROUP_ID, CHANNEL_ID, GROUP_URL, CHANNEL_URL, RARITY_MAP

# ---------------------------
# Helpers
# ---------------------------

def _owner_match_values(user_id: int):
    return {"$in": [user_id, str(user_id)]}


def _build_channel_link(channel_id, msg_id):
    try:
        cid = str(channel_id)
        if not cid:
            return None
        if cid.startswith("-100"):
            return f"https://t.me/c/{cid[4:]}/{msg_id}"
        if CHANNEL_URL:
            return f"{CHANNEL_URL}/{msg_id}"
        return None
    except Exception:
        return None


def _emoji_for_rarity(rarity_name: str):
    for emoji, name in RARITY_MAP.items():
        if name == rarity_name:
            return emoji
    return "⭐"


async def _safe_edit_text(query, text, **kwargs):
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception:
        try:
            await query.edit_message_caption(caption=text, **kwargs)
        except Exception:
            try:
                await query.message.reply_text(text, **kwargs)
            except Exception:
                pass


# ---------------------------
# Membership checker
# ---------------------------

async def check_membership(user_id, context):
    """Checks if user is in BOTH group & channel."""
    try:
        await context.bot.get_chat_member(GROUP_ID, user_id)
        await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return True
    except:
        return False


# ---------------------------
# /myitems entry
# ---------------------------

async def items_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user

    # global ban check
    if await is_globally_banned(user.id):
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return

    # membership check (REPLACED is_member)
    if not await check_membership(user.id, context):
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

    await show_category_selection(update, context)


# recheck (Try Again) button
async def recheck_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await check_membership(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_items")],
        ]
        await _safe_edit_text(
            query,
            "<b>⚠️ You still need to join both the group and channel.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    await show_category_selection(update, context, from_callback=True)


# show category selection (waifu / husbando)
async def show_category_selection(update: Update, context, from_callback=False):
    user = update.effective_user
    user_id = user.id
    now = datetime.utcnow()

    base_filter = {
        "user_id": _owner_match_values(user_id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    waifu_count = await db.submissions.count_documents({**base_filter, "type": "waifu"})
    husbando_count = await db.submissions.count_documents({**base_filter, "type": "husbando"})

    keyboard = []
    if waifu_count > 0:
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if husbando_count > 0:
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    text = "Choose a category:" if keyboard else "<b>You have no ongoing items.</b>"

    if from_callback and update.callback_query:
        await _safe_edit_text(
            update.callback_query,
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
        )


# type selection handler
async def type_selection_handler(update, context):
    query = update.callback_query
    await query.answer()
    _, _, category = query.data.split("_")

    keyboard = [
        [
            InlineKeyboardButton("🌟 View All", callback_data=f"view_all_{category}_1"),
            InlineKeyboardButton("🎯 Filter by Rarity", callback_data=f"filter_rarity_{category}")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    await _safe_edit_text(
        query,
        f"<b>Selected category:</b> {category.capitalize()}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# view all items
async def view_all_handler(update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    data = query.data.split("_")
    category = data[2]
    page = int(data[3]) if len(data) > 3 else 1
    now = datetime.utcnow()

    base_filter = {
        "type": category,
        "user_id": _owner_match_values(user.id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    cursor = db.submissions.find(base_filter, {
        "waifu_name": 1, "anime_name": 1, "channel_message_id": 1,
        "channel_id": 1, "rarity_name": 1, "current_bid": 1, "base_bid": 1
    }).sort("_id", 1)

    results = await cursor.to_list(None)
    total = len(results)

    if total == 0:
        await _safe_edit_text(query, f"No ongoing {category}.", parse_mode="HTML")
        return

    items_per_page = 10
    total_pages = (total + items_per_page - 1) // items_per_page

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * items_per_page
    end = page * items_per_page
    current_items = results[start:end]

    items_list = ""
    for item in current_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown")
        msg_id = item.get("channel_message_id")
        channel_id = item.get("channel_id")
        link = _build_channel_link(channel_id, msg_id) or CHANNEL_URL or ""

        emoji = _emoji_for_rarity(item.get("rarity_name"))
        current_bid = item.get("current_bid") or item.get("base_bid") or 0

        items_list += f"{emoji} <a href='{link}'>{item['_id']}. {name}</a> ({anime}) — <b>Current:</b> {current_bid}\n"

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⏮ Prev", callback_data=f"view_all_{category}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ⏭", callback_data=f"view_all_{category}_{page+1}"))

    keyboard = []
    if nav:
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton("⬅ Back", callback_data=f"select_type_{category}"),
        InlineKeyboardButton("🗑 Delete", callback_data="delete")
    ])

    text = (
        f"<b>💫 Your {category.capitalize()} Auctions</b>\n"
        f"Page {page}/{total_pages}\n\n{items_list}"
    )

    await _safe_edit_text(
        query,
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# filter by rarity
async def filter_rarity_handler(update, context):
    query = update.callback_query
    await query.answer()
    _, _, category = query.data.split("_")
    user = update.effective_user
    now = datetime.utcnow()

    base_filter = {
        "type": category,
        "user_id": _owner_match_values(user.id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    cursor = db.submissions.find(base_filter, {"rarity_name": 1})
    rarities = {item["rarity_name"] async for item in cursor if item.get("rarity_name")}

    if not rarities:
        await _safe_edit_text(query, f"<b>No {category} available.</b>", parse_mode="HTML")
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

    await _safe_edit_text(
        query,
        f"<b>Filter {category.capitalize()} by Rarity</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# rarity selection
async def rarity_selection_handler(update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    data = query.data.split("_")
    category = data[2]
    emoji = data[3]
    page = int(data[4]) if len(data) > 4 else 1
    rarity_name = RARITY_MAP.get(emoji)
    now = datetime.utcnow()

    base_filter = {
        "type": category,
        "user_id": _owner_match_values(user.id),
        "rarity_name": rarity_name,
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    cursor = db.submissions.find(base_filter, {
        "waifu_name": 1, "anime_name": 1, "channel_message_id": 1,
        "channel_id": 1, "current_bid": 1, "base_bid": 1
    }).sort("_id", 1)

    results = await cursor.to_list(None)
    total = len(results)
    if total == 0:
        await _safe_edit_text(query, "No items found.", parse_mode="HTML")
        return

    items_per_page = 10
    total_pages = (total + items_per_page - 1) // items_per_page
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * items_per_page
    end = page * items_per_page
    current = results[start:end]

    items_list = ""
    for item in current:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown")
        msg_id = item.get("channel_message_id")
        channel_id = item.get("channel_id")
        link = _build_channel_link(channel_id, msg_id) or CHANNEL_URL or ""
        current_bid = item.get("current_bid") or item.get("base_bid") or 0
        items_list += f"• <a href='{link}'>{item['_id']}. {name}</a> ({anime}) — <b>Current:</b> {current_bid}\n"

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⏮ Prev", callback_data=f"select_rarity_{category}_{emoji}_{page-1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ⏭", callback_data=f"select_rarity_{category}_{emoji}_{page+1}"))

    keyboard = []
    if nav:
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton("⬅ Back", callback_data=f"filter_rarity_{category}"),
        InlineKeyboardButton("🗑 Delete", callback_data="delete")
    ])

    await _safe_edit_text(
        query,
        f"{emoji} <b>{rarity_name}</b> {category.capitalize()}s\nPage {page}/{total_pages}\n\n{items_list}",
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# back handler
async def back_handler(update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    now = datetime.utcnow()

    base_filter = {
        "user_id": _owner_match_values(user.id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    keyboard = []
    if await db.submissions.count_documents({**base_filter, "type": "waifu"}):
        keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if await db.submissions.count_documents({**base_filter, "type": "husbando"}):
        keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    if not keyboard:
        await _safe_edit_text(query, "<b>No ongoing auctions.</b>", parse_mode="HTML")
        return

    await _safe_edit_text(
        query,
        "Choose a category:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# delete
async def delete_menu_handler(update, context):
    query = update.callback_query
    await query.answer()
    try:
        await query.delete_message()
    except Exception:
        pass


# handlers export
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
