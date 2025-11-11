# # models/submission.py
# from sqlalchemy import Column, Integer, String, DateTime, Boolean , BigInteger , JSON
# from utils.database import Base
# from datetime import datetime, timedelta

# class Submission(Base):
#     __tablename__ = "Submission"

#     id = Column(Integer, primary_key=True, index=True , autoincrement=True)
#     user_id = Column(String(50))
#     user_name = Column(String(100))
#     username = Column(String(100))
#     type = Column(String(50))
#     rarity = Column(String(10))
#     rarity_name = Column(String(50))
#     anime_name = Column(String(200))
#     waifu_name = Column(String(200))
#     optional_tag = Column(String(200))
#     caption = Column(String(1000))
#     file_id = Column(String(200))
#     submitted_time = Column(DateTime, default=datetime.utcnow)
#     status = Column(String(20), default="pending")
#     base_bid = Column(Integer, nullable=True)
#     channel_id = Column(String, nullable=True)
#     previous_bidders = Column(JSON, default=[])
#     # === NEW FIELDS ===
#     # Channel message ID where the post was sent (used to edit later)
#     channel_message_id = Column(Integer, nullable=True)
#     group_message_id = Column(Integer , nullable=True)
#     # When the bid should expire (3 days after posting)
#     expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=3))

#     # Whether the bid has already expired (so we don't process twice)
#     is_expired = Column(Boolean, default=False) 
#     current_bid = Column(Integer, default=0)
#     last_bidder_id = Column(Integer, nullable=True)
#     last_bidder_username = Column(String(255), nullable=True)
#     last_bid_time = Column(DateTime, nullable=True, default=None)

# class User(Base):
#     __tablename__ = "user"

#     id = Column(BigInteger, primary_key=True, index=True)  # Telegram user ID
#     full_name = Column(String(255), nullable=False)
#     username = Column(String(255), nullable=True)
#     is_banned = Column(Boolean, default=False)  # Optional local ban
#     first_seen = Column(DateTime, default=datetime.utcnow)
#     last_seen = Column(DateTime, default=datetime.utcnow)








# models/submission.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

# === Helper ===
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

# === Submission Model ===
class Submission(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: Optional[str]
    user_name: Optional[str]
    username: Optional[str]
    type: Optional[str]
    rarity: Optional[str]
    rarity_name: Optional[str]
    anime_name: Optional[str]
    waifu_name: Optional[str]
    optional_tag: Optional[str]
    caption: Optional[str]
    file_id: Optional[str]
    submitted_time: datetime = Field(default_factory=datetime.utcnow)
    status: str = "pending"
    base_bid: Optional[int] = None
    channel_id: Optional[str] = None
    previous_bidders: List[dict] = []
    channel_message_id: Optional[int] = None
    group_message_id: Optional[int] = None
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=3))
    is_expired: bool = False
    current_bid: int = 0
    last_bidder_id: Optional[int] = None
    last_bidder_username: Optional[str] = None
    last_bid_time: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}

# === User Model ===
class User(BaseModel):
    id: int  # Telegram user ID
    full_name: str
    username: Optional[str] = None
    is_banned: bool = False
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}