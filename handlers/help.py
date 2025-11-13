from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from config import OWNER_ID, ADMINS, GROUP_URL, CHANNEL_URL

# ================= USER & ADMIN COMMANDS =================
USER_COMMANDS = [
    ("/start", "Start the bot and see the welcome message"),
    ("/add", "Add a new Waifu/Husbando to the auction"),
    ("/items", "View all active auction items"),
    ("/myitems", "View your submitted items"),
    ("/bid &lt;item_id&gt; &lt;amount&gt;", "Place a bid on an item"),
    ("/help", "Show all available commands"),
]

ADMIN_COMMANDS = [
    ("/aban &lt;user_id&gt; &lt;reason&gt;", "Globally ban a user"),
    ("/unaban &lt;user_id&gt;", "Unban a globally banned user"),
    ("/forceend &lt;item_id&gt;", "Force-end an auction manually"),
    ("/rm &lt;item_id(s)&gt;", "Remove one or multiple items by ID"),
]

# ================= HELPER FUNCTION =================
def format_commands(commands):
    """Format a list of (command, description) tuples into HTML text."""
    return "\n".join(f"• <b>{cmd}</b> — {desc}" for cmd, desc in commands)


# ================= /HELP COMMAND =================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name

    # Check if the user is admin or owner
    is_admin = user_id == OWNER_ID or user_id in ADMINS

    # Header
    text = f"👋 Hello <b>{first_name}</b>!\n\nHere are the available commands:\n\n"

    # User Commands
    text += "<b>🧑‍💻 User Commands:</b>\n"
    text += format_commands(USER_COMMANDS)

    # Admin Commands (only for admins)
    if is_admin:
        text += "\n\n<b>🛡️ Admin Commands:</b>\n"
        text += format_commands(ADMIN_COMMANDS)

    # Auction Rules
    text += (
        "\n\n<b>📜 Auction Rules:</b>\n"
        "1️⃣ After adding a <b>Waifu/Husbando</b> to auction, it will be sent for approval.\n"
        "   Approval is granted <b>only after</b> you give your Waifu/Husbando to <b>@Nagi_seishiro007</b> in the main group.\n\n"
        "2️⃣ The <b>winner</b> will receive the Waifu/Husbando from admin <b>after paying extols</b> to the seller.\n\n"
        "3️⃣ The <b>seller remains hidden</b> until the end of the auction.\n\n"
        "4️⃣ The <b>auction automatically ends after 3 days</b> once approved.\n\n"
        "5️⃣ <b>Bid only if you can afford</b> — bids <b>cannot be cancelled</b> once placed.\n\n"
        "6️⃣ Do not send the <b>same Waifu/Husbando</b> for approval if it’s already in auction.\n"
    )

    # Buttons for group/channel
    keyboard = [
        [InlineKeyboardButton("📢 Channel", url=CHANNEL_URL)],
        [InlineKeyboardButton("💬 Group", url=GROUP_URL)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Reply safely (handle group/private chat)
    try:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        await context.bot.send_message(chat_id=user.id, text=text, parse_mode="HTML", reply_markup=reply_markup)


# ================= HANDLER REGISTRATION =================
help_handler = CommandHandler("help", help_command)
