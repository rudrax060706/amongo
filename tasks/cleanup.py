# tasks/remove_expired_bids.py
import asyncio
from datetime import datetime
from telegram import InlineKeyboardMarkup
from telegram.error import BadRequest
from utils.database import submissions_collection
from config import CHANNEL_ID  # fallback channel id if needed


async def remove_expired_bids(bot):
    """
    Periodically removes '💸 Bid Now' buttons from expired submissions in MongoDB.
    """
    while True:
        now = datetime.utcnow()

        # Find all expired submissions that haven't been marked yet
        expired_items = await submissions_collection.find({
            "expires_at": {"$lte": now},
            "is_expired": False
        }).to_list(length=None)

        for item in expired_items:
            try:
                # Remove inline buttons
                await bot.edit_message_reply_markup(
                    chat_id=int(item.get("channel_id") or CHANNEL_ID),
                    message_id=item["channel_message_id"],
                    reply_markup=InlineKeyboardMarkup([]),
                )
            except BadRequest:
                # Message might already be deleted or uneditable
                pass

            # Mark as expired in MongoDB
            await submissions_collection.update_one(
                {"_id": item["_id"]},
                {"$set": {"is_expired": True}}
            )

        # Wait 1 hour before next check
        await asyncio.sleep(3600)