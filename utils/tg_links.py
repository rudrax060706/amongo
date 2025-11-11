def build_user_link(user_or_id, username=None, name=None):
    """
    Returns a clickable HTML link to a Telegram user.
    Works with either a Telegram `User` object or raw ID/username.
    """
    # If a full User object is passed
    if hasattr(user_or_id, "id"):
        user_id = user_or_id.id
        display_name = getattr(user_or_id, "first_name", "User")
    else:
        user_id = user_or_id
        display_name = name or (username if username and username.startswith("@") else f"User {user_id}")

    return f'<a href="tg://user?id={user_id}">{display_name}</a>'