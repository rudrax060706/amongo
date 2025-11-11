import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.database import submissions_collection as db
from config import LOG_GROUP_ID, GROUP_ID
from utils.tg_links import build_user_link


async def check_expired_auctions(bot):
    now = datetime.utcnow()

    expired_items_cursor = db.find({
        "status": "approved",
        "is_expired": {"$ne": True},
        "expires_at": {"$lte": now}
    })

    expired_items = [item async for item in expired_items_cursor]

    if not expired_items:
        print("✅ No expired auctions found.")
        return

    for submission in expired_items:
        item_id = submission.get("_id")
        try:
            print(f"🔍 Processing expired auction ID: {item_id}")

            # === Prepare announcement text ===
            type_name = (submission.get("type") or "Waifu").capitalize()
            rarity_text = f"💎 Rarity: {submission.get('rarity_name', '')} ({submission.get('rarity', '')})"

            owner_id = submission.get("user_id")
            winner_id = submission.get("last_bidder_id")

            owner_link = build_user_link(owner_id, submission.get("username")) if owner_id else "Unknown Seller"
            winner_link = build_user_link(winner_id, submission.get("last_bidder_username")) if winner_id else "No Winner"

            announcement = (
                f"🎉 <b>Auction Ended!</b>\n\n"
                f"💞 <b>{type_name}</b>: <code>{submission.get('waifu_name', '')}</code>\n"
                f"🎬 <b>Anime:</b> <code>{submission.get('anime_name', '')}</code>\n"
                f"{rarity_text}\n\n"
                f"💰 <b>Winning Bid:</b> <code>{submission.get('current_bid', 'N/A')}</code>\n"
                f"👤 <b>Seller:</b> {owner_link}\n"
                f"🏆 <b>Winner:</b> {winner_link}\n\n"
                f"🆔 <b>Item ID:</b> <code>{item_id}</code>"
            )

            optional_tag = submission.get("optional_tag")
            if optional_tag and optional_tag != "—":
                announcement += f"\n{optional_tag}"

            # === Inline buttons ===
            buttons = []
            if owner_id:
                buttons.append(InlineKeyboardButton("👤 Contact Seller", url=f"tg://user?id={owner_id}"))
            if winner_id:
                buttons.append(InlineKeyboardButton("🏆 Contact Winner", url=f"tg://user?id={winner_id}"))
            reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None

            # === 1️⃣ Send to main group ===
            try:
                await bot.send_photo(
                    chat_id=GROUP_ID,
                    photo=submission.get("file_id"),
                    caption=announcement,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except Exception as e:
                print(f"⚠️ Failed to send group announcement for item {item_id}: {e}")

            # === 2️⃣ Edit channel message ===
            channel_message_id = submission.get("channel_message_id")
            channel_id = submission.get("channel_id")
            if channel_message_id and channel_id:
                try:
                    await bot.edit_message_caption(
                        chat_id=channel_id,
                        message_id=channel_message_id,
                        caption=f"{announcement}\n\n⏰ <b>Auction Ended</b>",
                        parse_mode="HTML",
                        reply_markup=None
                    )
                except Exception as e:
                    print(f"⚠️ Failed to edit channel caption for item {item_id}: {e}")

            # === 3️⃣ Notify winner ===
            if winner_id:
                try:
                    winner_msg = (
                        f"🎉 Congratulations {winner_link}!\n\n"
                        f"You’ve <b>won</b> the auction for:\n"
                        f"💞 <b>{type_name}</b>: {submission.get('waifu_name', '')}\n"
                        f"🎬 <b>Anime:</b> {submission.get('anime_name', '')}\n\n"
                        f"💰 <b>Final Bid:</b> <code>{submission.get('current_bid')}</code>\n"
                        f"🆔 <b>Item ID:</b> <code>{item_id}</code>\n\n"
                        f"Please contact the seller for delivery 💎"
                    )
                    await bot.send_message(chat_id=winner_id, text=winner_msg, parse_mode="HTML")
                except Exception as e:
                    print(f"⚠️ Failed to notify winner {winner_id}: {e}")

            # === 4️⃣ Notify seller ===
            if owner_id:
                try:
                    owner_msg = (
                        f"🕊️ Hello {owner_link},\n\n"
                        f"Your auction for <b>{submission.get('waifu_name', '')}</b> has ended!\n"
                        f"🏆 <b>Winner:</b> {winner_link}\n"
                        f"💰 <b>Final Bid:</b> <code>{submission.get('current_bid')}</code>\n\n"
                        f"🆔 <b>Item ID:</b> <code>{item_id}</code>\n"
                        f"You can contact the winner directly."
                    )
                    await bot.send_message(chat_id=owner_id, text=owner_msg, parse_mode="HTML")
                except Exception as e:
                    print(f"⚠️ Failed to notify seller {owner_id}: {e}")

            # === 5️⃣ Log to admin group ===
            if LOG_GROUP_ID:
                try:
                    await bot.send_photo(
                        chat_id=LOG_GROUP_ID,
                        photo=submission.get("file_id"),
                        caption=f"✅ <b>Auction Ended Log</b>\n\n{announcement}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"⚠️ Failed to send log for item {item_id}: {e}")

            # === 6️⃣ Update MongoDB status ===
            await db.update_one(
                {"_id": item_id},
                {"$set": {"is_expired": True, "status": "ended"}}
            )

            print(f"🕒 Auction ended: {submission.get('waifu_name') or submission.get('anime_name')} (ID: {item_id})")
            await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ Error processing auction ID {item_id}: {e}")

    print("✅ Finished processing all expired auctions.")


async def start_expiry_task(bot, interval: int = 5):
    """Run expiry checker every `interval` hours."""
    while True:
        try:
            print(f"⏱️ Checking expired auctions... ({datetime.utcnow().strftime('%H:%M:%S')})")
            await check_expired_auctions(bot)
        except Exception as e:
            print(f"⚠️ Expiry task crashed: {e}")
        await asyncio.sleep(interval * 3600)