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
    return await db.users.find_one({"id": user_id}) is not None


async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
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
    banned = await db.global_bans.find_one({"user_id": str(user_id)})
    if banned:
        return "banned"
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

    # Must be member
    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_bid")],
        ]
        await update.message.reply_text(
            "<b>⚠️ You must join the main group and channel to place a bid.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # Must bid inside main group
    if chat_id != int(GROUP_ID):
        await update.message.reply_text("⚠️ You can only bid in the main auction group.")
        return

    try:
        item_id = None
        bid_amount = None

        # 2️⃣ Detect item from reply OR command
        if update.message.reply_to_message:
            replied_msg = update.message.reply_to_message
            text_source = replied_msg.caption or replied_msg.text
            if text_source and "🆔 Item ID:" in text_source:
                try:
                    item_id = int(text_source.split("🆔 Item ID:")[1].split("\n")[0].strip())
                except:
                    pass

            if len(context.args) >= 1:
                try:
                    bid_amount = int(context.args[0])
                except:
                    await update.message.reply_text("⚠️ Invalid amount. Use: /bid <amount>")
                    return
        else:
            if len(context.args) < 2:
                await update.message.reply_text(
                    "Usage:\n• Reply: /bid <amount>\n• Or: /bid <item_id> <amount>"
                )
                return

            try:
                item_id = int(context.args[0])
                bid_amount = int(context.args[1])
            except:
                await update.message.reply_text("⚠️ Invalid format. Use: /bid <item_id> <amount>")
                return

        if not item_id or not bid_amount:
            await update.message.reply_text("⚠️ Could not determine item ID.")
            return

        # 3️⃣ Fetch item
        submission = await db.submissions.find_one({"_id": int(item_id)})
        if not submission:
            await update.message.reply_text("❌ Item not found.")
            return

        if submission.get("is_expired") or submission.get("status") in ["ended", "sold", "cancelled"]:
            await update.message.reply_text("🚫 This auction has already ended.")
            return

        # Prevent self-bidding
        if str(submission.get("user_id")) == str(user.id):
            await update.message.reply_text("🚫 You cannot bid on your own item.")
            return

        # 4️⃣ Proper current bid handling
        db_current = submission.get("current_bid")
        if db_current is None:
            db_current = submission.get("base_bid") or 0

        min_next_bid = db_current + 5

        # Check minimum bid
        if bid_amount < min_next_bid:
            await update.message.reply_text(f"⚠️ Minimum next bid is {min_next_bid}.")
            return

        # 5️⃣ Anti-race condition: update only if current bid hasn't changed
        result = await db.submissions.find_one_and_update(
            {"_id": item_id, "current_bid": submission.get("current_bid")},
            {
                "$set": {
                    "current_bid": bid_amount,
                    "last_bidder_id": user.id,
                    "last_bidder_username": f"@{user.username}" if user.username else user.first_name,
                    "last_bid_time": datetime.utcnow(),
                },
                "$push": {
                    "previous_bidders": {
                        "id": user.id,
                        "username": f"@{user.username}" if user.username else user.first_name,
                        "bid": bid_amount,
                        "time": datetime.utcnow().isoformat(),
                    }
                }
            }
        )

        # ❌ Update failed → someone else bid first
        if not result:
            latest = await db.submissions.find_one({"_id": item_id})
            latest_bid = latest.get("current_bid") or latest.get("base_bid")
            min_next = latest_bid + 5

            await update.message.reply_text(
                f"⚠️ Someone else already placed a higher bid!\n"
                f"💰 Current highest bid: {latest_bid}\n"
                f"➡️ Minimum next bid: {min_next}"
            )
            return

        # 6️⃣ Update success → refresh post
        updated_submission = await db.submissions.find_one({"_id": item_id})

        # Build caption
        user_link = build_user_link(user)
        caption = (
            f"🆔 Item ID: {item_id}\n"
            f"🎬 Anime: {updated_submission.get('anime_name')}\n"
            f"💞 {updated_submission.get('type', '').capitalize()}: {updated_submission.get('waifu_name')}\n"
            f"💎 Rarity: {updated_submission.get('rarity_name')} {updated_submission.get('rarity')}\n\n"
            f"💰 Base Bid: {updated_submission.get('base_bid')}\n"
            f"🏆 Highest Bid: {bid_amount} by {user_link}"
        )

        bid_url = f"{GROUP_URL}?start=bid_{item_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💸 Bid Now", url=bid_url)]])

        # Update channel
        try:
            await context.bot.edit_message_caption(
                chat_id=int(CHANNEL_ID),
                message_id=updated_submission.get("channel_message_id"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            print("Channel update error:", e)

        # Update group
        try:
            await context.bot.edit_message_caption(
                chat_id=int(GROUP_ID),
                message_id=updated_submission.get("group_message_id"),
                caption=caption,
                parse_mode="HTML",
            )
        except Exception as e:
            print("Group update error:", e)

        await update.message.reply_text(f"✅ Your bid of {bid_amount} has been placed!")

    except Exception as e:
        print(f"[BID ERROR] {e}")
        await update.message.reply_text("❌ An error occurred. Try again later.")



# ====== RECHECK CALLBACK ======
async def recheck_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    user = query.from_user
    await query.answer()

    if not await is_member(user.id, context):
        keyboard = [
            [
                InlineKeyboardButton("📣 Join Group", url=GROUP_URL),
                InlineKeyboardButton("📢 Join Channel", url=CHANNEL_URL),
            ],
            [InlineKeyboardButton("🔁 Try Again", callback_data="recheck_bid")],
        ]
        await query.edit_message_text(
            "<b>⚠️ You must join the main group and channel to place a bid.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text(
            "✅ You’ve successfully joined the group and channel!\nYou can now place bids using /bid.",
            parse_mode="HTML",
        )


# ====== HANDLER LIST ======
auction_bid_handlers = [
    CommandHandler("bid", bid_command),
    CallbackQueryHandler(recheck_bid, pattern="^recheck_bid$"),
]
