from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.database import db
from config import OWNER_ID, ADMINS


# ================= /STATUS COMMAND =================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Allow only Owner or Admins
    if user_id != OWNER_ID and user_id not in ADMINS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    text_msg = "📊 <b>System Status Overview</b>\n\n"

    # ================= MONGODB CONNECTION =================
    try:
        await db.command("ping")
        mongo_status = "✅ Connected"
    except Exception:
        mongo_status = "❌ Disconnected"

    # ================= BOT STATUS =================
    bot_status = "✅ Running"

    # ================= USER STATS =================
    try:
        active_users = await db.users.count_documents({"is_banned": {"$ne": True}})
        inactive_users = await db.users.count_documents({"is_banned": True})
    except Exception:
        active_users = "⚠️ Error"
        inactive_users = "⚠️ Error"

    # ================= AUCTION STATS =================
    try:
        active_auctions = await db.submissions.count_documents({"status": "active"})
        inactive_auctions = await db.submissions.count_documents({"status": "ended"})
    except Exception:
        active_auctions = "⚠️ Error"
        inactive_auctions = "⚠️ Error"

    # ================= ITEM STATS =================
    try:
        active_items = await db.submissions.count_documents({"status": "active"})
        pending_items = await db.submissions.count_documents({"status": "pending"})
    except Exception:
        active_items = "⚠️ Error"
        pending_items = "⚠️ Error"

    # ================= TIMESTAMP =================
    last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ================= BUILD MESSAGE =================
    text_msg += (
        f"🧑‍💻 <b>Active Users:</b> {active_users}\n"
        f"😴 <b>Inactive/Banned Users:</b> {inactive_users}\n\n"
        f"🏷️ <b>Active Auctions:</b> {active_auctions}\n"
        f"💤 <b>Inactive Auctions:</b> {inactive_auctions}\n\n"
        f"📦 <b>Active Items:</b> {active_items}\n"
        f"⏳ <b>Pending Items:</b> {pending_items}\n\n"
        f"🧩 <b>MongoDB Status:</b> {mongo_status}\n"
        f"🤖 <b>Bot Status:</b> {bot_status}\n"
        f"🕒 <b>Last Update:</b> {last_update}\n"
    )

    await update.message.reply_text(text_msg, parse_mode="HTML")


# ================= HANDLER REGISTRATION =================
status_handler = CommandHandler("status", status_command)