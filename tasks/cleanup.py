import asyncio
from datetime import datetime
from telegram import InlineKeyboardMarkup
from telegram.error import BadRequest
from utils.database import submissions_collection
from config import CHANNEL_ID


async def remove_expired_bids(bot):
    """
    Periodically removes '💸 Bid Now' buttons from expired submissions in MongoDB.
    If MongoDB is unreachable, it retries without crashing the bot.
    """
    while True:
        try:
            now = datetime.utcnow()

            expired_items = await submissions_collection.find({
                "expires_at": {"$lte": now},
                "is_expired": False
            }).to_list(length=None)

            for item in expired_items:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=int(item.get("channel_id") or CHANNEL_ID),
                        message_id=item["channel_message_id"],
                        reply_markup=InlineKeyboardMarkup([]),
                    )
                except BadRequest:
                    pass  # Message may already be deleted or uneditable

                await submissions_collection.update_one(
                    {"_id": item["_id"]},
                    {"$set": {"is_expired": True}}
                )

        except Exception as e:
            # Catch network/SSL/MongoDB errors
            print(f"⚠️ remove_expired_bids error: {e}")
            # Wait a bit before retrying
            await asyncio.sleep(10)

        # Wait 1 hour before next normal check
        await asyncio.sleep(3600)
