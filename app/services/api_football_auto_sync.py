"""Automatic API-Football result and Fantasy statistics synchronization."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api_football import ApiFootballClient
from app.models import FantasyPlayer, FantasyPlayerMatchStat, FantasyTeam, Match
from app.runtime import TOURNAMENT_CODE
from app.services.matches import apply_match_result_from_admin, is_playoff_match
from app.wc2026_sync import get_fixture_final_score, get_fixture_score, get_winner_side

FINISHED_STATUSES = {"FT", "AET", "PEN"}


def _match_label(match: Match) -> str:
    return f"{match.home_team} — {match.away_team}"


def calculate_fantasy_points_for_stat(player: FantasyPlayer, stat: dict) -> int:
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


def extract_player_fixture_stats(api_player_item: dict) -> dict:
    """Extract the first fixture statistics block from API-Football /fixtures/players."""
    statistics = api_player_item.get("statistics") or []
    first = statistics[0] if statistics else {}

    games = first.get("games") or {}
    goals = first.get("goals") or {}
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


def recalculate_fantasy_team_points(db: Session) -> int:
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


def sync_one_match_result_from_api(db: Session, match: Match, client: ApiFootballClient | None = None) -> dict:
    """Sync one match result/status from API-Football."""
    if not match.external_fixture_id:
        return {"ok": False, "updated": False, "message": "no external_fixture_id"}

    client = client or ApiFootballClient()
    api_fixture = client.get_fixture_by_id(match.external_fixture_id)

    if not api_fixture:
        return {"ok": False, "updated": False, "message": "fixture not found"}

    status = api_fixture["fixture"]["status"]["short"]
    match.status_short = status
    match.status_long = api_fixture["fixture"]["status"].get("long")
    match.synced_at = datetime.now(timezone.utc)

    if status not in FINISHED_STATUSES:
        db.commit()
        return {"ok": True, "updated": False, "message": f"status {status}"}

    # Predictions are scored by regular time; keep the extra-time score only
    # for display and the independent advancing-team bet.
    score_home, score_away = get_fixture_score(api_fixture)
    final_score_home, final_score_away = get_fixture_final_score(api_fixture)
    if score_home is None or score_away is None:
        db.commit()
        return {"ok": False, "updated": False, "message": "API did not return score"}

    winner_side = get_winner_side(api_fixture) if is_playoff_match(match) else None
    if is_playoff_match(match) and winner_side is None:
        db.commit()
        return {"ok": False, "updated": False, "message": "playoff winner not found"}

    already_finished_with_same_score = (
        bool(match.is_finished)
        and match.score_home == score_home
        and match.score_away == score_away
        and match.final_score_home == final_score_home
        and match.final_score_away == final_score_away
        and match.winner_side == winner_side
    )

    if already_finished_with_same_score:
        db.commit()
        return {"ok": True, "updated": False, "message": f"already {score_home}:{score_away}"}

    apply_match_result_from_admin(
        db=db,
        match=match,
        score_home=score_home,
        score_away=score_away,
        winner_side=winner_side,
        final_score_home=final_score_home,
        final_score_away=final_score_away,
    )

    return {"ok": True, "updated": True, "message": f"updated {score_home}:{score_away}"}


def sync_recent_match_results(db: Session, *, lookback_hours: int = 8, limit: int = 20) -> dict:
    """Find recently started/finished matches and update their result automatically."""
    now = datetime.now(timezone.utc)
    started_after = now - timedelta(hours=max(1, lookback_hours))

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.external_provider == "api-football",
            Match.external_fixture_id.isnot(None),
            Match.is_finished == False,
            Match.starts_at <= now,
            Match.starts_at >= started_after,
        )
        .order_by(Match.starts_at.asc())
        .limit(limit)
        .all()
    )

    client = ApiFootballClient()
    results = []

    for match in matches:
        try:
            result = sync_one_match_result_from_api(db, match, client)
        except Exception as error:
            result = {"ok": False, "updated": False, "message": str(error)}
        results.append({"match_id": match.id, "label": _match_label(match), **result})

    return {
        "checked": len(matches),
        "updated": sum(1 for item in results if item.get("updated")),
        "results": results,
    }


def sync_fantasy_player_stats(db: Session, *, lookback_hours: int = 36, limit: int = 20) -> dict:
    """Sync player statistics for recently finished API-Football fixtures."""
    now = datetime.now(timezone.utc)
    started_after = now - timedelta(hours=max(1, lookback_hours))

    client = ApiFootballClient()
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.external_provider == "api-football",
            Match.external_fixture_id.isnot(None),
            Match.is_finished == True,
            Match.starts_at >= started_after,
        )
        .order_by(Match.starts_at.asc())
        .limit(limit)
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

                extracted = extract_player_fixture_stats(api_player_item)
                points = calculate_fantasy_points_for_stat(fantasy_player, extracted)

                row = (
                    db.query(FantasyPlayerMatchStat)
                    .filter(
                        FantasyPlayerMatchStat.player_id == fantasy_player.id,
                        FantasyPlayerMatchStat.match_id == match.id,
                    )
                    .first()
                )

                if not row:
                    row = FantasyPlayerMatchStat(player_id=fantasy_player.id, match_id=match.id)
                    db.add(row)

                for key, value in extracted.items():
                    setattr(row, key, value)

                row.points = points
                row.source_updated_at = datetime.now(timezone.utc)
                stat_rows += 1

    teams_updated = recalculate_fantasy_team_points(db)
    db.commit()

    return {
        "checked_matches": checked,
        "stat_rows_upserted": stat_rows,
        "skipped_matches": skipped,
        "fantasy_teams_updated": teams_updated,
        "errors": errors[:20],
    }


def auto_sync_results_and_fantasy(db: Session) -> dict:
    """Run the complete automatic post-match sync pipeline."""
    result_sync = sync_recent_match_results(db)
    stats_sync = sync_fantasy_player_stats(db)
    return {"results": result_sync, "fantasy_stats": stats_sync}
