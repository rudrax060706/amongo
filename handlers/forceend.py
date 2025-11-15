import asyncio
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from utils.database import db
from config import LOG_GROUP_ID, GROUP_ID, ADMINS, OWNER_ID
from utils.tg_links import build_user_link


async def forceend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Admin check
    if user.id not in ADMINS and user.id != OWNER_ID:
        return

    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: /forceend <item_id>")
        return

    item_id_raw = context.args[0]

    # --- Detect integer counter ID or ObjectId ---
    if item_id_raw.isdigit():
        item_id = int(item_id_raw)
    elif ObjectId.is_valid(item_id_raw):
        item_id = ObjectId(item_id_raw)
    else:
        await update.message.reply_text("❌ Invalid Item ID format.")
        return

    try:
        submission = await db.submissions.find_one({"_id": item_id})
        if not submission:
            await update.message.reply_text("❌ No item found with that ID.")
            return

        if submission.get("status") not in ["approved"]:
            await update.message.reply_text("⚠️ This auction is not active or already ended.")
            return

        # --- Stop auction immediately ---
        await db.submissions.update_one(
            {"_id": item_id},
            {"$set": {
                "is_expired": True,
                "status": "ended",
                "expires_at": datetime.utcnow(),
            }}
        )

        type_name = submission.get("type", "Waifu").capitalize()
        rarity_text = f"💎 Rarity: {submission.get('rarity_name', '')} ({submission.get('rarity', '')})"

        owner_link = (
            build_user_link(submission.get("user_id"), submission.get("username"))
            if submission.get("user_id") else "Unknown Seller"
        )
        winner_link = (
            build_user_link(submission.get("last_bidder_id"), submission.get("last_bidder_username"))
            if submission.get("last_bidder_id") else "No Winner"
        )

        announcement = (
            f"🚨 <b>Auction Force-Ended by Admin!</b>\n\n"
            f"💞 <b>{type_name}</b>: <code>{submission.get('waifu_name', '')}</code>\n"
            f"🎬 <b>Anime:</b> <code>{submission.get('anime_name', '')}</code>\n"
            f"{rarity_text}\n\n"
            f"💰 <b>Winning Bid:</b> <code>{submission.get('current_bid', 'N/A')}</code>\n"
            f"👤 <b>Seller:</b> {owner_link}\n"
            f"🏆 <b>Winner:</b> {winner_link}\n\n"
            f"🆔 <b>Item ID:</b> <code>{str(submission.get('_id'))}</code>\n"
            f"🛑 <i>Ended manually by admin {build_user_link(user.id, user.username)}</i>"
        )

        # --- Buttons ---
        buttons = []
        if submission.get("user_id"):
            buttons.append(InlineKeyboardButton("👤 Contact Seller", url=f"tg://user?id={submission['user_id']}"))
        if submission.get("last_bidder_id"):
            buttons.append(InlineKeyboardButton("🏆 Contact Winner", url=f"tg://user?id={submission['last_bidder_id']}"))
        reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None

        # === 1️⃣ Send announcement to group ===
        await context.bot.send_photo(
            chat_id=GROUP_ID,
            photo=submission.get("file_id"),
            caption=announcement,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

        # === 2️⃣ Edit channel post ===
        if submission.get("channel_message_id"):
            try:
                await context.bot.edit_message_caption(
                    chat_id=submission.get("channel_id"),
                    message_id=submission.get("channel_message_id"),
                    caption=f"{announcement}\n\n⏰ <b>Auction Force-Ended by Admin</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Failed to edit channel caption: {e}")

        # === 3️⃣ Notify winner ===
        if submission.get("last_bidder_id"):
            try:
                msg = (
                    f"⚠️ <b>Admin Notice</b>\n\n"
                    f"Your auction win for <b>{submission.get('waifu_name', '')}</b> "
                    f"was force-ended by admin.\n"
                    f"💰 Final Bid: <code>{submission.get('current_bid', 'N/A')}</code>\n"
                    f"🆔 Item ID: <code>{str(submission.get('_id'))}</code>"
                )
                await context.bot.send_message(
                    chat_id=submission["last_bidder_id"],
                    text=msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Failed to notify winner: {e}")

        # === 4️⃣ Notify seller ===
        if submission.get("user_id"):
            try:
                msg = (
                    f"🕊️ <b>Your auction has been force-ended by admin.</b>\n\n"
                    f"💞 <b>{submission.get('waifu_name', '')}</b>\n"
                    f"🏆 Winner: {winner_link}\n"
                    f"💰 Final Bid: <code>{submission.get('current_bid', 'N/A')}</code>"
                )
                await context.bot.send_message(
                    chat_id=submission["user_id"],
                    text=msg,
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Failed to notify seller: {e}")

        # === 5️⃣ Log in admin group ===
        if LOG_GROUP_ID:
            try:
                await context.bot.send_photo(
                    chat_id=LOG_GROUP_ID,
                    photo=submission.get("file_id"),
                    caption=f"🛑 <b>Force-End Log</b>\n\n{announcement}",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"⚠️ Failed to send log: {e}")

        await update.message.reply_text(
            f"✅ Auction ID <code>{str(submission.get('_id'))}</code> force-ended successfully!",
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"❌ Force end failed: {e}")
        await update.message.reply_text("❌ Something went wrong while ending this auction.")


def forceend_handler():
    return CommandHandler("forceend", forceend_command)
