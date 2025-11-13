# import os
# from sqlalchemy import create_engine
# from sqlalchemy.orm import declarative_base, sessionmaker
# from config import DATABASE_URL

# # Detect if using SQLite
# is_sqlite = DATABASE_URL.startswith("sqlite")

# # Create engine depending on DB type
# if is_sqlite:
#     engine = create_engine(
#         DATABASE_URL,
#         connect_args={"check_same_thread": False},
#         echo=False
#     )
# else:
#     engine = create_engine(
#         DATABASE_URL,
#         pool_pre_ping=True,  # keeps MySQL connections stable
#         echo=False,
#         future=True
#     )

# # Define Base and session
# Base = declarative_base()
# SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# # Auto-create all tables
# def init_db():
#     # Import all models that define tables
#     from models.tables import Submission
#     Base.metadata.create_all(bind=engine)
#     print("✅ Database initialized successfully!")


from motor.motor_asyncio import AsyncIOMotorClient
import certifi
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

client = AsyncIOMotorClient(
    MONGO_URL,
    tls=True,
    tlsCAFile=certifi.where(),  # Important for secure connection
    serverSelectionTimeoutMS=5000
)

db = client.get_database("AUCTIONBOT")
submissions_collection = db["submissions"]
counters_collection = db["counters"]


# ====== CONNECTION CHECK ======
async def init_db(retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            await db.command("ping")
            print("✅ MongoDB connected successfully")
            # 🔹 Ensure the counter document exists on first connection
            await ensure_counter_exists()
            return True
        except Exception as e:
            print(f"⚠️ MongoDB connection attempt {attempt} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise


# ====== COUNTER SETUP ======
async def ensure_counter_exists():
    """
    Ensures the counter document for submissions exists.
    Creates it if it doesn't.
    """
    existing = await counters_collection.find_one({"_id": "submission_id"})
    if not existing:
        await counters_collection.insert_one({
            "_id": "submission_id",
            "sequence_value": 0
        })
        print("🆕 Created initial counter document for submissions.")
    else:
        print("ℹ️ Counter document already exists.")


# ====== AUTO-INCREMENT FUNCTION ======
async def get_next_sequence(name: str):
    """
    Generates auto-increment numeric ID (1, 2, 3...) for any collection.
    Example: await get_next_sequence("submission_id")
    """
    counter = await counters_collection.find_one_and_update(
        {"_id": name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=True
    )
    return counter["sequence_value"]
