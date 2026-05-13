from datetime import datetime, timezone

from app.api_football import ApiFootballClient
from app.models import Match


API_PROVIDER = "api-football"
TOURNAMENT_CODE = "wc2026"


TEAM_NAME_RU = {
    "Mexico": "Мексика",
    "South Africa": "ЮАР",
    "Canada": "Канада",
    "United States": "США",
    "Brazil": "Бразилия",
    "Argentina": "Аргентина",
    "France": "Франция",
    "Spain": "Испания",
    "England": "Англия",
    "Portugal": "Португалия",
    "Germany": "Германия",
    "Netherlands": "Нидерланды",
    "Belgium": "Бельгия",
    "Croatia": "Хорватия",
    "Uruguay": "Уругвай",
    "Japan": "Япония",
    "South Korea": "Южная Корея",
    "Iran": "Иран",
    "Australia": "Австралия",
    "Morocco": "Марокко",
    "Senegal": "Сенегал",
    "Tunisia": "Тунис",
    "Ecuador": "Эквадор",
    "Colombia": "Колумбия",
    "Switzerland": "Швейцария",
    "Denmark": "Дания",
    "Poland": "Польша",
    "Serbia": "Сербия",
    "Czechia": "Чехия",
    "Bosnia and Herzegovina": "Босния и Герцеговина",
    "New Zealand": "Новая Зеландия",
    "Saudi Arabia": "Саудовская Аравия",
}


def display_team_name(api_name: str | None) -> str:
    if not api_name:
        return "TBD"

    return TEAM_NAME_RU.get(api_name, api_name)


def parse_datetime_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def normalize_stage(api_round: str | None) -> str:
    if not api_round:
        return "group"

    value = api_round.lower()

    if "group" in value:
        return "group"

    if "round of 32" in value:
        return "round_of_32"

    if "round of 16" in value:
        return "round_of_16"

    if "quarter" in value:
        return "quarterfinal"

    if "semi" in value:
        return "semifinal"

    if "third" in value:
        return "third_place"

    if "final" in value:
        return "final"

    return "group"


def normalize_match_round(api_round: str | None) -> str | None:
    if not api_round:
        return None

    value = api_round.lower()

    if "group" in value:
        # возможные форматы API: "Group Stage - 1", "Group A - 1"
        for token in ["1", "2", "3"]:
            if token in value:
                return token

        return "1"

    if "round of 32" in value:
        return "1/16"

    if "round of 16" in value:
        return "1/8"

    if "quarter" in value:
        return "1/4"

    if "semi" in value:
        return "1/2"

    if "third" in value:
        return "матч за 3 место"

    if "final" in value:
        return "финал"

    return api_round


def extract_group_code(api_round: str | None) -> str | None:
    if not api_round:
        return None

    # Часто API round содержит что-то вроде "Group A - 1"
    value = api_round.strip()

    for group in list("ABCDEFGHIJKL"):
        if f"Group {group}" in value:
            return group

    return None


def extract_fifa_match_no(api_fixture: dict) -> int | None:
    # API-Football может не отдавать номер матча FIFA напрямую.
    # Поэтому оставляем None. Если появится в payload — добавим здесь.
    return None


def get_fixture_score(api_fixture: dict) -> tuple[int | None, int | None]:
    goals = api_fixture.get("goals") or {}

    return goals.get("home"), goals.get("away")


def get_winner_side(api_fixture: dict) -> str | None:
    teams = api_fixture.get("teams") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}

    if home.get("winner") is True:
        return "home"

    if away.get("winner") is True:
        return "away"

    return None


def normalize_api_fixture(api_fixture: dict) -> dict:
    fixture = api_fixture["fixture"]
    league = api_fixture.get("league") or {}
    teams = api_fixture.get("teams") or {}
    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}

    api_round = league.get("round")

    score_home, score_away = get_fixture_score(api_fixture)

    return {
        "external_fixture_id": str(fixture["id"]),
        "external_provider": API_PROVIDER,
        "tournament_code": TOURNAMENT_CODE,

        "fifa_match_no": extract_fifa_match_no(api_fixture),

        "home_team": display_team_name(home.get("name")),
        "away_team": display_team_name(away.get("name")),

        "home_external_team_id": home.get("id"),
        "away_external_team_id": away.get("id"),

        "stage": normalize_stage(api_round),
        "match_round": normalize_match_round(api_round),
        "group_code": extract_group_code(api_round),
        "api_league_round": api_round,

        "starts_at": parse_datetime_utc(fixture["date"]),

        "venue": venue.get("name"),
        "city": venue.get("city"),

        "score_home": score_home,
        "score_away": score_away,

        "winner_side": get_winner_side(api_fixture),

        "status_short": status.get("short"),
        "status_long": status.get("long"),

        "is_finished": status.get("short") in {"FT", "AET", "PEN"},
        "synced_at": datetime.now(timezone.utc),

        "home_team_api_name": home.get("name"),
        "away_team_api_name": away.get("name"),

    }


def upsert_match_from_api_fixture(db, api_fixture: dict) -> tuple[Match, bool]:
    row = normalize_api_fixture(api_fixture)

    match = db.query(Match).filter(
        Match.external_provider == API_PROVIDER,
        Match.external_fixture_id == row["external_fixture_id"],
    ).first()

    created = False

    if not match:
        match = Match(
            external_provider=row["external_provider"],
            external_fixture_id=row["external_fixture_id"],
            tournament_code=row["tournament_code"],
            home_team=row["home_team"],
            away_team=row["away_team"],
            starts_at=row["starts_at"],
            stage=row["stage"],
        )
        db.add(match)
        created = True

    for key, value in row.items():
        setattr(match, key, value)

    return match, created


def sync_wc2026_schedule(db) -> dict:
    client = ApiFootballClient()

    fixtures = client.get_world_cup_fixtures(season=2026)

    created = 0
    updated = 0

    for api_fixture in fixtures:
        _, was_created = upsert_match_from_api_fixture(db, api_fixture)

        if was_created:
            created += 1
        else:
            updated += 1

    db.commit()

    return {
        "total": len(fixtures),
        "created": created,
        "updated": updated,
    }