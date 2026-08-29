"""UEFA Champions League 2026/27 league-phase helpers.

The API-Football competition feed may include qualifying/play-off rounds and, at
least initially, may expose all league-phase fixtures with placeholder kickoff
values.  This module keeps the production import focused on the 144 confirmed
league-phase fixtures and stores club names in Russian for the Mini App.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import unicodedata
from typing import Any

from sqlalchemy.orm import Session

from app.models import Match, Tournament

UCL_2026_2027_CODE = "ucl_2026_2027"
UCL_LOCAL_TZ = ZoneInfo("Europe/Zurich")

UCL_TEAM_META: dict[str, dict[str, Any]] = {
    "AEK Athens": {"ru": "АЕК Афины", "flag": "🇬🇷", "flag_code": "gr", "aliases": ["AEK Athens FC", "AEK Athens"]},
    "Arsenal": {"ru": "Арсенал", "flag": "🏴", "flag_code": "gb-eng", "aliases": ["Arsenal"]},
    "Aston Villa": {"ru": "Астон Вилла", "flag": "🏴", "flag_code": "gb-eng", "aliases": ["Aston Villa"]},
    "Atletico Madrid": {"ru": "Атлетико Мадрид", "flag": "🇪🇸", "flag_code": "es", "aliases": ["Atlético de Madrid", "Atleti", "Atletico Madrid", "Atl. Madrid"]},
    "Barcelona": {"ru": "Барселона", "flag": "🇪🇸", "flag_code": "es", "aliases": ["Barcelona", "FC Barcelona"]},
    "Bayern Munich": {"ru": "Бавария", "flag": "🇩🇪", "flag_code": "de", "aliases": ["Bayern München", "Bayern Munich", "FC Bayern Munich", "Bayern"]},
    "Bodo/Glimt": {"ru": "Будё-Глимт", "flag": "🇳🇴", "flag_code": "no", "aliases": ["Bodø/Glimt", "Bodo/Glimt", "Bodoe/Glimt", "Bodo Glimt"]},
    "Borussia Dortmund": {"ru": "Боруссия Дортмунд", "flag": "🇩🇪", "flag_code": "de", "aliases": ["Borussia Dortmund", "B. Dortmund", "Dortmund"]},
    "Club Brugge": {"ru": "Брюгге", "flag": "🇧🇪", "flag_code": "be", "aliases": ["Club Brugge", "Club Brugge KV"]},
    "Como": {"ru": "Комо", "flag": "🇮🇹", "flag_code": "it", "aliases": ["Como"]},
    "Fenerbahce": {"ru": "Фенербахче", "flag": "🇹🇷", "flag_code": "tr", "aliases": ["Fenerbahçe", "Fenerbahce"]},
    "Feyenoord": {"ru": "Фейеноорд", "flag": "🇳🇱", "flag_code": "nl", "aliases": ["Feyenoord"]},
    "Galatasaray": {"ru": "Галатасарай", "flag": "🇹🇷", "flag_code": "tr", "aliases": ["Galatasaray"]},
    "Inter": {"ru": "Интер", "flag": "🇮🇹", "flag_code": "it", "aliases": ["Inter", "Inter Milan", "Internazionale"]},
    "LASK": {"ru": "ЛАСК", "flag": "🇦🇹", "flag_code": "at", "aliases": ["LASK", "Lask Linz", "LASK Linz"]},
    "Lens": {"ru": "Ланс", "flag": "🇫🇷", "flag_code": "fr", "aliases": ["Lens", "RC Lens"]},
    "Leipzig": {"ru": "Лейпциг", "flag": "🇩🇪", "flag_code": "de", "aliases": ["Leipzig", "RB Leipzig", "RasenBallsport Leipzig"]},
    "Lille": {"ru": "Лилль", "flag": "🇫🇷", "flag_code": "fr", "aliases": ["Lille", "LOSC Lille"]},
    "Liverpool": {"ru": "Ливерпуль", "flag": "🏴", "flag_code": "gb-eng", "aliases": ["Liverpool"]},
    "Manchester City": {"ru": "Манчестер Сити", "flag": "🏴", "flag_code": "gb-eng", "aliases": ["Manchester City", "Man City"]},
    "Manchester United": {"ru": "Манчестер Юнайтед", "flag": "🏴", "flag_code": "gb-eng", "aliases": ["Manchester United", "Man Utd", "Manchester Utd"]},
    "Napoli": {"ru": "Наполи", "flag": "🇮🇹", "flag_code": "it", "aliases": ["Napoli", "SSC Napoli"]},
    "Paris Saint-Germain": {"ru": "ПСЖ", "flag": "🇫🇷", "flag_code": "fr", "aliases": ["Paris Saint-Germain", "Paris SG", "PSG", "Paris"]},
    "Porto": {"ru": "Порту", "flag": "🇵🇹", "flag_code": "pt", "aliases": ["Porto", "FC Porto"]},
    "PSV Eindhoven": {"ru": "ПСВ", "flag": "🇳🇱", "flag_code": "nl", "aliases": ["PSV Eindhoven", "PSV"]},
    "Real Betis": {"ru": "Бетис", "flag": "🇪🇸", "flag_code": "es", "aliases": ["Real Betis", "Betis"]},
    "Real Madrid": {"ru": "Реал Мадрид", "flag": "🇪🇸", "flag_code": "es", "aliases": ["Real Madrid"]},
    "Roma": {"ru": "Рома", "flag": "🇮🇹", "flag_code": "it", "aliases": ["Roma", "AS Roma"]},
    "Sabah": {"ru": "Сабах", "flag": "🇦🇿", "flag_code": "az", "aliases": ["Sabah", "Sabah FK"]},
    "Shakhtar Donetsk": {"ru": "Шахтёр", "flag": "🇺🇦", "flag_code": "ua", "aliases": ["Shakhtar", "Shakhtar Donetsk", "Shakhtar Donets'k"]},
    "Slavia Praha": {"ru": "Славия Прага", "flag": "🇨🇿", "flag_code": "cz", "aliases": ["Slavia Praha", "Slavia Prague"]},
    "Slovan Bratislava": {"ru": "Слован Братислава", "flag": "🇸🇰", "flag_code": "sk", "aliases": ["Slovan Bratislava", "S. Bratislava"]},
    "Sporting CP": {"ru": "Спортинг", "flag": "🇵🇹", "flag_code": "pt", "aliases": ["Sporting CP", "Sporting Lisbon", "Sporting"]},
    "Stuttgart": {"ru": "Штутгарт", "flag": "🇩🇪", "flag_code": "de", "aliases": ["Stuttgart", "VfB Stuttgart"]},
    "Viking": {"ru": "Викинг", "flag": "🇳🇴", "flag_code": "no", "aliases": ["Viking", "Viking FK"]},
    "Villarreal": {"ru": "Вильярреал", "flag": "🇪🇸", "flag_code": "es", "aliases": ["Villarreal", "Villarreal CF"]},
}

UCL_LEAGUE_PHASE_FIXTURES: list[tuple[int, str, str, str, str]] = [
    (1, "2026-09-08", "18:45", "AEK Athens", "LASK"),
    (1, "2026-09-08", "18:45", "Club Brugge", "Aston Villa"),
    (1, "2026-09-08", "21:00", "Borussia Dortmund", "Villarreal"),
    (1, "2026-09-08", "21:00", "Porto", "Manchester City"),
    (1, "2026-09-08", "21:00", "Lille", "Real Betis"),
    (1, "2026-09-08", "21:00", "Real Madrid", "Inter"),
    (1, "2026-09-09", "18:45", "Barcelona", "Feyenoord"),
    (1, "2026-09-09", "18:45", "Stuttgart", "Viking"),
    (1, "2026-09-09", "21:00", "Liverpool", "Atletico Madrid"),
    (1, "2026-09-09", "21:00", "Paris Saint-Germain", "Slovan Bratislava"),
    (1, "2026-09-09", "21:00", "Sporting CP", "Galatasaray"),
    (1, "2026-09-09", "21:00", "Napoli", "Arsenal"),
    (1, "2026-09-10", "18:45", "Fenerbahce", "Roma"),
    (1, "2026-09-10", "18:45", "PSV Eindhoven", "Shakhtar Donetsk"),
    (1, "2026-09-10", "21:00", "Como", "Leipzig"),
    (1, "2026-09-10", "21:00", "Bayern Munich", "Bodo/Glimt"),
    (1, "2026-09-10", "21:00", "Manchester United", "Sabah"),
    (1, "2026-09-10", "21:00", "Slavia Praha", "Lens"),
    (2, "2026-10-13", "18:45", "Lens", "Sporting CP"),
    (2, "2026-10-13", "18:45", "Sabah", "Slavia Praha"),
    (2, "2026-10-13", "21:00", "Arsenal", "Lille"),
    (2, "2026-10-13", "21:00", "Atletico Madrid", "Manchester United"),
    (2, "2026-10-13", "21:00", "Inter", "Club Brugge"),
    (2, "2026-10-13", "21:00", "Galatasaray", "Barcelona"),
    (2, "2026-10-13", "21:00", "Leipzig", "PSV Eindhoven"),
    (2, "2026-10-13", "21:00", "Viking", "Bayern Munich"),
    (2, "2026-10-13", "21:00", "Villarreal", "Napoli"),
    (2, "2026-10-14", "18:45", "Feyenoord", "Como"),
    (2, "2026-10-14", "18:45", "LASK", "Liverpool"),
    (2, "2026-10-14", "21:00", "Roma", "Real Madrid"),
    (2, "2026-10-14", "21:00", "Aston Villa", "Fenerbahce"),
    (2, "2026-10-14", "21:00", "Shakhtar Donetsk", "AEK Athens"),
    (2, "2026-10-14", "21:00", "Bodo/Glimt", "Borussia Dortmund"),
    (2, "2026-10-14", "21:00", "Manchester City", "Paris Saint-Germain"),
    (2, "2026-10-14", "21:00", "Real Betis", "Porto"),
    (2, "2026-10-14", "21:00", "Slovan Bratislava", "Stuttgart"),
    (3, "2026-10-20", "18:45", "Fenerbahce", "Slavia Praha"),
    (3, "2026-10-20", "18:45", "Sabah", "Borussia Dortmund"),
    (3, "2026-10-20", "21:00", "Roma", "Slovan Bratislava"),
    (3, "2026-10-20", "21:00", "Porto", "PSV Eindhoven"),
    (3, "2026-10-20", "21:00", "Liverpool", "Villarreal"),
    (3, "2026-10-20", "21:00", "Manchester City", "AEK Athens"),
    (3, "2026-10-20", "21:00", "Paris Saint-Germain", "Barcelona"),
    (3, "2026-10-20", "21:00", "Napoli", "Bodo/Glimt"),
    (3, "2026-10-20", "21:00", "Stuttgart", "Atletico Madrid"),
    (3, "2026-10-21", "18:45", "Como", "Manchester United"),
    (3, "2026-10-21", "18:45", "Lille", "Galatasaray"),
    (3, "2026-10-21", "21:00", "Aston Villa", "Viking"),
    (3, "2026-10-21", "21:00", "Club Brugge", "Lens"),
    (3, "2026-10-21", "21:00", "Bayern Munich", "Arsenal"),
    (3, "2026-10-21", "21:00", "Inter", "Shakhtar Donetsk"),
    (3, "2026-10-21", "21:00", "Real Madrid", "Leipzig"),
    (3, "2026-10-21", "21:00", "Real Betis", "Feyenoord"),
    (3, "2026-10-21", "21:00", "Sporting CP", "LASK"),
    (4, "2026-11-03", "18:45", "Shakhtar Donetsk", "Sporting CP"),
    (4, "2026-11-03", "18:45", "Galatasaray", "Stuttgart"),
    (4, "2026-11-03", "21:00", "Atletico Madrid", "Bayern Munich"),
    (4, "2026-11-03", "21:00", "Barcelona", "Aston Villa"),
    (4, "2026-11-03", "21:00", "Feyenoord", "Inter"),
    (4, "2026-11-03", "21:00", "Bodo/Glimt", "Lille"),
    (4, "2026-11-03", "21:00", "LASK", "Slovan Bratislava"),
    (4, "2026-11-03", "21:00", "Manchester United", "Roma"),
    (4, "2026-11-03", "21:00", "Villarreal", "Paris Saint-Germain"),
    (4, "2026-11-04", "18:45", "AEK Athens", "Real Madrid"),
    (4, "2026-11-04", "18:45", "Fenerbahce", "Liverpool"),
    (4, "2026-11-04", "21:00", "Borussia Dortmund", "Real Betis"),
    (4, "2026-11-04", "21:00", "Porto", "Napoli"),
    (4, "2026-11-04", "21:00", "PSV Eindhoven", "Club Brugge"),
    (4, "2026-11-04", "21:00", "Leipzig", "Manchester City"),
    (4, "2026-11-04", "21:00", "Lens", "Como"),
    (4, "2026-11-04", "21:00", "Slavia Praha", "Arsenal"),
    (4, "2026-11-04", "21:00", "Viking", "Sabah"),
    (5, "2026-11-24", "18:45", "Bodo/Glimt", "LASK"),
    (5, "2026-11-24", "18:45", "Galatasaray", "Aston Villa"),
    (5, "2026-11-24", "21:00", "Arsenal", "Borussia Dortmund"),
    (5, "2026-11-24", "21:00", "Como", "AEK Athens"),
    (5, "2026-11-24", "21:00", "Feyenoord", "Porto"),
    (5, "2026-11-24", "21:00", "Manchester City", "Napoli"),
    (5, "2026-11-24", "21:00", "Leipzig", "Lens"),
    (5, "2026-11-24", "21:00", "Real Madrid", "PSV Eindhoven"),
    (5, "2026-11-24", "21:00", "Slovan Bratislava", "Real Betis"),
    (5, "2026-11-25", "18:45", "Sabah", "Barcelona"),
    (5, "2026-11-25", "18:45", "Slavia Praha", "Villarreal"),
    (5, "2026-11-25", "21:00", "Atletico Madrid", "Viking"),
    (5, "2026-11-25", "21:00", "Club Brugge", "Liverpool"),
    (5, "2026-11-25", "21:00", "Inter", "Stuttgart"),
    (5, "2026-11-25", "21:00", "Shakhtar Donetsk", "Fenerbahce"),
    (5, "2026-11-25", "21:00", "Lille", "Bayern Munich"),
    (5, "2026-11-25", "21:00", "Paris Saint-Germain", "Roma"),
    (5, "2026-11-25", "21:00", "Sporting CP", "Manchester United"),
    (6, "2026-12-08", "18:45", "Viking", "Feyenoord"),
    (6, "2026-12-08", "18:45", "Villarreal", "Sabah"),
    (6, "2026-12-08", "21:00", "AEK Athens", "Galatasaray"),
    (6, "2026-12-08", "21:00", "Roma", "Sporting CP"),
    (6, "2026-12-08", "21:00", "Aston Villa", "Paris Saint-Germain"),
    (6, "2026-12-08", "21:00", "Barcelona", "Manchester City"),
    (6, "2026-12-08", "21:00", "Bayern Munich", "Slavia Praha"),
    (6, "2026-12-08", "21:00", "Manchester United", "Leipzig"),
    (6, "2026-12-08", "21:00", "Napoli", "Club Brugge"),
    (6, "2026-12-09", "18:45", "Real Betis", "Como"),
    (6, "2026-12-09", "18:45", "Slovan Bratislava", "Shakhtar Donetsk"),
    (6, "2026-12-09", "21:00", "Arsenal", "Real Madrid"),
    (6, "2026-12-09", "21:00", "Borussia Dortmund", "Inter"),
    (6, "2026-12-09", "21:00", "LASK", "Fenerbahce"),
    (6, "2026-12-09", "21:00", "Liverpool", "Porto"),
    (6, "2026-12-09", "21:00", "PSV Eindhoven", "Atletico Madrid"),
    (6, "2026-12-09", "21:00", "Lens", "Bodo/Glimt"),
    (6, "2026-12-09", "21:00", "Stuttgart", "Lille"),
    (7, "2027-01-19", "18:45", "Bodo/Glimt", "Atletico Madrid"),
    (7, "2027-01-19", "18:45", "Galatasaray", "Feyenoord"),
    (7, "2027-01-19", "21:00", "AEK Athens", "Roma"),
    (7, "2027-01-19", "21:00", "Aston Villa", "Borussia Dortmund"),
    (7, "2027-01-19", "21:00", "Inter", "Liverpool"),
    (7, "2027-01-19", "21:00", "Porto", "Slavia Praha"),
    (7, "2027-01-19", "21:00", "Lille", "Slovan Bratislava"),
    (7, "2027-01-19", "21:00", "Real Madrid", "LASK"),
    (7, "2027-01-19", "21:00", "Stuttgart", "Club Brugge"),
    (7, "2027-01-20", "18:45", "Fenerbahce", "Villarreal"),
    (7, "2027-01-20", "18:45", "Sabah", "Napoli"),
    (7, "2027-01-20", "21:00", "Como", "Paris Saint-Germain"),
    (7, "2027-01-20", "21:00", "Manchester United", "Bayern Munich"),
    (7, "2027-01-20", "21:00", "Leipzig", "Shakhtar Donetsk"),
    (7, "2027-01-20", "21:00", "Lens", "Manchester City"),
    (7, "2027-01-20", "21:00", "Real Betis", "Arsenal"),
    (7, "2027-01-20", "21:00", "Sporting CP", "Barcelona"),
    (7, "2027-01-20", "21:00", "Viking", "PSV Eindhoven"),
    (8, "2027-01-27", "21:00", "Arsenal", "Sabah"),
    (8, "2027-01-27", "21:00", "Roma", "Lille"),
    (8, "2027-01-27", "21:00", "Atletico Madrid", "Fenerbahce"),
    (8, "2027-01-27", "21:00", "Borussia Dortmund", "AEK Athens"),
    (8, "2027-01-27", "21:00", "Club Brugge", "Bodo/Glimt"),
    (8, "2027-01-27", "21:00", "Bayern Munich", "Real Betis"),
    (8, "2027-01-27", "21:00", "Barcelona", "Como"),
    (8, "2027-01-27", "21:00", "Shakhtar Donetsk", "Real Madrid"),
    (8, "2027-01-27", "21:00", "Feyenoord", "Leipzig"),
    (8, "2027-01-27", "21:00", "LASK", "Porto"),
    (8, "2027-01-27", "21:00", "Liverpool", "Lens"),
    (8, "2027-01-27", "21:00", "Manchester City", "Sporting CP"),
    (8, "2027-01-27", "21:00", "Paris Saint-Germain", "Galatasaray"),
    (8, "2027-01-27", "21:00", "PSV Eindhoven", "Stuttgart"),
    (8, "2027-01-27", "21:00", "Slavia Praha", "Aston Villa"),
    (8, "2027-01-27", "21:00", "Napoli", "Viking"),
    (8, "2027-01-27", "21:00", "Villarreal", "Manchester United"),
    (8, "2027-01-27", "21:00", "Slovan Bratislava", "Inter"),
]


def _key(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("&", " and ").lower()
    return re.sub(r"[^a-z0-9]+", "", value)


_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, meta in UCL_TEAM_META.items():
    _ALIAS_TO_CANONICAL[_key(canonical)] = canonical
    for alias in meta.get("aliases") or []:
        _ALIAS_TO_CANONICAL[_key(alias)] = canonical


def canonical_ucl_team_name(value: str | None) -> str | None:
    return _ALIAS_TO_CANONICAL.get(_key(value))


def ucl_team_meta(value: str | None) -> dict[str, Any] | None:
    canonical = canonical_ucl_team_name(value)
    return UCL_TEAM_META.get(canonical) if canonical else None


def ucl_team_ru(value: str | None) -> str:
    meta = ucl_team_meta(value)
    return str(meta.get("ru")) if meta else str(value or "")


def ucl_fixture_datetime(date_value: str, time_value: str) -> datetime:
    hour, minute = [int(part) for part in time_value.split(":", 1)]
    year, month, day = [int(part) for part in date_value.split("-", 2)]
    return datetime(year, month, day, hour, minute, tzinfo=UCL_LOCAL_TZ).astimezone(timezone.utc)


def _official_fixture_map() -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for matchday, date_value, time_value, home, away in UCL_LEAGUE_PHASE_FIXTURES:
        home_canonical = canonical_ucl_team_name(home) or home
        away_canonical = canonical_ucl_team_name(away) or away
        result[(home_canonical, away_canonical)] = {
            "matchday": matchday,
            "starts_at": ucl_fixture_datetime(date_value, time_value),
            "home": home_canonical,
            "away": away_canonical,
        }
    return result


OFFICIAL_UCL_FIXTURES = _official_fixture_map()


def _match_key(match: Match) -> tuple[str | None, str | None]:
    home = canonical_ucl_team_name(match.home_team_api_name) or canonical_ucl_team_name(match.home_team)
    away = canonical_ucl_team_name(match.away_team_api_name) or canonical_ucl_team_name(match.away_team)
    return home, away


def _looks_like_qualifying(match: Match) -> bool:
    text = " ".join(str(value or "") for value in [match.stage, match.match_round, match.api_league_round]).lower()
    if "qualif" in text or "play-off" in text or "playoff" in text:
        return True
    starts_at = getattr(match, "starts_at", None)
    return bool(starts_at and starts_at < ucl_fixture_datetime("2026-09-08", "00:00"))


def apply_ucl_league_phase_cleanup(db: Session) -> dict[str, Any]:
    """Remove qualifying fixtures and normalize the 144 league-phase matches."""
    matches = db.query(Match).filter(Match.tournament_code == UCL_2026_2027_CODE).all()
    deleted = 0
    normalized = 0
    unmatched_kept: list[str] = []

    for match in matches:
        key = _match_key(match)
        official = OFFICIAL_UCL_FIXTURES.get(key) if all(key) else None

        if not official:
            if _looks_like_qualifying(match):
                db.delete(match)
                deleted += 1
                continue
            unmatched_kept.append(f"{match.home_team} — {match.away_team}")
            continue

        home_meta = UCL_TEAM_META[official["home"]]
        away_meta = UCL_TEAM_META[official["away"]]
        changed = False
        updates = {
            "home_team": home_meta["ru"],
            "away_team": away_meta["ru"],
            "starts_at": official["starts_at"],
            "stage": "league",
            "match_round": f"Matchday {official['matchday']}",
            "group_code": None,
        }
        for field, value in updates.items():
            if getattr(match, field) != value:
                setattr(match, field, value)
                changed = True
        if changed:
            normalized += 1

    tournament = db.query(Tournament).filter(Tournament.code == UCL_2026_2027_CODE).first()
    first_match_at = min(item["starts_at"] for item in OFFICIAL_UCL_FIXTURES.values())
    if tournament:
        tournament.starts_at = first_match_at
        tournament.prediction_deadline = first_match_at

    db.commit()
    remaining = db.query(Match).filter(Match.tournament_code == UCL_2026_2027_CODE).count()
    return {
        "deleted_non_league_phase": deleted,
        "normalized_league_phase": normalized,
        "remaining_matches": remaining,
        "expected_league_phase_matches": len(OFFICIAL_UCL_FIXTURES),
        "first_match_at": first_match_at.isoformat(),
        "unmatched_kept": unmatched_kept[:20],
        "unmatched_kept_count": len(unmatched_kept),
    }
