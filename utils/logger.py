# utils/logger.py
import re
from config import LOG_GROUP_ID

# MarkdownV2 special characters that need escaping
MD2_SPECIAL_CHARS = r'_*[]()~`>#+-=|{}.!'

def escape_markdown(text: str) -> str:
    """
    Escape all MarkdownV2 special characters in the text.
    """
    if not text:
        return ""
    
    # Remove zero-width or invisible characters
    text = re.sub(r'[\u200B\u200C\u200D\uFEFF]', '', text)
    
    # Escape all MarkdownV2 special characters
    return re.sub(f'([{re.escape(MD2_SPECIAL_CHARS)}])', r'\\\1', text)

async def log_user_start(context, log_text: str):
    """
    Send a log message to the LOG_GROUP_ID safely with MarkdownV2 escaping.
    """
    try:
        # Escape entire log text
        safe_text = escape_markdown(log_text)
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=safe_text,
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        # Print raw error for debugging
        print(f"Failed to send log: {e}")
        # Optional: fallback to plain text without MarkdownV2
        await context.bot.send_message(
            chat_id=LOG_GROUP_ID,
            text=log_text
        )