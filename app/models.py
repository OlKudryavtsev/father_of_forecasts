from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
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

    predictions = relationship("Prediction", back_populates="user")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)

    tournament_code = Column(String, nullable=False, default="wc2026")

    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)

    stage = Column(String, nullable=False, default="group")

    starts_at = Column(DateTime(timezone=True), nullable=False)

    score_home = Column(Integer, nullable=True)
    score_away = Column(Integer, nullable=True)

    winner_side = Column(String, nullable=True)

    is_finished = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    predictions = relationship("Prediction", back_populates="match")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)

    pred_home = Column(Integer, nullable=False)
    pred_away = Column(Integer, nullable=False)

    advancement_bet_enabled = Column(Boolean, default=False)
    predicted_advancing_side = Column(String, nullable=True)

    score_points = Column(Integer, default=0)
    advancement_points = Column(Integer, default=0)

    points = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")

    __table_args__ = (
        UniqueConstraint("user_id", "match_id", name="uq_user_match_prediction"),
    )