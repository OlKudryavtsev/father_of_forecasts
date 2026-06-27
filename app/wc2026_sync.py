from datetime import datetime, timezone

from app.api_football import ApiFootballClient
from app.models import Match, Prediction
from app.scoring import score_match_prediction


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


def normalize_api_fixture(
    api_fixture: dict,
    team_group_map: dict[int, str] | None = None,
) -> dict:
    fixture = api_fixture["fixture"]
    league = api_fixture.get("league") or {}
    teams = api_fixture.get("teams") or {}
    venue = fixture.get("venue") or {}
    status = fixture.get("status") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}

    team_group_map = team_group_map or {}

    home_team_id = home.get("id")
    away_team_id = away.get("id")

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
        # Group membership is useful for group-stage fixtures only.  A knockout
        # fixture can inherit one participant's group through team_group_map;
        # persisting it here made R32 teams appear as fifth/sixth rows in the
        # Mini App group table.  Keep playoff rows explicitly outside groups.
        "group_code": (
            extract_group_code(api_round)
            or team_group_map.get(home_team_id)
            or team_group_map.get(away_team_id)
        ) if normalize_stage(api_round) == "group" else None,
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


def _is_playoff_stage(stage: str | None) -> bool:
    return stage in {
        "round_of_32",
        "round_of_16",
        "quarterfinal",
        "semifinal",
        "third_place",
        "final",
    }


def _prediction_points_are_stale(db, match: Match, row: dict) -> bool:
    """Check whether stored prediction points disagree with the final API score.

    The schedule synchronizer can discover a final score before the ordinary
    result synchronizer sees the fixture. In that case all score fields are
    already present on the match, but predictions still contain their previous
    zero values. Detect that state so a later calendar refresh self-heals it.
    """
    if not row.get("is_finished"):
        return False

    score_home = row.get("score_home")
    score_away = row.get("score_away")
    if score_home is None or score_away is None:
        return False

    predictions = db.query(Prediction).filter(Prediction.match_id == match.id).all()
    for prediction in predictions:
        expected = score_match_prediction(
            pred_home=prediction.pred_home,
            pred_away=prediction.pred_away,
            actual_home=score_home,
            actual_away=score_away,
            advancement_bet_enabled=bool(prediction.advancement_bet_enabled),
            predicted_advancing_side=prediction.predicted_advancing_side,
            actual_winner_side=row.get("winner_side"),
        )
        if (
            int(prediction.score_points or 0) != int(expected["score_points"])
            or int(prediction.advancement_points or 0) != int(expected["advancement_points"])
            or int(prediction.points or 0) != int(expected["total_points"])
        ):
            return True

    return False


def _apply_final_result_and_recalculate_predictions(
    db,
    match: Match,
    score_home: int,
    score_away: int,
    winner_side: str | None,
) -> int:
    """Persist a final result and recalculate every prediction for the match.

    Kept local to schedule synchronization to avoid importing the Telegram
    service layer (and its runtime dependencies) from a background sync job.
    """
    match.score_home = score_home
    match.score_away = score_away
    match.winner_side = winner_side
    match.is_finished = True

    predictions = db.query(Prediction).filter(Prediction.match_id == match.id).all()
    for prediction in predictions:
        result = score_match_prediction(
            pred_home=prediction.pred_home,
            pred_away=prediction.pred_away,
            actual_home=score_home,
            actual_away=score_away,
            advancement_bet_enabled=bool(prediction.advancement_bet_enabled),
            predicted_advancing_side=prediction.predicted_advancing_side,
            actual_winner_side=winner_side,
        )
        prediction.score_points = result["score_points"]
        prediction.advancement_points = result["advancement_points"]
        prediction.points = result["total_points"]

    return len(predictions)


def upsert_match_from_api_fixture(
    db,
    api_fixture: dict,
    team_group_map: dict[int, str] | None = None,
) -> tuple[Match, bool, bool]:
    """Create/update a fixture and recalculate predictions when a final arrives.

    Final scores must go through the same scorer as manual result entry.
    Writing them directly into ``matches`` marks a match as finished but leaves
    participant predictions at stale values.
    """
    row = normalize_api_fixture(
        api_fixture=api_fixture,
        team_group_map=team_group_map,
    )

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

    # Result fields are deliberately excluded here: finished results are applied
    # below through apply_match_result_from_admin(), which recalculates points.
    result_keys = {"score_home", "score_away", "winner_side", "is_finished"}
    for key, value in row.items():
        if key not in result_keys:
            setattr(match, key, value)

    recalculated = False
    has_final_score = (
        bool(row.get("is_finished"))
        and row.get("score_home") is not None
        and row.get("score_away") is not None
    )

    if has_final_score:
        playoff_requires_winner = _is_playoff_stage(match.stage)
        winner_side = row.get("winner_side") if playoff_requires_winner else None
        result_changed = (
            not bool(match.is_finished)
            or match.score_home != row.get("score_home")
            or match.score_away != row.get("score_away")
            or match.winner_side != winner_side
        )
        points_stale = (
            not created
            and (not playoff_requires_winner or winner_side is not None)
            and _prediction_points_are_stale(db, match, row)
        )

        if (result_changed or points_stale) and (not playoff_requires_winner or winner_side is not None):
            _apply_final_result_and_recalculate_predictions(
                db=db,
                match=match,
                score_home=int(row["score_home"]),
                score_away=int(row["score_away"]),
                winner_side=winner_side,
            )
            recalculated = True
        else:
            # New historical fixtures normally have no predictions yet. Preserve
            # their final result without invoking the scorer unnecessarily.
            match.score_home = row.get("score_home")
            match.score_away = row.get("score_away")
            match.winner_side = winner_side
            match.is_finished = True
    else:
        # Keep live/unknown score metadata, but never mark the match as final.
        match.score_home = row.get("score_home")
        match.score_away = row.get("score_away")
        match.winner_side = row.get("winner_side")
        match.is_finished = bool(row.get("is_finished"))

    return match, created, recalculated


def sync_wc2026_schedule(db) -> dict:
    client = ApiFootballClient()

    fixtures = client.get_world_cup_fixtures(season=2026)

    try:
        standings = client.get_world_cup_standings(season=2026)
        team_group_map = build_team_group_map_from_standings(standings)
    except Exception as error:
        print(f"Failed to load WC2026 standings/groups: {error}")
        team_group_map = {}

    created = 0
    updated = 0
    recalculated_results = 0

    for api_fixture in fixtures:
        _, was_created, was_recalculated = upsert_match_from_api_fixture(
            db=db,
            api_fixture=api_fixture,
            team_group_map=team_group_map,
        )

        if was_created:
            created += 1
        else:
            updated += 1

        if was_recalculated:
            recalculated_results += 1

    db.commit()

    return {
        "total": len(fixtures),
        "created": created,
        "updated": updated,
        "recalculated_results": recalculated_results,
    }

def build_team_group_map_from_standings(standings: list[list[dict]]) -> dict[int, str]:
    """
    Возвращает:
    {
        team_id: "A",
        team_id: "B",
        ...
    }
    """

    team_group_map = {}

    for group_rows in standings:
        for row in group_rows:
            group_name = row.get("group") or ""

            team = row.get("team") or {}
            team_id = team.get("id")

            if not team_id:
                continue

            group_code = None

            # Возможные варианты:
            # "Group A"
            # "World Cup - Group A"
            # "A"
            for letter in list("ABCDEFGHIJKL"):
                if f"Group {letter}" in group_name or group_name.strip() == letter:
                    group_code = letter
                    break

            if group_code:
                team_group_map[team_id] = group_code

    return team_group_map