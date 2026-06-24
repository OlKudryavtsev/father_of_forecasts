"""FastAPI endpoints used by the Telegram Mini App."""

from __future__ import annotations

import asyncio
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import os
import random
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import create_web_session_for_user, get_current_user, get_db, hash_web_session_token
from app.api_football import ApiFootballClient
from app.constants.notifications import ADMIN_NOTIFICATION_SETTING_KEYS, NOTIFICATION_OPTIONS
from app.models import (
    AppSetting,
    FatherMatchPrediction,
    PushSubscription,
    WebSession,
    FantasyPlayer,
    FantasyPlayerMatchStat,
    FantasyTeam,
    FantasyTeamPlayer,
    HistoricalArchiveCard,
    League,
    LeagueMember,
    LeagueActivityEvent,
    AnalyticsEvent,
    Match,
    MatchVideo,
    Prediction,
    QuizAnswer,
    QuizQuestion,
    TournamentPrediction,
    User,
    UserNotificationSetting,
    WorldCupFact,
)
from app.runtime import TOURNAMENT_CODE
from app.services.matches import apply_match_result_from_admin, build_match_emotion_payload, get_all_available_matches, get_nearest_matchday_matches, is_playoff_match
from app.services.misc import build_table_rows, get_team_flag, get_team_flag_code
from app.services.rating_history import build_rating_history
from app.services.predictions import save_prediction_and_notify_admins
from app.services.tournament import get_tournament_starts_at, is_tournament_started, save_tournament_prediction_and_notify_admins, tournament_prediction_submit_state
from app.services.forecast import build_forecast_text
from app.services.matchtv_videos import sync_matchtv_videos
from app.services.match_details import build_match_details_payload, sync_match_details_cache
from app.services.tournament_hub import find_top_scorer, get_team_scorers, get_top_scorers, player_match_rows, resolve_player_by_name
from app.services.leagues import (
    create_user_league,
    deactivate_league,
    get_user_active_leagues,
    join_league_by_invite_code,
    league_scoring_start_at,
    list_league_members,
    normalize_invite_code,
    remove_league_member,
    require_user_league,
    set_league_member_role,
    update_league_chat_id,
)
from app.services.tournament_forecast import get_top_scorer_candidates, get_top_scorer_hint, serialize_father_tournament_forecast
from app.team_names import get_team_name_ru
from app.wc2026_sync import get_fixture_score, get_winner_side

router = APIRouter(prefix="/api/webapp", tags=["Telegram Mini App"])
US_TOURNAMENT_TIMEZONE = ZoneInfo(os.getenv("TOURNAMENT_DAY_TIMEZONE", "America/New_York"))


# Product analytics is intentionally limited to named interaction events.  This
# makes reports useful without retaining Telegram IDs, raw prediction content,
# search text, or arbitrary click labels in the event payload.
ANALYTICS_ALLOWED_EVENTS = {
    "app_open",
    "screen_view",
    "match_open",
    "prediction_open",
    "prediction_save",
    "forecast_open",
    "tournament_mode_open",
    "team_open",
    "player_open",
    "participant_history_open",
    "participant_history_filter",
    "rating_race_open",
    "rating_race_play",
    "rating_match_analytics_open",
    "league_open",
    "league_selected",
    "league_create",
    "league_join",
    "league_activity_open",
    "resource_open",
    "video_open",
    "tournament_prediction_open",
    "tournament_prediction_save",
    "admin_open",
    "analytics_open",
}

ANALYTICS_ALLOWED_SCREENS = {
    "matches", "predictions", "rating", "leagues", "resources", "profile", "admin",
}

ANALYTICS_ALLOWED_SOURCES = {"telegram", "pwa", "browser"}

ANALYTICS_ALLOWED_PROPERTY_KEYS = {
    "match_id", "league_id", "participant_id", "team_id", "player_id", "video_id",
    "filter", "mode", "scope", "group_code", "entry_point", "is_update", "tab",
    "resource", "result", "section", "destination",
}

ANALYTICS_EVENT_LABELS = {
    "app_open": "Открыл приложение",
    "screen_view": "Открыл раздел",
    "match_open": "Открыл матч",
    "prediction_open": "Открыл форму прогноза",
    "prediction_save": "Сохранил прогноз",
    "forecast_open": "Открыл прогноз Отца",
    "tournament_mode_open": "Открыл раздел турнира",
    "team_open": "Открыл сборную",
    "player_open": "Открыл игрока",
    "participant_history_open": "Открыл историю участника",
    "participant_history_filter": "Применил фильтр истории",
    "rating_race_open": "Открыл гонку рейтинга",
    "rating_race_play": "Запустил гонку рейтинга",
    "league_open": "Открыл лигу",
    "league_selected": "Выбрал лигу",
    "league_create": "Создал лигу",
    "league_join": "Вступил в лигу",
    "league_activity_open": "Открыл историю лиги",
    "resource_open": "Открыл ресурс",
    "video_open": "Открыл видео",
    "tournament_prediction_open": "Открыл турнирный прогноз",
    "tournament_prediction_save": "Сохранил турнирный прогноз",
    "admin_open": "Открыл администрирование",
    "analytics_open": "Открыл аналитику",
}

ANALYTICS_SCREEN_LABELS = {
    "matches": "Матч-центр",
    "predictions": "Прогнозы",
    "rating": "Рейтинг",
    "leagues": "Лиги",
    "resources": "Ресурсы",
    "profile": "Профиль",
    "admin": "Администрирование",
}


def _sanitize_analytics_properties(properties: dict | None) -> dict:
    """Keep only a small allowlist of non-personal primitive properties."""
    clean: dict = {}
    for raw_key, raw_value in (properties or {}).items():
        key = str(raw_key).strip()
        if key not in ANALYTICS_ALLOWED_PROPERTY_KEYS:
            continue

        if isinstance(raw_value, bool):
            clean[key] = raw_value
        elif isinstance(raw_value, int) and not isinstance(raw_value, bool):
            clean[key] = raw_value
        elif isinstance(raw_value, float):
            clean[key] = round(raw_value, 4)
        elif isinstance(raw_value, str):
            value = raw_value.strip()
            if value:
                clean[key] = value[:64]

    return clean


def _analytics_event_label(event_name: str, properties: dict | None = None) -> str:
    """Build a compact admin-readable description without exposing payload data."""
    label = ANALYTICS_EVENT_LABELS.get(event_name, event_name)
    properties = properties or {}
    suffixes = {
        "filter": {"exact": "Точные счета", "outcome": "Исходы"},
        "mode": {"tournament": "Турнир", "scorers": "Бомбардиры", "matches": "Матчи"},
        "resource": {"fact": "Факт о ЧМ", "archive": "Архив Отца", "father_forecast": "Прогноз Отца", "scorer_help": "Подсказка по бомбардирам"},
    }
    for key, values in suffixes.items():
        value = properties.get(key)
        if value in values:
            return f"{label}: {values[value]}"
    return label


class PredictionPayload(BaseModel):
    """Payload for creating/updating a match prediction."""

    match_id: int
    pred_home: int = Field(ge=0, le=20)
    pred_away: int = Field(ge=0, le=20)
    advancement_bet_enabled: bool = False
    predicted_advancing_side: str | None = None


class TournamentPredictionPayload(BaseModel):
    """Payload for saving the user's tournament prediction."""

    champion: str
    runner_up: str
    third_place: str
    top_scorer: str


class QuizAnswerPayload(BaseModel):
    """Payload for saving an answer in the Mini App quick quiz."""

    question_id: int
    selected_option: str


class LeagueCreatePayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class LeagueJoinPayload(BaseModel):
    invite_code: str = Field(min_length=3, max_length=80)


class LeagueRolePayload(BaseModel):
    role: str = Field(pattern="^(admin|member)$")


class LeagueSettingsPayload(BaseModel):
    chat_id: str | None = Field(default=None, max_length=80)


class MatchResultPayload(BaseModel):
    score_home: int = Field(ge=0, le=30)
    score_away: int = Field(ge=0, le=30)
    winner_side: str | None = None


class MatchVideoPayload(BaseModel):
    video_type: str = Field(default="highlights", max_length=40)
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=1000)
    source: str = Field(default="matchtv", max_length=80)
    is_active: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    discovery_status: str = Field(default="manual", max_length=40)
    confidence: int = Field(default=100, ge=0, le=100)


class MatchTvSyncPayload(BaseModel):
    lookback_days: int = Field(default=3, ge=0, le=30)
    lookahead_days: int = Field(default=2, ge=0, le=30)
    activate_min_confidence: int = Field(default=85, ge=0, le=100)


class NotificationSettingsPayload(BaseModel):
    settings: dict[str, bool]


class AdminSettingPayload(BaseModel):
    value: str | None = None


class PushSubscriptionPayload(BaseModel):
    endpoint: str
    keys: dict[str, str]


class AnalyticsEventPayload(BaseModel):
    """Client-side Mini App event with a restricted, non-personal payload."""

    event_name: str = Field(min_length=2, max_length=64)
    screen: str | None = Field(default=None, max_length=64)
    session_id: str = Field(min_length=8, max_length=96)
    source: str = Field(default="web", max_length=24)
    app_version: str | None = Field(default=None, max_length=32)
    properties: dict = Field(default_factory=dict)


class FantasyTeamPayload(BaseModel):
    """Payload for saving a user's fantasy squad."""

    formation: str = "4-3-3"
    player_ids: list[int] = Field(min_length=15, max_length=15)
    starting_player_ids: list[int] = Field(min_length=11, max_length=11)
    captain_player_id: int


def _ensure_utc(dt: datetime) -> datetime:
    """Return timezone-aware UTC datetime."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _serialize_match(match: Match, user_prediction: Prediction | None = None) -> dict:
    """Serialize a match for the Mini App API."""
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)

    return {
        "id": match.id,
        "label": _match_label(match),
        "home_team": home_name,
        "away_team": away_name,
        "home_flag": get_team_flag(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag": get_team_flag(away_name, getattr(match, "away_team_api_name", None)),
        "home_flag_code": get_team_flag_code(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag_code": get_team_flag_code(away_name, getattr(match, "away_team_api_name", None)),
        "home_team_id": match.home_external_team_id,
        "away_team_id": match.away_external_team_id,
        "stage": match.stage,
        "match_round": match.match_round,
        "group_code": match.group_code,
        "starts_at": _ensure_utc(match.starts_at).isoformat(),
        "venue": match.venue,
        "city": match.city,
        "score_home": match.score_home,
        "score_away": match.score_away,
        "winner_side": match.winner_side,
        "is_finished": bool(match.is_finished),
        "is_playoff": is_playoff_match(match),
        "prediction": _serialize_prediction(user_prediction) if user_prediction else None,
    }



def _stage_label_for_match(match: Match | None) -> str:
    """Return compact current tournament stage label for header."""
    if not match:
        return "До старта"

    stage = (match.stage or "").lower()
    round_text = (match.match_round or match.api_league_round or "").strip()
    joined = f"{stage} {round_text}".lower()

    if stage == "group":
        number = _parse_round_number(match.match_round) or _parse_round_number(match.api_league_round) or 1
        return f"{number} тур"

    if "round of 16" in joined or "1/8" in joined or "16" in joined or stage in {"r16", "round_16", "last_16"}:
        return "1/8 финала"
    if "quarter" in joined or "1/4" in joined or stage in {"quarter", "quarterfinal", "quarter-final"}:
        return "1/4 финала"
    if "semi" in joined or "1/2" in joined or stage in {"semi", "semifinal", "semi-final"}:
        return "1/2 финала"
    if "third" in joined or "3rd" in joined or "брон" in joined:
        return "Матч за 3-е место"
    if "final" in joined or stage == "final":
        return "Финал"

    return round_text or match.stage or "Турнир"


def _current_stage_label(db: Session) -> str:
    """Return current/nearest tournament stage label for top Mini App header."""
    now = datetime.now(timezone.utc)
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )

    if not matches:
        return "Турнир"

    started = [match for match in matches if _ensure_utc(match.starts_at) <= now]
    if started:
        unfinished = [match for match in started if not match.is_finished]
        if unfinished:
            return _stage_label_for_match(unfinished[-1])
        return _stage_label_for_match(started[-1])

    return "До старта"


def _match_label(match: Match) -> str:
    """Build a compact human-readable match label."""
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)
    home_flag = get_team_flag(home_name, getattr(match, "home_team_api_name", None))
    away_flag = get_team_flag(away_name, getattr(match, "away_team_api_name", None))

    parts = []

    if match.match_round:
        parts.append(f"Тур {match.match_round}" if match.stage == "group" else match.match_round)

    if match.group_code:
        parts.append(f"Группа {match.group_code}")

    postfix = f". {'. '.join(parts)}" if parts else ""
    return f"{home_name} {home_flag} — {away_flag} {away_name}{postfix}".strip()


def _serialize_prediction(prediction: Prediction) -> dict:
    """Serialize a user's prediction."""
    return {
        "id": prediction.id,
        "pred_home": prediction.pred_home,
        "pred_away": prediction.pred_away,
        "advancement_bet_enabled": bool(prediction.advancement_bet_enabled),
        "predicted_advancing_side": prediction.predicted_advancing_side,
        "score_points": prediction.score_points or 0,
        "advancement_points": prediction.advancement_points or 0,
        "points": prediction.points or 0,
    }



VALID_MATCH_VIDEO_TYPES = {"live", "highlights", "review", "full_replay", "goal", "moment", "other"}


def _normalize_match_video_payload(payload: MatchVideoPayload) -> dict:
    """Validate and normalize a match video payload."""
    video_type = (payload.video_type or "other").strip().lower()
    if video_type not in VALID_MATCH_VIDEO_TYPES:
        video_type = "other"

    url = (payload.url or "").strip()
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        raise HTTPException(status_code=400, detail="URL должен начинаться с http:// или https://")

    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Укажите название видео")

    source = (payload.source or "matchtv").strip() or "matchtv"

    discovery_status = (getattr(payload, "discovery_status", "manual") or "manual").strip().lower()
    if discovery_status not in {"manual", "found", "verified", "hidden"}:
        discovery_status = "manual"

    return {
        "video_type": video_type,
        "title": title,
        "url": url,
        "source": source,
        "is_active": bool(payload.is_active),
        "priority": int(payload.priority or 100),
        "discovery_status": discovery_status,
        "confidence": int(getattr(payload, "confidence", 100) or 0),
    }


def _serialize_match_video(video: MatchVideo) -> dict:
    """Serialize a match video link for Mini App/API."""
    return {
        "id": video.id,
        "match_id": video.match_id,
        "source": video.source,
        "video_type": video.video_type,
        "title": video.title,
        "url": video.url,
        "is_active": bool(video.is_active),
        "priority": video.priority or 100,
        "discovery_status": getattr(video, "discovery_status", "manual") or "manual",
        "confidence": getattr(video, "confidence", 100) or 0,
        "external_id": getattr(video, "external_id", None),
        "available_from": _ensure_utc(video.available_from).isoformat() if video.available_from else None,
        "discovered_at": _ensure_utc(video.discovered_at).isoformat() if getattr(video, "discovered_at", None) else None,
        "created_at": _ensure_utc(video.created_at).isoformat() if video.created_at else None,
        "updated_at": _ensure_utc(video.updated_at).isoformat() if video.updated_at else None,
    }


def _active_videos_for_match(db: Session, match_id: int) -> list[MatchVideo]:
    """Return active video links for a match in display order."""
    return (
        db.query(MatchVideo)
        .filter(MatchVideo.match_id == match_id, MatchVideo.is_active == True)
        .order_by(MatchVideo.priority.asc(), MatchVideo.id.asc())
        .all()
    )


def _require_miniapp_admin(user: User) -> None:
    """Raise if current Mini App user is not an admin."""
    if not bool(user.is_admin):
        raise HTTPException(status_code=403, detail="Admin access required")


def _get_app_setting(db: Session, key: str, default: str | None = None) -> str | None:
    setting = db.query(AppSetting).filter(AppSetting.setting_key == key).first()
    return setting.setting_value if setting else default


def _set_app_setting(db: Session, key: str, value: str | None) -> None:
    setting = db.query(AppSetting).filter(AppSetting.setting_key == key).first()

    if not setting:
        setting = AppSetting(setting_key=key, setting_value=value)
        db.add(setting)
    else:
        setting.setting_value = value
        setting.updated_at = datetime.now(timezone.utc)


def _notification_settings_for_user(db: Session, user: User) -> dict:
    rows = (
        db.query(UserNotificationSetting)
        .filter(UserNotificationSetting.user_id == user.id)
        .all()
    )
    by_key = {row.notification_key: bool(row.is_enabled) for row in rows}

    return {
        option["key"]: by_key.get(option["key"], bool(option["default"]))
        for option in NOTIFICATION_OPTIONS
    }




def _score_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def _father_builtin_score(db: Session, match: Match) -> tuple[int, int] | None:
    """Return hardcoded Father forecast for already known first two matches."""
    if getattr(match, "fifa_match_no", None) == 1:
        return (1, 0)
    if getattr(match, "fifa_match_no", None) == 2:
        return (1, 1)

    first_matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc(), Match.id.asc())
        .limit(2)
        .all()
    )

    if len(first_matches) > 0 and first_matches[0].id == match.id:
        return (1, 0)
    if len(first_matches) > 1 and first_matches[1].id == match.id:
        return (1, 1)

    return None


def _parse_father_score_from_text(text: str) -> tuple[int, int] | None:
    match = re.search(r"Прогноз счета:\s*(\d+)\s*[:—-]\s*(\d+)", text or "", flags=re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(?:счет|прогноз)[^0-9]{0,20}(\d+)\s*[:—-]\s*(\d+)", text or "", flags=re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def _serialize_father_prediction(prediction: FatherMatchPrediction | None, match: Match | None = None) -> dict | None:
    if not prediction:
        return None

    points = None
    result_class = None
    if match and match.is_finished and match.score_home is not None and match.score_away is not None:
        if prediction.pred_home == match.score_home and prediction.pred_away == match.score_away:
            points = 3
            result_class = "exact"
        elif _score_outcome(prediction.pred_home, prediction.pred_away) == _score_outcome(match.score_home, match.score_away):
            points = 1
            result_class = "outcome"
        else:
            points = 0
            result_class = "miss"

    return {
        "id": prediction.id,
        "match_id": prediction.match_id,
        "pred_home": prediction.pred_home,
        "pred_away": prediction.pred_away,
        "outcome": prediction.outcome,
        "confidence": prediction.confidence,
        "source": prediction.source,
        "forecast_text": prediction.forecast_text,
        "points": points,
        "result_class": result_class,
    }


def _ensure_father_match_prediction(db: Session, match: Match, allow_ai: bool = True) -> FatherMatchPrediction:
    existing = db.query(FatherMatchPrediction).filter(FatherMatchPrediction.match_id == match.id).first()
    if existing:
        return existing

    score = _father_builtin_score(db, match)
    source = "seed"
    text = None

    if score is None and allow_ai:
        try:
            text = build_forecast_text(db, match)
            score = _parse_father_score_from_text(text)
            source = "ai"
        except Exception as error:
            text = f"Прогноз Отца временно недоступен, использован осторожный fallback 1:1. Ошибка: {error}"
            score = (1, 1)
            source = "fallback"

    if score is None:
        score = (1, 1)
        source = "fallback"
        text = "Прогноз Отца: 1:1. Осторожная ничья, потому что Отец сегодня без хрустального мяча."

    pred_home, pred_away = score
    if text is None:
        text = (
            "🤖 Прогноз Отца прогнозов\n\n"
            f"{match.home_team} — {match.away_team}\n"
            f"Прогноз счета: {pred_home}:{pred_away}\n\n"
            "Зафиксировано автоматически и больше не меняется после старта матча."
        )

    prediction = FatherMatchPrediction(
        match_id=match.id,
        pred_home=pred_home,
        pred_away=pred_away,
        outcome=_score_outcome(pred_home, pred_away),
        confidence=None,
        source=source,
        forecast_text=text,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction

def _prediction_by_match_id(db: Session, user: User, matches: list[Match]) -> dict[int, Prediction]:
    """Return user's predictions mapped by match id."""
    match_ids = [match.id for match in matches]

    if not match_ids:
        return {}

    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == user.id, Prediction.match_id.in_(match_ids))
        .all()
    )

    return {prediction.match_id: prediction for prediction in predictions}


def _league_invite_url(league: League) -> str | None:
    """Build Telegram deep-link for a league invite when bot username is configured."""
    if not league.invite_code:
        return None
    bot_username = (
        os.getenv("BOT_USERNAME", "").strip().lstrip("@")
        or os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    )
    if not bot_username:
        return None
    return f"https://t.me/{bot_username}?start=league_{league.invite_code}"


def _serialize_league(league: League, current_user: User | None = None) -> dict:
    """Serialize a league for Mini App UI."""
    current_member = None
    if current_user:
        for member in league.members or []:
            if member.user_id == current_user.id:
                current_member = member
                break

    active_members_count = sum(1 for member in (league.members or []) if member.status == "active")
    role = current_member.role if current_member else None
    if current_user and league.owner_user_id == current_user.id:
        role = "owner"
    return {
        "id": league.id,
        "name": league.name,
        "description": league.description,
        "league_type": league.league_type,
        "invite_code": league.invite_code,
        "invite_url": _league_invite_url(league),
        "chat_id": league.chat_id if (current_user and (current_user.is_admin or league.owner_user_id == current_user.id or role in {"owner", "admin"})) else None,
        "is_owner": bool(current_user and league.owner_user_id == current_user.id),
        "role": role,
        "can_manage": role in {"owner", "admin"} or bool(current_user and (current_user.is_admin or league.owner_user_id == current_user.id)),
        "can_deactivate": bool(current_user and league.league_type != "system" and (current_user.is_admin or league.owner_user_id == current_user.id)),
        "scoring_start_at": _ensure_utc(league_scoring_start_at(league)).isoformat() if league_scoring_start_at(league) else None,
        "members_count": active_members_count,
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    """Return current Mini App user profile."""
    return {
        "id": current_user.id,
        "telegram_id": current_user.telegram_id,
        "username": current_user.username,
        "display_name": current_user.display_name,
        "is_admin": bool(current_user.is_admin),
    }


def _league_match_filter(query, league: League):
    """Apply league scoring-start filter to a Match query."""
    scoring_start = league_scoring_start_at(league)
    if scoring_start is not None:
        query = query.filter(Match.starts_at >= scoring_start)
    return query


def _league_started_before_match_filter(league: League):
    """Return SQLAlchemy filter ensuring a match is in the league scoring period."""
    scoring_start = league_scoring_start_at(league)
    if scoring_start is None:
        return True
    return Match.starts_at >= scoring_start


def _serialize_match_points_analytics_item(
    match: Match,
    count: int,
    total_predictions: int,
    result_kind: str,
) -> dict:
    """Serialize one completed match for the rating analytics cards.

    ``count`` always equals the number of visible predictions for the card:
    exact / outcome hits for the first two rankings and all missed predictions
    for the "Никто не угадал" ranking. The Mini App can therefore use this
    value both as the compact counter and as the modal trigger.
    """
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)
    return {
        "match_id": match.id,
        "home_team": home_name,
        "away_team": away_name,
        "home_flag": get_team_flag(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag": get_team_flag(away_name, getattr(match, "away_team_api_name", None)),
        "home_flag_code": get_team_flag_code(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag_code": get_team_flag_code(away_name, getattr(match, "away_team_api_name", None)),
        "score_home": match.score_home,
        "score_away": match.score_away,
        "count": count,
        "total_predictions": total_predictions,
        "result_kind": result_kind,
        "starts_at": _ensure_utc(match.starts_at).isoformat(),
    }


def _build_league_match_points_analytics(db: Session, league: League) -> dict:
    """Return the selected league's most and least predictable matches.

    The first two rankings show the ten matches with most exact-score (3pt)
    and outcome (1pt) hits. ``nobody_guessed`` intentionally includes only
    matches where every submitted forecast scored zero; it is ordered by the
    number of missed forecasts so the most broadly surprising matches appear
    first.
    """
    matches_query = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
    )
    scoring_start = league_scoring_start_at(league)
    if scoring_start is not None:
        matches_query = matches_query.filter(Match.starts_at >= scoring_start)

    exact_rows: list[dict] = []
    outcome_rows: list[dict] = []
    nobody_rows: list[dict] = []

    for match in matches_query.order_by(Match.starts_at.desc()).all():
        predictions = (
            db.query(Prediction)
            .join(LeagueMember, LeagueMember.user_id == Prediction.user_id)
            .filter(
                Prediction.match_id == match.id,
                LeagueMember.league_id == league.id,
                LeagueMember.status == "active",
                LeagueMember.joined_at <= match.starts_at,
            )
            .all()
        )
        total_predictions = len(predictions)
        if not total_predictions:
            continue

        exact_count = sum(1 for prediction in predictions if int(prediction.score_points or 0) == 3)
        outcome_count = sum(1 for prediction in predictions if int(prediction.score_points or 0) == 1)
        success_count = exact_count + outcome_count

        if exact_count:
            exact_rows.append(_serialize_match_points_analytics_item(match, exact_count, total_predictions, "exact"))
        if outcome_count:
            outcome_rows.append(_serialize_match_points_analytics_item(match, outcome_count, total_predictions, "outcome"))
        if success_count == 0:
            nobody_rows.append(_serialize_match_points_analytics_item(match, total_predictions, total_predictions, "miss"))

    sort_key = lambda row: (row["count"], row["total_predictions"], row["starts_at"])
    exact_rows.sort(key=sort_key, reverse=True)
    outcome_rows.sort(key=sort_key, reverse=True)
    nobody_rows.sort(key=sort_key, reverse=True)

    return {
        "exact_scores": exact_rows[:10],
        "outcomes": outcome_rows[:10],
        "nobody_guessed": nobody_rows[:10],
    }


@router.get("/leagues")
def get_my_leagues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return leagues where the current user is an active member."""
    leagues = get_user_active_leagues(db, current_user)
    default_league = None
    try:
        default_league = require_user_league(db, current_user, None)
    except ValueError:
        default_league = leagues[0] if leagues else None

    return {
        "leagues": [_serialize_league(league, current_user) for league in leagues],
        "default_league_id": default_league.id if default_league else None,
        "active_league_id": default_league.id if default_league else None,
    }


@router.post("/leagues")
def create_league_endpoint(
    payload: LeagueCreatePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a private league and add current user as admin."""
    try:
        league = create_user_league(db, current_user, payload.name, payload.description)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"ok": True, "league": _serialize_league(league, current_user)}


@router.post("/leagues/join")
def join_league_endpoint(
    payload: LeagueJoinPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Join an existing league by invite code."""
    try:
        league = join_league_by_invite_code(db, current_user, payload.invite_code)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"ok": True, "league": _serialize_league(league, current_user)}



def _absolute_app_url(request: Request, token: str | None = None) -> str:
    """Build absolute /app URL for browser/PWA mode."""
    url = str(request.url_for("telegram_mini_app"))
    if token:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}web_token={token}"
    return url




def _serialize_league_activity(event: LeagueActivityEvent) -> dict:
    """Serialize a compact participant action for the selected league feed."""
    payload = event.payload if isinstance(event.payload, dict) else {}
    actor = event.actor
    actor_name = actor.display_name if actor else "Участник"
    action_type = event.action_type

    if action_type == "league_created":
        title = "Создал лигу"
        detail = payload.get("league_name") or "Новая лига"
        icon = "🏁"
    elif action_type == "member_joined":
        title = "Вступил в лигу"
        detail = payload.get("league_name") or "Лига"
        icon = "👋"
    elif action_type in {"match_prediction_created", "match_prediction_updated"}:
        # The activity feed must never disclose a participant's predicted score.
        # Legacy records may still carry payload["prediction"], so intentionally
        # ignore it here as well as in newly recorded events.
        title = "Сделал прогноз" if action_type.endswith("created") else "Изменил прогноз"
        detail = payload.get("match_label") or "Матч"
        icon = "🎯"
    elif action_type in {"tournament_prediction_created", "tournament_prediction_updated"}:
        title = "Заполнил прогноз на турнир" if action_type.endswith("created") else "Изменил прогноз на турнир"
        detail = f"🏆 {payload.get('champion') or 'Выбор команд'} · ⚽ {payload.get('top_scorer') or 'Бомбардир'}"
        icon = "🏆"
    else:
        title = "Действие в лиге"
        detail = ""
        icon = "•"

    return {
        "id": event.id,
        "type": action_type,
        "icon": icon,
        "actor_name": actor_name,
        "title": title,
        "detail": detail,
        "created_at": _ensure_utc(event.created_at).isoformat() if event.created_at else None,
    }


def _serialize_league_member(member: LeagueMember, league: League) -> dict:
    user = member.user
    is_owner = bool(user and league.owner_user_id == user.id)
    role = "owner" if is_owner else member.role
    return {
        "id": member.id,
        "user_id": member.user_id,
        "telegram_id": user.telegram_id if user else None,
        "display_name": user.display_name if user else "Участник",
        "username": user.username if user else None,
        "is_bot_admin": bool(user and user.is_admin),
        "role": role,
        "status": member.status,
        "is_owner": is_owner,
        "joined_at": member.joined_at.isoformat() if member.joined_at else None,
    }


@router.patch("/leagues/{league_id}")
def update_league_settings_endpoint(
    league_id: int,
    payload: LeagueSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update manageable league settings."""
    try:
        league = update_league_chat_id(db, current_user, league_id, payload.chat_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "league": _serialize_league(league, current_user)}


@router.get("/leagues/{league_id}/activity")
def get_league_activity_endpoint(
    league_id: int,
    limit: int = Query(default=30, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a recent participant-only activity feed for the selected league.

    Activity records are created per league, so actions from a different private
    league can never leak into this feed.
    """
    try:
        league = require_user_league(db, current_user, league_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    events = (
        db.query(LeagueActivityEvent)
        .join(User, User.id == LeagueActivityEvent.actor_user_id)
        .filter(LeagueActivityEvent.league_id == league.id)
        .order_by(LeagueActivityEvent.created_at.desc(), LeagueActivityEvent.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "ok": True,
        "league": _serialize_league(league, current_user),
        "events": [_serialize_league_activity(event) for event in events],
    }


@router.get("/leagues/{league_id}/members")
def get_league_members_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return members for a league manageable by the current user."""
    try:
        league, members = list_league_members(db, current_user, league_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "ok": True,
        "league": _serialize_league(league, current_user),
        "members": [_serialize_league_member(member, league) for member in members],
    }


@router.patch("/leagues/{league_id}/members/{user_id}")
def update_league_member_endpoint(
    league_id: int,
    user_id: int,
    payload: LeagueRolePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Promote/demote a league member."""
    try:
        member = set_league_member_role(db, current_user, league_id, user_id, payload.role)
        league = member.league
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "member": _serialize_league_member(member, league)}


@router.delete("/leagues/{league_id}/members/{user_id}")
def remove_league_member_endpoint(
    league_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove a user from a league."""
    try:
        member = remove_league_member(db, current_user, league_id, user_id)
        league = member.league
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "member": _serialize_league_member(member, league)}


@router.post("/leagues/{league_id}/deactivate")
def deactivate_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Deactivate a private league."""
    try:
        league = deactivate_league(db, current_user, league_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "league": _serialize_league(league, current_user)}


@router.post("/web-session/create")
def create_web_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a browser/PWA session linked to current Telegram account."""
    user_agent = request.headers.get("user-agent")
    token, session = create_web_session_for_user(db, current_user, user_agent=user_agent)

    return {
        "ok": True,
        "token": token,
        "url": _absolute_app_url(request, token=token),
        "expires_at": _ensure_utc(session.expires_at).isoformat() if session.expires_at else None,
    }


@router.get("/web-session/status")
def get_web_session_status(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current authenticated web session/user status."""
    return {
        "ok": True,
        "user": {
            "id": current_user.id,
            "telegram_id": current_user.telegram_id,
            "display_name": current_user.display_name,
            "username": current_user.username,
            "is_admin": bool(current_user.is_admin),
        },
        "app_url": _absolute_app_url(request),
    }


@router.post("/web-session/logout")
def logout_web_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Revoke current browser session token when present."""
    raw_token = (request.headers.get("x-web-session-token") or request.cookies.get("ff_web_session") or "").strip()
    if not raw_token:
        auth_header = request.headers.get("authorization") or ""
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header.split(" ", 1)[1].strip()

    if raw_token:
        token_hash = hash_web_session_token(raw_token)
        session = db.query(WebSession).filter(WebSession.token_hash == token_hash).first()
        if session and session.user_id == current_user.id:
            session.is_active = False
            db.commit()

    response.delete_cookie(key="ff_web_session", path="/")
    return {"ok": True}


@router.get("/push/public-key")
def get_push_public_key(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return VAPID public key for browser push notifications."""
    from app.services.web_push import get_vapid_public_key, web_push_enabled

    return {
        "enabled": web_push_enabled(),
        "public_key": get_vapid_public_key(),
    }


@router.get("/push/status")
def get_push_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's browser/PWA push subscription status on the server."""
    from app.services.web_push import web_push_enabled

    active_count = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id, PushSubscription.is_active == True)
        .count()
    )
    last_subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .order_by(PushSubscription.id.desc())
        .first()
    )

    return {
        "enabled": web_push_enabled(),
        "active_subscriptions": active_count,
        "has_active_subscription": active_count > 0,
        "last_success_at": last_subscription.last_success_at.isoformat() if last_subscription and last_subscription.last_success_at else None,
        "last_error": last_subscription.last_error if last_subscription else None,
    }


@router.post("/push/subscribe")
def subscribe_push(
    payload: PushSubscriptionPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Store browser Push API subscription for current user."""
    p256dh = payload.keys.get("p256dh")
    auth_value = payload.keys.get("auth")

    if not payload.endpoint or not p256dh or not auth_value:
        raise HTTPException(status_code=400, detail="Invalid push subscription")

    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .first()
    )

    if not subscription:
        subscription = PushSubscription(endpoint=payload.endpoint)

    subscription.user_id = current_user.id
    subscription.p256dh = p256dh
    subscription.auth = auth_value
    subscription.user_agent = request.headers.get("user-agent")
    subscription.is_active = True
    subscription.updated_at = datetime.now(timezone.utc)

    db.add(subscription)
    db.commit()

    return {"ok": True}


@router.post("/push/unsubscribe")
def unsubscribe_push(
    payload: PushSubscriptionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Disable browser Push API subscription for current user."""
    subscription = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == payload.endpoint)
        .first()
    )

    if subscription and subscription.user_id == current_user.id:
        subscription.is_active = False
        db.commit()

    return {"ok": True}




@router.post("/analytics/events")
def create_analytics_event(
    payload: AnalyticsEventPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Persist one allowlisted Mini App interaction for product analytics."""
    event_name = payload.event_name.strip().lower()
    screen = (payload.screen or "").strip().lower() or None
    source = payload.source.strip().lower() or "web"

    if event_name not in ANALYTICS_ALLOWED_EVENTS:
        raise HTTPException(status_code=422, detail="Неизвестное событие аналитики")
    if screen and screen not in ANALYTICS_ALLOWED_SCREENS:
        raise HTTPException(status_code=422, detail="Неизвестный экран аналитики")
    if source not in ANALYTICS_ALLOWED_SOURCES:
        source = "browser"

    event = AnalyticsEvent(
        user_id=current_user.id,
        session_id=payload.session_id.strip()[:96],
        event_name=event_name,
        screen=screen,
        source=source,
        app_version=(payload.app_version or "").strip()[:32] or None,
        properties=_sanitize_analytics_properties(payload.properties),
    )
    db.add(event)
    db.commit()
    return {"ok": True}


@router.get("/admin/analytics")
def get_admin_analytics(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return compact, privacy-aware product usage analytics for administrators."""
    _require_miniapp_admin(current_user)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    base = db.query(AnalyticsEvent).filter(AnalyticsEvent.created_at >= since)

    def unique_users_for(event_names: list[str]) -> int:
        return int(
            db.query(func.count(func.distinct(AnalyticsEvent.user_id)))
            .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_name.in_(event_names))
            .scalar() or 0
        )

    def event_count_for(event_names: list[str]) -> int:
        return int(
            db.query(func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_name.in_(event_names))
            .scalar() or 0
        )

    active_users = int(base.with_entities(func.count(func.distinct(AnalyticsEvent.user_id))).scalar() or 0)
    active_sessions = int(base.with_entities(func.count(func.distinct(AnalyticsEvent.session_id))).scalar() or 0)
    app_opens = event_count_for(["app_open"])
    predictions_saved = event_count_for(["prediction_save"])
    app_open_users = unique_users_for(["app_open"])
    match_open_users = unique_users_for(["match_open"])
    prediction_users = unique_users_for(["prediction_save"])

    screen_rows = (
        db.query(
            AnalyticsEvent.screen,
            func.count(AnalyticsEvent.id).label("events"),
            func.count(func.distinct(AnalyticsEvent.user_id)).label("users"),
        )
        .filter(AnalyticsEvent.created_at >= since, AnalyticsEvent.event_name == "screen_view")
        .group_by(AnalyticsEvent.screen)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .all()
    )

    event_rows = (
        db.query(
            AnalyticsEvent.event_name,
            func.count(AnalyticsEvent.id).label("events"),
            func.count(func.distinct(AnalyticsEvent.user_id)).label("users"),
        )
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_name)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .limit(12)
        .all()
    )

    daily_rows = (
        db.query(
            func.date(AnalyticsEvent.created_at).label("day"),
            func.count(AnalyticsEvent.id).label("events"),
            func.count(func.distinct(AnalyticsEvent.user_id)).label("users"),
        )
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(func.date(AnalyticsEvent.created_at))
        .order_by(func.date(AnalyticsEvent.created_at).asc())
        .all()
    )

    feature_definitions = [
        ("Матч-центр", ["match_open"]),
        ("Турнир", ["tournament_mode_open"]),
        ("Бомбардиры", ["player_open"]),
        ("Рейтинг", ["participant_history_open"]),
        ("Лиги", ["league_open", "league_create", "league_join"]),
        ("Ресурсы", ["resource_open"]),
        ("Прогноз Отца", ["forecast_open"]),
    ]
    features = [
        {
            "label": label,
            "events": event_count_for(event_names),
            "users": unique_users_for(event_names),
        }
        for label, event_names in feature_definitions
    ]
    features.sort(key=lambda row: (row["users"], row["events"]), reverse=True)

    recent_rows = (
        db.query(AnalyticsEvent, User)
        .outerjoin(User, User.id == AnalyticsEvent.user_id)
        .filter(AnalyticsEvent.created_at >= since)
        .order_by(AnalyticsEvent.created_at.desc())
        .limit(40)
        .all()
    )

    def ratio(value: int, base_value: int) -> int:
        return round(value * 100 / base_value) if base_value else 0

    return {
        "period_days": days,
        "since": since.isoformat(),
        "summary": {
            "active_users": active_users,
            "active_sessions": active_sessions,
            "app_opens": app_opens,
            "predictions_saved": predictions_saved,
            "prediction_conversion": ratio(prediction_users, match_open_users),
        },
        "funnel": [
            {"label": "Открыли приложение", "value": app_open_users, "percent": 100 if app_open_users else 0},
            {"label": "Открыли матч", "value": match_open_users, "percent": ratio(match_open_users, app_open_users)},
            {"label": "Сохранили прогноз", "value": prediction_users, "percent": ratio(prediction_users, match_open_users)},
        ],
        "screens": [
            {
                "key": row.screen or "unknown",
                "label": ANALYTICS_SCREEN_LABELS.get(row.screen or "", "Другой экран"),
                "events": int(row.events or 0),
                "users": int(row.users or 0),
            }
            for row in screen_rows
        ],
        "events": [
            {
                "key": row.event_name,
                "label": ANALYTICS_EVENT_LABELS.get(row.event_name, row.event_name),
                "events": int(row.events or 0),
                "users": int(row.users or 0),
            }
            for row in event_rows
        ],
        "features": features,
        "activity": [
            {
                "date": row.day.isoformat() if row.day else "",
                "events": int(row.events or 0),
                "users": int(row.users or 0),
            }
            for row in daily_rows
        ],
        "recent": [
            {
                "id": event.id,
                "user_name": user.display_name if user else "Пользователь",
                "event_name": event.event_name,
                "label": _analytics_event_label(event.event_name, event.properties),
                "screen": ANALYTICS_SCREEN_LABELS.get(event.screen or "", ""),
                "created_at": _ensure_utc(event.created_at).isoformat() if event.created_at else None,
            }
            for event, user in recent_rows
        ],
    }


LIVE_MATCH_STATUS_CODES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}


def _live_goal_events(details: dict) -> list[dict]:
    """Keep the compact home card focused on goals and their authors."""
    events = []
    for event in details.get("events") or []:
        if str(event.get("type") or "") != "Goal":
            continue
        if "Missed Penalty" in str(event.get("detail") or ""):
            continue
        events.append({
            "minute": event.get("minute") or "",
            "side": event.get("side") or "",
            "player": event.get("player") or "",
            "assist": event.get("assist") or "",
            "label": event.get("label") or "Гол",
        })
    return events


def _live_matches_payload(
    db: Session,
    current_user: User,
    league_id: int | None = None,
) -> list[dict]:
    """Return every currently live tournament fixture in a compact card format.

    The existing match-details cache is refreshed at most once per minute while
    a game is live. Returning a small ordered list lets the Match Center show
    simultaneous games in a swipeable carousel without additional endpoints.
    """
    now = datetime.now(timezone.utc)
    candidates = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished.is_(False),
            Match.external_fixture_id.isnot(None),
            Match.starts_at <= now,
            Match.starts_at >= now - timedelta(hours=6),
        )
        .order_by(Match.starts_at.asc())
        .limit(8)
        .all()
    )
    if not candidates:
        return []

    predictions = _prediction_by_match_id(db, current_user, candidates)
    live_matches: list[dict] = []
    for match in candidates:
        details = build_match_details_payload(db, match, refresh=True)
        overview = details.get("overview") or {}
        status_short = str(overview.get("status_short") or match.status_short or "").upper()
        if status_short not in LIVE_MATCH_STATUS_CODES:
            continue
        payload = _serialize_match_center_match(
            db,
            match,
            predictions.get(match.id),
            league_id=league_id,
        )
        payload.update({
            "is_live": True,
            "status_short": status_short,
            "status_long": overview.get("status_long") or match.status_long or "В игре",
            "elapsed": overview.get("elapsed"),
            "score_home": overview.get("score_home"),
            "score_away": overview.get("score_away"),
            "goal_events": _live_goal_events(details),
        })
        live_matches.append(payload)
    return live_matches


@router.get("/dashboard")
def get_dashboard(
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return compact dashboard data for the Mini App home page and selected league."""
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    nearest_matches = get_nearest_matchday_matches(db, matchdays_count=1)
    predictions_by_match = _prediction_by_match_id(db, current_user, nearest_matches)

    all_available_matches = get_all_available_matches(db, limit=100)
    all_predictions_by_match = _prediction_by_match_id(db, current_user, all_available_matches)

    missing_matches = [
        match
        for match in all_available_matches
        if match.id not in all_predictions_by_match
    ]

    nearest_missing_matches = [
        match
        for match in nearest_matches
        if match.id not in predictions_by_match
    ]

    tournament_prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    tournament_starts_at = get_tournament_starts_at()
    days_until_tournament = max((tournament_starts_at.date() - datetime.now(timezone.utc).date()).days, 0)

    table_rows = build_table_rows(db, league_id=active_league.id)
    current_rank = None
    current_points = 0

    for index, row in enumerate(table_rows, start=1):
        if row["name"] == current_user.display_name:
            current_rank = index
            current_points = row["points"]
            break

    live_matches = _live_matches_payload(db, current_user, league_id=active_league.id)

    return {
        "user": {
            "id": current_user.id,
            "display_name": current_user.display_name,
            "is_admin": bool(current_user.is_admin),
        },
        "rank": current_rank,
        "points": current_points,
        "league": _serialize_league(active_league, current_user),
        # ``live_match`` remains for clients on earlier builds; new clients
        # render the complete ``live_matches`` carousel.
        "live_match": live_matches[0] if live_matches else None,
        "live_matches": live_matches,
        "nearest_matches": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in nearest_matches
        ],
        "nearest_missing_predictions_count": len(nearest_missing_matches),
        "nearest_missing_matches_preview": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in nearest_missing_matches[:5]
        ],
        "missing_predictions_count": len(missing_matches),
        "missing_matches_preview": [
            _serialize_match(match)
            for match in missing_matches[:5]
        ],
        "tournament": {
            "days_until_start": days_until_tournament,
            "has_prediction": tournament_prediction is not None,
            "is_started": is_tournament_started(),
            "starts_at": tournament_starts_at.isoformat(),
            "current_stage_label": _current_stage_label(db),
        },
    }


@router.get("/matches")
def get_matches(
    scope: str = Query(default="all", regex="^(nearest|all|missing)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return matches for predictions or browsing."""
    if scope == "nearest":
        matches = get_nearest_matchday_matches(db, matchdays_count=1)
    else:
        matches = get_all_available_matches(db, limit=100)

    predictions_by_match = _prediction_by_match_id(db, current_user, matches)

    if scope == "missing":
        matches = [match for match in matches if match.id not in predictions_by_match]

    return {
        "matches": [
            _serialize_match(match, predictions_by_match.get(match.id))
            for match in matches
        ]
    }


@router.get("/matches/{match_id}")
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a single match card with current user's prediction."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id, Prediction.match_id == match.id)
        .first()
    )

    return {"match": _serialize_match(match, prediction)}




@router.get("/matches/{match_id}/details")
def get_match_details(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return cached API-Football details for a match.

    The service refreshes the shared backend cache only when it is stale.  The
    endpoint stays useful for future matches too: it returns local match facts
    and a clear pending state until lineups/events become available.
    """
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id, Prediction.match_id == match.id)
        .first()
    )
    details = build_match_details_payload(db, match, refresh=True)
    return {
        "match": _serialize_match(match, prediction),
        "details": details,
    }


@router.post("/admin/matches/{match_id}/details/sync")
def admin_sync_match_details(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Force-refresh one cached match details record for troubleshooting."""
    _require_miniapp_admin(current_user)
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    cache = sync_match_details_cache(db, match, force=True)
    return {
        "ok": bool(cache),
        "match_id": match.id,
        "status": getattr(cache, "sync_status", "unavailable") if cache else "unavailable",
        "last_error": getattr(cache, "last_error", None) if cache else None,
    }


@router.get("/matches/{match_id}/predictions")
def get_match_predictions_visibility(
    match_id: int,
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return participants who predicted a match; reveal scores only after kickoff."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    has_started = _ensure_utc(match.starts_at) <= datetime.now(timezone.utc)
    predictions = (
        db.query(Prediction, User)
        .join(User, User.id == Prediction.user_id)
        .join(LeagueMember, LeagueMember.user_id == User.id)
        .filter(
            Prediction.match_id == match.id,
            LeagueMember.league_id == active_league.id,
            LeagueMember.status == "active",
            LeagueMember.joined_at <= match.starts_at,
            User.access_status == "approved",
        )
        .order_by(User.display_name.asc())
        .all()
    )

    participants = []

    for prediction, user in predictions:
        item = {
            "user_id": user.id,
            "display_name": user.display_name,
            "username": user.username,
            "has_prediction": True,
        }

        if has_started:
            result_class = None
            if match.is_finished and match.score_home is not None and match.score_away is not None:
                if prediction.score_points == 3:
                    result_class = "exact"
                elif prediction.score_points == 1:
                    result_class = "outcome"
                else:
                    result_class = "miss"

            item.update(
                {
                    "pred_home": prediction.pred_home,
                    "pred_away": prediction.pred_away,
                    "advancement_bet_enabled": bool(prediction.advancement_bet_enabled),
                    "predicted_advancing_side": prediction.predicted_advancing_side,
                    "score_points": prediction.score_points or 0,
                    "advancement_points": prediction.advancement_points or 0,
                    "points": prediction.points or 0,
                    "result_class": result_class,
                }
            )

        participants.append(item)

    father_prediction = _ensure_father_match_prediction(db, match, allow_ai=True) if has_started else None

    return {
        "match": _serialize_match(match),
        "league": _serialize_league(active_league, current_user),
        "has_started": has_started,
        "participants_count": len(participants),
        "participants": participants,
        "father_prediction": _serialize_father_prediction(father_prediction, match) if father_prediction else None,
    }


@router.get("/forecast/{match_id}")
async def get_forecast_for_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return AI forecast text for a selected match."""
    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    prediction = _ensure_father_match_prediction(db, match, allow_ai=True)
    return {
        "match_id": match.id,
        "text": prediction.forecast_text or f"Прогноз счета: {prediction.pred_home}:{prediction.pred_away}",
        "father_prediction": _serialize_father_prediction(prediction, match),
    }


@router.get("/tournament-teams")
def get_tournament_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return unique tournament teams for Mini App autocomplete fields."""
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )

    teams_by_name: dict[str, dict] = {}

    for match in matches:
        for display_name, api_name in [
            (match.home_team, getattr(match, "home_team_api_name", None)),
            (match.away_team, getattr(match, "away_team_api_name", None)),
        ]:
            if not display_name or display_name == "TBD":
                continue

            name = get_team_name_ru(display_name)

            if name not in teams_by_name:
                teams_by_name[name] = {
                    "name": name,
                    "api_name": api_name or display_name,
                    "flag": get_team_flag(name, api_name or display_name),
                    "flag_code": get_team_flag_code(name, api_name or display_name),
                }

    teams = sorted(teams_by_name.values(), key=lambda item: item["name"])

    return {"teams": teams}


@router.post("/predictions")
async def save_prediction_endpoint(
    payload: PredictionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create or update current user's prediction for a match."""
    match = db.query(Match).filter(Match.id == payload.match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if payload.predicted_advancing_side not in (None, "home", "away"):
        raise HTTPException(status_code=400, detail="Invalid advancing side")

    if not is_playoff_match(match) and payload.advancement_bet_enabled:
        raise HTTPException(status_code=400, detail="Advancement bet is only available for playoff matches")

    success, text = await save_prediction_and_notify_admins(
        db=db,
        user=current_user,
        match=match,
        pred_home=payload.pred_home,
        pred_away=payload.pred_away,
        advancement_bet_enabled=payload.advancement_bet_enabled,
        predicted_advancing_side=payload.predicted_advancing_side,
    )

    if not success:
        raise HTTPException(status_code=400, detail=text)

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id, Prediction.match_id == match.id)
        .first()
    )

    return {
        "ok": True,
        "message": text,
        "match": _serialize_match(match, prediction),
    }


@router.get("/table")
def get_table(
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return tournament leaderboard with compact participant progress details."""
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    league_scoring_start = league_scoring_start_at(active_league)
    rows = build_table_rows(db, league_id=active_league.id)

    league_users = (
        db.query(User)
        .join(LeagueMember, LeagueMember.user_id == User.id)
        .filter(
            LeagueMember.league_id == active_league.id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .all()
    )
    # Prefer the immutable ID carried by build_table_rows. Keep the name map as
    # a compatibility fallback for legacy/custom table row builders.
    users_by_id = {user.id: user for user in league_users}
    users_by_name = {user.display_name: user for user in league_users}

    total_matches_query = db.query(Match).filter(Match.tournament_code == TOURNAMENT_CODE)
    if league_scoring_start is not None:
        total_matches_query = total_matches_query.filter(Match.starts_at >= league_scoring_start)
    total_matches_count = total_matches_query.count()

    father_predictions_query = (
        db.query(FatherMatchPrediction)
        .join(Match, FatherMatchPrediction.match_id == Match.id)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
    )
    if league_scoring_start is not None:
        father_predictions_query = father_predictions_query.filter(Match.starts_at >= league_scoring_start)
    father_predictions = father_predictions_query.all()
    father_points = 0
    father_exact = 0
    father_outcomes = 0
    father_finished_total = 0

    for fp in father_predictions:
        match = fp.match
        if not match or not match.is_finished or match.score_home is None or match.score_away is None:
            continue

        father_finished_total += 1

        if fp.pred_home == match.score_home and fp.pred_away == match.score_away:
            father_points += 3
            father_exact += 1
        elif _score_outcome(fp.pred_home, fp.pred_away) == _score_outcome(match.score_home, match.score_away):
            father_points += 1
            father_outcomes += 1

    father_successful = father_exact + father_outcomes
    father_row = {
        "name": "🤖 Отец прогнозов",
        "points": father_points,
        "match_points": father_points,
        "tournament_points": 0,
        "fantasy_points": 0,
        "total_predictions": len(father_predictions),
        "match_predictions_count": len(father_predictions),
        "match_predictions_finished_count": father_finished_total,
        "match_predictions_available": total_matches_count,
        "match_predictions_progress": f"{len(father_predictions)}/{total_matches_count}" if total_matches_count else str(len(father_predictions)),
        "exact_scores": father_exact,
        "outcomes": father_outcomes,
        "advancement_plus": 0,
        "advancement_minus": 0,
        "successful_predictions": father_successful,
        "accuracy_base": father_finished_total,
        "accuracy_percent": round(father_successful * 100 / father_finished_total) if father_finished_total else 0,
        "is_father": True,
        "is_current_user": False,
        "tournament_prediction_count": 0,
        "tournament_prediction_total": 0,
        "tournament_prediction_progress": "—",
        "has_tournament_prediction": False,
        "fantasy_team_progress": "—",
        "fantasy_team_complete": False,
        "points_with_fantasy": father_points,
    }

    for index, row in enumerate(rows, start=1):
        user = users_by_id.get(row.get("user_id")) or users_by_name.get(row["name"])
        tournament_prediction = None
        fantasy_team = None
        user_predictions_count = row.get("total_predictions", 0)
        finished_predictions_count = 0

        if user:
            tournament_prediction = (
                db.query(TournamentPrediction)
                .filter(
                    TournamentPrediction.user_id == user.id,
                    TournamentPrediction.tournament_code == TOURNAMENT_CODE,
                )
                .first()
            )
            user_predictions_query = (
                db.query(Prediction)
                .join(Match, Prediction.match_id == Match.id)
                .filter(
                    Prediction.user_id == user.id,
                    Match.tournament_code == TOURNAMENT_CODE,
                )
            )
            if league_scoring_start is not None:
                user_predictions_query = user_predictions_query.filter(Match.starts_at >= league_scoring_start)
            user_predictions_count = user_predictions_query.count()

            finished_predictions_query = user_predictions_query.filter(
                Match.is_finished == True,
                Match.score_home.isnot(None),
                Match.score_away.isnot(None),
            )
            finished_predictions_count = finished_predictions_query.count()
            fantasy_team = (
                db.query(FantasyTeam)
                .filter(
                    FantasyTeam.user_id == user.id,
                    FantasyTeam.tournament_code == TOURNAMENT_CODE,
                )
                .first()
            )

        exact_scores = row.get("exact_scores", 0)
        outcomes = row.get("outcomes", 0)
        advancement_plus = row.get("advancement_plus", 0)
        advancement_minus = row.get("advancement_minus", 0)
        match_points = row.get("match_points", 0)
        tournament_points = row.get("tournament_points", 0)
        total_points = row.get("points", 0)
        successful_predictions = exact_scores + outcomes

        row["rank"] = index
        # Stable identifier used by the Mini App participant-history drawer.
        # Do not rely on display_name: it may be changed or duplicated.
        row["user_id"] = user.id if user else None
        row["is_current_user"] = row["name"] == current_user.display_name
        row["is_father"] = False
        row["match_predictions_count"] = user_predictions_count
        row["match_predictions_finished_count"] = finished_predictions_count
        row["match_predictions_available"] = total_matches_count
        row["match_predictions_progress"] = (
            f"{user_predictions_count}/{total_matches_count}"
            if total_matches_count
            else str(user_predictions_count)
        )
        row["tournament_prediction_count"] = 4 if tournament_prediction else 0
        row["tournament_prediction_total"] = 4
        row["tournament_prediction_progress"] = "4/4" if tournament_prediction else "0/4"
        row["has_tournament_prediction"] = tournament_prediction is not None
        fantasy_selected_count = len(fantasy_team.players) if fantasy_team else 0
        row["fantasy_team_progress"] = f"{fantasy_selected_count}/15"
        row["fantasy_team_complete"] = fantasy_selected_count == 15 and bool(fantasy_team and fantasy_team.captain_player_id)
        row["fantasy_points"] = fantasy_team.points if fantasy_team else 0
        row["points_with_fantasy"] = row["points"] + row["fantasy_points"]
        row["exact_scores"] = exact_scores
        row["outcomes"] = outcomes
        row["advancement_plus"] = advancement_plus
        row["advancement_minus"] = advancement_minus
        row["match_points"] = match_points
        row["tournament_points"] = tournament_points
        row["points"] = total_points
        row["successful_predictions"] = successful_predictions
        row["accuracy_base"] = finished_predictions_count
        row["accuracy_percent"] = round(successful_predictions * 100 / finished_predictions_count) if finished_predictions_count else 0

    return {
        "league": _serialize_league(active_league, current_user),
        "rows": rows,
        "father_row": father_row,
        "match_analytics": _build_league_match_points_analytics(db, active_league),
    }


@router.get("/rating-history")
def get_rating_history(
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return match-by-match leaderboard movement for the selected league."""
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    history = build_rating_history(db, active_league, current_user_id=current_user.id)
    history["league"] = _serialize_league(active_league, current_user)
    return history


@router.get("/table/participant/{participant_user_id}/predictions")
def get_participant_finished_predictions(
    participant_user_id: int,
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a participant's finished-match predictions inside the selected league.

    The endpoint deliberately scopes records to the active league period and to
    matches that started after the participant joined that league. This keeps a
    private league from exposing results from prior matches or other leagues.
    Only completed matches are returned, so score predictions are no longer
    secret at the moment they are shown.
    """
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    membership = (
        db.query(LeagueMember)
        .join(User, User.id == LeagueMember.user_id)
        .filter(
            LeagueMember.league_id == active_league.id,
            LeagueMember.user_id == participant_user_id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Участник не состоит в выбранной лиге")

    participant = db.query(User).filter(User.id == participant_user_id).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")

    matches_query = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
    )
    scoring_start = league_scoring_start_at(active_league)
    if scoring_start is not None:
        matches_query = matches_query.filter(Match.starts_at >= scoring_start)

    joined_at = _ensure_utc(membership.joined_at) if membership.joined_at else None
    matches = matches_query.order_by(Match.starts_at.desc()).all()
    if joined_at is not None:
        matches = [match for match in matches if _ensure_utc(match.starts_at) >= joined_at]

    predictions_by_match = {}
    if matches:
        predictions = (
            db.query(Prediction)
            .filter(
                Prediction.user_id == participant.id,
                Prediction.match_id.in_([match.id for match in matches]),
            )
            .all()
        )
        predictions_by_match = {prediction.match_id: prediction for prediction in predictions}

    rows: list[dict] = []
    exact_count = 0
    outcome_count = 0
    total_match_points = 0

    for match in matches:
        prediction = predictions_by_match.get(match.id)
        score_points = int(prediction.score_points or 0) if prediction else 0
        total_points = int(prediction.points or 0) if prediction else 0
        advancement_points = int(prediction.advancement_points or 0) if prediction else 0

        if prediction is None:
            result_type = "missing"
            result_label = "Без прогноза"
        elif score_points == 3:
            result_type = "exact"
            result_label = "Точный счет"
            exact_count += 1
        elif score_points == 1:
            result_type = "outcome"
            result_label = "Угадан исход"
            outcome_count += 1
        else:
            result_type = "miss"
            result_label = "Не угадан"

        total_match_points += total_points
        home_name = get_team_name_ru(match.home_team)
        away_name = get_team_name_ru(match.away_team)
        rows.append(
            {
                "match_id": match.id,
                "starts_at": _ensure_utc(match.starts_at).isoformat(),
                "home_team": home_name,
                "away_team": away_name,
                "home_flag": get_team_flag(home_name, getattr(match, "home_team_api_name", None)),
                "away_flag": get_team_flag(away_name, getattr(match, "away_team_api_name", None)),
                "home_flag_code": get_team_flag_code(home_name, getattr(match, "home_team_api_name", None)),
                "away_flag_code": get_team_flag_code(away_name, getattr(match, "away_team_api_name", None)),
                "actual_home": match.score_home,
                "actual_away": match.score_away,
                "prediction_home": prediction.pred_home if prediction else None,
                "prediction_away": prediction.pred_away if prediction else None,
                "result_type": result_type,
                "result_label": result_label,
                "score_points": score_points,
                "advancement_points": advancement_points,
                "points": total_points,
            }
        )

    return {
        "league": _serialize_league(active_league, current_user),
        "participant": {
            "id": participant.id,
            "name": participant.display_name,
        },
        "summary": {
            "matches_count": len(rows),
            "exact_scores": exact_count,
            "outcomes": outcome_count,
            "match_points": total_match_points,
        },
        "rows": rows,
    }


@router.get("/tournament-forecast")
def get_father_tournament_forecast(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return static Father Forecast for tournament outcomes."""
    return {"forecast": serialize_father_tournament_forecast()}


@router.get("/top-scorer-candidates")
def get_top_scorer_candidates_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return top scorer candidates and hint for Mini App."""
    return {
        "candidates": get_top_scorer_candidates(),
        "hint": get_top_scorer_hint(),
    }


@router.get("/tournament-prediction/me")
def get_my_tournament_prediction(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's long-term tournament prediction."""
    prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    submit_state = tournament_prediction_submit_state(db, current_user)

    return {
        "prediction": _serialize_tournament_prediction(prediction, db=db) if prediction else None,
        "is_closed": bool(submit_state["is_closed"]),
        "can_submit": bool(submit_state["can_submit"]),
        "is_late_entry": bool(submit_state["is_late_entry"]),
    }


@router.post("/tournament-prediction")
async def save_tournament_prediction_endpoint(
    payload: TournamentPredictionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create or update current user's tournament prediction."""
    submit_state = tournament_prediction_submit_state(db, current_user)
    if not submit_state["can_submit"]:
        raise HTTPException(status_code=400, detail="Tournament predictions are closed")

    success, text = await save_tournament_prediction_and_notify_admins(
        db=db,
        user=current_user,
        champion=payload.champion.strip(),
        runner_up=payload.runner_up.strip(),
        third_place=payload.third_place.strip(),
        top_scorer=payload.top_scorer.strip(),
    )

    if not success:
        raise HTTPException(status_code=400, detail=text)

    prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    return {"ok": True, "message": text, "prediction": _serialize_tournament_prediction(prediction, db=db)}


@router.get("/tournament-predictions")
def get_tournament_predictions(
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return tournament predictions with pre-start privacy rules, scoped by league."""
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    users = (
        db.query(User)
        .join(LeagueMember, LeagueMember.user_id == User.id)
        .filter(
            LeagueMember.league_id == active_league.id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .order_by(User.display_name)
        .all()
    )
    predictions = (
        db.query(TournamentPrediction)
        .filter(TournamentPrediction.tournament_code == TOURNAMENT_CODE)
        .all()
    )
    predictions_by_user = {prediction.user_id: prediction for prediction in predictions}
    revealed = is_tournament_started()

    rows = []

    for user in users:
        prediction = predictions_by_user.get(user.id)
        rows.append(
            {
                "user_name": user.display_name,
                "has_prediction": prediction is not None,
                "prediction": _serialize_tournament_prediction(prediction, db=db) if revealed and prediction else None,
            }
        )

    return {"revealed": revealed, "league": _serialize_league(active_league, current_user), "rows": rows}


def _top_scorer_photo(db: Session | None, player_name: str | None) -> str | None:
    """Find a stored player photo for a tournament top scorer name."""
    if db is None or not player_name:
        return None

    name = player_name.strip()
    if not name:
        return None

    exact = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
            FantasyPlayer.photo.isnot(None),
            FantasyPlayer.photo != "",
            func.lower(FantasyPlayer.player_name) == name.lower(),
        )
        .order_by(FantasyPlayer.is_active.desc())
        .first()
    )
    if exact and exact.photo:
        return exact.photo

    parts = [part for part in re.split(r"\s+", name) if len(part) >= 3]
    if not parts:
        return None

    query = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
            FantasyPlayer.photo.isnot(None),
            FantasyPlayer.photo != "",
        )
    )
    for part in parts[:2]:
        query = query.filter(FantasyPlayer.player_name.ilike(f"%{part}%"))

    player = query.order_by(FantasyPlayer.is_active.desc()).first()
    return player.photo if player else None


def _prediction_status_stage_label(match: Match) -> str:
    """Return the human-readable stage used in a tournament-prediction status."""
    if str(match.stage or "").lower() == "group":
        return "групповой этап"

    raw = f"{match.match_round or ''} {match.api_league_round or ''} {match.stage or ''}".lower()
    if "round of 16" in raw or "1/8" in raw:
        return "1/8 финала"
    if "quarter" in raw or "1/4" in raw:
        return "1/4 финала"
    if "semi" in raw or "1/2" in raw:
        return "1/2 финала"
    if "third" in raw or "3rd" in raw or "3 место" in raw:
        return "матч за 3-е место"
    if "final" in raw:
        return "финал"
    return "плей-офф"


def _prediction_team_context(db: Session) -> dict[str, dict]:
    """Index tournament teams once for preview-card links and life-cycle statuses."""
    context: dict[str, dict] = {}
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )
    for match in matches:
        for side, raw_name, api_name, team_id in (
            ("home", match.home_team, match.home_team_api_name, match.home_external_team_id),
            ("away", match.away_team, match.away_team_api_name, match.away_external_team_id),
        ):
            name = get_team_name_ru(raw_name)
            if not name or name == "TBD":
                continue
            row = context.setdefault(name, {
                "team_id": team_id,
                "api_name": api_name or raw_name,
                "matches": [],
            })
            if team_id and not row.get("team_id"):
                row["team_id"] = team_id
            row["matches"].append((match, side))
    return context


def _team_lost_match(match: Match, side: str) -> bool:
    """Check defeat using provider winner data first, then the finished score."""
    winner = str(match.winner_side or "").lower().strip()
    if winner in {"home", "away"}:
        return winner != side
    if match.score_home is None or match.score_away is None:
        return False
    home, away = int(match.score_home), int(match.score_away)
    if home == away:
        return False
    return (home < away) if side == "home" else (away < home)


def _prediction_team_status(
    team_name: str,
    context: dict[str, dict],
    standings_by_group: dict[str, dict],
) -> dict:
    """Build a compact, factual current status for an selected tournament team."""
    record = context.get(get_team_name_ru(team_name))
    if not record:
        return {"label": "Статус уточняется", "tone": "muted"}

    entries = list(record.get("matches") or [])
    now = datetime.now(timezone.utc)
    pending = [(match, side) for match, side in entries if not bool(match.is_finished)]
    if pending:
        live_codes = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}
        is_live = any(
            str(match.status_short or "").upper() in live_codes
            or (_ensure_utc(match.starts_at) <= now <= _ensure_utc(match.starts_at) + timedelta(hours=4))
            for match, _ in pending
        )
        return {"label": "В игре" if is_live else "Участвует", "tone": "active"}

    group_entries = [(match, side) for match, side in entries if str(match.stage or "").lower() == "group"]
    if group_entries:
        group_code = next((str(match.group_code or "").strip() for match, _ in group_entries if match.group_code), "")
        group_finished = bool(group_entries) and all(bool(match.is_finished) for match, _ in group_entries)
        if group_finished and group_code:
            standing = standings_by_group.get(group_code, {}).get(get_team_name_ru(team_name))
            rank = int(standing.get("rank") or 0) if standing else 0
            if rank >= 4:
                return {"label": "Вылетела · групповой этап", "tone": "eliminated"}
            if rank:
                return {"label": "Вышла из группы", "tone": "active"}

    finished = [(match, side) for match, side in entries if bool(match.is_finished)]
    finished.sort(key=lambda item: _ensure_utc(item[0].starts_at), reverse=True)
    for match, side in finished:
        if str(match.stage or "").lower() == "group":
            continue
        stage = _prediction_status_stage_label(match)
        if _team_lost_match(match, side):
            return {"label": f"Вылетела · {stage}", "tone": "eliminated"}
        if stage == "финал":
            return {"label": "Победитель турнира", "tone": "winner"}
        if stage == "матч за 3-е место":
            return {"label": "3-е место турнира", "tone": "winner"}
        return {"label": "Продолжает путь", "tone": "active"}

    return {"label": "Участвует", "tone": "active"}


def _find_prediction_scorer(db: Session, player_name: str | None) -> dict | None:
    """Resolve a tournament-prediction scorer via cache, Fantasy roster and aliases."""
    return resolve_player_by_name(db, player_name, refresh=False)


def _serialize_tournament_prediction(prediction: TournamentPrediction | None, db: Session | None = None) -> dict | None:
    """Serialize a tournament prediction with stable profile links and live statuses."""
    if not prediction:
        return None

    payload = {
        "champion": prediction.champion,
        "runner_up": prediction.runner_up,
        "third_place": prediction.third_place,
        "top_scorer": prediction.top_scorer,
        "champion_flag": get_team_flag(prediction.champion),
        "runner_up_flag": get_team_flag(prediction.runner_up),
        "third_place_flag": get_team_flag(prediction.third_place),
        "champion_flag_code": get_team_flag_code(prediction.champion),
        "runner_up_flag_code": get_team_flag_code(prediction.runner_up),
        "third_place_flag_code": get_team_flag_code(prediction.third_place),
        "top_scorer_photo": _top_scorer_photo(db, prediction.top_scorer),
        "champion_points": prediction.champion_points or 0,
        "runner_up_points": prediction.runner_up_points or 0,
        "third_place_points": prediction.third_place_points or 0,
        "top_scorer_points": prediction.top_scorer_points or 0,
        "points": prediction.points or 0,
    }
    if db is None:
        return payload

    context = _prediction_team_context(db)
    standings = _build_group_standings(db)
    standings_by_group = {
        item.get("group_code"): {row.get("team"): row for row in item.get("rows") or []}
        for item in standings
    }
    for key in ("champion", "runner_up", "third_place"):
        name = payload.get(key) or ""
        reference = context.get(get_team_name_ru(name)) or {}
        payload[f"{key}_team_id"] = reference.get("team_id")
        payload[f"{key}_status"] = _prediction_team_status(name, context, standings_by_group)

    scorer = _find_prediction_scorer(db, prediction.top_scorer)
    payload["top_scorer_player_id"] = scorer.get("player_id") if scorer else None
    payload["top_scorer_team_id"] = scorer.get("team_id") if scorer else None
    scorer_team_name = (scorer or {}).get("team") or ""
    payload["top_scorer_status"] = _prediction_team_status(scorer_team_name, context, standings_by_group) if scorer_team_name else {"label": "Статус уточняется", "tone": "muted"}
    if scorer and not payload.get("top_scorer_photo"):
        payload["top_scorer_photo"] = scorer.get("photo") or None
    return payload


def _favorite_score(predictions: list[Prediction]) -> str | None:
    """Return the user's most frequent predicted score."""
    if not predictions:
        return None

    counts: dict[str, int] = {}

    for prediction in predictions:
        key = f"{prediction.pred_home}:{prediction.pred_away}"
        counts[key] = counts.get(key, 0) + 1

    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _profile_status(points: int, exact_scores: int, total_predictions: int, missing_count: int) -> str:
    """Return a playful profile status based on current user stats."""
    if missing_count > 0:
        return "Думающий стратег"
    if total_predictions == 0:
        return "Тень будущего прогноза"
    if exact_scores >= 5:
        return "Снайпер счета"
    if points >= 25:
        return "Кандидат в Отцы"
    if total_predictions >= 20:
        return "Стабильный участник"
    return "Футбольный шаман в разогреве"


def _profile_badges(
    *,
    exact_scores: int,
    outcomes: int,
    total_predictions: int,
    missing_count: int,
    tournament_prediction: TournamentPrediction | None,
    rank: int | None,
) -> list[dict]:
    """Build achievement badges for the Mini App profile."""
    badges = [
        {
            "code": "early_bird",
            "title": "Хладнокровный",
            "description": "Все доступные прогнозы сделаны",
            "icon": "check",
            "earned": total_predictions > 0 and missing_count == 0,
            "progress": 1 if total_predictions > 0 and missing_count == 0 else 0,
            "goal": 1,
        },
        {
            "code": "sniper",
            "title": "Снайпер",
            "description": "Точные счета",
            "icon": "target",
            "earned": exact_scores >= 3,
            "progress": min(exact_scores, 3),
            "goal": 3,
        },
        {
            "code": "oracle",
            "title": "Оракул исходов",
            "description": "Угаданные исходы",
            "icon": "fire",
            "earned": outcomes >= 5,
            "progress": min(outcomes, 5),
            "goal": 5,
        },
        {
            "code": "marathon",
            "title": "Марафонец",
            "description": "Прогнозы на матчи",
            "icon": "ball",
            "earned": total_predictions >= 20,
            "progress": min(total_predictions, 20),
            "goal": 20,
        },
        {
            "code": "longterm",
            "title": "Долгосрочник",
            "description": "Турнирный прогноз заполнен",
            "icon": "cup",
            "earned": tournament_prediction is not None,
            "progress": 1 if tournament_prediction else 0,
            "goal": 1,
        },
        {
            "code": "top3",
            "title": "На пьедестале",
            "description": "Попасть в топ-3 рейтинга",
            "icon": "rank",
            "earned": bool(rank and rank <= 3),
            "progress": 1 if rank and rank <= 3 else 0,
            "goal": 1,
        },
    ]

    return badges



FANTASY_FORMATION = "4-3-3"
FANTASY_SUPPORTED_FORMATIONS = {
    "4-3-3": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 3, "Attacker": 3},
    "4-4-2": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 4, "Attacker": 2},
    "4-2-2": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 4, "Attacker": 2},
    "5-4-1": {"Goalkeeper": 1, "Defender": 5, "Midfielder": 4, "Attacker": 1},
    "4-5-1": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 5, "Attacker": 1},
    "3-5-2": {"Goalkeeper": 1, "Defender": 3, "Midfielder": 5, "Attacker": 2},
    "3-4-3": {"Goalkeeper": 1, "Defender": 3, "Midfielder": 4, "Attacker": 3},
    "5-3-2": {"Goalkeeper": 1, "Defender": 5, "Midfielder": 3, "Attacker": 2},
    "4-1-4-1": {"Goalkeeper": 1, "Defender": 4, "Midfielder": 5, "Attacker": 1},
}
FANTASY_SQUAD_POSITION_LIMITS = {
    "Goalkeeper": 2,
    "Defender": 5,
    "Midfielder": 5,
    "Attacker": 3,
}
FANTASY_STARTER_POSITION_LIMITS = FANTASY_SUPPORTED_FORMATIONS[FANTASY_FORMATION]
FANTASY_POSITION_LABELS = {
    "Goalkeeper": "ВР",
    "Defender": "ЗЩ",
    "Midfielder": "ПЗ",
    "Attacker": "НП",
}
FANTASY_CATEGORY_LIMITS_GROUP = {1: 3, 2: 3, 3: 3, 4: 2}
FANTASY_CATEGORY_LIMITS_R16 = {1: 4, 2: 4, 3: 4, 4: 3}
FANTASY_MAX_FROM_ONE_TEAM_BY_STAGE = {
    "group_1": 2,
    "group_2": 2,
    "group_3": 2,
    "r16": 2,
    "quarter": 2,
    "semi": 2,
    "final": 2,
}
FANTASY_FREE_TRANSFERS = {
    "group_1": None,
    "group_2": 2,
    "group_3": 2,
    "r16": None,
    "quarter": 4,
    "semi": 5,
    "final": 6,
}
FANTASY_EXTRA_TRANSFER_PENALTY = 3


def _parse_round_number(value: str | None) -> int | None:
    """Parse group round number from match_round/api text."""
    if not value:
        return None

    text = str(value).lower()
    for number in (1, 2, 3):
        if str(number) in text:
            return number
    return None


def _fantasy_stage_key(match: Match) -> str:
    """Return fantasy transfer window key for a match."""
    if match.stage == "group":
        return f"group_{_parse_round_number(match.match_round) or 1}"

    text = f"{match.stage or ''} {match.match_round or ''} {match.api_league_round or ''}".lower()

    if "round of 16" in text or "1/8" in text or "16" in text:
        return "r16"
    if "quarter" in text or "1/4" in text:
        return "quarter"
    if "semi" in text or "1/2" in text:
        return "semi"
    if "third" in text or "3" in text:
        return "final"
    if "final" in text:
        return "final"

    return match.stage or "future"


def _fantasy_stage_title(key: str) -> str:
    """Return user-facing fantasy stage title."""
    return {
        "group_1": "1-й тур группового этапа",
        "group_2": "2-й тур группового этапа",
        "group_3": "3-й тур группового этапа",
        "r16": "1/8 финала",
        "quarter": "1/4 финала",
        "semi": "1/2 финала",
        "final": "финал и матч за 3 место",
    }.get(key, key)


def _fantasy_round_state(db: Session) -> dict:
    """Return current fantasy transfer window and next deadline."""
    now = datetime.now(timezone.utc)
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .all()
    )

    windows: dict[str, datetime] = {}
    order = ["group_1", "group_2", "group_3", "r16", "quarter", "semi", "final"]

    for match in matches:
        key = _fantasy_stage_key(match)
        starts_at = _ensure_utc(match.starts_at)
        if key not in windows or starts_at < windows[key]:
            windows[key] = starts_at

    upcoming_key = None
    upcoming_deadline = None

    for key in order:
        deadline = windows.get(key)
        if deadline and deadline > now:
            upcoming_key = key
            upcoming_deadline = deadline
            break

    if not upcoming_key:
        return {
            "key": "locked",
            "title": "Трансферы закрыты",
            "deadline_at": None,
            "is_locked": True,
            "free_transfers": 0,
            "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
            "max_from_one_team": 2,
            "category_limits": {},
            "category_limits_enabled": False,
        }

    if upcoming_key == "group_1":
        category_limits = FANTASY_CATEGORY_LIMITS_GROUP
    elif upcoming_key == "r16":
        category_limits = FANTASY_CATEGORY_LIMITS_R16
    elif upcoming_key.startswith("group_"):
        category_limits = FANTASY_CATEGORY_LIMITS_GROUP
    else:
        category_limits = {}

    return {
        "key": upcoming_key,
        "title": _fantasy_stage_title(upcoming_key),
        "deadline_at": upcoming_deadline.isoformat(),
        "is_locked": False,
        "free_transfers": FANTASY_FREE_TRANSFERS.get(upcoming_key),
        "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
        "max_from_one_team": FANTASY_MAX_FROM_ONE_TEAM_BY_STAGE.get(upcoming_key, 2),
        "category_limits": category_limits,
        "category_limits_enabled": bool(category_limits),
    }


def _load_baseline_ids(value: str | None) -> set[int]:
    """Load baseline player IDs from serialized text."""
    if not value:
        return set()
    try:
        return {int(item) for item in json.loads(value)}
    except Exception:
        return set()


def _fantasy_category_title(category: int) -> str:
    """Return readable FIFA ranking category title."""
    return {
        1: "Элита",
        2: "Сильные претенденты",
        3: "Середина",
        4: "Аутсайдеры и дебютанты",
    }.get(category, "Категория")


def _serialize_fantasy_player(player: FantasyPlayer) -> dict:
    """Serialize a fantasy player for Mini App."""
    return {
        "id": player.id,
        "external_player_id": player.external_player_id,
        "external_team_id": player.external_team_id,
        "name": player.player_name,
        "team_name": player.team_name,
        "team_display_name": player.team_display_name,
        "team_flag": player.team_flag or get_team_flag(player.team_display_name, player.team_name),
        "age": player.age,
        "number": player.number,
        "position": player.position,
        "position_label": FANTASY_POSITION_LABELS.get(player.position, player.position),
        "photo": player.photo,
        "fifa_rank": player.fifa_rank,
        "fifa_category": player.fifa_category,
        "fifa_category_title": _fantasy_category_title(player.fifa_category),
        "is_active": bool(player.is_active),
    }


def _serialize_fantasy_team(team: FantasyTeam | None) -> dict | None:
    """Serialize user's fantasy team."""
    if not team:
        return None

    team_players = sorted(
        team.players,
        key=lambda item: (
            {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Attacker": 3}.get(item.position, 9),
            item.position_slot,
        ),
    )

    return {
        "id": team.id,
        "formation": team.formation,
        "captain_player_id": team.captain_player_id,
        "points": team.points or 0,
        "is_locked": bool(team.is_locked),
        "transfer_window_key": getattr(team, "transfer_window_key", None),
        "transfers_used": getattr(team, "transfers_used", 0) or 0,
        "transfer_penalty_points": getattr(team, "transfer_penalty_points", 0) or 0,
        "players": [
            {
                "position_slot": item.position_slot,
                "position": item.position,
                "position_label": FANTASY_POSITION_LABELS.get(item.position, item.position),
                "is_captain": bool(item.is_captain),
                "is_starter": bool(getattr(item, "is_starter", True)),
                "bench_order": getattr(item, "bench_order", None),
                "points": item.points or 0,
                "player": _serialize_fantasy_player(item.player),
            }
            for item in team_players
        ],
    }


def _fantasy_rules_payload(db: Session | None = None) -> dict:
    """Return FIFA-style fantasy rules adapted for WC2026 Mini App."""
    round_state = _fantasy_round_state(db) if db is not None else {
        "key": "group_1",
        "title": "1-й тур группового этапа",
        "deadline_at": None,
        "is_locked": is_tournament_started(),
        "free_transfers": None,
        "extra_transfer_penalty": FANTASY_EXTRA_TRANSFER_PENALTY,
        "max_from_one_team": 2,
        "category_limits": FANTASY_CATEGORY_LIMITS_GROUP,
        "category_limits_enabled": True,
    }
    # FIFA ranking category limits are intentionally disabled.
    category_limits = {}
    max_from_one_team = round_state.get("max_from_one_team") or 2

    return {
        "formation": FANTASY_FORMATION,
        "supported_formations": FANTASY_SUPPORTED_FORMATIONS,
        "squad_size": 15,
        "starters_size": 11,
        "squad_positions": FANTASY_SQUAD_POSITION_LIMITS,
        "starter_positions": FANTASY_STARTER_POSITION_LIMITS,
        "position_labels": FANTASY_POSITION_LABELS,
        "max_from_one_team": max_from_one_team,
        "category_limits": category_limits,
        "round_state": round_state,
        "categories": [
            {"id": 1, "title": "Элита", "range": "ФИФА 1–12", "limit": category_limits.get(1), "enabled": 1 in category_limits},
            {"id": 2, "title": "Сильные претенденты", "range": "ФИФА 13–24", "limit": category_limits.get(2), "enabled": 2 in category_limits},
            {"id": 3, "title": "Середина", "range": "ФИФА 25–36", "limit": category_limits.get(3), "enabled": 3 in category_limits},
            {"id": 4, "title": "Аутсайдеры и дебютанты", "range": "ФИФА 37–48", "limit": category_limits.get(4), "enabled": 4 in category_limits},
        ],
        "transfer_rules": [
            {"stage": "До 1-го тура", "free": "без ограничений", "penalty": 0},
            {"stage": "До 2-го тура", "free": 2, "penalty": -3},
            {"stage": "До 3-го тура", "free": 2, "penalty": -3},
            {"stage": "До 1/8", "free": "без ограничений", "penalty": 0},
            {"stage": "До 1/4", "free": 4, "penalty": -3},
            {"stage": "До 1/2", "free": 5, "penalty": -3},
            {"stage": "Перед финалом", "free": 6, "penalty": -3},
        ],
        "scoring": [
            {"title": "Выход на поле", "description": "игрок сыграл в матче", "points": 1, "type": "plus"},
            {"title": "60+ минут", "description": "игрок провел на поле 60 минут и больше", "points": 1, "type": "plus"},
            {"title": "Гол вратаря", "description": "ВР забил гол", "points": 9, "type": "plus"},
            {"title": "Гол защитника", "description": "ЗЩ забил гол", "points": 7, "type": "plus"},
            {"title": "Гол полузащитника", "description": "ПЗ забил гол", "points": 5, "type": "plus"},
            {"title": "Гол нападающего", "description": "НП забил гол", "points": 5, "type": "plus"},
            {"title": "Голевая передача", "description": "ассист", "points": 3, "type": "plus"},
            {"title": "Сухой матч", "description": "ВР или ЗЩ, 60+ минут", "points": 5, "type": "plus"},
            {"title": "Сухой матч ПЗ", "description": "ПЗ, 60+ минут", "points": 1, "type": "plus"},
            {"title": "3 сейва", "description": "ВР: каждые 3 сейва", "points": 1, "type": "plus"},
            {"title": "Отбитый пенальти", "description": "ВР отбил пенальти", "points": 3, "type": "plus"},
            {"title": "Отборы", "description": "ПЗ: каждые 3 отбора", "points": 1, "type": "plus"},
            {"title": "Удары в створ", "description": "НП: каждые 2 удара в створ", "points": 1, "type": "plus"},
            {"title": "Желтая карточка", "description": "предупреждение", "points": -1, "type": "minus"},
            {"title": "Красная карточка", "description": "удаление", "points": -2, "type": "minus"},
            {"title": "Автогол", "description": "гол в свои ворота", "points": -2, "type": "minus"},
            {"title": "Нереализованный пенальти", "description": "игрок не забил пенальти", "points": -2, "type": "minus"},
        ],
        "detailed_rules": [
            "Состав: 15 игроков — 2 ВР, 5 ЗЩ, 5 ПЗ, 3 НП. В основе 11 игроков по схеме 4-3-3.",
            "Игроки скамейки тоже набирают очки, но в общий счет идут только очки основы и ручные/автоматические замены по правилам тура.",
            "Капитана можно менять внутри тура только на игрока, который еще не сыграл. Если капитан заменен, двойные очки предыдущего капитана теряются.",
            "Перед 1-м туром и 1/8 финала трансферы бесплатные без ограничений. Перед 2-м и 3-м турами — 2 бесплатных трансфера, перед 1/4 — 4, перед 1/2 — 5, перед финалом — 6.",
            "Каждый лишний трансфер дает штраф -3 очка.",
            "Бюджета игроков в нашей версии нет.",
            "Лимит сборных: групповой этап — до 3 игроков из одной сборной, 1/8 — до 4, 1/4 — до 5, 1/2 — до 6, финал — до 8.",
            "Лимиты по категориям FIFA действуют на группе и 1/8; с 1/4 ограничения Г1/Г2/Г3/Г4 снимаются.",
        ],
        "captain": {
            "enabled": True,
            "multiplier": 2,
            "description": "Очки капитана удваиваются.",
        },
        "is_locked": bool(round_state.get("is_locked")),
    }

def _fantasy_team_summary(team: FantasyTeam | None) -> dict:
    """Build fantasy progress summary."""
    if not team:
        return {
            "selected": 0,
            "total": 15,
            "progress": "0/15",
            "points": 0,
            "captain_selected": False,
            "complete": False,
        }

    selected = len(team.players)
    return {
        "selected": selected,
        "total": 15,
        "progress": f"{selected}/15",
        "points": team.points or 0,
        "captain_selected": team.captain_player_id is not None,
        "complete": selected == 15 and team.captain_player_id is not None,
    }


def _validate_fantasy_payload(
    players: list[FantasyPlayer],
    starting_player_ids: list[int],
    captain_player_id: int,
    formation: str,
    rules: dict,
) -> None:
    """Validate fantasy squad, starting XI and active transfer-window constraints."""
    if len(players) != 15:
        raise HTTPException(status_code=400, detail="В fantasy-команде должно быть ровно 15 игроков.")

    player_ids = [player.id for player in players]

    if len(set(player_ids)) != 15:
        raise HTTPException(status_code=400, detail="Игроки в fantasy-команде не должны повторяться.")

    if len(set(starting_player_ids)) != 11:
        raise HTTPException(status_code=400, detail="В стартовом составе должно быть ровно 11 разных игроков.")

    if not set(starting_player_ids).issubset(set(player_ids)):
        raise HTTPException(status_code=400, detail="Стартовый состав должен состоять из игроков вашей fantasy-команды.")

    if captain_player_id not in starting_player_ids:
        raise HTTPException(status_code=400, detail="Капитан должен быть выбран из стартового состава.")

    position_counts = Counter(player.position for player in players)

    for position, limit in FANTASY_SQUAD_POSITION_LIMITS.items():
        if position_counts.get(position, 0) != limit:
            label = FANTASY_POSITION_LABELS.get(position, position)
            raise HTTPException(
                status_code=400,
                detail=f"В заявке нужно выбрать {limit} игроков позиции {label}.",
            )

    players_by_id = {player.id: player for player in players}
    starter_limits = FANTASY_SUPPORTED_FORMATIONS.get(formation)

    if not starter_limits:
        raise HTTPException(status_code=400, detail=f"Схема {formation} не поддерживается.")

    starter_counts = Counter(players_by_id[player_id].position for player_id in starting_player_ids)

    for position, limit in starter_limits.items():
        if starter_counts.get(position, 0) != limit:
            label = FANTASY_POSITION_LABELS.get(position, position)
            raise HTTPException(
                status_code=400,
                detail=f"Для схемы {formation} в основе нужно выбрать {limit} игроков позиции {label}.",
            )

    max_from_one_team = rules.get("max_from_one_team") or 2
    team_counts = Counter(player.team_display_name for player in players)
    too_many_team = [team for team, count in team_counts.items() if count > max_from_one_team]

    if too_many_team:
        raise HTTPException(
            status_code=400,
            detail=f"На текущей стадии из одной сборной можно взять не больше {max_from_one_team} игроков: {too_many_team[0]}.",
        )

    # FIFA ranking category limits are disabled by product decision.


@router.get("/fantasy/rules")
def get_fantasy_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return fantasy rules and scoring."""
    return _fantasy_rules_payload(db)


@router.get("/fantasy/players")
def get_fantasy_players(
    position: str | None = Query(default=None),
    team: str | None = Query(default=None),
    category: int | None = Query(default=None, ge=1, le=4),
    q: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return fantasy players with filters."""
    query = db.query(FantasyPlayer).filter(
        FantasyPlayer.tournament_code == TOURNAMENT_CODE,
        FantasyPlayer.is_active == True,
    )

    if position:
        query = query.filter(FantasyPlayer.position == position)

    if team:
        query = query.filter(FantasyPlayer.team_display_name == team)

    if category:
        query = query.filter(FantasyPlayer.fifa_category == category)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(FantasyPlayer.player_name.ilike(like))

    players = (
        query
        .order_by(
            FantasyPlayer.fifa_category.asc(),
            FantasyPlayer.team_display_name.asc(),
            FantasyPlayer.position.asc(),
            FantasyPlayer.player_name.asc(),
        )
        .limit(limit)
        .all()
    )

    teams = [
        {"name": name, "flag": get_team_flag(name)}
        for (name,) in db.query(FantasyPlayer.team_display_name)
        .filter(FantasyPlayer.tournament_code == TOURNAMENT_CODE, FantasyPlayer.is_active == True)
        .distinct()
        .order_by(FantasyPlayer.team_display_name.asc())
        .all()
    ]

    return {
        "players": [_serialize_fantasy_player(player) for player in players],
        "teams": teams,
        "rules": _fantasy_rules_payload(db),
    }



def _serialize_fantasy_stat_row(row: FantasyPlayerMatchStat) -> dict:
    """Serialize one fantasy player match stat row."""
    match = row.match
    return {
        "match_id": row.match_id,
        "match_label": _match_label(match) if match else None,
        "starts_at": _ensure_utc(match.starts_at).isoformat() if match and match.starts_at else None,
        "minutes": row.minutes or 0,
        "goals": row.goals or 0,
        "assists": row.assists or 0,
        "starts": bool(row.starts),
        "saves": row.saves or 0,
        "penalties_saved": row.penalties_saved or 0,
        "balls_recovered": row.balls_recovered or 0,
        "shots_on_target": row.shots_on_target or 0,
        "yellow_cards": row.yellow_cards or 0,
        "red_cards": row.red_cards or 0,
        "clean_sheet": bool(row.clean_sheet),
        "goals_conceded": row.goals_conceded or 0,
        "own_goals": row.own_goals or 0,
        "penalty_missed": row.penalty_missed or 0,
        "points": row.points or 0,
        "source_updated_at": _ensure_utc(row.source_updated_at).isoformat() if row.source_updated_at else None,
    }


def _fantasy_teams_visibility(db: Session) -> dict:
    """Return whether fantasy squads may be shown to other participants."""
    now = datetime.now(timezone.utc)
    started_match = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at <= now,
        )
        .order_by(Match.starts_at.desc())
        .first()
    )

    if not started_match:
        return {
            "visible": False,
            "stage_key": "pre_tournament",
            "title": "До старта 1 тура",
            "reason": "Составы участников откроются после старта первого тура/стадии.",
        }

    return {
        "visible": True,
        "stage_key": _fantasy_stage_key(started_match),
        "title": _fantasy_stage_title(_fantasy_stage_key(started_match)),
        "reason": None,
    }


@router.get("/fantasy/players/{player_id}/stats")
def get_fantasy_player_stats(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return fantasy player statistics and points breakdown."""
    player = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.id == player_id,
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    if not player:
        raise HTTPException(status_code=404, detail="Fantasy player not found")

    rows = (
        db.query(FantasyPlayerMatchStat)
        .filter(FantasyPlayerMatchStat.player_id == player.id)
        .join(Match, FantasyPlayerMatchStat.match_id == Match.id)
        .order_by(Match.starts_at.asc())
        .all()
    )

    total_points = sum((row.points or 0) for row in rows)

    totals = {
        "minutes": sum((row.minutes or 0) for row in rows),
        "goals": sum((row.goals or 0) for row in rows),
        "assists": sum((row.assists or 0) for row in rows),
        "saves": sum((row.saves or 0) for row in rows),
        "penalties_saved": sum((row.penalties_saved or 0) for row in rows),
        "balls_recovered": sum((row.balls_recovered or 0) for row in rows),
        "shots_on_target": sum((row.shots_on_target or 0) for row in rows),
        "yellow_cards": sum((row.yellow_cards or 0) for row in rows),
        "red_cards": sum((row.red_cards or 0) for row in rows),
        "clean_sheets": sum(1 for row in rows if row.clean_sheet),
        "goals_conceded": sum((row.goals_conceded or 0) for row in rows),
        "own_goals": sum((row.own_goals or 0) for row in rows),
        "penalty_missed": sum((row.penalty_missed or 0) for row in rows),
    }

    return {
        "player": _serialize_fantasy_player(player),
        "total_points": total_points,
        "totals": totals,
        "matches": [_serialize_fantasy_stat_row(row) for row in rows],
    }


@router.get("/fantasy/teams")
def get_visible_fantasy_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return participants' fantasy squads after the current tour/stage has started."""
    visibility = _fantasy_teams_visibility(db)

    if not visibility["visible"]:
        return {
            "visible": False,
            "visibility": visibility,
            "teams": [],
        }

    teams = (
        db.query(FantasyTeam)
        .filter(FantasyTeam.tournament_code == TOURNAMENT_CODE)
        .join(User, FantasyTeam.user_id == User.id)
        .order_by(User.display_name.asc())
        .all()
    )

    return {
        "visible": True,
        "visibility": visibility,
        "teams": [
            {
                "user": {
                    "id": team.user.id,
                    "display_name": team.user.display_name,
                    "username": team.user.username,
                    "is_current_user": team.user_id == current_user.id,
                },
                "team": _serialize_fantasy_team(team),
            }
            for team in teams
        ],
    }




@router.get("/fantasy/team/me")
def get_my_fantasy_team(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's fantasy team."""
    team = (
        db.query(FantasyTeam)
        .filter(
            FantasyTeam.user_id == current_user.id,
            FantasyTeam.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    return {
        "team": _serialize_fantasy_team(team),
        "summary": _fantasy_team_summary(team),
        "rules": _fantasy_rules_payload(db),
    }


@router.post("/fantasy/team")
def save_my_fantasy_team(
    payload: FantasyTeamPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save current user's fantasy squad and apply transfer-window rules."""
    rules = _fantasy_rules_payload(db)
    round_state = rules["round_state"]

    if round_state.get("is_locked"):
        raise HTTPException(status_code=400, detail="Fantasy-команду уже нельзя менять: дедлайны турнира прошли.")

    if payload.formation not in FANTASY_SUPPORTED_FORMATIONS:
        raise HTTPException(status_code=400, detail=f"Схема {payload.formation} не поддерживается.")

    players = (
        db.query(FantasyPlayer)
        .filter(
            FantasyPlayer.tournament_code == TOURNAMENT_CODE,
            FantasyPlayer.is_active == True,
            FantasyPlayer.id.in_(payload.player_ids),
        )
        .all()
    )

    if len(players) != len(set(payload.player_ids)):
        raise HTTPException(status_code=400, detail="Не все выбранные игроки найдены в fantasy-списке.")

    _validate_fantasy_payload(players, payload.starting_player_ids, payload.captain_player_id, payload.formation, rules)

    team = (
        db.query(FantasyTeam)
        .filter(
            FantasyTeam.user_id == current_user.id,
            FantasyTeam.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    new_ids = {int(player_id) for player_id in payload.player_ids}
    window_key = round_state["key"]
    free_transfers = round_state.get("free_transfers")
    transfers_used = 0
    transfer_penalty = 0

    if not team:
        team = FantasyTeam(
            user_id=current_user.id,
            tournament_code=TOURNAMENT_CODE,
            formation=payload.formation,
        )
        db.add(team)
        db.flush()
        baseline_ids = set(new_ids)
    else:
        current_ids = {item.player_id for item in team.players}
        if team.transfer_window_key != window_key:
            baseline_ids = set(current_ids)
        else:
            baseline_ids = _load_baseline_ids(getattr(team, "transfer_baseline_player_ids", None)) or set(current_ids)

        if free_transfers is not None and baseline_ids:
            transfers_used = len(new_ids - baseline_ids)
            transfer_penalty = max(0, transfers_used - int(free_transfers)) * FANTASY_EXTRA_TRANSFER_PENALTY

    team.formation = payload.formation
    team.captain_player_id = payload.captain_player_id
    team.transfer_window_key = window_key
    team.transfer_baseline_player_ids = json.dumps(sorted(baseline_ids))
    team.transfers_used = transfers_used
    team.transfer_penalty_points = transfer_penalty
    team.updated_at = datetime.now(timezone.utc)

    db.query(FantasyTeamPlayer).filter(FantasyTeamPlayer.fantasy_team_id == team.id).delete()

    players_by_id = {player.id: player for player in players}
    starter_id_set = {int(player_id) for player_id in payload.starting_player_ids}
    position_indexes: dict[str, int] = {}
    order = {"Goalkeeper": 0, "Defender": 1, "Midfielder": 2, "Attacker": 3}

    starter_ordered_ids = list(payload.starting_player_ids)
    bench_ordered_ids = [player_id for player_id in payload.player_ids if player_id not in starter_id_set]
    ordered_ids = starter_ordered_ids + bench_ordered_ids

    for player_id in ordered_ids:
        player = players_by_id[int(player_id)]
        is_starter = player.id in starter_id_set
        position_indexes[player.position] = position_indexes.get(player.position, 0) + 1
        slot_prefix = FANTASY_POSITION_LABELS.get(player.position, player.position)
        slot = f"{slot_prefix}{position_indexes[player.position]}" if is_starter else f"ЗАП{len([x for x in ordered_ids[:ordered_ids.index(player_id)] if x not in starter_id_set]) + 1}"
        db.add(
            FantasyTeamPlayer(
                fantasy_team_id=team.id,
                player_id=player.id,
                position_slot=slot,
                position=player.position,
                is_captain=player.id == payload.captain_player_id,
                is_starter=is_starter,
                bench_order=None if is_starter else bench_ordered_ids.index(player.id) + 1,
            )
        )

    db.commit()
    db.refresh(team)

    return {
        "team": _serialize_fantasy_team(team),
        "summary": _fantasy_team_summary(team),
        "rules": _fantasy_rules_payload(db),
    }




@router.get("/notifications/settings")
def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's notification subscriptions."""
    return {
        "options": NOTIFICATION_OPTIONS,
        "settings": _notification_settings_for_user(db, current_user),
    }


@router.post("/notifications/settings")
def save_notification_settings(
    payload: NotificationSettingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save current user's notification subscriptions."""
    allowed = {option["key"] for option in NOTIFICATION_OPTIONS}

    for key, value in payload.settings.items():
        if key not in allowed:
            continue

        setting = (
            db.query(UserNotificationSetting)
            .filter(
                UserNotificationSetting.user_id == current_user.id,
                UserNotificationSetting.notification_key == key,
            )
            .first()
        )

        if not setting:
            setting = UserNotificationSetting(
                user_id=current_user.id,
                notification_key=key,
                is_enabled=bool(value),
            )
            db.add(setting)
        else:
            setting.is_enabled = bool(value)
            setting.updated_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "options": NOTIFICATION_OPTIONS,
        "settings": _notification_settings_for_user(db, current_user),
    }


def _serialize_admin_match(match: Match) -> dict:
    """Serialize match for admin panel."""
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)

    return {
        "id": match.id,
        "external_fixture_id": match.external_fixture_id,
        "label": _match_label(match),
        "home_team": home_name,
        "away_team": away_name,
        "home_flag": get_team_flag(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag": get_team_flag(away_name, getattr(match, "away_team_api_name", None)),
        "home_flag_code": get_team_flag_code(home_name, getattr(match, "home_team_api_name", None)),
        "away_flag_code": get_team_flag_code(away_name, getattr(match, "away_team_api_name", None)),
        "starts_at": _ensure_utc(match.starts_at).isoformat(),
        "stage": match.stage,
        "match_round": match.match_round,
        "group_code": match.group_code,
        "score_home": match.score_home,
        "score_away": match.score_away,
        "winner_side": match.winner_side,
        "is_finished": bool(match.is_finished),
        "status_short": match.status_short,
        "status_long": match.status_long,
        "videos_count": len(getattr(match, "videos", []) or []),
    }


def _calculate_fantasy_points_for_stat(player: FantasyPlayer, stat: dict) -> int:
    """Calculate fantasy points using current Mini App scoring rules."""
    minutes = int(stat.get("minutes") or 0)
    goals = int(stat.get("goals") or 0)
    assists = int(stat.get("assists") or 0)
    saves = int(stat.get("saves") or 0)
    penalties_saved = int(stat.get("penalties_saved") or 0)
    balls_recovered = int(stat.get("balls_recovered") or 0)
    shots_on_target = int(stat.get("shots_on_target") or 0)
    yellow_cards = int(stat.get("yellow_cards") or 0)
    red_cards = int(stat.get("red_cards") or 0)
    own_goals = int(stat.get("own_goals") or 0)
    penalty_missed = int(stat.get("penalty_missed") or 0)
    goals_conceded = int(stat.get("goals_conceded") or 0)
    clean_sheet = bool(stat.get("clean_sheet"))

    if minutes <= 0:
        return 0

    points = 1

    if minutes >= 60:
        points += 1

    if player.position == "Goalkeeper":
        points += goals * 9
    elif player.position == "Defender":
        points += goals * 7
    else:
        points += goals * 5

    points += assists * 3

    if clean_sheet and player.position in {"Goalkeeper", "Defender"}:
        points += 5
    elif clean_sheet and player.position == "Midfielder":
        points += 1

    if player.position == "Goalkeeper":
        points += saves // 3
        points += penalties_saved * 3

    if player.position == "Midfielder":
        points += balls_recovered // 3

    if player.position == "Attacker":
        points += shots_on_target // 2

    if player.position in {"Goalkeeper", "Defender"}:
        points -= goals_conceded

    points -= yellow_cards
    points -= red_cards * 2
    points -= own_goals * 2
    points -= penalty_missed * 2

    return points


def _extract_player_fixture_stats(api_player_item: dict) -> dict:
    """Extract the first fixture statistics block from API-Football /fixtures/players."""
    statistics = api_player_item.get("statistics") or []
    first = statistics[0] if statistics else {}

    games = first.get("games") or {}
    goals = first.get("goals") or {}
    passes = first.get("passes") or {}
    cards = first.get("cards") or {}
    penalty = first.get("penalty") or {}
    tackles = first.get("tackles") or {}
    shots = first.get("shots") or {}

    return {
        "minutes": games.get("minutes") or 0,
        "starts": bool(games.get("captain") is not None and games.get("minutes")),
        "goals": goals.get("total") or 0,
        "assists": goals.get("assists") or 0,
        "saves": goals.get("saves") or 0,
        "penalties_saved": penalty.get("saved") or 0,
        "balls_recovered": tackles.get("total") or 0,
        "shots_on_target": shots.get("on") or 0,
        "yellow_cards": cards.get("yellow") or 0,
        "red_cards": cards.get("red") or 0,
        "own_goals": goals.get("conceded_own") or 0,
        "penalty_missed": penalty.get("missed") or 0,
        "goals_conceded": goals.get("conceded") or 0,
        "clean_sheet": bool((games.get("minutes") or 0) >= 60 and (goals.get("conceded") or 0) == 0),
    }


def _recalculate_fantasy_team_points(db: Session) -> int:
    """Recalculate fantasy team points from stored player match stats."""
    teams = db.query(FantasyTeam).filter(FantasyTeam.tournament_code == TOURNAMENT_CODE).all()
    updated = 0

    for team in teams:
        total = 0

        for item in team.players:
            stat_points = (
                db.query(func.coalesce(func.sum(FantasyPlayerMatchStat.points), 0))
                .filter(FantasyPlayerMatchStat.player_id == item.player_id)
                .scalar()
            ) or 0

            player_points = int(stat_points)

            if item.is_captain:
                player_points *= 2

            item.points = player_points
            total += player_points

        team.points = total - (getattr(team, "transfer_penalty_points", 0) or 0)
        team.updated_at = datetime.now(timezone.utc)
        updated += 1

    return updated


@router.get("/admin/overview")
def get_admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return admin panel overview."""
    _require_miniapp_admin(current_user)

    now = datetime.now(timezone.utc)
    recent_matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
        .limit(200)
        .all()
    )
    active_players = (
        db.query(FantasyPlayer)
        .filter(FantasyPlayer.tournament_code == TOURNAMENT_CODE, FantasyPlayer.is_active == True)
        .count()
    )
    fantasy_stats_count = db.query(FantasyPlayerMatchStat).count()
    active_push_subscriptions = (
        db.query(PushSubscription)
        .filter(PushSubscription.is_active == True)
        .count()
    )
    push_users_count = (
        db.query(PushSubscription.user_id)
        .filter(PushSubscription.is_active == True)
        .distinct()
        .count()
    )

    return {
        "matches": [_serialize_admin_match(match) for match in recent_matches],
        "summary": {
            "matches_total": len(recent_matches),
            "finished": sum(1 for match in recent_matches if match.is_finished),
            "ready_for_api_sync": sum(1 for match in recent_matches if not match.is_finished and _ensure_utc(match.starts_at) <= now),
            "active_fantasy_players": active_players,
            "fantasy_stat_rows": fantasy_stats_count,
            "active_push_subscriptions": active_push_subscriptions,
            "push_users_count": push_users_count,
        },
        "notification_options": NOTIFICATION_OPTIONS,
        "notification_settings": {
            key: _get_app_setting(db, key, default)
            for key, default in ADMIN_NOTIFICATION_SETTING_KEYS.items()
        },
    }




@router.get("/app-version")
def get_app_version(response: Response) -> dict:
    """Return currently deployed backend/frontend version for PWA update checks."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    version_path = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except Exception:
        version = "unknown"

    return {
        "version": version,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/admin/match-videos/sync-matchtv")
def admin_sync_matchtv_videos(
    payload: MatchTvSyncPayload | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Discover and link Match TV videos for nearby World Cup matches."""
    _require_miniapp_admin(current_user)
    payload = payload or MatchTvSyncPayload()

    result = sync_matchtv_videos(
        db,
        lookback_days=payload.lookback_days,
        lookahead_days=payload.lookahead_days,
        activate_min_confidence=payload.activate_min_confidence,
    )

    return {
        "message": (
            f"Match TV: найдено {result['videos_found_on_source']}, "
            f"проверено матчей {result['matches_checked']}, "
            f"связано {result['videos_matched']}, "
            f"добавлено {result['created']}, обновлено {result['updated']}. "
            f"Без изменений {result.get('duplicates_unchanged', 0)}, "
            f"push {result.get('push_notifications_sent', 0)}, "
            f"не связано {result['skipped_low_confidence']}"
        ),
        **result,
    }


@router.get("/admin/matches/{match_id}/videos")
def admin_get_match_videos(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return video links configured for a match."""
    _require_miniapp_admin(current_user)

    match = db.query(Match).filter(Match.id == match_id, Match.tournament_code == TOURNAMENT_CODE).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")

    videos = (
        db.query(MatchVideo)
        .filter(MatchVideo.match_id == match.id)
        .order_by(MatchVideo.priority.asc(), MatchVideo.id.asc())
        .all()
    )

    return {
        "match": _serialize_admin_match(match),
        "videos": [_serialize_match_video(video) for video in videos],
    }


@router.post("/admin/matches/{match_id}/videos")
def admin_create_match_video(
    match_id: int,
    payload: MatchVideoPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a video link for a match."""
    _require_miniapp_admin(current_user)

    match = db.query(Match).filter(Match.id == match_id, Match.tournament_code == TOURNAMENT_CODE).first()
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")

    data = _normalize_match_video_payload(payload)
    video = MatchVideo(match_id=match.id, **data)
    db.add(video)
    db.commit()
    db.refresh(video)

    return {
        "message": f"Видео добавлено: {video.title}",
        "video": _serialize_match_video(video),
    }


@router.put("/admin/match-videos/{video_id}")
def admin_update_match_video(
    video_id: int,
    payload: MatchVideoPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update an existing match video link."""
    _require_miniapp_admin(current_user)

    video = db.query(MatchVideo).filter(MatchVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")

    data = _normalize_match_video_payload(payload)
    for key, value in data.items():
        setattr(video, key, value)
    video.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(video)

    return {
        "message": f"Видео обновлено: {video.title}",
        "video": _serialize_match_video(video),
    }


@router.delete("/admin/match-videos/{video_id}")
def admin_delete_match_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a video link from a match."""
    _require_miniapp_admin(current_user)

    video = db.query(MatchVideo).filter(MatchVideo.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")

    title = video.title
    db.delete(video)
    db.commit()

    return {"message": f"Видео удалено: {title}"}


@router.post("/admin/matches/{match_id}/result")
def admin_set_match_result(
    match_id: int,
    payload: MatchResultPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Manually set match result from Mini App admin panel."""
    _require_miniapp_admin(current_user)

    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    try:
        lines = apply_match_result_from_admin(
            db=db,
            match=match,
            score_home=payload.score_home,
            score_away=payload.score_away,
            winner_side=payload.winner_side,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    db.refresh(match)

    return {
        "ok": True,
        "match": _serialize_admin_match(match),
        "message": "\n".join(lines),
    }


@router.post("/admin/matches/{match_id}/sync-result")
def admin_sync_match_result(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Sync one match result from API-Football."""
    _require_miniapp_admin(current_user)

    match = db.query(Match).filter(Match.id == match_id).first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if not match.external_fixture_id:
        raise HTTPException(status_code=400, detail="У матча нет external_fixture_id.")

    client = ApiFootballClient()
    api_fixture = client.get_fixture_by_id(match.external_fixture_id)

    if not api_fixture:
        raise HTTPException(status_code=404, detail="Fixture not found in API-Football.")

    status_short = api_fixture["fixture"]["status"]["short"]
    match.status_short = status_short
    match.status_long = api_fixture["fixture"]["status"].get("long")
    match.synced_at = datetime.now(timezone.utc)

    if status_short not in {"FT", "AET", "PEN"}:
        db.commit()
        return {
            "ok": False,
            "match": _serialize_admin_match(match),
            "message": f"Матч еще не завершен. Статус API-Football: {status_short}.",
        }

    score_home, score_away = get_fixture_score(api_fixture)

    if score_home is None or score_away is None:
        db.commit()
        raise HTTPException(status_code=400, detail="API-Football не вернул счет.")

    winner_side = get_winner_side(api_fixture) if is_playoff_match(match) else None

    if is_playoff_match(match) and winner_side is None:
        db.commit()
        raise HTTPException(status_code=400, detail="Плей-офф: API-Football не вернул winner.")

    lines = apply_match_result_from_admin(
        db=db,
        match=match,
        score_home=score_home,
        score_away=score_away,
        winner_side=winner_side,
    )

    db.refresh(match)

    return {
        "ok": True,
        "match": _serialize_admin_match(match),
        "message": "\n".join(lines),
    }


@router.post("/admin/sync-results")
def admin_sync_all_results(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Sync recently started unfinished matches from API-Football."""
    _require_miniapp_admin(current_user)

    now = datetime.now(timezone.utc)
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.external_provider == "api-football",
            Match.external_fixture_id.isnot(None),
            Match.is_finished == False,
            Match.starts_at <= now,
        )
        .order_by(Match.starts_at.asc())
        .limit(30)
        .all()
    )

    results = []

    for match in matches:
        try:
            result = admin_sync_match_result(match.id, db, current_user)
            results.append({"match_id": match.id, "label": _match_label(match), "ok": result["ok"], "message": result["message"]})
        except Exception as error:
            results.append({"match_id": match.id, "label": _match_label(match), "ok": False, "message": str(error)})

    return {
        "checked": len(matches),
        "updated": sum(1 for item in results if item["ok"]),
        "results": results,
    }


@router.post("/admin/fantasy/sync-player-stats")
def admin_sync_fantasy_player_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Sync player match statistics for finished API-Football fixtures."""
    _require_miniapp_admin(current_user)

    client = ApiFootballClient()
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.external_provider == "api-football",
            Match.external_fixture_id.isnot(None),
            Match.is_finished == True,
        )
        .order_by(Match.starts_at.asc())
        .limit(120)
        .all()
    )

    checked = 0
    stat_rows = 0
    skipped = 0
    errors = []

    for match in matches:
        checked += 1

        try:
            payload = client.get("/fixtures/players", {"fixture": match.external_fixture_id})
            teams_payload = payload.get("response", [])
        except Exception as error:
            skipped += 1
            errors.append(f"{_match_label(match)}: {error}")
            continue

        if not teams_payload:
            skipped += 1
            continue

        for team_block in teams_payload:
            for api_player_item in team_block.get("players") or []:
                api_player = api_player_item.get("player") or {}
                external_player_id = api_player.get("id")

                if not external_player_id:
                    continue

                fantasy_player = (
                    db.query(FantasyPlayer)
                    .filter(
                        FantasyPlayer.tournament_code == TOURNAMENT_CODE,
                        FantasyPlayer.external_player_id == int(external_player_id),
                    )
                    .first()
                )

                if not fantasy_player:
                    continue

                extracted = _extract_player_fixture_stats(api_player_item)
                points = _calculate_fantasy_points_for_stat(fantasy_player, extracted)

                row = (
                    db.query(FantasyPlayerMatchStat)
                    .filter(
                        FantasyPlayerMatchStat.player_id == fantasy_player.id,
                        FantasyPlayerMatchStat.match_id == match.id,
                    )
                    .first()
                )

                if not row:
                    row = FantasyPlayerMatchStat(
                        player_id=fantasy_player.id,
                        match_id=match.id,
                    )
                    db.add(row)

                for key, value in extracted.items():
                    setattr(row, key, value)

                row.points = points
                row.source_updated_at = datetime.now(timezone.utc)
                stat_rows += 1

    teams_updated = _recalculate_fantasy_team_points(db)
    db.commit()

    return {
        "checked_matches": checked,
        "stat_rows_upserted": stat_rows,
        "skipped_matches": skipped,
        "fantasy_teams_updated": teams_updated,
        "errors": errors[:20],
    }


@router.post("/admin/push/test")
def admin_send_test_push(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Send a test Web Push notification to the current admin's active PWA subscriptions."""
    _require_miniapp_admin(current_user)

    from app.services.web_push import notify_web_push_subscribers_for_user, web_push_enabled

    active_count = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id, PushSubscription.is_active == True)
        .count()
    )

    if not web_push_enabled():
        return {
            "ok": False,
            "sent": 0,
            "active_subscriptions": active_count,
            "message": "Web Push не настроен на сервере: проверь VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY и pywebpush.",
        }

    if active_count == 0:
        return {
            "ok": False,
            "sent": 0,
            "active_subscriptions": 0,
            "message": "У текущего администратора нет активной PWA push-подписки. Открой web/PWA-версию с экрана Домой и нажми «Включить уведомления».",
        }

    sent = notify_web_push_subscribers_for_user(
        db,
        user_id=current_user.id,
        title="Отец прогнозов",
        body="Тестовое push-уведомление работает ✅",
        url="/app",
    )

    return {
        "ok": sent > 0,
        "sent": sent,
        "active_subscriptions": active_count,
        "message": f"Тестовое push-уведомление отправлено: {sent} из {active_count} активных подписок.",
    }


@router.post("/admin/settings/{setting_key}")
def admin_save_setting(
    setting_key: str,
    payload: AdminSettingPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save admin global notification/app setting."""
    _require_miniapp_admin(current_user)

    if setting_key not in ADMIN_NOTIFICATION_SETTING_KEYS:
        raise HTTPException(status_code=404, detail="Unknown setting.")

    value = "true" if str(payload.value).lower() in {"1", "true", "yes", "on"} else "false"
    _set_app_setting(db, setting_key, value)
    db.commit()

    return {
        "setting_key": setting_key,
        "value": value,
    }



@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return current user's Mini App profile, stats and achievements."""
    predictions = (
        db.query(Prediction)
        .filter(Prediction.user_id == current_user.id)
        .all()
    )

    future_matches = get_all_available_matches(db, limit=1000)
    predictions_by_future_match = _prediction_by_match_id(db, current_user, future_matches)

    missing_count = sum(
        1
        for match in future_matches
        if match.id not in predictions_by_future_match
    )
    editable_count = sum(
        1
        for match in future_matches
        if match.id in predictions_by_future_match
    )

    tournament_prediction = (
        db.query(TournamentPrediction)
        .filter(
            TournamentPrediction.user_id == current_user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        )
        .first()
    )

    table_rows = build_table_rows(db)
    rank = None
    total_points = 0
    match_points = 0
    tournament_points = 0

    for index, row in enumerate(table_rows, start=1):
        if row["name"] == current_user.display_name:
            rank = index
            total_points = row["points"]
            match_points = row["match_points"]
            tournament_points = row["tournament_points"]
            break

    exact_scores = sum(1 for prediction in predictions if prediction.score_points == 3)
    outcomes = sum(1 for prediction in predictions if prediction.score_points == 1)
    advancement_plus = sum(1 for prediction in predictions if prediction.advancement_points == 1)
    advancement_minus = sum(1 for prediction in predictions if prediction.advancement_points == -1)

    total_predictions = len(predictions)
    favorite_score = _favorite_score(predictions)
    status_text = _profile_status(total_points, exact_scores, total_predictions, missing_count)

    return {
        "user": {
            "id": current_user.id,
            "telegram_id": current_user.telegram_id,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "initials": "".join(part[:1] for part in current_user.display_name.split()[:2]).upper() or "ОП",
            "is_admin": bool(current_user.is_admin),
            "created_at": _ensure_utc(current_user.created_at).isoformat() if current_user.created_at else None,
        },
        "summary": {
            "rank": rank,
            "status": status_text,
            "points": total_points,
            "match_points": match_points,
            "tournament_points": tournament_points,
            "fantasy_points": 0,
            "total_predictions": total_predictions,
            "missing_predictions": missing_count,
            "editable_predictions": editable_count,
            "exact_scores": exact_scores,
            "outcomes": outcomes,
            "advancement_plus": advancement_plus,
            "advancement_minus": advancement_minus,
            "favorite_score": favorite_score,
        },
        "points_breakdown": [
            {"key": "matches", "title": "Прогнозы", "points": match_points, "icon": "ball"},
            {"key": "tournament", "title": "Турнир", "points": tournament_points, "icon": "cup"},
        ],
        "tournament_prediction": _serialize_tournament_prediction(tournament_prediction, db=db) if tournament_prediction else None,
        "badges": _profile_badges(
            exact_scores=exact_scores,
            outcomes=outcomes,
            total_predictions=total_predictions,
            missing_count=missing_count,
            tournament_prediction=tournament_prediction,
            rank=rank,
        ),
    }


@router.get("/facts/random")
def get_random_fact(
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random active World Cup fact."""
    query = db.query(WorldCupFact).filter(WorldCupFact.is_active == True)

    if category and category != "any":
        query = query.filter(WorldCupFact.category == category)

    facts = query.all()

    if not facts:
        raise HTTPException(status_code=404, detail="Facts not found")

    fact = random.choice(facts)

    return {
        "fact": {
            "id": fact.id,
            "title": fact.title,
            "text": fact.fact_text,
            "category": fact.category,
            "tournament_year": fact.tournament_year,
            "spicy_comment": fact.spicy_comment,
        }
    }


@router.get("/quiz/random")
def get_random_quiz(
    category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random active quiz question."""
    query = db.query(QuizQuestion).filter(QuizQuestion.is_active == True)

    if category and category != "any":
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        raise HTTPException(status_code=404, detail="Quiz questions not found")

    question = random.choice(questions)

    return {
        "question": {
            "id": question.id,
            "text": question.question_text,
            "options": {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d,
            },
        }
    }


@router.post("/quiz/answer")
def save_quiz_answer(
    payload: QuizAnswerPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save a quick quiz answer and reveal whether it is correct."""
    selected_option = payload.selected_option.upper().strip()

    if selected_option not in {"A", "B", "C", "D"}:
        raise HTTPException(status_code=400, detail="Invalid option")

    question = db.query(QuizQuestion).filter(QuizQuestion.id == payload.question_id).first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = selected_option == question.correct_option.upper()

    answer = QuizAnswer(
        quiz_question_id=question.id,
        user_id=current_user.id,
        telegram_id=current_user.telegram_id,
        selected_option=selected_option,
        is_correct=is_correct,
    )

    db.add(answer)
    db.commit()

    options = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }

    return {
        "ok": True,
        "is_correct": is_correct,
        "correct_option": question.correct_option.upper(),
        "correct_text": options.get(question.correct_option.upper()),
        "explanation": question.explanation,
    }


@router.get("/archive/random")
def get_random_archive_card(
    card_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a random public archive card."""
    query = db.query(HistoricalArchiveCard).filter(
        HistoricalArchiveCard.is_active == True,
        HistoricalArchiveCard.is_public == True,
    )

    if card_type and card_type != "any":
        query = query.filter(HistoricalArchiveCard.card_type == card_type)

    cards = query.all()

    if not cards:
        raise HTTPException(status_code=404, detail="Archive cards not found")

    card = random.choice(cards)

    return {
        "card": {
            "id": card.id,
            "title": card.title,
            "text": card.text,
            "card_type": card.card_type,
            "tournament_code": card.tournament_code,
            "related_name": card.related_name,
        }
    }


def _empty_group_row(team_name: str, api_name: str | None = None, team_id: int | None = None) -> dict:
    """Create an empty group standings row for a national team."""
    display_name = get_team_name_ru(team_name)

    return {
        "team": display_name,
        "flag": get_team_flag(display_name, api_name),
        "flag_code": get_team_flag_code(display_name, api_name),
        "team_id": team_id,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }


def _apply_group_match_result(row_home: dict, row_away: dict, match: Match) -> None:
    """Apply a finished group-stage match result to two standings rows."""
    if match.score_home is None or match.score_away is None:
        return

    home_goals = int(match.score_home)
    away_goals = int(match.score_away)

    row_home["played"] += 1
    row_away["played"] += 1

    row_home["goals_for"] += home_goals
    row_home["goals_against"] += away_goals
    row_home["goal_difference"] = row_home["goals_for"] - row_home["goals_against"]

    row_away["goals_for"] += away_goals
    row_away["goals_against"] += home_goals
    row_away["goal_difference"] = row_away["goals_for"] - row_away["goals_against"]

    if home_goals > away_goals:
        row_home["wins"] += 1
        row_home["points"] += 3
        row_away["losses"] += 1
    elif home_goals < away_goals:
        row_away["wins"] += 1
        row_away["points"] += 3
        row_home["losses"] += 1
    else:
        row_home["draws"] += 1
        row_away["draws"] += 1
        row_home["points"] += 1
        row_away["points"] += 1


def _prediction_distribution(db: Session, match: Match, league_id: int | None = None) -> dict:
    """Return aggregated user prediction distribution for a match, optionally scoped by league."""
    query = db.query(Prediction).filter(Prediction.match_id == match.id)
    if league_id is not None:
        query = (
            query.join(User, User.id == Prediction.user_id)
            .join(LeagueMember, LeagueMember.user_id == User.id)
            .filter(
                LeagueMember.league_id == league_id,
                LeagueMember.status == "active",
                LeagueMember.joined_at <= match.starts_at,
                User.access_status == "approved",
            )
        )
    predictions = query.all()
    total = len(predictions)

    home = 0
    draw = 0
    away = 0

    for prediction in predictions:
        if prediction.pred_home > prediction.pred_away:
            home += 1
        elif prediction.pred_home < prediction.pred_away:
            away += 1
        else:
            draw += 1

    def percent(value: int) -> int:
        if total <= 0:
            return 0
        return round(value * 100 / total)

    return {
        "total": total,
        "home": home,
        "draw": draw,
        "away": away,
        "home_percent": percent(home),
        "draw_percent": percent(draw),
        "away_percent": percent(away),
    }


def _serialize_match_center_match(
    db: Session,
    match: Match,
    user_prediction: Prediction | None = None,
    league_id: int | None = None,
) -> dict:
    """Serialize a match card for Mini App 2.0 match center."""
    payload = _serialize_match(match, user_prediction)
    payload["prediction_distribution"] = _prediction_distribution(db, match, league_id=league_id)
    payload["fifa_match_no"] = match.fifa_match_no
    payload["status_short"] = match.status_short
    payload["status_long"] = match.status_long
    payload["day_key"] = _ensure_utc(match.starts_at).date().isoformat()
    payload["videos"] = [_serialize_match_video(video) for video in _active_videos_for_match(db, match.id)]
    return payload


def _build_group_standings(db: Session) -> list[dict]:
    """Build group standings for all WC2026 groups from stored results."""
    group_matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.group_code.isnot(None),
        )
        .order_by(Match.group_code.asc(), Match.starts_at.asc())
        .all()
    )

    groups: dict[str, dict[str, dict]] = {}

    for match in group_matches:
        group_code = str(match.group_code or "").strip()

        if not group_code:
            continue

        if group_code not in groups:
            groups[group_code] = {}

        for team_name, api_name, team_id in [
            (match.home_team, getattr(match, "home_team_api_name", None), getattr(match, "home_external_team_id", None)),
            (match.away_team, getattr(match, "away_team_api_name", None), getattr(match, "away_external_team_id", None)),
        ]:
            if not team_name or team_name == "TBD":
                continue

            display_name = get_team_name_ru(team_name)

            if display_name not in groups[group_code]:
                groups[group_code][display_name] = _empty_group_row(team_name, api_name, team_id)

        if bool(match.is_finished):
            home_name = get_team_name_ru(match.home_team)
            away_name = get_team_name_ru(match.away_team)

            if home_name in groups[group_code] and away_name in groups[group_code]:
                _apply_group_match_result(
                    groups[group_code][home_name],
                    groups[group_code][away_name],
                    match,
                )

    result = []

    for group_code in sorted(groups):
        rows = list(groups[group_code].values())
        rows.sort(
            key=lambda row: (
                row["points"],
                row["goal_difference"],
                row["goals_for"],
                row["team"],
            ),
            reverse=True,
        )

        for index, row in enumerate(rows, start=1):
            row["rank"] = index
            row["qualification_zone"] = (
                "direct" if index <= 2 else "playoff" if index == 3 else "out"
            )

        result.append(
            {
                "group_code": group_code,
                "rows": rows,
                "matches_played": sum(row["played"] for row in rows) // 2,
            }
        )

    return result


def _default_tournament_group_codes(db: Session) -> list[str]:
    """Return groups playing on the current U.S. tournament day.

    The World Cup schedule is organized around North American local dates. When
    there are no matches today, fall back to the nearest upcoming matchday (or
    the latest completed day once the group stage is over) so the hub is never
    empty on first open.
    """
    rows = (
        db.query(Match.group_code, Match.starts_at)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.group_code.isnot(None),
        )
        .order_by(Match.starts_at.asc())
        .all()
    )
    by_day: dict = {}
    for group_code, starts_at in rows:
        code = str(group_code or "").strip()
        if not code or not starts_at:
            continue
        day = _ensure_utc(starts_at).astimezone(US_TOURNAMENT_TIMEZONE).date()
        by_day.setdefault(day, set()).add(code)

    if not by_day:
        return []

    today = datetime.now(US_TOURNAMENT_TIMEZONE).date()
    if today in by_day:
        target_day = today
    else:
        upcoming = sorted(day for day in by_day if day > today)
        target_day = upcoming[0] if upcoming else max(by_day)

    return sorted(by_day.get(target_day, set()))


@router.get("/tournament/overview")
def get_tournament_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return tournament-wide navigation data from local standings plus shared cache."""
    del current_user  # authenticated access is enough; data is public within the app.
    return {
        "groups": _build_group_standings(db),
        "default_group_codes": _default_tournament_group_codes(db),
        "top_scorers": get_top_scorers(db, refresh=True, limit=20),
    }


def _team_profile_matches(db: Session, team_id: int) -> list[Match]:
    return (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            (Match.home_external_team_id == team_id) | (Match.away_external_team_id == team_id),
        )
        .order_by(Match.starts_at.asc())
        .all()
    )


@router.get("/tournament/teams/{team_id}")
def get_tournament_team_profile(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return a national team profile built from current local tournament data."""
    matches = _team_profile_matches(db, team_id)
    if not matches:
        raise HTTPException(status_code=404, detail="Сборная не найдена в матчах турнира")

    first = matches[0]
    is_home = int(first.home_external_team_id or 0) == int(team_id)
    raw_name = first.home_team if is_home else first.away_team
    api_name = first.home_team_api_name if is_home else first.away_team_api_name
    team_name = get_team_name_ru(raw_name)
    group_code = next((item.group_code for item in matches if item.group_code), None)

    standings = _build_group_standings(db)
    standing_row = None
    if group_code:
        group = next((item for item in standings if item["group_code"] == group_code), None)
        if group:
            standing_row = next((row for row in group["rows"] if row["team"] == team_name), None)

    finished = [match for match in matches if match.is_finished and match.score_home is not None and match.score_away is not None]
    wins = draws = losses = goals_for = goals_against = 0
    for match in finished:
        home_side = int(match.home_external_team_id or 0) == int(team_id)
        own, other = (int(match.score_home), int(match.score_away)) if home_side else (int(match.score_away), int(match.score_home))
        goals_for += own
        goals_against += other
        if own > other:
            wins += 1
        elif own == other:
            draws += 1
        else:
            losses += 1

    predictions = _prediction_by_match_id(db, current_user, matches)
    scorers = get_team_scorers(db, team_id, refresh=True, limit=50)

    return {
        "team": {
            "id": team_id,
            "name": team_name,
            "api_name": api_name or raw_name,
            "flag": get_team_flag(team_name, api_name),
            "flag_code": get_team_flag_code(team_name, api_name),
            "group_code": group_code,
            "standing": standing_row,
            "stats": {
                "played": len(finished), "wins": wins, "draws": draws, "losses": losses,
                "goals_for": goals_for, "goals_against": goals_against,
            },
        },
        "matches": [_serialize_match(match, predictions.get(match.id)) for match in matches],
        "scorers": scorers[:10],
    }


@router.get("/tournament/players/{player_id}")
def get_tournament_player_profile(
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return cached player tournament card and already-synced appearances."""
    del current_user
    player = find_top_scorer(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Игрок пока не найден в кэше турнира")
    return {
        "player": player,
        "matches": player_match_rows(db, player_id),
    }


@router.get("/matches/{match_id}/emotion")
def get_match_emotion(
    match_id: int,
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the current user's post-match recap for one selected league."""
    match = (
        db.query(Match)
        .filter(Match.id == match_id, Match.tournament_code == TOURNAMENT_CODE)
        .first()
    )
    if not match:
        raise HTTPException(status_code=404, detail="Матч не найден")
    if not match.is_finished or match.score_home is None or match.score_away is None:
        raise HTTPException(status_code=400, detail="Итог станет доступен после завершения матча")

    try:
        league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    membership = (
        db.query(LeagueMember)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.user_id == current_user.id,
            LeagueMember.status == "active",
        )
        .first()
    )
    scoring_start = league_scoring_start_at(league)
    is_eligible = bool(
        membership
        and membership.joined_at
        and membership.joined_at <= match.starts_at
        and (scoring_start is None or match.starts_at >= scoring_start)
    )

    if not is_eligible:
        return {
            "eligible": False,
            "league": _serialize_league(league, current_user),
            "message": "Этот матч не входит в зачет выбранной лиги для вашего участия.",
        }

    try:
        emotion = build_match_emotion_payload(db, current_user, match, league)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "eligible": True,
        "league": _serialize_league(league, current_user),
        "emotion": emotion,
    }


@router.get("/match-center")
def get_match_center(
    scope: str = Query(default="all", pattern="^(all|results|upcoming)$"),
    group_code: str | None = Query(default=None),
    league_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return Mini App 2.0 match center data with filters and standings."""
    try:
        active_league = require_user_league(db, current_user, league_id)
    except ValueError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    query = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE)
        .order_by(Match.starts_at.asc())
    )

    if group_code:
        query = query.filter(Match.group_code == group_code)

    if scope == "results":
        query = query.filter(Match.is_finished == True)
    elif scope == "upcoming":
        query = query.filter(Match.is_finished == False)

    matches = query.all()
    predictions_by_match = _prediction_by_match_id(db, current_user, matches)

    all_group_standings = _build_group_standings(db)
    selected_group_standings = (
        [
            group
            for group in all_group_standings
            if not group_code or group["group_code"] == group_code
        ]
    )

    groups = [
        {
            "group_code": group["group_code"],
            "teams_count": len(group["rows"]),
            "matches_played": group["matches_played"],
        }
        for group in all_group_standings
    ]

    return {
        "filters": {
            "scope": scope,
            "group_code": group_code,
            "league_id": active_league.id,
        },
        "league": _serialize_league(active_league, current_user),
        "groups": groups,
        "standings": selected_group_standings,
        "matches": [
            _serialize_match_center_match(db, match, predictions_by_match.get(match.id), league_id=active_league.id)
            for match in matches
        ],
    }
