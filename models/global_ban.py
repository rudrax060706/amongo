# # models/global_ban.py
# from sqlalchemy import Column, BigInteger, String, DateTime
# from datetime import datetime
# from utils.database import Base

# class GlobalBan(Base):
#     __tablename__ = "global_bans"

#     user_id = Column(BigInteger, primary_key=True, index=True)
#     reason = Column(String(255), nullable=True)
#     banned_by = Column(BigInteger, nullable=False)
#     timestamp = Column(DateTime, default=datetime.utcnow)




# models/global_ban.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId

# Helper for ObjectId
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

# === GlobalBan Model ===
class GlobalBan(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: int
    reason: Optional[str] = None
    banned_by: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}