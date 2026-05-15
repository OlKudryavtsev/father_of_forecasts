from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
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

    fifa_match_no = Column(Integer, nullable=True)

    match_round = Column(String, nullable=True)
    group_code = Column(String, nullable=True)

    venue = Column(String, nullable=True)
    city = Column(String, nullable=True)

    external_provider = Column(String, nullable=True)
    external_fixture_id = Column(String, nullable=True)

    home_external_team_id = Column(Integer, nullable=True)
    away_external_team_id = Column(Integer, nullable=True)
    home_team_api_name = Column(String, nullable=True)
    away_team_api_name = Column(String, nullable=True)

    api_league_round = Column(String, nullable=True)

    status_short = Column(String, nullable=True)
    status_long = Column(String, nullable=True)

    synced_at = Column(DateTime(timezone=True), nullable=True)


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

class TournamentPrediction(Base):
    __tablename__ = "tournament_predictions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    tournament_code = Column(String, nullable=False, default="wc2026")

    champion = Column(String, nullable=False)
    runner_up = Column(String, nullable=False)
    third_place = Column(String, nullable=False)
    top_scorer = Column(String, nullable=False)

    champion_points = Column(Integer, default=0)
    runner_up_points = Column(Integer, default=0)
    third_place_points = Column(Integer, default=0)
    top_scorer_points = Column(Integer, default=0)
    points = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tournament_code",
            name="uq_user_tournament_prediction",
        ),
    )

class TournamentResult(Base):
    __tablename__ = "tournament_results"

    id = Column(Integer, primary_key=True, index=True)

    tournament_code = Column(String, nullable=False, unique=True, default="wc2026")

    champion = Column(String, nullable=False)
    runner_up = Column(String, nullable=False)
    third_place = Column(String, nullable=False)
    top_scorer = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)

    reminder_type = Column(String, nullable=False)
    reminder_key = Column(String, nullable=False)

    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    match = relationship("Match")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "match_id",
            "reminder_type",
            "reminder_key",
            name="uq_reminder_user_match_type_key",
        ),
    )

class CommandLog(Base):
    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)
    display_name = Column(String, nullable=True)

    command = Column(String, nullable=False)
    full_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

class WorldCupFact(Base):
    __tablename__ = "world_cup_facts"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=True)

    title = Column(String, nullable=False)
    fact_text = Column(Text, nullable=False)

    category = Column(String, nullable=True)
    tournament_year = Column(Integer, nullable=True)

    source_text = Column(String, nullable=True)
    source_url = Column(Text, nullable=True)

    spicy_comment = Column(Text, nullable=True)

    needs_verification = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FactDeliveryLog(Base):
    __tablename__ = "fact_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)

    fact_id = Column(Integer, ForeignKey("world_cup_facts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)

    delivery_type = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    fact = relationship("WorldCupFact")
    user = relationship("User")

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=True)

    question_text = Column(Text, nullable=False)

    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)

    correct_option = Column(String, nullable=False)

    explanation = Column(Text, nullable=True)

    category = Column(String, nullable=True)
    tournament_year = Column(Integer, nullable=True)

    source_fact_id = Column(Integer, ForeignKey("world_cup_facts.id"), nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_fact = relationship("WorldCupFact")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, index=True)

    quiz_question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)

    selected_option = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    question = relationship("QuizQuestion")
    user = relationship("User")