from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
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
    access_status = Column(String, nullable=False, default="approved", server_default="approved", index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    access_requested_at = Column(DateTime(timezone=True), nullable=True)
    pending_invite_code = Column(String, nullable=True, index=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejected_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Personal delivery tone for AI-generated private messages. The default keeps
    # the league's original "Без пощады" experience.
    personal_humor_mode = Column(String, nullable=False, default="ruthless", server_default="ruthless")

    predictions = relationship("Prediction", back_populates="user")
    league_memberships = relationship("LeagueMember", back_populates="user", cascade="all, delete-orphan", foreign_keys="LeagueMember.user_id")


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    league_type = Column(String, nullable=False, default="system", server_default="system", index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    invite_code = Column(String, nullable=True, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    scoring_start_at = Column(DateTime(timezone=True), nullable=True)
    chat_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    # Tone used only for league-chat summaries; individual users have their own preference.
    humor_mode = Column(String, nullable=False, default="ruthless", server_default="ruthless")
    # Achievement progress starts at this release, while normal leaderboard stats remain historical.
    gamification_started_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())

    owner = relationship("User", foreign_keys=[owner_user_id])
    members = relationship("LeagueMember", back_populates="league", cascade="all, delete-orphan")


class LeagueMember(Base):
    __tablename__ = "league_members"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="member", server_default="member", index=True)
    status = Column(String, nullable=False, default="active", server_default="active", index=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    league = relationship("League", back_populates="members")
    user = relationship("User", back_populates="league_memberships", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_members_league_user"),
    )


class LeagueActivityEvent(Base):
    """Feed item describing an action of a participant inside a league.

    An event is written per league, rather than globally per user. This keeps
    the activity feed correctly scoped when a participant belongs to several
    private leagues at the same time.
    """

    __tablename__ = "league_activity_events"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    event_key = Column(String, nullable=False, unique=True, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    league = relationship("League")
    actor = relationship("User", foreign_keys=[actor_user_id])


class AnalyticsEvent(Base):
    """Privacy-aware product analytics event for the Mini App.

    Events deliberately store only the internal user id and a compact allowlisted
    properties payload. Telegram identifiers, user names, prediction values and
    free text are not copied into this table.
    """

    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    session_id = Column(String(96), nullable=False, index=True)
    event_name = Column(String(64), nullable=False, index=True)
    screen = Column(String(64), nullable=True, index=True)
    source = Column(String(24), nullable=False, default="web", server_default="web", index=True)
    app_version = Column(String(32), nullable=True)
    properties = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])


class WebSession(Base):
    __tablename__ = "web_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    token_hash = Column(String, nullable=False, unique=True, index=True)
    title = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    endpoint = Column(Text, nullable=False)
    p256dh = Column(Text, nullable=False)
    auth = Column(Text, nullable=False)
    user_agent = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscription_endpoint"),
    )


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
    videos = relationship("MatchVideo", back_populates="match", cascade="all, delete-orphan")

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


class MatchDetailsCache(Base):
    """Single normalized API-Football cache row per match for Mini App details."""
    __tablename__ = "match_details_cache"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    fixture_payload = Column(JSON, nullable=True)
    events_payload = Column(JSON, nullable=True)
    statistics_payload = Column(JSON, nullable=True)
    lineups_payload = Column(JSON, nullable=True)
    players_payload = Column(JSON, nullable=True)
    sync_status = Column(String, nullable=False, default="pending", server_default="pending", index=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    match = relationship("Match")


class TournamentDataCache(Base):
    """Shared API-Football cache for tournament-level Mini App data."""
    __tablename__ = "tournament_data_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, nullable=False, unique=True, index=True)
    payload = Column(JSON, nullable=True)
    sync_status = Column(String, nullable=False, default="pending", server_default="pending", index=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MatchVideo(Base):
    __tablename__ = "match_videos"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)

    source = Column(String, nullable=False, default="matchtv")
    video_type = Column(String, nullable=False, default="highlights")
    title = Column(String, nullable=False)
    url = Column(Text, nullable=False)

    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=100)

    discovery_status = Column(String, nullable=False, default="manual", index=True)
    confidence = Column(Integer, default=100)
    external_id = Column(String, nullable=True, index=True)

    available_from = Column(DateTime(timezone=True), nullable=True)
    discovered_at = Column(DateTime(timezone=True), nullable=True)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match", back_populates="videos")


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





class FatherMatchPrediction(Base):
    __tablename__ = "father_match_predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, unique=True, index=True)

    pred_home = Column(Integer, nullable=False)
    pred_away = Column(Integer, nullable=False)
    outcome = Column(String, nullable=False)
    # Father follows the same playoff rule as participants: an optional pick for
    # the team that advances after extra time / penalties.
    advancement_bet_enabled = Column(Boolean, nullable=False, default=False, server_default="false")
    predicted_advancing_side = Column(String, nullable=True)
    confidence = Column(Integer, nullable=True)
    source = Column(String, nullable=False, default="ai")
    forecast_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match")

class FantasyPlayer(Base):
    __tablename__ = "fantasy_players"

    id = Column(Integer, primary_key=True, index=True)

    tournament_code = Column(String, nullable=False, default="wc2026", index=True)

    external_player_id = Column(Integer, nullable=False, index=True)
    external_team_id = Column(Integer, nullable=False, index=True)

    team_name = Column(String, nullable=False, index=True)
    team_display_name = Column(String, nullable=False, index=True)
    team_flag = Column(String, nullable=True)

    player_name = Column(String, nullable=False, index=True)
    age = Column(Integer, nullable=True)
    number = Column(Integer, nullable=True)
    position = Column(String, nullable=False, index=True)
    photo = Column(Text, nullable=True)

    fifa_rank = Column(Integer, nullable=True)
    fifa_category = Column(Integer, nullable=False, default=4, index=True)

    is_active = Column(Boolean, default=True, index=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tournament_code",
            "external_player_id",
            "external_team_id",
            name="uq_fantasy_player_tournament_external_player_team",
        ),
    )


class FantasyTeam(Base):
    __tablename__ = "fantasy_teams"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    tournament_code = Column(String, nullable=False, default="wc2026", index=True)

    formation = Column(String, nullable=False, default="4-3-3")
    captain_player_id = Column(Integer, ForeignKey("fantasy_players.id"), nullable=True)

    points = Column(Integer, default=0)
    transfer_penalty_points = Column(Integer, default=0)
    transfers_used = Column(Integer, default=0)
    transfer_window_key = Column(String, nullable=True)
    transfer_baseline_player_ids = Column(Text, nullable=True)
    is_locked = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    captain = relationship("FantasyPlayer", foreign_keys=[captain_player_id])
    players = relationship(
        "FantasyTeamPlayer",
        back_populates="fantasy_team",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tournament_code",
            name="uq_fantasy_team_user_tournament",
        ),
    )


class FantasyTeamPlayer(Base):
    __tablename__ = "fantasy_team_players"

    id = Column(Integer, primary_key=True, index=True)

    fantasy_team_id = Column(Integer, ForeignKey("fantasy_teams.id"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("fantasy_players.id"), nullable=False, index=True)

    position_slot = Column(String, nullable=False)
    position = Column(String, nullable=False, index=True)
    is_captain = Column(Boolean, default=False)
    is_starter = Column(Boolean, default=True)
    bench_order = Column(Integer, nullable=True)

    points = Column(Integer, default=0)

    fantasy_team = relationship("FantasyTeam", back_populates="players")
    player = relationship("FantasyPlayer")

    __table_args__ = (
        UniqueConstraint(
            "fantasy_team_id",
            "position_slot",
            name="uq_fantasy_team_position_slot",
        ),
        UniqueConstraint(
            "fantasy_team_id",
            "player_id",
            name="uq_fantasy_team_player",
        ),
    )


class FantasyPlayerMatchStat(Base):
    __tablename__ = "fantasy_player_match_stats"

    id = Column(Integer, primary_key=True, index=True)

    player_id = Column(Integer, ForeignKey("fantasy_players.id"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)

    minutes = Column(Integer, default=0)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    starts = Column(Boolean, default=False)
    saves = Column(Integer, default=0)
    penalties_saved = Column(Integer, default=0)
    balls_recovered = Column(Integer, default=0)
    shots_on_target = Column(Integer, default=0)
    yellow_cards = Column(Integer, default=0)
    red_cards = Column(Integer, default=0)
    clean_sheet = Column(Boolean, default=False)
    goals_conceded = Column(Integer, default=0)
    own_goals = Column(Integer, default=0)
    penalty_missed = Column(Integer, default=0)

    points = Column(Integer, default=0)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)

    player = relationship("FantasyPlayer")
    match = relationship("Match")

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "match_id",
            name="uq_fantasy_player_match_stat",
        ),
    )



class UserAchievement(Base):
    """One durable per-league achievement level for a participant."""

    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_code = Column(String(64), nullable=False, index=True)
    level = Column(Integer, nullable=False, default=0, server_default="0")
    earned_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    league = relationship("League")

    __table_args__ = (
        UniqueConstraint("user_id", "league_id", "achievement_code", name="uq_user_league_achievement"),
    )


class WorldCupNewsItem(Base):
    """Curated World Cup 2026 news item collected from configured RSS feeds.

    RSS is the discovery layer; OpenAI only decides whether a candidate is a
    good fit and writes a compact, fact-bounded recap/commentary.
    """

    __tablename__ = "world_cup_news_items"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(128), nullable=False, unique=True, index=True)
    source_name = Column(String(160), nullable=True)
    source_url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    father_commentary = Column(Text, nullable=True)
    category = Column(String(64), nullable=True, index=True)
    relevance_score = Column(Integer, nullable=False, default=0, server_default="0")
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    selected_at = Column(DateTime(timezone=True), nullable=True, index=True)
    published_for_date = Column(Date, nullable=True, index=True)
    selection_status = Column(String(24), nullable=False, default="pending", server_default="pending", index=True)


class LeagueNewsDelivery(Base):
    """One delivery record per league and curated news item.

    The constraint makes chat publication idempotent across bot restarts.
    """

    __tablename__ = "league_news_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    news_item_id = Column(Integer, ForeignKey("world_cup_news_items.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(String(80), nullable=True)
    delivered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    league = relationship("League")
    news_item = relationship("WorldCupNewsItem")

    __table_args__ = (
        UniqueConstraint("league_id", "news_item_id", name="uq_league_news_delivery"),
    )


class AiUsageLog(Base):
    """Compact per-request usage accounting for optional AI workflows."""

    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    purpose = Column(String(64), nullable=False, index=True)
    model = Column(String(96), nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    output_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    estimated_cost_usd = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class UserNotificationSetting(Base):
    __tablename__ = "user_notification_settings"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notification_key = Column(String, nullable=False, index=True)
    is_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_key",
            name="uq_user_notification_setting",
        ),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)

    setting_key = Column(String, nullable=False, unique=True, index=True)
    setting_value = Column(Text, nullable=True)

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

    chat_id = Column(BigInteger, nullable=True)

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

class HistoricalArchiveCard(Base):
    __tablename__ = "historical_archive_cards"

    id = Column(Integer, primary_key=True, index=True)

    external_id = Column(String, unique=True, nullable=False)

    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)

    card_type = Column(String, nullable=True)
    tournament_code = Column(String, nullable=True)

    related_name = Column(String, nullable=True)
    related_telegram_id = Column(BigInteger, nullable=True)

    is_public = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HistoricalArchiveDeliveryLog(Base):
    __tablename__ = "historical_archive_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)

    archive_card_id = Column(
        Integer,
        ForeignKey("historical_archive_cards.id"),
        nullable=False,
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)
    chat_id = Column(BigInteger, nullable=True)

    delivery_type = Column(String, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    archive_card = relationship("HistoricalArchiveCard")
    user = relationship("User")


class GroupQuizSession(Base):
    __tablename__ = "group_quiz_sessions"

    id = Column(Integer, primary_key=True, index=True)

    chat_id = Column(BigInteger, nullable=False)
    quiz_question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)

    status = Column(String, nullable=False, default="open")

    started_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)

    message_id = Column(BigInteger, nullable=True)

    category = Column(String, nullable=True)

    question = relationship("QuizQuestion")
    started_by = relationship("User")


class GroupQuizAnswer(Base):
    __tablename__ = "group_quiz_answers"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(Integer, ForeignKey("group_quiz_sessions.id"), nullable=False)
    quiz_question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_id = Column(BigInteger, nullable=True)
    display_name = Column(String, nullable=True)

    selected_option = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("GroupQuizSession")
    question = relationship("QuizQuestion")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_group_quiz_session_user"),
    )

class GroupQuizGame(Base):
    """A timed multi-question quiz battle running in a Telegram group chat."""

    __tablename__ = "group_quiz_games"

    id = Column(Integer, primary_key=True, index=True)

    chat_id = Column(BigInteger, nullable=False, index=True)
    status = Column(String, nullable=False, default="setup", index=True)

    questions_total = Column(Integer, nullable=False)
    current_question_index = Column(Integer, default=0)

    seconds_per_question = Column(Integer, nullable=False, default=60)

    started_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    started_by = relationship("User")


class GroupQuizGameQuestion(Base):
    """A single question inside a timed group quiz battle."""

    __tablename__ = "group_quiz_game_questions"

    id = Column(Integer, primary_key=True, index=True)

    game_id = Column(Integer, ForeignKey("group_quiz_games.id"), nullable=False, index=True)
    quiz_question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False, index=True)

    question_order = Column(Integer, nullable=False)

    message_id = Column(BigInteger, nullable=True)

    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String, nullable=False, default="pending", index=True)

    game = relationship("GroupQuizGame")
    question = relationship("QuizQuestion")

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "question_order",
            name="uq_group_quiz_game_question_order",
        ),
    )


class GroupQuizGameAnswer(Base):
    """A user's answer to one question in a timed group quiz battle."""

    __tablename__ = "group_quiz_game_answers"

    id = Column(Integer, primary_key=True, index=True)

    game_id = Column(Integer, ForeignKey("group_quiz_games.id"), nullable=False, index=True)
    game_question_id = Column(
        Integer,
        ForeignKey("group_quiz_game_questions.id"),
        nullable=False,
        index=True,
    )
    quiz_question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    display_name = Column(String, nullable=True)

    selected_option = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)

    answered_at = Column(DateTime(timezone=True), server_default=func.now())
    answer_seconds = Column(Integer, nullable=True)

    game = relationship("GroupQuizGame")
    game_question = relationship("GroupQuizGameQuestion")
    question = relationship("QuizQuestion")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "game_question_id",
            "user_id",
            name="uq_group_quiz_game_question_user",
        ),
    )



# v3.0.1 — league-scoped synchronous quiz platform. These tables deliberately
# use the ``league_quiz_*`` prefix to avoid changing legacy /quiz and quiz-battle
# records from the early bot implementation.
class LeagueQuizQuestion(Base):
    __tablename__ = "league_quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    question_type = Column(String(40), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="draft", server_default="draft", index=True)
    question_text = Column(Text, nullable=False)
    explanation = Column(Text, nullable=True)
    default_points = Column(Integer, nullable=False, default=100, server_default="100")
    tags = Column(String(500), nullable=True)
    # Stage 3 keeps type-specific immutable authoring data here: aliases,
    # Jeopardy topic, countdown facts and the ranked answers of «Сто к одному».
    question_payload = Column(JSON, nullable=False, default=dict, server_default="{}")
    times_used = Column(Integer, nullable=False, default=0, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    league = relationship("League")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    approver = relationship("User", foreign_keys=[approved_by_user_id])
    options = relationship("LeagueQuizQuestionOption", back_populates="question", cascade="all, delete-orphan")
    sources = relationship("LeagueQuizQuestionSource", back_populates="question", cascade="all, delete-orphan")
    aliases = relationship("LeagueQuizQuestionAlias", back_populates="question", cascade="all, delete-orphan")


class LeagueQuizQuestionOption(Base):
    __tablename__ = "league_quiz_question_options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("league_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    option_key = Column(String(12), nullable=False)
    option_text = Column(Text, nullable=False)
    position = Column(Integer, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False, server_default="false")

    question = relationship("LeagueQuizQuestion", back_populates="options")

    __table_args__ = (
        UniqueConstraint("question_id", "option_key", name="uq_league_quiz_question_option_key"),
        UniqueConstraint("question_id", "position", name="uq_league_quiz_question_option_position"),
    )


class LeagueQuizQuestionAlias(Base):
    __tablename__ = "league_quiz_question_aliases"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("league_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    alias_text = Column(String(500), nullable=False)
    normalized_alias = Column(String(500), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question = relationship("LeagueQuizQuestion", back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("question_id", "normalized_alias", name="uq_league_quiz_question_alias"),
    )


class LeagueQuizQuestionSource(Base):
    __tablename__ = "league_quiz_question_sources"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("league_quiz_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_title = Column(String(500), nullable=True)
    source_url = Column(Text, nullable=True)
    source_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question = relationship("LeagueQuizQuestion", back_populates="sources")


class LeagueQuizSession(Base):
    __tablename__ = "league_quiz_sessions"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="registration_open", server_default="registration_open", index=True)
    scheduled_start_at = Column(DateTime(timezone=True), nullable=True, index=True)
    registration_opened_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    seconds_per_question = Column(Integer, nullable=False, default=30, server_default="30")
    reveal_seconds = Column(Integer, nullable=False, default=12, server_default="12")
    allow_late_registration = Column(Boolean, nullable=False, default=False, server_default="false")
    rounds_total = Column(Integer, nullable=False, default=1, server_default="1")
    current_round_order = Column(Integer, nullable=True)
    current_question_order = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    league = relationship("League")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    rounds = relationship("LeagueQuizSessionRound", back_populates="quiz_session", cascade="all, delete-orphan")
    participants = relationship("LeagueQuizSessionParticipant", back_populates="quiz_session", cascade="all, delete-orphan")


class LeagueQuizSessionRound(Base):
    __tablename__ = "league_quiz_session_rounds"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("league_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    round_order = Column(Integer, nullable=False)
    round_type = Column(String(40), nullable=False)
    title = Column(String(160), nullable=False)
    status = Column(String(24), nullable=False, default="pending", server_default="pending", index=True)
    points_mode = Column(String(24), nullable=False, default="positive", server_default="positive")
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    quiz_session = relationship("LeagueQuizSession", back_populates="rounds")
    questions = relationship("LeagueQuizSessionQuestion", back_populates="round", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("session_id", "round_order", name="uq_league_quiz_session_round_order"),
    )


class LeagueQuizSessionQuestion(Base):
    __tablename__ = "league_quiz_session_questions"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("league_quiz_session_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_question_id = Column(Integer, ForeignKey("league_quiz_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    question_order = Column(Integer, nullable=False)
    question_type = Column(String(40), nullable=False)
    question_text_snapshot = Column(Text, nullable=False)
    explanation_snapshot = Column(Text, nullable=True)
    options_snapshot = Column(JSON, nullable=False)
    # Snapshot of the bank question payload. It prevents later editing of the
    # bank from changing a scheduled or finished game.
    payload_snapshot = Column(JSON, nullable=False, default=dict, server_default="{}")
    # Mutable, server-only state: e.g. currently opened clue in «Обратный отсчёт».
    runtime_state = Column(JSON, nullable=False, default=dict, server_default="{}")
    points = Column(Integer, nullable=False, default=0, server_default="0")
    negative_on_wrong = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(String(24), nullable=False, default="pending", server_default="pending", index=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closes_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    revealed_at = Column(DateTime(timezone=True), nullable=True)
    revealed_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    round = relationship("LeagueQuizSessionRound", back_populates="questions")
    bank_question = relationship("LeagueQuizQuestion")
    answers = relationship("LeagueQuizSessionAnswer", back_populates="session_question", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("round_id", "question_order", name="uq_league_quiz_session_question_order"),
    )


class LeagueQuizSessionParticipant(Base):
    __tablename__ = "league_quiz_session_participants"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("league_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(24), nullable=False, default="registered", server_default="registered", index=True)
    score_total = Column(Integer, nullable=False, default=0, server_default="0")
    joined_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    quiz_session = relationship("LeagueQuizSession", back_populates="participants")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_league_quiz_session_participant"),
    )


class LeagueQuizSessionAnswer(Base):
    __tablename__ = "league_quiz_session_answers"

    id = Column(Integer, primary_key=True, index=True)
    session_question_id = Column(Integer, ForeignKey("league_quiz_session_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    selected_option_key = Column(String(12), nullable=True)
    answer_text = Column(Text, nullable=True)
    answer_payload = Column(JSON, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    points_awarded = Column(Integer, nullable=True)
    answered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    scored_at = Column(DateTime(timezone=True), nullable=True)

    session_question = relationship("LeagueQuizSessionQuestion", back_populates="answers")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("session_question_id", "user_id", name="uq_league_quiz_session_question_answer"),
    )


class LeagueQuizScoreEvent(Base):
    __tablename__ = "league_quiz_score_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("league_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    round_id = Column(Integer, ForeignKey("league_quiz_session_rounds.id", ondelete="SET NULL"), nullable=True, index=True)
    session_question_id = Column(Integer, ForeignKey("league_quiz_session_questions.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False, index=True)
    delta_points = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LeagueQuizEvent(Base):
    __tablename__ = "league_quiz_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("league_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class LeagueQuizAdminAction(Base):
    __tablename__ = "league_quiz_admin_actions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("league_quiz_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class LeagueQuizTelegramDelivery(Base):
    """Durable one-time delivery record for Telegram quiz announcements."""

    __tablename__ = "league_quiz_telegram_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("league_quiz_events.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_key = Column(String(160), nullable=False)
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    chat_id = Column(String(80), nullable=True)
    message_kind = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, default="sent", server_default="sent", index=True)
    error_text = Column(Text, nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    event = relationship("LeagueQuizEvent")
    recipient_user = relationship("User")

    __table_args__ = (
        UniqueConstraint("event_id", "destination_key", name="uq_league_quiz_telegram_event_destination"),
    )
