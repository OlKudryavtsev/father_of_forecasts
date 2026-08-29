"""Tournament registry and archive-import helpers for multi-tournament mode."""

from __future__ import annotations

from datetime import datetime, timezone
import zlib
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import League, LeagueMember, Match, Prediction, Tournament, TournamentPrediction, TournamentResult, User
from app.runtime import TOURNAMENT_CODE, TOURNAMENT_STARTS_AT_RAW, APP_TIMEZONE

DEFAULT_SCORING_RULES = {
    "exact_score": 3,
    "outcome": 1,
    "advancement_correct": 1,
    "advancement_wrong": -1,
    "champion": 15,
    "runner_up": 10,
    "third_place": 5,
    "top_scorer": 15,
}


def normalize_tournament_code(value: str | None) -> str:
    code = str(value or TOURNAMENT_CODE or "wc2026").strip().lower()
    code = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in code)
    return code.strip("_") or "wc2026"


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TIMEZONE)
    return dt.astimezone(timezone.utc)


def default_tournament_start() -> datetime:
    dt = _parse_datetime(TOURNAMENT_STARTS_AT_RAW) or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_default_tournament(db: Session) -> Tournament:
    code = normalize_tournament_code(TOURNAMENT_CODE)
    tournament = db.query(Tournament).filter(Tournament.code == code).first()
    if tournament:
        return tournament
    tournament = Tournament(
        code=code,
        name="ЧМ-2026" if code == "wc2026" else code.upper(),
        short_name="ЧМ-2026" if code == "wc2026" else code.upper(),
        tournament_type="world_cup" if code == "wc2026" else "custom",
        year=2026 if code == "wc2026" else None,
        host="США · Мексика · Канада" if code == "wc2026" else None,
        status="finished" if code == "wc2026" else "active",
        starts_at=default_tournament_start(),
        prediction_deadline=default_tournament_start(),
        has_third_place_match=True,
        scoring_rules=DEFAULT_SCORING_RULES,
        is_default=True,
        display_order=10,
    )
    db.add(tournament)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(Tournament).filter(Tournament.code == code).first()
        if existing:
            return existing
        raise
    db.refresh(tournament)
    return tournament


def get_tournament(db: Session, tournament_code: str | None = None) -> Tournament:
    code = normalize_tournament_code(tournament_code)
    tournament = db.query(Tournament).filter(Tournament.code == code).first()
    if tournament:
        return tournament
    if code == normalize_tournament_code(TOURNAMENT_CODE):
        return ensure_default_tournament(db)
    raise ValueError(f"Турнир {code} не найден")


def get_default_tournament(db: Session) -> Tournament:
    tournament = (
        db.query(Tournament)
        .filter(Tournament.is_default == True)  # noqa: E712
        .order_by(Tournament.display_order.asc(), Tournament.code.asc())
        .first()
    )
    return tournament or ensure_default_tournament(db)


def list_tournaments(db: Session) -> list[Tournament]:
    ensure_default_tournament(db)
    return (
        db.query(Tournament)
        .order_by(Tournament.display_order.asc(), Tournament.year.desc().nullslast(), Tournament.code.asc())
        .all()
    )


def tournament_is_read_only(tournament: Tournament | None) -> bool:
    return str(getattr(tournament, "status", "") or "").lower() in {"finished", "archived"}


def tournament_payload(tournament: Tournament) -> dict:
    starts_at = getattr(tournament, "starts_at", None)
    ends_at = getattr(tournament, "ends_at", None)
    deadline = getattr(tournament, "prediction_deadline", None)
    return {
        "code": tournament.code,
        "name": tournament.name,
        "short_name": tournament.short_name or tournament.name,
        "type": tournament.tournament_type,
        "year": tournament.year,
        "host": tournament.host,
        "status": tournament.status,
        "starts_at": starts_at.isoformat() if starts_at else None,
        "ends_at": ends_at.isoformat() if ends_at else None,
        "prediction_deadline": deadline.isoformat() if deadline else None,
        "has_third_place_match": bool(tournament.has_third_place_match),
        "scoring_rules": tournament.scoring_rules or DEFAULT_SCORING_RULES,
        "is_default": bool(tournament.is_default),
        "display_order": int(tournament.display_order or 100),
        "is_read_only": tournament_is_read_only(tournament),
    }


def get_tournament_starts_at_for_code(db: Session, tournament_code: str | None = None) -> datetime:
    tournament = get_tournament(db, tournament_code)
    return (tournament.prediction_deadline or tournament.starts_at or default_tournament_start()).astimezone(timezone.utc)


def tournament_started_for_code(db: Session, tournament_code: str | None = None) -> bool:
    tournament = get_tournament(db, tournament_code)
    if tournament_is_read_only(tournament):
        return True
    return datetime.now(timezone.utc) >= get_tournament_starts_at_for_code(db, tournament.code)


def _placeholder_telegram_id(display_name: str, tournament_code: str) -> int:
    payload = f"{tournament_code}:{display_name}".encode("utf-8")
    return -int(zlib.crc32(payload) or 1)


def upsert_archive_user(db: Session, row: dict, tournament_code: str) -> User:
    telegram_id = row.get("telegram_id")
    display_name = (row.get("display_name") or row.get("name") or row.get("user_name") or "").strip()
    if telegram_id not in (None, ""):
        telegram_id = int(telegram_id)
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
    else:
        if not display_name:
            raise ValueError("archive user requires display_name/name when telegram_id is absent")
        telegram_id = _placeholder_telegram_id(display_name, tournament_code)
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = db.query(User).filter(User.display_name == display_name).first()
    if user:
        if display_name and user.display_name != display_name:
            user.display_name = display_name
        user.username = row.get("username") or user.username
        user.access_status = "approved"
        return user
    user = User(
        telegram_id=telegram_id,
        username=row.get("username") or None,
        display_name=display_name,
        access_status="approved",
    )
    db.add(user)
    db.flush()
    return user



def _ensure_archive_league(db: Session, payload: dict) -> League | None:
    league_data = dict(payload.get("league") or {})
    league_name = (payload.get("league_name") or league_data.get("name") or "Отец прогнозов").strip()
    if not league_name:
        return None
    league = db.query(League).filter(League.name == league_name).first()
    if league:
        league.is_active = True
        return league
    league = League(
        name=league_name,
        description=league_data.get("description") or "Архивная лига, созданная импортом турнира",
        league_type=league_data.get("league_type") or "system",
        is_active=True,
    )
    db.add(league)
    db.flush()
    return league


def _ensure_archive_membership(db: Session, league: League | None, user: User) -> bool:
    if league is None:
        return False
    member = db.query(LeagueMember).filter(
        LeagueMember.league_id == league.id,
        LeagueMember.user_id == user.id,
    ).first()
    if member:
        member.status = "active"
        return False
    db.add(LeagueMember(league_id=league.id, user_id=user.id, role="member", status="active"))
    return True

def import_tournament_archive(db: Session, payload: dict) -> dict:
    """Import a complete historical tournament from a normalized JSON payload.

    The importer is idempotent by ``tournament.code`` and match ``external_fixture_id``/``fifa_match_no``
    when supplied. It creates placeholder users for old participants without Telegram IDs.
    """
    tournament_data = dict(payload.get("tournament") or {})
    code = normalize_tournament_code(tournament_data.get("code") or payload.get("tournament_code"))
    if not code:
        raise ValueError("tournament.code is required")

    tournament = db.query(Tournament).filter(Tournament.code == code).first()
    if not tournament:
        tournament = Tournament(code=code)
        db.add(tournament)
    tournament.name = tournament_data.get("name") or tournament.name or code.upper()
    tournament.short_name = tournament_data.get("short_name") or tournament.short_name or tournament.name
    tournament.tournament_type = tournament_data.get("type") or tournament_data.get("tournament_type") or tournament.tournament_type or "custom"
    tournament.year = tournament_data.get("year") or tournament.year
    tournament.host = tournament_data.get("host") or tournament.host
    tournament.status = tournament_data.get("status") or "archived"
    tournament.starts_at = _parse_datetime(tournament_data.get("starts_at")) or tournament.starts_at
    tournament.ends_at = _parse_datetime(tournament_data.get("ends_at")) or tournament.ends_at
    tournament.prediction_deadline = _parse_datetime(tournament_data.get("prediction_deadline")) or tournament.prediction_deadline or tournament.starts_at
    tournament.has_third_place_match = bool(tournament_data.get("has_third_place_match", True))
    tournament.scoring_rules = tournament_data.get("scoring_rules") or tournament.scoring_rules or DEFAULT_SCORING_RULES
    tournament.is_default = bool(tournament_data.get("is_default", False))
    tournament.display_order = int(tournament_data.get("display_order") or tournament.display_order or 100)

    league = _ensure_archive_league(db, payload)
    auto_add_members = bool(payload.get("add_users_to_league", True))
    imported_memberships = 0

    users_by_key: dict[str, User] = {}
    for row in payload.get("users") or []:
        user = upsert_archive_user(db, row, code)
        if auto_add_members and _ensure_archive_membership(db, league, user):
            imported_memberships += 1
        for key in (row.get("id"), row.get("telegram_id"), row.get("display_name"), row.get("name"), row.get("user_name")):
            if key not in (None, ""):
                users_by_key[str(key)] = user

    matches_by_key: dict[str, Match] = {}
    imported_matches = 0
    for row in payload.get("matches") or []:
        external_id = str(row.get("external_fixture_id") or row.get("external_id") or row.get("id") or "").strip() or None
        fifa_match_no = row.get("fifa_match_no") or row.get("match_no")
        query = db.query(Match).filter(Match.tournament_code == code)
        if external_id:
            match = query.filter(Match.external_fixture_id == external_id).first()
        elif fifa_match_no not in (None, ""):
            match = query.filter(Match.fifa_match_no == int(fifa_match_no)).first()
        else:
            match = query.filter(Match.home_team == row.get("home_team"), Match.away_team == row.get("away_team"), Match.starts_at == _parse_datetime(row.get("starts_at"))).first()
        if not match:
            match = Match(tournament_code=code, home_team=row["home_team"], away_team=row["away_team"], starts_at=_parse_datetime(row.get("starts_at")) or datetime.now(timezone.utc))
            db.add(match)
            imported_matches += 1
        match.tournament_code = code
        match.home_team = row.get("home_team") or match.home_team
        match.away_team = row.get("away_team") or match.away_team
        match.starts_at = _parse_datetime(row.get("starts_at")) or match.starts_at
        match.stage = row.get("stage") or match.stage or "group"
        match.match_round = row.get("match_round") or match.match_round
        match.group_code = row.get("group_code") or match.group_code
        match.venue = row.get("venue") or match.venue
        match.city = row.get("city") or match.city
        match.fifa_match_no = int(fifa_match_no) if fifa_match_no not in (None, "") else match.fifa_match_no
        match.external_provider = row.get("external_provider") or match.external_provider or "archive"
        match.external_fixture_id = external_id or match.external_fixture_id
        for field in ("score_home", "score_away", "final_score_home", "final_score_away"):
            if row.get(field) not in (None, ""):
                setattr(match, field, int(row[field]))
        match.winner_side = row.get("winner_side") or match.winner_side
        match.is_finished = bool(row.get("is_finished", True))
        db.flush()
        for key in (row.get("id"), external_id, match.fifa_match_no):
            if key not in (None, ""):
                matches_by_key[str(key)] = match

    imported_predictions = 0
    for row in payload.get("predictions") or payload.get("match_predictions") or []:
        user_key = str(row.get("user_id") or row.get("telegram_id") or row.get("user_name") or row.get("display_name") or "")
        match_key = str(row.get("match_id") or row.get("external_fixture_id") or row.get("fifa_match_no") or "")
        user = users_by_key.get(user_key)
        if not user and (row.get("display_name") or row.get("user_name") or row.get("telegram_id")):
            user = upsert_archive_user(db, row, code)
            if auto_add_members and _ensure_archive_membership(db, league, user):
                imported_memberships += 1
        match = matches_by_key.get(match_key)
        if not user or not match:
            continue
        prediction = db.query(Prediction).filter(Prediction.user_id == user.id, Prediction.match_id == match.id).first()
        if not prediction:
            prediction = Prediction(user_id=user.id, match_id=match.id, pred_home=0, pred_away=0)
            db.add(prediction)
            imported_predictions += 1
        prediction.pred_home = int(row.get("pred_home"))
        prediction.pred_away = int(row.get("pred_away"))
        prediction.advancement_bet_enabled = bool(row.get("advancement_bet_enabled", False))
        prediction.predicted_advancing_side = row.get("predicted_advancing_side") or None
        prediction.score_points = int(row.get("score_points") or 0)
        prediction.advancement_points = int(row.get("advancement_points") or 0)
        prediction.points = int(row.get("points") or (prediction.score_points or 0) + (prediction.advancement_points or 0))

    imported_tournament_predictions = 0
    for row in payload.get("tournament_predictions") or []:
        user_key = str(row.get("user_id") or row.get("telegram_id") or row.get("user_name") or row.get("display_name") or "")
        user = users_by_key.get(user_key)
        if not user and (row.get("display_name") or row.get("user_name") or row.get("telegram_id")):
            user = upsert_archive_user(db, row, code)
            if auto_add_members and _ensure_archive_membership(db, league, user):
                imported_memberships += 1
        if not user:
            continue
        prediction = db.query(TournamentPrediction).filter(TournamentPrediction.user_id == user.id, TournamentPrediction.tournament_code == code).first()
        if not prediction:
            prediction = TournamentPrediction(user_id=user.id, tournament_code=code, champion="", runner_up="", third_place="", top_scorer="")
            db.add(prediction)
            imported_tournament_predictions += 1
        prediction.champion = row.get("champion") or prediction.champion
        prediction.runner_up = row.get("runner_up") or prediction.runner_up
        prediction.third_place = row.get("third_place") or prediction.third_place
        prediction.top_scorer = row.get("top_scorer") or prediction.top_scorer
        for field in ("champion_points", "runner_up_points", "third_place_points", "top_scorer_points", "points"):
            if row.get(field) not in (None, ""):
                setattr(prediction, field, int(row[field]))

    result_data = payload.get("tournament_result") or payload.get("result")
    if result_data:
        result = db.query(TournamentResult).filter(TournamentResult.tournament_code == code).first()
        if not result:
            result = TournamentResult(tournament_code=code, champion="", runner_up="", third_place="", top_scorer="")
            db.add(result)
        result.champion = result_data.get("champion") or result.champion
        result.runner_up = result_data.get("runner_up") or result.runner_up
        result.third_place = result_data.get("third_place") or result.third_place
        result.top_scorer = result_data.get("top_scorer") or result.top_scorer

    db.commit()
    return {
        "tournament_code": code,
        "matches": imported_matches,
        "predictions": imported_predictions,
        "tournament_predictions": imported_tournament_predictions,
        "users": len(users_by_key),
        "league": league.name if league else None,
        "memberships": imported_memberships,
    }
