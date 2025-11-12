from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from motor.motor_asyncio import AsyncIOMotorClient
from models.tables import Submission
from config import GROUP_ID, CHANNEL_ID, GROUP_URL, CHANNEL_URL, MONGO_URL, MONGO_DB
from utils.tg_links import build_user_link


# ====== MONGO SETUP ======
client = AsyncIOMotorClient(MONGO_URL)
db = client[MONGO_DB]


# ====== COMMON HELPER FUNCTIONS ======
async def has_started_bot(user_id: int) -> bool:
    """Check if user has a record in users collection"""
    return await db.users.find_one({"id": user_id}) is not None


async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is a member of both group and channel"""
    try:
        member_group = await context.bot.get_chat_member(GROUP_ID, user_id)
        member_channel = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        return (
            member_group.status not in ("left", "kicked") and
            member_channel.status not in ("left", "kicked")
        )
    except Exception:
        return False


async def check_user_status(user_id: int) -> str:
    """Returns 'banned', 'not_started', or 'ok'"""
    banned = await db.global_bans.find_one({"user_id": str(user_id)})
    if banned:
        return "banned"
    if not await has_started_bot(user_id):
        return "not_started"
    return "ok"


# =================== /bid Command ===================
async def bid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # 1️⃣ Check user eligibility
    status = await check_user_status(user.id)
    if status == "banned":
        await update.message.reply_text("🚫 You are globally banned from using this bot.")
        return
    if status == "not_started":
        keyboard = [[InlineKeyboardButton("▶️ Start Bot", url=f"https://t.me/{context.bot.username}?start=1")]]
        await update.message.reply_text(
            "<b>⚠️ You need to start the bot first!</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    if not await is_member(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
             InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_bid")]
        ]
        await update.message.reply_text(
            "<b>⚠️ You must join the main group and channel to place a bid.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 2️⃣ Must be in main group
    if chat_id != int(GROUP_ID):
        await update.message.reply_text("⚠️ You can only bid in the main auction group.")
        return

    try:
        item_id = None
        bid_amount = None

        # 3️⃣ If message is a reply — detect item_id from replied post
        if update.message.reply_to_message:
            replied_msg = update.message.reply_to_message

            # Try to extract item_id from caption or text
            if replied_msg.caption and "🆔 Item ID:" in replied_msg.caption:
                try:
                    item_id = int(replied_msg.caption.split("🆔 Item ID:")[1].split("\n")[0].strip())
                except Exception:
                    pass
            elif replied_msg.text and "🆔 Item ID:" in replied_msg.text:
                try:
                    item_id = int(replied_msg.text.split("🆔 Item ID:")[1].split("\n")[0].strip())
                except Exception:
                    pass

            # Parse bid amount (/bid <amount>)
            if len(context.args) >= 1:
                try:
                    bid_amount = int(context.args[0])
                except ValueError:
                    await update.message.reply_text("⚠️ Invalid amount. Use: /bid <amount>")
                    return

        # 4️⃣ Fallback: /bid <item_id> <amount>
        else:
            if len(context.args) < 2:
                await update.message.reply_text("Usage:\n• Reply: /bid <amount>\n• Or: /bid <item_id> <amount>")
                return

            try:
                item_id = int(context.args[0])
                bid_amount = int(context.args[1])
            except ValueError:
                await update.message.reply_text("⚠️ Invalid format. Use: /bid <item_id> <amount>")
                return

        # ✅ Ensure we have both values
        if not item_id or not bid_amount:
            await update.message.reply_text("⚠️ Could not determine the item ID. Please reply to the auction post or use /bid <item_id> <amount>.")
            return

        # 5️⃣ Fetch item from MongoDB
        submission = await db.submissions.find_one({"id": item_id})
        if not submission:
            await update.message.reply_text("❌ Item not found.")
            return

        # 🚫 Block bidding on ended or expired items
        if submission.get("is_expired") or submission.get("status") in ["ended", "sold", "cancelled"]:
            await update.message.reply_text("🚫 This auction has already ended. You can’t bid anymore.")
            return

        # 🚫 Prevent self-bidding
        if str(submission.get("user_id")) == str(user.id):
            await update.message.reply_text("🚫 You can’t bid on your own waifu/husbando.")
            return

        # 💰 Check bid validity
        current_bid = submission.get("current_bid") or submission.get("base_bid") or 0
        min_next = current_bid + 5
        if bid_amount < min_next:
            await update.message.reply_text(f"⚠️ Minimum next bid is {min_next}.")
            return

        # ✅ Update bidders history
        previous_bidders = submission.get("previous_bidders", [])
        new_bidder = {
            "id": user.id,
            "username": f"@{user.username}" if user.username else user.first_name,
            "bid": bid_amount,
            "time": datetime.utcnow().isoformat()
        }

        previous_bidders.append(new_bidder)
        if len(previous_bidders) > 2:
            previous_bidders = previous_bidders[-2:]

        # Update submission document in MongoDB
        await db.submissions.update_one(
            {"id": item_id},
            {"$set": {
                "previous_bidders": previous_bidders,
                "current_bid": bid_amount,
                "last_bidder_id": user.id,
                "last_bidder_username": new_bidder["username"],
                "last_bid_time": datetime.utcnow()
            }}
        )

        # 6️⃣ Update post captions
        user_link = build_user_link(user)
        caption = (
            f"🆔 Item ID: {submission.get('id')}\n"
            f"🎬 Anime: {submission.get('anime_name')}\n"
            f"💞 {submission.get('type', '').capitalize()}: {submission.get('waifu_name')}\n"
            f"💎 Rarity: {submission.get('rarity_name')} {submission.get('rarity')}\n\n"
            f"💰 Base Bid: {submission.get('base_bid')}\n"
            f"🏆 Highest Bid: {bid_amount} by {user_link}"
        )

        bid_url = f"{GROUP_URL}?start=bid_{item_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💸 Bid Now", url=bid_url)]])

        # Channel post update
        try:
            await context.bot.edit_message_caption(
                chat_id=int(CHANNEL_ID),
                message_id=submission.get("channel_message_id"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            print(f"[Error updating channel post] {e}")

        # Group post update
        if submission.get("group_message_id"):
            try:
                await context.bot.edit_message_caption(
                    chat_id=int(GROUP_ID),
                    message_id=submission.get("group_message_id"),
                    caption=caption,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[Error updating group post] {e}")

        await update.message.reply_text(f"✅ You placed a bid of {bid_amount} on item #{item_id}!")

    except Exception as e:
        print(f"[BID COMMAND ERROR] {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again later.")


# ====== RECHECK CALLBACK ======
async def recheck_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    user = query.from_user
    await query.answer()

    # ✅ Only recheck membership — don’t rerun /bid
    if not await is_member(user.id, context):
        keyboard = [
            [InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
             InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL)],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_bid")]
        ]
        await query.edit_message_text(
            "<b>⚠️ You must join the main group and channel to place a bid.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            "✅ You’ve successfully joined the group and channel!\nYou can now place bids using /bid.",
            parse_mode="HTML"
        )


# ====== HANDLER LIST ======
auction_bid_handlers = [
    CommandHandler("bid", bid_command),
    CallbackQueryHandler(recheck_bid, pattern="^recheck_bid$"),
]
