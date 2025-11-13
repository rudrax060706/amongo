import asyncio
import nest_asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from telegram.ext import ApplicationBuilder, CommandHandler , MessageHandler, filters

# Configuration and Utilities
from config import BOT_TOKEN
from utils.database import db  # MongoDB client
from utils.database import init_db  # type: ignore

# Handlers
from handlers.start_handler import start_command
from handlers.add_command import add_handlers
from handlers.photo_handler import photo_handlers
from handlers.bid_handler import bid_handlers
from handlers.approval_handler import approval_handlers
from handlers.auction_bid import auction_bid_handlers
from handlers.item_command import items_handlers
from handlers.my_items import myitems_handlers
from handlers.global_ban import aban, unaban
from handlers.rm import register_remove_handlers
from handlers.forceend import forceend_handler
from handlers.status import status_handler
from handlers.help import help_handler
from handlers.get_file_id import get_file_id
# Background Tasks (MongoDB-compatible)
from tasks.cleanup import remove_expired_bids
from tasks.auction_expiry import start_expiry_task


# ============================================================
# ✅ HEALTH CHECK SERVER (to keep Render service alive)
# ============================================================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def start_healthcheck_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 Healthcheck server running on port {port}")
    server.serve_forever()


# ============================================================
# ✅ MAIN BOT INITIALIZATION
# ============================================================
async def main():
    print("🔄 Initializing MongoDB...")
    await init_db()
    print("✅ MongoDB connected successfully.")

    # Create bot application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ================== 1️⃣ BASIC COMMANDS ==================
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(help_handler)
    app.add_handler(CommandHandler("aban", aban))
    app.add_handler(CommandHandler("unaban", unaban))
    app.add_handler(status_handler)
    app.add_handler(forceend_handler())
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, get_file_id))
    # ================== 2️⃣ COMBINED SPECIALIZED HANDLERS ==================
    all_specialized_handlers = (
        add_handlers +
        photo_handlers +
        bid_handlers +
        approval_handlers +
        auction_bid_handlers +
        items_handlers +
        myitems_handlers
    )
    for handler in all_specialized_handlers:
        app.add_handler(handler)

    # ================== 3️⃣ PING COMMAND ==================
    async def ping(update, context):
        await update.message.reply_text("🏓 Pong!")
    app.add_handler(CommandHandler("ping", ping))

    # ================== 4️⃣ REMOVE HANDLERS ==================
    register_remove_handlers(app)

    # ================== 5️⃣ BACKGROUND TASKS ==================
    asyncio.create_task(remove_expired_bids(app.bot))
    asyncio.create_task(start_expiry_task(app.bot, 1))

    print("🤖 Bot is running...")
    await app.run_polling()


# ============================================================
# ✅ ENTRY POINT
# ============================================================
if __name__ == "__main__":
    nest_asyncio.apply()

    # Start fake web server in background for Render
    threading.Thread(target=start_healthcheck_server, daemon=True).start()

    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("❌ Bot stopped by user.")
    except Exception as e:
        print(f"⚠️ Unexpected error: {e}")
