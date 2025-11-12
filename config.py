import os
from telegram.helpers import escape_markdown
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID"))
GROUP_ID = int(os.getenv("GROUP_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",")]

MONGO_URL = os.getenv("DATABASE_URL") 
MONGO_DB = os.getenv("")
GROUP_URL = os.getenv("GROUP_URL")
CHANNEL_URL = os.getenv("CHANNEL_URL")
SUPPORT_GROUP_URL = os.getenv("SUPPORT_GROUP_URL")
WELCOME_VIDEO_ID = os.getenv("WELCOME_VIDEO_ID")

WELCOME_MESSAGE_RAW = (
    "💎 Gʀᴇᴇᴛɪɴɢs, I'ᴍ ˹Tʜᴇ Pʜᴀɴᴛᴏᴍ Tʀᴏᴜᴘᴇ Aᴜᴄᴛɪᴏɴ Bᴏᴛ˼ 🕊️ ɴɪᴄᴇ ᴛᴏ ᴍᴇᴇᴛ ʏᴏᴜ!\n"
    "━━━━━━━▧▣▧━━━━━━━\n"
    "⦾ Tᴏ ᴜsᴇ ᴍᴇ: Jᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴀɴᴅ ᴄʜᴀɴɴᴇʟ\n"
    "⦾ Wʜᴀᴛ I ᴅᴏ: I ʜᴏsᴛ ʟɪᴠᴇ ᴀᴜᴄᴛɪᴏɴs ᴡʜᴇʀᴇ ᴜsᴇʀs ʙɪᴅ ᴛᴏ ᴡɪɴ Hᴜsʙᴀɴᴅᴏ ᴀɴᴅ Wᴀɪғᴜs\n"
    "⦾ Tʜɪɴᴋ ғᴀsᴛ, ʙɪᴅ ғᴀsᴛᴇʀ — ᴛʀᴇᴀsᴜʀᴇs ᴅᴏɴ’ᴛ ᴡᴀɪᴛ!\n"
    "━━━━━━━▧▣▧━━━━━━━"
)

WELCOME_MESSAGE = escape_markdown(WELCOME_MESSAGE_RAW, version=2)

RARITY_MAP = {
    "🔵": "Common",
    "🔴": "Medium",
    "🟠": "Rare",
    "🟡": "Legendary",
    "💮": "Exclusive",
    "🔮": "Limited",
    "🎐": "Celestial",
}
