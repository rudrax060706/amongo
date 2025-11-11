from bson import ObjectId
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.database import db
from config import OWNER_ID, ADMINS, CHANNEL_ID, GROUP_ID


# ========== REMOVE ITEMS COMMAND ==========
async def rm_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Only allow owner or admins
    if user_id != OWNER_ID and user_id not in ADMINS:
        return

    # Validate command arguments
    if not context.args:
        await update.message.reply_text("Usage: /rm <item_id1> <item_id2> ...")
        return

    # Parse and validate MongoDB ObjectIds
    item_ids = []
    for arg in context.args:
        try:
            item_ids.append(ObjectId(arg))
        except Exception:
            await update.message.reply_text(f"⚠️ Invalid ObjectId: {arg}")
            return

    deleted_count = 0

    for item_id in item_ids:
        item = await db.submissions.find_one({"_id": item_id})
        if item:
            # Try deleting messages from channel and group
            try:
                if item.get("channel_message_id"):
                    await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=item["channel_message_id"])
                if item.get("group_message_id"):
                    await context.bot.delete_message(chat_id=GROUP_ID, message_id=item["group_message_id"])
            except Exception:
                # Ignore Telegram API errors (message already deleted, etc.)
                pass

            # Delete from MongoDB
            await db.submissions.delete_one({"_id": item_id})
            deleted_count += 1

    if deleted_count > 0:
        await update.message.reply_text(f"✅ Successfully deleted {deleted_count} item(s).")
    else:
        await update.message.reply_text("⚠️ No matching items found.")


# ========== REGISTER HANDLER ==========
def register_remove_handlers(app):
    app.add_handler(CommandHandler("rm", rm_items))