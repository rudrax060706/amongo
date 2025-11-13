# utils/id_generator.py
from utils.database import db

async def get_next_sequence(name: str) -> int:
    """Generate an auto-increment ID for a collection (like MySQL AUTO_INCREMENT)."""
    result = await db["counters"].find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return result["seq"]
