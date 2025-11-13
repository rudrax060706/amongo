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

    # 2️⃣ Must be in main group
    if chat_id != int(GROUP_ID):
        await update.message.reply_text("⚠️ You can only bid in the main auction group.")
        return

    try:
        item_id = None
        bid_amount = None

        # 3️⃣ Detect item_id (reply or direct)
        if update.message.reply_to_message:
            replied_msg = update.message.reply_to_message
            text_source = replied_msg.caption or replied_msg.text
            if text_source and "🆔 Item ID:" in text_source:
                try:
                    item_id = int(
                        text_source.split("🆔 Item ID:")[1].split("\n")[0].strip()
                    )
                except Exception:
                    pass

            if len(context.args) >= 1:
                try:
                    bid_amount = int(context.args[0])
                except ValueError:
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
            except ValueError:
                await update.message.reply_text("⚠️ Invalid format. Use: /bid <item_id> <amount>")
                return

        if not item_id or not bid_amount:
            await update.message.reply_text(
                "⚠️ Could not determine item ID. Please reply to auction post or use /bid <item_id> <amount>."
            )
            return

        # 4️⃣ Fetch item
        submission = await db.submissions.find_one({"_id": int(item_id)})
        if not submission:
            await update.message.reply_text("❌ Item not found.")
            return

        # Stop bidding on ended/expired items
        if submission.get("is_expired") or submission.get("status") in ["ended", "sold", "cancelled"]:
            await update.message.reply_text("🚫 This auction has already ended.")
            return

        # Prevent self-bidding
        if str(submission.get("user_id")) == str(user.id):
            await update.message.reply_text("🚫 You can’t bid on your own waifu/husbando.")
            return

        # 💰 Bid validity
        current_bid = submission.get("current_bid") or submission.get("base_bid") or 0
        min_next = current_bid + 5
        if bid_amount < min_next:
            await update.message.reply_text(f"⚠️ Minimum next bid is {min_next}.")
            return

        # 🧠 Prepare bidder entry
        previous_bidders = submission.get("previous_bidders", [])
        new_bidder = {
            "id": user.id,
            "username": f"@{user.username}" if user.username else user.first_name,
            "bid": bid_amount,
            "time": datetime.utcnow().isoformat(),
        }
        previous_bidders.append(new_bidder)
        if len(previous_bidders) > 2:
            previous_bidders = previous_bidders[-2:]

        # 🚦 Anti-Race Lock: Update only if current_bid is unchanged
        result = await db.submissions.find_one_and_update(
            {"_id": int(item_id), "current_bid": current_bid},
            {
                "$set": {
                    "previous_bidders": previous_bidders,
                    "current_bid": bid_amount,
                    "last_bidder_id": user.id,
                    "last_bidder_username": new_bidder["username"],
                    "last_bid_time": datetime.utcnow(),
                }
            },
            return_document=False,
        )

        if not result:
            # Another user bid before this one
            latest = await db.submissions.find_one({"_id": int(item_id)})
            await update.message.reply_text(
                f"⚠️ Someone else just placed a higher bid!\n"
                f"💰 Current highest bid: {latest.get('current_bid')}"
            )
            return

        # 🆕 Re-fetch updated data
        updated_submission = await db.submissions.find_one({"_id": int(item_id)})

        # 🖼️ Update post captions
        user_link = build_user_link(user)
        caption = (
            f"🆔 Item ID: {updated_submission.get('_id')}\n"
            f"🎬 Anime: {updated_submission.get('anime_name')}\n"
            f"💞 {updated_submission.get('type', '').capitalize()}: {updated_submission.get('waifu_name')}\n"
            f"💎 Rarity: {updated_submission.get('rarity_name')} {updated_submission.get('rarity')}\n\n"
            f"💰 Base Bid: {updated_submission.get('base_bid')}\n"
            f"🏆 Highest Bid: {bid_amount} by {user_link}"
        )

        bid_url = f"{GROUP_URL}?start=bid_{item_id}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💸 Bid Now", url=bid_url)]])

        # Update Channel Post
        try:
            await context.bot.edit_message_caption(
                chat_id=int(CHANNEL_ID),
                message_id=updated_submission.get("channel_message_id"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            print(f"[Error updating channel post] {e}")

        # Update Group Post
        if updated_submission.get("group_message_id"):
            try:
                await context.bot.edit_message_caption(
                    chat_id=int(GROUP_ID),
                    message_id=updated_submission.get("group_message_id"),
                    caption=caption,
                    parse_mode="HTML",
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
