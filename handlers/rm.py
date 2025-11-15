from bson import ObjectId
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.database import db
from config import OWNER_ID, ADMINS, CHANNEL_ID, GROUP_ID


async def rm_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Only owner or admins
    if user_id != OWNER_ID and user_id not in ADMINS:
        return

    # Validate args
    if not context.args:
        await update.message.reply_text("Usage: /rm <item_id1> <item_id2> ...")
        return

    item_ids = []

    # --- Parse BOTH integer ID & ObjectId ---
    for arg in context.args:
        if arg.isdigit():  # integer counter ID
            item_ids.append(int(arg))
        elif ObjectId.is_valid(arg):  # ObjectId
            item_ids.append(ObjectId(arg))
        else:
            await update.message.reply_text(f"⚠️ Invalid ID: {arg}")
            return

    deleted_count = 0

    for item_id in item_ids:
        item = await db.submissions.find_one({"_id": item_id})

        if item:
            # Try deleting messages
            try:
                if item.get("channel_message_id"):
                    await context.bot.delete_message(
                        chat_id=item.get("channel_id", CHANNEL_ID),
                        message_id=item["channel_message_id"]
                    )
                if item.get("group_message_id"):
                    await context.bot.delete_message(
                        chat_id=item.get("group_id", GROUP_ID),
                        message_id=item["group_message_id"]
                    )
            except Exception:
                pass  # ignore Telegram API errors

            # Remove DB entry
            await db.submissions.delete_one({"_id": item_id})
            deleted_count += 1

    # Final response
    if deleted_count > 0:
        await update.message.reply_text(f"✅ Successfully deleted {deleted_count} item(s).")
    else:
        await update.message.reply_text("⚠️ No matching items found.")


def register_remove_handlers(app):
    app.add_handler(CommandHandler("rm", rm_items))
