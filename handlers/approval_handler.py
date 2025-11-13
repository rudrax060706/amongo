from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, JobQueue


from utils.database import db  # motor async client from utils/database.py
from models.tables import Submission
from .add_command import safe_split, RARITY_MAP, GROUP_ID, CHANNEL_ID, GROUP_URL
from config import OWNER_ID, ADMINS


# ====== AUTO UNPIN AFTER DELAY ======
async def unpin_after_delay(context: ContextTypes.DEFAULT_TYPE):
    """Automatically unpins the auction post after 3 days."""
    data = context.job.data
    chat_id = int(data.get("chat_id"))
    message_id = int(data.get("message_id"))

    try:
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=message_id)
        print(f"✅ Unpinned message {message_id} in chat {chat_id}")
    except Exception as e:
        err = str(e).lower()
        if "message to unpin not found" in err or "message can't be unpinned" in err:
            print(f"⚠️ Already unpinned or deleted ({message_id})")
        elif "chat not found" in err:
            print(f"⚠️ Chat {chat_id} no longer exists or bot removed.")
        else:
            print(f"[Error unpinning message {message_id}] {e}")


# ====== APPROVAL HANDLER ======
async def approval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    split_data = safe_split(query.data)
    if not isinstance(split_data, list) or len(split_data) < 2:
        return

    action = split_data[0]
    raw_item_id = split_data[1]

    # Validate MongoDB ObjectId
    try:
        item_id = int(raw_item_id)
    except Exception:
        try:
            await query.edit_message_caption(caption="⚠️ Invalid item ID.")
        except Exception:
            pass
        return

    # === Fetch submission ===
    submission = await db.submissions.find_one({"_id": int(submission_id)})
    if not submission:
        try:
            await query.edit_message_caption(caption="⚠️ Submission not found.")
        except Exception:
            pass
        return

    # Admin check
    if query.from_user.id != OWNER_ID and query.from_user.id not in ADMINS:
        await query.answer("🚫 Only the owner or an admin can approve/reject.", show_alert=True)
        return

    # Prevent double action
    if submission.get("status") in ("approved", "rejected"):
        await query.answer(f"⚠️ This item is already {submission['status']}!", show_alert=True)
        return

    type_name = submission.get("type", "item").capitalize()
    status_text = "✅ <b>Approved</b>" if action == "approve" else "❌ <b>Rejected</b>"

    final_caption = (
        f"📩 <b>{type_name} Submission</b>\n\n"
        f"🆔 <b>Item ID:</b> <code>{str(submission['_id'])}</code>\n"
        f"👤 <b>Name:</b> {submission.get('user_name', 'N/A')}\n"
        f"🔗 <b>Username:</b> {submission.get('username', 'N/A')}\n"
        f"🎬 <b>Anime:</b> {submission.get('anime_name', 'N/A')}\n"
        f"💞 <b>{type_name}:</b> {submission.get('waifu_name', 'N/A')}\n"
        f"💎 <b>Rarity:</b> {submission.get('rarity_name', 'N/A')} {submission.get('rarity', '')}\n"
        f"💰 Base Bid: {submission.get('base_bid', 0)}\n\n"
        f"🏷️ <b>Tag:</b> {submission.get('optional_tag', 'N/A')}\n"
        f"⏰ <b>Submitted:</b> {submission.get('submitted_time', datetime.now()).strftime('%d %B %Y • %I:%M %p')}"
    )

    post_link = None

    # ===== APPROVE FLOW =====
    if action == "approve":
        await db.submissions.update_one({"_id": item_id}, {"$set": {"status": "approved"}})

        rarity_text = f"{submission.get('rarity', '')}𝗥𝗔𝗥𝗜𝗧𝗬: {submission.get('rarity_name', '')}"
        new_caption = (
            f"🆔 Item ID: {str(submission['_id'])}\n"
            f"🎬 Anime name: {submission.get('anime_name', '')}\n"
            f"💞 {type_name} name: {submission.get('waifu_name', '')}\n"
            f"{rarity_text}\n\n"
            f"💰 Base Bid: {submission.get('base_bid', 0)}\n\n"
        )
        if submission.get("optional_tag") and submission.get("optional_tag") != "—":
            new_caption += str(submission.get("optional_tag"))

        sent_msg = None
        group_post_link = None

        # === Step 1: Send to group ===
        try:
            group_msg = await context.bot.send_photo(
                chat_id=int(GROUP_ID),
                photo=submission.get("file_id"),
                caption=new_caption,
                parse_mode="HTML",
            )

            await db.submissions.update_one(
                {"_id": item_id},
                {"$set": {"group_message_id": group_msg.message_id}},
            )

            # Pin message
            await context.bot.pin_chat_message(chat_id=int(GROUP_ID), message_id=group_msg.message_id)

            # Build group link
            try:
                group_chat = await context.bot.get_chat(GROUP_ID)
                if getattr(group_chat, "username", None):
                    group_post_link = f"https://t.me/{group_chat.username}/{group_msg.message_id}"
            except Exception as e:
                print(f"[Error building group link] {e}")

            # Schedule unpin after 3 days
            if isinstance(context.job_queue, JobQueue):
                context.job_queue.run_once(
                    unpin_after_delay,
                    when=timedelta(days=3),
                    data={"chat_id": GROUP_ID, "message_id": group_msg.message_id},
                    name=f"unpin_{group_msg.message_id}",
                )
        except Exception as e:
            print(f"[Error sending/pinning in group] {e}")

        # === Step 2: Send to channel ===
        try:
            bid_url = group_post_link if group_post_link else f"{GROUP_URL}?start=bid_{str(item_id)}"
            bid_keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("💸 Bid Now", url=bid_url)]]
            )

            sent_msg = await context.bot.send_photo(
                chat_id=int(CHANNEL_ID),
                photo=submission.get("file_id"),
                caption=new_caption,
                parse_mode="HTML",
                reply_markup=bid_keyboard,
            )
        except Exception as e:
            print(f"[Error sending to channel] {e}")

        # === Step 3: Update submission info ===
        if sent_msg:
            await db.submissions.update_one(
                {"_id": item_id},
                {
                    "$set": {
                        "channel_id": CHANNEL_ID,
                        "channel_message_id": sent_msg.message_id,
                        "expires_at": datetime.utcnow() + timedelta(days=3),
                        "is_expired": False,
                    }
                },
            )

        # === Step 4: Channel post link ===
        try:
            channel_chat = await context.bot.get_chat(CHANNEL_ID)
            if getattr(channel_chat, "username", None) and sent_msg:
                post_link = f"https://t.me/{channel_chat.username}/{sent_msg.message_id}"
        except Exception as e:
            print(f"[Error building channel post link] {e}")

        # === Step 5: Notify user ===
        try:
            user_chat_id = int(submission.get("user_id"))
            user_caption = (
                f"🎉 <b>Your {type_name} has been approved!</b>\n\n"
                f"💎 <b>Rarity:</b> {submission.get('rarity_name')} {submission.get('rarity')}\n"
                f"💞 <b>Name:</b> {submission.get('waifu_name')}\n"
                f"🎬 <b>Anime:</b> {submission.get('anime_name')}"
            )

            await context.bot.send_photo(
                chat_id=user_chat_id,
                photo=submission.get("file_id"),
                caption=user_caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("👉 View Post", url=post_link)]]
                ) if post_link else None,
            )

        except Exception as e:
            print(f"[Error notifying user] {e}")

    # ===== REJECT FLOW =====
    else:
        await db.submissions.update_one({"_id": item_id}, {"$set": {"status": "rejected"}})
        try:
            caption = (
                f"❌ <b>Your {type_name} submission was rejected.</b>\n\n"
                f"🎬 <b>Anime:</b> {submission.get('anime_name', 'N/A')}\n"
                f"💞 <b>{type_name}:</b> {submission.get('waifu_name', 'N/A')}\n"
                f"💎 <b>Rarity:</b> {submission.get('rarity_name', 'N/A')} {submission.get('rarity', '')}\n"
            )
            if submission.get("optional_tag") and submission.get("optional_tag") != "—":
                caption += f"🏷️ <b>Tag:</b> {submission.get('optional_tag')}\n"
            caption += "\nPlease review and try again!"

            await context.bot.send_photo(
                chat_id=int(submission.get("user_id")),
                photo=submission.get("file_id"),
                caption=caption,
                parse_mode="HTML",
            )
        except Exception as e:
            print(f"[Error sending rejection notice] {e}")

    # Update admin caption
    final_caption += f"\n\n{status_text}"
    try:
        await query.edit_message_caption(caption=final_caption, parse_mode="HTML")
    except Exception:
        pass


# ====== HANDLERS ======
approval_handlers = [
    CallbackQueryHandler(approval_handler, pattern="^(approve|reject)_"),
]
