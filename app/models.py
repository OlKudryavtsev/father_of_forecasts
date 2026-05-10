from sqlalchemy import Column, BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    username = Column(String, nullable=True)

    display_name = Column(String, nullable=False)

    is_admin = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())