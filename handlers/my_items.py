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

def _user_id_filter(user_id):
    # Handles both string/int formats in DB
    return {"$in": [str(user_id), user_id]}

def _build_channel_link(channel_id, msg_id):
    if not channel_id or not msg_id:
        return CHANNEL_URL or ""
    cid = str(channel_id)
    if cid.startswith("-100"):
        return f"https://t.me/c/{cid[4:]}/{msg_id}"
    return f"{CHANNEL_URL}/{msg_id}" if CHANNEL_URL else ""

def _emoji_for_rarity(rarity_name: str):
    for emoji, name in RARITY_MAP.items():
        if name == rarity_name:
            return emoji
    return "⭐"

async def _safe_edit(query, text, **kwargs):
    try:
        await query.edit_message_text(text, **kwargs)
    except:
        try:
            await query.edit_message_caption(caption=text, **kwargs)
        except:
            try:
                await query.message.reply_text(text, **kwargs)
            except:
                pass

async def check_membership(user_id, context):
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

    if await is_globally_banned(user.id):
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return

    if not await check_membership(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
             InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_items")]
        ]
        await update.message.reply_text(
            "<b>⚠️ Join both the group and channel to use this feature.</b>\nTap Try Again after joining.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await show_category_selection(update, context)

# ---------------------------
# Callback handlers
# ---------------------------

async def recheck_items(update, context):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not await check_membership(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
             InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_items")]
        ]
        await _safe_edit(query, "<b>⚠️ You still need to join both group & channel.</b>",
                         parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    await show_category_selection(update, context, from_callback=True)

async def show_category_selection(update, context, from_callback=False):
    user = update.effective_user
    now = datetime.utcnow()
    base_filter = {
        "user_id": _user_id_filter(user.id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    waifu_count = await db.submissions.count_documents({**base_filter, "type": "waifu"})
    husbando_count = await db.submissions.count_documents({**base_filter, "type": "husbando"})

    keyboard = []
    if waifu_count: keyboard.append([InlineKeyboardButton("💖 Waifu", callback_data="select_type_waifu")])
    if husbando_count: keyboard.append([InlineKeyboardButton("💪 Husbando", callback_data="select_type_husbando")])

    text = "Choose a category:" if keyboard else "<b>No ongoing items.</b>"

    if from_callback and update.callback_query:
        await _safe_edit(update.callback_query, text, parse_mode="HTML",
                         reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    else:
        await update.message.reply_text(text, parse_mode="HTML",
                                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def type_selection_handler(update, context):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[2]

    keyboard = [
        [InlineKeyboardButton("🌟 View All", callback_data=f"view_all_{category}_1"),
         InlineKeyboardButton("🎯 Filter by Rarity", callback_data=f"filter_rarity_{category}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]
    await _safe_edit(query, f"<b>Selected category:</b> {category.capitalize()}",
                     parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------------------
# View / Filter Handlers (user-specific)
# ---------------------------

async def view_all_handler(update, context):
    await _list_items(update, context, mode="all")

async def filter_rarity_handler(update, context):
    await _list_items(update, context, mode="filter_rarity")

async def rarity_selection_handler(update, context):
    await _list_items(update, context, mode="rarity")

async def back_handler(update, context):
    await show_category_selection(update, context, from_callback=True)

async def delete_menu_handler(update, context):
    query = update.callback_query
    await query.answer()
    try: await query.delete_message()
    except: pass

# ---------------------------
# Generic item listing
# ---------------------------
async def _list_items(update, context, mode="all"):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data = query.data.split("_")
    category = data[2]
    page = int(data[-1]) if data[-1].isdigit() else 1
    now = datetime.utcnow()

    base_filter = {
        "type": category,
        "user_id": _user_id_filter(user.id),
        "status": "approved",
        "is_expired": False,
        "expires_at": {"$gt": now}
    }

    if mode == "rarity":
        emoji = data[3]
        rarity_name = RARITY_MAP.get(emoji)
        base_filter["rarity_name"] = rarity_name

    cursor = db.submissions.find(base_filter, {
        "waifu_name": 1, "anime_name": 1,
        "channel_message_id": 1, "channel_id": 1,
        "rarity_name": 1, "current_bid": 1, "base_bid": 1
    }).sort("_id", 1)
    results = await cursor.to_list(None)

    if not results:
        await _safe_edit(query, "<b>No items found.</b>", parse_mode="HTML")
        return

    # Pagination
    items_per_page = 10
    total_pages = (len(results) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))
    current_items = results[(page-1)*items_per_page : page*items_per_page]

    items_text = ""
    for item in current_items:
        name = item.get("waifu_name", "Unnamed")
        anime = item.get("anime_name", "Unknown")
        link = _build_channel_link(item.get("channel_id"), item.get("channel_message_id"))
        emoji = _emoji_for_rarity(item.get("rarity_name"))
        bid = item.get("current_bid") or item.get("base_bid") or 0
        items_text += f"{emoji} <a href='{link}'>{item['_id']}. {name}</a> ({anime}) — <b>Current:</b> {bid}\n"

    nav_buttons = []
    if page > 1: nav_buttons.append(InlineKeyboardButton("⏮ Prev", callback_data=f"{data[0]}_{category}_{page-1}"))
    if page < total_pages: nav_buttons.append(InlineKeyboardButton("Next ⏭", callback_data=f"{data[0]}_{category}_{page+1}"))

    keyboard = [nav_buttons] if nav_buttons else []
    keyboard.append([InlineKeyboardButton("⬅ Back", callback_data=f"select_type_{category}"),
                     InlineKeyboardButton("🗑 Delete", callback_data="delete")])

    text_header = f"<b>💫 Your {category.capitalize()} Auctions</b>\nPage {page}/{total_pages}\n\n"
    await _safe_edit(query, text_header + items_text, parse_mode="HTML", disable_web_page_preview=True,
                     reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------------------
# Handlers export
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
