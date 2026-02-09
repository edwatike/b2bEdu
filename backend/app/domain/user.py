from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from ..adapters.db.models import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)  # NOT NULL в БД
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="moderator", nullable=False)  # admin, moderator
    is_active = Column(Boolean, default=True, nullable=False)
    createdat = Column(DateTime(timezone=True), server_default=func.now())  # createdat в БД