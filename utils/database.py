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


# utils/database.py
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
    tlsCAFile=certifi.where(),  # <— Critical for Render
    serverSelectionTimeoutMS=5000
)

db = client.get_database("AUCTIONBOT")
submissions_collection = db["submissions"]

async def init_db(retries=5, delay=3):
    for attempt in range(1, retries + 1):
        try:
            await db.command("ping")
            print("✅ MongoDB connected successfully")
            return True
        except Exception as e:
            print(f"⚠️ MongoDB connection attempt {attempt} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
            else:
                raise
