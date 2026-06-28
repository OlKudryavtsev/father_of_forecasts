"""Real implementation extracted from the former bot_runtime monolith."""


import asyncio
import os
import re

from app.constants.categories import PLAYOFF_STAGES
from app.formatters.matches import format_datetime, format_match_label, format_match_result, format_user_match_prediction
from app.formatters.misc import format_reminder_offset
from app.keyboards.matches import build_matches_keyboard, build_prediction_reminder_keyboard
from app.models import AppSetting, FatherMatchPrediction, League, LeagueMember
from app.services.gamification import normalize_humor_mode, sync_new_achievements
from app.runtime import (
    APP_TIMEZONE,
    MATCHDAY_TIMEZONE,
    Match,
    Prediction,
    SessionLocal,
    TOURNAMENT_CODE,
    User,
    bot,
    GROUP_CHAT_ID_RAW,
    csv,
    datetime,
    io,
    score_match_prediction,
    timedelta,
    timezone,
)

def is_playoff_match(match: Match) -> bool:
    """Provide bot helper logic for is_playoff_match."""
    return match.stage in PLAYOFF_STAGES


def parse_admin_match_payload(text: str):
    """Provide bot helper logic for parse_admin_match_payload."""
    payload = text.replace("/admin_add_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (4, 5, 6):
        raise ValueError("Invalid admin match format")

    home_team = parts[0]
    away_team = parts[1]
    starts_at_raw = parts[2]
    stage = parts[3]
    match_round = parts[4] if len(parts) >= 5 else get_default_match_round(stage)
    tournament_code = parts[5] if len(parts) == 6 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return home_team, away_team, starts_at, stage, match_round, tournament_code


def parse_admin_edit_match_payload(text: str):
    """Provide bot helper logic for parse_admin_edit_match_payload."""
    payload = text.replace("/admin_edit_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (5, 6, 7):
        raise ValueError("Invalid admin edit match format")

    match_id_raw = parts[0]

    if not match_id_raw.isdigit():
        raise ValueError("Match ID must be number")

    match_id = int(match_id_raw)
    home_team = parts[1]
    away_team = parts[2]
    starts_at_raw = parts[3]
    stage = parts[4]
    match_round = parts[5] if len(parts) >= 6 else get_default_match_round(stage)
    tournament_code = parts[6] if len(parts) == 7 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return match_id, home_team, away_team, starts_at, stage, match_round, tournament_code


def parse_match_id_command(text: str, command: str) -> int:
    """Provide bot helper logic for parse_match_id_command."""
    payload = text.replace(command, "", 1).strip()

    if not payload.isdigit():
        raise ValueError("Match ID must be number")

    return int(payload)


def parse_result_payload(text: str):
    """Provide bot helper logic for parse_result_payload."""
    from app.services.predictions import parse_score
    parts = text.split()

    if len(parts) not in (3, 4):
        raise ValueError("Invalid result format")

    _, match_id_raw, score_raw, *winner_side_raw = parts

    if not match_id_raw.isdigit():
        raise ValueError("Match ID must be number")

    match_id = int(match_id_raw)
    score_home, score_away = parse_score(score_raw)

    winner_side = winner_side_raw[0].lower() if winner_side_raw else None

    if winner_side not in (None, "home", "away"):
        raise ValueError("Invalid winner_side")

    return match_id, score_home, score_away, winner_side


def get_available_matches_query(db):
    """Provide bot helper logic for get_available_matches_query."""
    now = datetime.now(timezone.utc)

    return db.query(Match).filter(
        Match.is_finished == False,
        Match.starts_at > now,
    ).order_by(Match.starts_at.asc())


def get_nearest_matchday_matches(
    db,
    matchdays_count: int = 1,
) -> list[Match]:
    """
    Возвращает матчи ближайших N игровых дней.

    По умолчанию matchdays_count=1 — текущее поведение:
    только ближайший игровой день.

    Игровой день считаем не по Москве, а по MATCHDAY_TIMEZONE.
    Например, для WC2026 удобно использовать America/New_York.
    """

    if matchdays_count < 1:
        matchdays_count = 1

    all_future_matches = get_available_matches_query(db).all()

    if not all_future_matches:
        return []

    selected_matchday_dates = []
    result = []

    for match in all_future_matches:
        matchday_date = match.starts_at.astimezone(
            MATCHDAY_TIMEZONE
        ).date()

        if matchday_date not in selected_matchday_dates:
            if len(selected_matchday_dates) >= matchdays_count:
                break

            selected_matchday_dates.append(matchday_date)

        if matchday_date in selected_matchday_dates:
            result.append(match)

    return result


def get_all_available_matches(db, limit: int = 30) -> list[Match]:
    """Provide bot helper logic for get_all_available_matches."""
    return get_available_matches_query(db).limit(limit).all()


def get_default_match_round(stage: str) -> str:
    """Provide bot helper logic for get_default_match_round."""
    mapping = {
        "group": "1",
        "round_of_32": "1/16",
        "round_of_16": "1/8",
        "quarterfinal": "1/4",
        "semifinal": "1/2",
        "third_place": "матч за 3 место",
        "final": "финал",
    }

    return mapping.get(stage, stage)


def parse_csv_matches(csv_text: str) -> list[dict]:
    """Provide bot helper logic for parse_csv_matches."""
    csv_text = csv_text.replace("\ufeff", "").strip()

    if not csv_text:
        raise ValueError("CSV is empty")

    first_line = csv_text.splitlines()[0]

    delimiter = ";" if ";" in first_line else ","

    reader = csv.DictReader(
        io.StringIO(csv_text),
        delimiter=delimiter,
    )

    required_columns = {
        "home_team",
        "away_team",
        "starts_at",
        "stage",
    }

    if not reader.fieldnames:
        raise ValueError("CSV has no header")

    fieldnames = {name.strip() for name in reader.fieldnames}

    missing = required_columns - fieldnames

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    rows = []

    for index, row in enumerate(reader, start=2):
        cleaned = {
            key.strip(): (value.strip() if value else "")
            for key, value in row.items()
            if key
        }

        if not cleaned.get("home_team") and not cleaned.get("away_team"):
            continue

        try:
            starts_at = datetime.fromisoformat(
                cleaned["starts_at"].replace("Z", "+00:00")
            )
        except ValueError:
            raise ValueError(
                f"Invalid starts_at at CSV line {index}: {cleaned.get('starts_at')}"
            )

        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

        starts_at = starts_at.astimezone(timezone.utc)

        fifa_match_no_raw = cleaned.get("fifa_match_no") or ""
        fifa_match_no = int(fifa_match_no_raw) if fifa_match_no_raw.isdigit() else None

        stage = cleaned.get("stage") or "group"

        rows.append(
            {
                "fifa_match_no": fifa_match_no,
                "home_team": cleaned["home_team"],
                "away_team": cleaned["away_team"],
                "starts_at": starts_at,
                "stage": stage,
                "match_round": cleaned.get("match_round") or get_default_match_round(stage),
                "tournament_code": cleaned.get("tournament_code") or TOURNAMENT_CODE,
                "group_code": cleaned.get("group_code") or None,
                "venue": cleaned.get("venue") or None,
                "city": cleaned.get("city") or None,
            }
        )

    return rows


def import_matches_from_rows(db, rows: list[dict]) -> dict:
    """Provide bot helper logic for import_matches_from_rows."""
    created = 0
    updated = 0
    skipped = 0
    imported_matches = []

    for row in rows:
        existing_match = None

        if row["fifa_match_no"] is not None:
            existing_match = db.query(Match).filter(
                Match.tournament_code == row["tournament_code"],
                Match.fifa_match_no == row["fifa_match_no"],
            ).first()

        if existing_match is None:
            existing_match = db.query(Match).filter(
                Match.tournament_code == row["tournament_code"],
                Match.home_team == row["home_team"],
                Match.away_team == row["away_team"],
                Match.starts_at == row["starts_at"],
            ).first()

        if existing_match:
            existing_match.home_team = row["home_team"]
            existing_match.away_team = row["away_team"]
            existing_match.starts_at = row["starts_at"]
            existing_match.stage = row["stage"]
            existing_match.match_round = row["match_round"]
            existing_match.group_code = row["group_code"]
            existing_match.venue = row["venue"]
            existing_match.city = row["city"]

            if row["fifa_match_no"] is not None:
                existing_match.fifa_match_no = row["fifa_match_no"]

            updated += 1
            match = existing_match
        else:
            match = Match(
                fifa_match_no=row["fifa_match_no"],
                home_team=row["home_team"],
                away_team=row["away_team"],
                starts_at=row["starts_at"],
                stage=row["stage"],
                match_round=row["match_round"],
                tournament_code=row["tournament_code"],
                group_code=row["group_code"],
                venue=row["venue"],
                city=row["city"],
            )

            db.add(match)
            created += 1

        imported_matches.append(row)

    db.commit()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(imported_matches),
    }


def apply_match_result_from_admin(
        db,
        match: Match,
        score_home: int,
        score_away: int,
        winner_side: str | None = None,
) -> list[str]:
    """Provide bot helper logic for apply_match_result_from_admin."""
    if is_playoff_match(match) and winner_side is None:
        raise ValueError("Playoff match requires winner_side")

    if not is_playoff_match(match) and winner_side is not None:
        raise ValueError("Group match must not have winner_side")

    match.score_home = score_home
    match.score_away = score_away
    match.winner_side = winner_side
    match.is_finished = True

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    recalculated = []

    for prediction in predictions:
        result = score_match_prediction(
            pred_home=prediction.pred_home,
            pred_away=prediction.pred_away,
            actual_home=score_home,
            actual_away=score_away,
            advancement_bet_enabled=prediction.advancement_bet_enabled,
            predicted_advancing_side=prediction.predicted_advancing_side,
            actual_winner_side=winner_side,
        )

        prediction.score_points = result["score_points"]
        prediction.advancement_points = result["advancement_points"]
        prediction.points = result["total_points"]

        recalculated.append(
            {
                "user": prediction.user.display_name,
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "score_points": prediction.score_points,
                "advancement_points": prediction.advancement_points,
                "total_points": prediction.points,
            }
        )

    db.commit()

    lines = [
        "Результат сохранен ✅",
        "",
        f"{format_match_label(match, include_id=False)}: {score_home}:{score_away}",
    ]

    if winner_side == "home":
        lines.append(f"Прошла команда: {match.home_team}")
    elif winner_side == "away":
        lines.append(f"Прошла команда: {match.away_team}")

    lines.append("")
    lines.append("Пересчет прогнозов:")

    if not recalculated:
        lines.append("Прогнозов на этот матч нет.")
    else:
        for item in recalculated:
            lines.append(
                f"{item['user']}: {item['prediction']} → "
                f"{item['total_points']} очк. "
                f"({item['score_points']} за счет/исход, "
                f"{item['advancement_points']} за проход)"
            )

    return lines


def get_recent_and_upcoming_matches(db, limit: int = 20) -> list[Match]:
    """Provide bot helper logic for get_recent_and_upcoming_matches."""
    now = datetime.now(timezone.utc)

    # Берем последние завершенные/начавшиеся и ближайшие будущие
    past_matches = (
        db.query(Match)
            .filter(Match.starts_at <= now)
            .order_by(Match.starts_at.desc())
            .limit(5)
            .all()
    )

    future_matches = (
        db.query(Match)
            .filter(Match.starts_at > now)
            .order_by(Match.starts_at)
            .limit(limit - len(past_matches))
            .all()
    )

    matches = list(reversed(past_matches)) + future_matches

    return matches


def get_match_status(match: Match) -> str:
    """Provide bot helper logic for get_match_status."""
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    if match.is_finished:
        return "🏁 Завершен"

    if now >= match_start:
        return "🔓 Идет / прогнозы открыты"

    return "⏳ Открыт для прогнозов"


def build_match_card_text(db, user: User, match: Match) -> str:
    """Provide bot helper logic for build_match_card_text."""
    now = datetime.now(timezone.utc)

    match_start = match.starts_at
    if match_start.tzinfo is None:
        match_start = match_start.replace(tzinfo=timezone.utc)

    predictions_are_revealed = now >= match_start

    my_prediction = db.query(Prediction).filter(
        Prediction.user_id == user.id,
        Prediction.match_id == match.id,
    ).first()

    predictions_count = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).count()

    users_count = db.query(User).count()

    lines = [
        "⚽ Карточка матча",
        "",
        format_match_label(match, include_id=True),
        f"Старт: {format_datetime(match.starts_at)}",
        f"Статус: {get_match_status(match)}",
        f"Стадия: {match.stage}",
    ]

    if match.group_code:
        lines.append(f"Группа: {match.group_code}")

    if match.match_round:
        if match.stage == "group":
            lines.append(f"Тур: {match.match_round}")
        else:
            lines.append(f"Раунд: {match.match_round}")

    if match.venue or match.city:
        venue_parts = [part for part in [match.venue, match.city] if part]
        lines.append(f"Стадион: {', '.join(venue_parts)}")

    lines.extend(
        [
            "",
            format_match_result(match),
            "",
            f"Прогнозов сделано: {predictions_count} из {users_count}",
            "",
            "Твой прогноз:",
            format_user_match_prediction(
                my_prediction,
                match,
                reveal=True,
            ),
            "",
        ]
    )

    users = db.query(User).order_by(User.display_name).all()

    predictions = db.query(Prediction).filter(
        Prediction.match_id == match.id
    ).all()

    predictions_by_user_id = {
        prediction.user_id: prediction
        for prediction in predictions
    }

    if predictions_are_revealed:
        lines.append("Прогнозы участников:")
        lines.append("")

        for participant in users:
            prediction = predictions_by_user_id.get(participant.id)

            lines.append(
                f"{participant.display_name}: "
                f"{format_user_match_prediction(prediction, match, reveal=True)}"
            )
    else:
        lines.append("До старта матча чужие прогнозы скрыты.")
        lines.append("Видно только, кто уже сделал прогноз:")
        lines.append("")

        for participant in users:
            prediction = predictions_by_user_id.get(participant.id)

            lines.append(
                f"{participant.display_name}: "
                f"{format_user_match_prediction(prediction, match, reveal=False)}"
            )

    return "\n".join(lines)




def _prediction_score_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def _father_builtin_score(db, match: Match) -> tuple[int, int] | None:
    """Return fixed Father scores for the first two matches."""
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


def _ensure_father_match_prediction_for_notifications(db, match: Match) -> FatherMatchPrediction:
    """Get or create Father's match prediction for notifications without importing webapp router."""
    existing = db.query(FatherMatchPrediction).filter(FatherMatchPrediction.match_id == match.id).first()
    if existing:
        return existing

    score = _father_builtin_score(db, match)
    source = "seed"
    text = None

    if score is None:
        try:
            from app.services.forecast import build_forecast_text
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
        outcome=_prediction_score_outcome(pred_home, pred_away),
        confidence=None,
        source=source,
        forecast_text=text,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def _format_father_prediction_line(db, match: Match) -> str:
    father = _ensure_father_match_prediction_for_notifications(db, match)
    return f"🤖 Отец прогнозов: {father.pred_home}:{father.pred_away}"


def _get_match_predictions_with_users(db, match: Match, league: League | None = None):
    query = (
        db.query(Prediction, User)
        .join(User, User.id == Prediction.user_id)
    )

    if league is not None:
        query = query.join(
            LeagueMember,
            (LeagueMember.user_id == User.id)
            & (LeagueMember.league_id == league.id)
            & (LeagueMember.status == "active")
            & (LeagueMember.joined_at <= match.starts_at),
        )

    return (
        query
        .filter(Prediction.match_id == match.id)
        .order_by(User.display_name.asc())
        .all()
    )


def _advancement_pick_text(prediction: Prediction, match: Match) -> str:
    """Render one explicit playoff advancement choice, including an omitted pick."""
    if not is_playoff_match(match):
        return ""
    if prediction.advancement_bet_enabled and prediction.predicted_advancing_side == "home":
        return f"проход: {match.home_team}"
    if prediction.advancement_bet_enabled and prediction.predicted_advancing_side == "away":
        return f"проход: {match.away_team}"
    return "проход: не указан"


def _format_participant_prediction_lines(db, match: Match, with_points: bool = False, league: League | None = None) -> list[str]:
    rows = _get_match_predictions_with_users(db, match, league=league)

    if not rows:
        return ["— прогнозов участников нет. Видимо, все оставили аналитику в черновиках."]

    lines = []
    for prediction, user in rows:
        text = f"— {user.display_name}: {prediction.pred_home}:{prediction.pred_away}"

        if is_playoff_match(match):
            text += f" · {_advancement_pick_text(prediction, match)}"

        if with_points and match.is_finished:
            points = prediction.points
            if points is None and match.score_home is not None and match.score_away is not None:
                result = score_match_prediction(
                    pred_home=prediction.pred_home,
                    pred_away=prediction.pred_away,
                    actual_home=match.score_home,
                    actual_away=match.score_away,
                    advancement_bet_enabled=prediction.advancement_bet_enabled,
                    predicted_advancing_side=prediction.predicted_advancing_side,
                    actual_winner_side=match.winner_side,
                )
                points = result["total_points"]
            text += f" → {points or 0} очк."

        lines.append(text)

    return lines


def build_match_start_group_notification_text(db, match: Match, league: League | None = None) -> str:
    participant_lines = _format_participant_prediction_lines(db, match, with_points=False, league=league)
    father_line = _format_father_prediction_line(db, match)

    return (
        "⚽ Матч начался!\n\n"
        f"{format_match_label(match, include_id=False)}\n"
        "Прогнозы раскрыты. Начинается коллективная проверка уверенности.\n\n"
        f"{father_line}\n\n"
        "👥 Прогнозы участников:\n"
        + "\n".join(participant_lines)
        + "\n\nОтец прогнозов уже приготовил таблицу. И красную ручку тоже."
    )


def build_daily_match_summary_text(db, now_local=None, league: League | None = None) -> str:
    """Build daily morning summary for matches finished/started during previous 24h."""
    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=24)

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at >= since_utc,
            Match.starts_at <= now_utc,
        )
        .order_by(Match.starts_at.asc())
        .all()
    )

    finished = [m for m in matches if m.is_finished and m.score_home is not None and m.score_away is not None]
    unfinished = [m for m in matches if not (m.is_finished and m.score_home is not None and m.score_away is not None)]

    lines = [
        "☕ Утренний разбор Отца прогнозов",
        "",
        "За последние сутки футбол снова попытался объяснить людям, что Excel не гарантирует понимание игры.",
    ]

    if not matches:
        lines.extend([
            "",
            "Матчей за последние 24 часа не было.",
            "Отец прогнозов уважительно молчит, но таблицу все равно держит открытой.",
        ])
        return "\n".join(lines)

    if finished:
        lines.extend(["", "🏁 Завершенные матчи:"])

        for match in finished:
            predictions = _get_match_predictions_with_users(db, match, league=league)
            exact = []
            outcome = []
            miss = []

            for prediction, user in predictions:
                label = f"{user.display_name} ({prediction.pred_home}:{prediction.pred_away})"
                score_points = prediction.score_points
                if score_points is None:
                    result = score_match_prediction(
                        pred_home=prediction.pred_home,
                        pred_away=prediction.pred_away,
                        actual_home=match.score_home,
                        actual_away=match.score_away,
                        advancement_bet_enabled=prediction.advancement_bet_enabled,
                        predicted_advancing_side=prediction.predicted_advancing_side,
                        actual_winner_side=match.winner_side,
                    )
                    score_points = result["score_points"]

                if score_points == 3:
                    exact.append(label)
                elif score_points == 1:
                    outcome.append(label)
                else:
                    miss.append(label)

            lines.extend([
                "",
                f"{format_match_label(match, include_id=False)}",
                f"Итог: {match.score_home}:{match.score_away}",
                f"🎯 Точный счет: {', '.join(exact) if exact else 'никто. Красная ручка скучала, но недолго.'}",
                f"🔵 Исход: {', '.join(outcome) if outcome else 'никто.'}",
                f"🔴 Мимо: {', '.join(miss) if miss else 'никто. Подозрительно качественный тур.'}",
            ])

    if unfinished:
        lines.extend(["", "⏳ Матчи без финального результата:"])
        for match in unfinished:
            lines.append(f"— {format_match_label(match, include_id=False)}: результат еще не внесен")

    lines.extend([
        "",
        "Итог дня: точный счет — это не интуиция, а редкий вид бытовой магии.",
    ])

    return "\n".join(lines)

def _app_event_sent(db, key: str) -> bool:
    return db.query(AppSetting).filter(AppSetting.setting_key == key).first() is not None


def _mark_app_event_sent(db, key: str):
    setting = AppSetting(setting_key=key, setting_value="sent")
    db.add(setting)
    db.commit()


def build_match_finished_group_notification_text(db, match: Match, league: League | None = None) -> str:
    predictions = _get_match_predictions_with_users(db, match, league=league)
    exact = []
    outcome = []
    miss = []

    for prediction, user in predictions:
        label = f"{user.display_name} ({prediction.pred_home}:{prediction.pred_away})"
        if prediction.score_points == 3:
            exact.append(label)
        elif prediction.score_points == 1:
            outcome.append(label)
        else:
            miss.append(label)

    return (
        "🏁 Матч окончен. Отец достает красную ручку.\n\n"
        f"{format_match_label(match, include_id=False)}\n"
        f"Итог: {match.score_home}:{match.score_away}\n\n"
        f"🎯 Точный счет: {', '.join(exact) if exact else 'никто. Коллективное мимо, но с достоинством.'}\n"
        f"🔵 Исход: {', '.join(outcome) if outcome else 'никто.'}\n"
        f"🔴 Мимо: {', '.join(miss) if miss else 'никто не пострадал.'}\n\n"
        "Если ваш прогноз не зашел — это не ошибка, это авторская трактовка футбола."
    )


def build_private_match_started_text(match: Match) -> str:
    return (
        "⚽ Матч начался!\n\n"
        f"{format_match_label(match, include_id=False)}\n\n"
        "Прогнозы раскрыты. Открой Матч-центр, чтобы посмотреть прогнозы участников своей лиги."
    )


def build_private_match_finished_text(match: Match) -> str:
    """Fallback for approved users who have not joined any active league yet."""
    return (
        "🏁 Матч окончен\n\n"
        f"{format_match_label(match, include_id=False)}\n"
        f"Итог: {match.score_home}:{match.score_away}\n\n"
        "Очки пересчитаны. Создай лигу или вступи по приглашению, чтобы получать лиговые итоги."
    )


def _prediction_total_points(prediction: Prediction, match: Match) -> int:
    """Return saved points, with a safe calculation fallback for old rows."""
    if prediction.points is not None:
        return int(prediction.points or 0)
    if match.score_home is None or match.score_away is None:
        return 0
    result = score_match_prediction(
        pred_home=prediction.pred_home,
        pred_away=prediction.pred_away,
        actual_home=match.score_home,
        actual_away=match.score_away,
        advancement_bet_enabled=prediction.advancement_bet_enabled,
        predicted_advancing_side=prediction.predicted_advancing_side,
        actual_winner_side=match.winner_side,
    )
    return int(result["total_points"] or 0)


def _league_rank_snapshots_for_match(db, league: League, match: Match) -> tuple[dict[int, int], dict[int, int], dict[int, int], int]:
    """Build current and pre-match rank snapshots for one league.

    Results are already written by the time notifications are sent. To describe
    movement in a personal notification we reconstruct the standings immediately
    before the match by subtracting the current match contribution for every
    eligible participant. This avoids storing another persistent leaderboard
    snapshot while keeping the message understandable.
    """
    from app.models import TournamentPrediction
    from app.services.leagues import league_scoring_start_at

    scoring_start = league_scoring_start_at(league)
    member_rows = (
        db.query(LeagueMember, User)
        .join(User, User.id == LeagueMember.user_id)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .all()
    )

    current_entries = []
    before_entries = []
    match_predictions = {
        prediction.user_id: prediction
        for prediction in (
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
    }

    for member, user in member_rows:
        predictions_query = (
            db.query(Prediction)
            .join(Match, Prediction.match_id == Match.id)
            .filter(
                Prediction.user_id == user.id,
                Match.tournament_code == TOURNAMENT_CODE,
            )
        )
        if scoring_start is not None:
            predictions_query = predictions_query.filter(Match.starts_at >= scoring_start)
        predictions = predictions_query.all()

        tournament_prediction = (
            db.query(TournamentPrediction)
            .filter(
                TournamentPrediction.user_id == user.id,
                TournamentPrediction.tournament_code == TOURNAMENT_CODE,
            )
            .first()
        )
        tournament_points = int(tournament_prediction.points or 0) if tournament_prediction else 0
        match_points = sum(_prediction_total_points(prediction, prediction.match) for prediction in predictions)
        exact_scores = sum(1 for prediction in predictions if int(prediction.score_points or 0) == 3)
        outcomes = sum(1 for prediction in predictions if int(prediction.score_points or 0) == 1)

        current_entries.append({
            "user_id": user.id,
            "points": match_points + tournament_points,
            "exact": exact_scores,
            "outcomes": outcomes,
        })

        prediction_for_match = match_predictions.get(user.id)
        contribution = _prediction_total_points(prediction_for_match, match) if prediction_for_match else 0
        score_points = int(prediction_for_match.score_points or 0) if prediction_for_match else 0
        before_entries.append({
            "user_id": user.id,
            "points": match_points + tournament_points - contribution,
            "exact": exact_scores - (1 if score_points == 3 else 0),
            "outcomes": outcomes - (1 if score_points == 1 else 0),
        })

    def _rank(entries):
        ordered = sorted(
            entries,
            key=lambda row: (row["points"], row["exact"], row["outcomes"]),
            reverse=True,
        )
        return {row["user_id"]: index for index, row in enumerate(ordered, start=1)}

    current_rank = _rank(current_entries)
    before_rank = _rank(before_entries)
    current_points = {entry["user_id"]: entry["points"] for entry in current_entries}
    return current_rank, before_rank, current_points, len(current_entries)


def _user_success_streak_for_league(db, user: User, league: League, match: Match) -> int:
    """Return current successful-prediction streak inside the league score window."""
    from app.services.leagues import league_scoring_start_at

    query = (
        db.query(Prediction)
        .join(Match, Prediction.match_id == Match.id)
        .filter(
            Prediction.user_id == user.id,
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
            Match.starts_at <= match.starts_at,
        )
        .order_by(Match.starts_at.desc())
    )
    scoring_start = league_scoring_start_at(league)
    if scoring_start is not None:
        query = query.filter(Match.starts_at >= scoring_start)

    streak = 0
    for prediction in query.all():
        if int(prediction.score_points or 0) > 0:
            streak += 1
        else:
            break
    return streak


def _plural_ru(value: int, one: str, few: str, many: str) -> str:
    """Return a Russian plural form for small notification fragments."""
    number = abs(int(value or 0))
    if 11 <= number % 100 <= 14:
        return many
    if number % 10 == 1:
        return one
    if number % 10 in {2, 3, 4}:
        return few
    return many


def _format_points(value: int) -> str:
    points = int(value or 0)
    return f"{points} {_plural_ru(points, 'очко', 'очка', 'очков')}"


def build_match_emotion_payload(
    db,
    user: User,
    match: Match,
    league: League,
    newly_unlocked: list[dict] | None = None,
) -> dict:
    """Build a reusable post-match recap for Telegram and the Mini App.

    The calculation intentionally reconstructs the standings immediately before
    kickoff from stored predictions. That keeps the position delta available
    for historical finished matches too, without a separate leaderboard table.
    """
    if not match.is_finished or match.score_home is None or match.score_away is None:
        raise ValueError("Эмоции доступны только после завершения матча")

    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == user.id, Prediction.match_id == match.id)
        .first()
    )

    current_rank, before_rank, current_points, participants_count = _league_rank_snapshots_for_match(db, league, match)
    rank_after = current_rank.get(user.id)
    rank_before = before_rank.get(user.id)
    rank_delta = (rank_before - rank_after) if rank_before and rank_after else 0
    league_points = int(current_points.get(user.id, 0) or 0)

    result_type = "no_prediction"
    result_title = "В этот раз без ставки"
    result_text = "Прогноза на матч не было — следующий свисток уже близко."
    prediction_score = None
    points = 0
    score_points = 0

    if prediction:
        prediction_score = f"{prediction.pred_home}:{prediction.pred_away}"
        points = _prediction_total_points(prediction, match)
        score_points = int(prediction.score_points or 0)

        if score_points == 3:
            result_type = "exact"
            result_title = "Точный счет!"
            result_text = f"Твой прогноз {prediction_score} попал в цель. +{_format_points(points)}."
        elif score_points == 1:
            result_type = "outcome"
            result_title = "Исход угадан"
            result_text = f"Прогноз {prediction_score} принес +{_format_points(points)}."
        elif points > 0:
            result_type = "bonus"
            result_title = "Футбольный бонус"
            result_text = f"Прогноз {prediction_score} дал +{_format_points(points)} за дополнительный исход."
        else:
            result_type = "miss"
            result_title = "Футбол выбрал свой сценарий"
            result_text = f"Твой прогноз {prediction_score} не принес очков. Реванш уже впереди."

    streak = _user_success_streak_for_league(db, user, league, match)
    achievements: list[dict] = list(newly_unlocked or [])
    if result_type == "exact":
        achievements.append({
            "code": "exact_hit",
            "icon": "🎯",
            "title": "Снайпер матча",
            "description": "Точный счет угадан.",
        })
    if streak >= 3:
        achievements.append({
            "code": "hot_streak",
            "icon": "🔥",
            "title": "Серия огня",
            "description": f"{streak} {_plural_ru(streak, 'удачный прогноз', 'удачных прогноза', 'удачных прогнозов')} подряд.",
        })
    if rank_delta >= 2:
        achievements.append({
            "code": "climber",
            "icon": "📈",
            "title": "Рывок вверх",
            "description": f"Подъем на {rank_delta} {_plural_ru(rank_delta, 'позицию', 'позиции', 'позиций')}.",
        })
    if rank_after == 1 and rank_before != 1:
        achievements.append({
            "code": "leader",
            "icon": "👑",
            "title": "Новый лидер",
            "description": "Ты вышел на первое место в лиге.",
        })

    return {
        "result_type": result_type,
        "title": result_title,
        "text": result_text,
        "prediction_score": prediction_score,
        "actual_score": f"{match.score_home}:{match.score_away}",
        "points": int(points or 0),
        "score_points": score_points,
        "rank_before": rank_before,
        "rank_after": rank_after,
        "rank_delta": int(rank_delta or 0),
        "league_points": league_points,
        "participants_count": participants_count,
        "streak": int(streak or 0),
        "achievements": achievements,
    }


def build_personal_match_emotion_text(db, user: User, match: Match, league: League) -> str:
    """Create a friendly, personal post-match summary for a league."""
    recap = build_match_emotion_payload(db, user, match, league)
    lines = [f"✨ Твой итог · {recap['title']}", recap["text"]]

    if recap["rank_after"]:
        if recap["rank_delta"] > 0:
            lines.append(
                f"📈 В лиге ты поднялся с #{recap['rank_before']} на #{recap['rank_after']} "
                f"из {recap['participants_count']}."
            )
        elif recap["rank_delta"] < 0:
            lines.append(
                f"↘️ Сейчас ты #{recap['rank_after']} из {recap['participants_count']}. "
                "Впереди есть повод для камбэка."
            )
        else:
            lines.append(
                f"🏆 В лиге сейчас #{recap['rank_after']} из {recap['participants_count']} · "
                f"{_format_points(recap['league_points'])}."
            )

    if recap["streak"] >= 2:
        lines.append(
            f"🔥 Серия: {recap['streak']} "
            f"{_plural_ru(recap['streak'], 'удачный прогноз', 'удачных прогноза', 'удачных прогнозов')} подряд."
        )

    if recap["achievements"]:
        lines.append("\n" + " · ".join(
            f"{item['icon']} {item['title']}" for item in recap["achievements"]
        ))

    return "\n".join(lines)

async def build_private_match_finished_league_text(db, user: User, match: Match, league: League) -> str:
    """Build a fact-first personal recap with optional OpenAI football commentary.

    The deterministic lines remain useful even when the API is unavailable. The
    model receives only the small calculated context below and never calculates
    scores, rankings or achievements itself.
    """
    newly_unlocked = sync_new_achievements(db, user, league)
    recap = build_match_emotion_payload(db, user, match, league, newly_unlocked=newly_unlocked)
    tone = normalize_humor_mode(
        getattr(user, "personal_humor_mode", None),
        default=normalize_humor_mode(getattr(league, "humor_mode", None)),
    )
    ai_context = {
        "league_name": league.name,
        "user_name": user.display_name,
        "match": f"{match.home_team} — {match.away_team}",
        "actual_score": recap["actual_score"],
        "prediction": recap.get("prediction_score"),
        "result_type": recap["result_type"],
        "points_for_match": recap["points"],
        "rank_before": recap.get("rank_before"),
        "rank_after": recap.get("rank_after"),
        "rank_delta": recap.get("rank_delta"),
        "success_streak": recap.get("streak"),
        "new_achievements": [item.get("title") for item in newly_unlocked],
    }
    try:
        from app.services.openai_gamification import generate_match_commentary
        commentary = await asyncio.to_thread(generate_match_commentary, ai_context, tone)
    except Exception as error:
        print(f"Failed to build AI match commentary: {error}")
        commentary = "Итог рассчитан по правилам лиги. Следующий матч уже ждёт новый сценарий."

    lines = [
        f"🏁 Лига «{league.name}» · матч окончен",
        "",
        f"{format_match_label(match, include_id=False)}",
        f"Итог: {recap['actual_score']}",
    ]
    if recap.get("prediction_score"):
        lines.append(f"Твой прогноз: {recap['prediction_score']} · +{_format_points(recap['points'])}")
    else:
        lines.append("Твоего прогноза на матч не было · +0 очков")

    if recap.get("rank_after"):
        if recap.get("rank_delta", 0) > 0:
            lines.append(f"📈 Место: #{recap['rank_before']} → #{recap['rank_after']} из {recap['participants_count']}")
        elif recap.get("rank_delta", 0) < 0:
            lines.append(f"↘️ Место: #{recap['rank_before']} → #{recap['rank_after']} из {recap['participants_count']}")
        else:
            lines.append(f"🏆 Сейчас #{recap['rank_after']} из {recap['participants_count']} · {_format_points(recap['league_points'])}")

    lines.extend(["", commentary])
    if newly_unlocked:
        lines.extend([
            "",
            "✨ Новое достижение: " + " · ".join(
                f"{item.get('icon', '🏅')} {item.get('title')} — {item.get('level_name')}"
                for item in newly_unlocked
            ),
        ])
    return "\n".join(lines)


def _pregame_score_outcome(prediction: Prediction) -> str:
    if int(prediction.pred_home) > int(prediction.pred_away):
        return "победа хозяев"
    if int(prediction.pred_home) < int(prediction.pred_away):
        return "победа гостей"
    return "ничья"


def _pregame_recent_form_for_user(db, user: User, league: League, before_at) -> dict:
    """Return only persisted, completed-prediction facts for the slot preview."""
    from app.services.leagues import league_scoring_start_at

    query = (
        db.query(Prediction)
        .join(Match, Prediction.match_id == Match.id)
        .join(
            LeagueMember,
            (LeagueMember.user_id == Prediction.user_id)
            & (LeagueMember.league_id == league.id)
            & (LeagueMember.status == "active")
            & (LeagueMember.joined_at <= Match.starts_at),
        )
        .filter(
            Prediction.user_id == user.id,
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at < before_at,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
    )
    scoring_start = league_scoring_start_at(league)
    if scoring_start is not None:
        query = query.filter(Match.starts_at >= scoring_start)

    predictions = query.order_by(Match.starts_at.desc(), Match.id.desc()).limit(3).all()
    entries = []
    for prediction in reversed(predictions):
        score_points = int(prediction.score_points or 0)
        icon = "🎯" if score_points == 3 else ("🔵" if score_points == 1 else "◌")
        entries.append({
            "icon": icon,
            "points": int(prediction.points or 0),
            "label": f"{prediction.match.home_team} — {prediction.match.away_team}",
        })

    return {
        "name": user.display_name,
        "recent_results": entries,
        "recent_points": sum(item["points"] for item in entries),
    }


def build_league_pregame_analysis_context(db, league: League, matches: list[Match]) -> dict:
    """Collect fact-only data for one started match slot in a league chat.

    The result is intentionally ready for both deterministic formatting and
    OpenAI wording. The model sees no hidden calculations and never decides the
    standings or outcomes itself.
    """
    if not matches:
        raise ValueError("Нужен хотя бы один матч для предматчевого разбора")

    ordered_matches = sorted(matches, key=lambda item: (item.starts_at, item.id))
    slot_start = ordered_matches[0].starts_at
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=timezone.utc)

    member_rows = (
        db.query(LeagueMember, User)
        .join(User, User.id == LeagueMember.user_id)
        .filter(
            LeagueMember.league_id == league.id,
            LeagueMember.status == "active",
            LeagueMember.joined_at <= slot_start,
            User.access_status == "approved",
        )
        .order_by(User.display_name.asc())
        .all()
    )
    members = [user for _member, user in member_rows if not getattr(user, "is_bot", False)]
    members_by_id = {user.id: user for user in members}

    from app.services.misc import build_table_rows

    table_rows = [row for row in build_table_rows(db, league_id=league.id) if int(row.get("user_id") or 0) in members_by_id]
    standings = [
        {
            "rank": index,
            "user_id": int(row.get("user_id") or 0),
            "name": row.get("name") or "Участник",
            "points": int(row.get("points") or 0),
            "exact_scores": int(row.get("exact_scores") or 0),
            "outcomes": int(row.get("outcomes") or 0),
        }
        for index, row in enumerate(table_rows, start=1)
    ]
    leader_points = int(standings[0]["points"] or 0) if standings else 0
    for row in standings:
        row["gap_to_leader"] = max(0, leader_points - int(row["points"] or 0))

    match_contexts = []
    unique_calls: list[dict] = []
    prediction_signatures: dict[int, list[str]] = {user.id: [] for user in members}

    for match in ordered_matches:
        # The Father forecast is revealed together with participants' locked
        # predictions. It is persisted before formatting so the score remains
        # immutable on subsequent reads and visible in the Mini App as well.
        father_prediction = _ensure_father_match_prediction_for_notifications(db, match)
        prediction_rows = _get_match_predictions_with_users(db, match, league=league)
        predictions = []
        score_groups: dict[str, list[str]] = {}
        outcome_counts = {"победа хозяев": 0, "ничья": 0, "победа гостей": 0}
        predicted_user_ids: set[int] = set()

        for prediction, user in prediction_rows:
            if user.id not in members_by_id:
                continue
            score = f"{prediction.pred_home}:{prediction.pred_away}"
            outcome = _pregame_score_outcome(prediction)
            predicted_user_ids.add(user.id)
            prediction_signatures.setdefault(user.id, []).append(f"{match.id}:{score}")
            predictions.append({
                "user_id": user.id,
                "name": user.display_name,
                "score": score,
                "outcome": outcome,
                "advancement": _advancement_pick_text(prediction, match) if is_playoff_match(match) else None,
            })
            score_groups.setdefault(score, []).append(user.display_name)
            outcome_counts[outcome] = int(outcome_counts.get(outcome, 0)) + 1

        for score, names in score_groups.items():
            if len(names) == 1:
                unique_calls.append({
                    "match": f"{match.home_team} — {match.away_team}",
                    "name": names[0],
                    "score": score,
                })

        missing_names = [user.display_name for user in members if user.id not in predicted_user_ids]
        consensus_score = None
        if len(members) >= 2 and len(predictions) == len(members) and len(score_groups) == 1:
            consensus_score = next(iter(score_groups.keys()))

        match_contexts.append({
            "match_id": match.id,
            "label": f"{match.home_team} — {match.away_team}",
            "is_playoff": is_playoff_match(match),
            "predictions": predictions,
            "score_groups": [
                {"score": score, "count": len(names), "names": names}
                for score, names in sorted(score_groups.items(), key=lambda item: (-len(item[1]), item[0]))
            ],
            "outcome_distribution": outcome_counts,
            "missing_participants": missing_names,
            "consensus_score": consensus_score,
            "father_prediction": {
                "score": f"{father_prediction.pred_home}:{father_prediction.pred_away}",
                "outcome": father_prediction.outcome,
                "source": father_prediction.source,
            },
        })

    close_duels = []
    for upper, lower in zip(standings, standings[1:]):
        upper_id = int(upper["user_id"])
        lower_id = int(lower["user_id"])
        upper_calls = prediction_signatures.get(upper_id) or []
        lower_calls = prediction_signatures.get(lower_id) or []
        if not upper_calls or not lower_calls or upper_calls == lower_calls:
            continue
        gap = max(0, int(upper["points"] or 0) - int(lower["points"] or 0))
        if gap <= 4:
            close_duels.append({
                "higher_name": upper["name"],
                "higher_rank": upper["rank"],
                "lower_name": lower["name"],
                "lower_rank": lower["rank"],
                "points_gap": gap,
            })

    recent_form = [
        _pregame_recent_form_for_user(db, user, league, slot_start)
        for user in members
    ]

    return {
        "league_name": league.name,
        "slot_started_at": slot_start.isoformat(),
        "participants_count": len(members),
        "matches": match_contexts,
        "standings": standings,
        "recent_form": recent_form,
        "unique_calls": unique_calls[:8],
        "close_duels": close_duels[:5],
        # A stable slot signature gives the language model a non-visible
        # variation key, so different kick-off windows do not drift into one
        # repeated stock phrase when their facts look similar.
        "style_seed": f"{league.id}:{slot_start.isoformat()}:{','.join(str(match.id) for match in ordered_matches)}",
    }


def _pregame_form_text(item: dict) -> str:
    entries = item.get("recent_results") or []
    if not entries:
        return "без завершённых прогнозов"
    icons = " ".join(str(entry.get("icon") or "◌") for entry in entries)
    return f"{icons} · {int(item.get('recent_points') or 0)} очк."


def _trim_telegram_text(text: str, limit: int = 3900) -> str:
    """Stay below Telegram's message limit without breaking an in-flight send."""
    if len(text) <= limit:
        return text
    return text[: limit - 58].rstrip() + "\n\n…Полная картина прогнозов доступна в Матч-центре."


async def build_league_pregame_analysis_text(db, league: League, matches: list[Match]) -> str:
    context = build_league_pregame_analysis_context(db, league, matches)
    tone = normalize_humor_mode(getattr(league, "humor_mode", None))
    try:
        from app.services.openai_gamification import generate_pregame_league_commentary

        commentary = await asyncio.to_thread(generate_pregame_league_commentary, context, tone)
    except Exception as error:
        print(f"Failed to build AI pregame analysis for league {league.id}: {error}")
        commentary = "Прогнозы раскрыты. Футболу остаётся только проверить, кто здесь правда что-то понимал."

    match_labels = [item["label"] for item in context["matches"]]
    header = "🔥 Прогнозы вскрыты" if len(match_labels) == 1 else "🔥 Прогнозы вскрыты · игровой слот"
    lines = [
        f"{header} · лига «{league.name}»",
        "",
        "⚽ " + "\n⚽ ".join(match_labels),
        "",
    ]

    for match_data in context["matches"]:
        lines.append(f"👥 {match_data['label']}")
        father_prediction = match_data.get("father_prediction") or {}
        father_score = father_prediction.get("score")
        if father_score:
            lines.append(f"🤖 Отец прогнозов: {father_score}")
        predictions = match_data.get("predictions") or []
        if predictions:
            for prediction in predictions:
                line = f"— {prediction['name']}: {prediction['score']}"
                if match_data.get("is_playoff"):
                    line += f" · {prediction.get('advancement') or 'проход: не указан'}"
                lines.append(line)
        else:
            lines.append("— прогнозов нет. Лига выбрала путь молчаливого наблюдателя.")

        distribution = match_data.get("outcome_distribution") or {}
        lines.append(
            "Исходы: "
            f"хозяева — {int(distribution.get('победа хозяев') or 0)}, "
            f"ничья — {int(distribution.get('ничья') or 0)}, "
            f"гости — {int(distribution.get('победа гостей') or 0)}"
        )
        if match_data.get("consensus_score"):
            lines.append(f"🤝 Единомышленники: все выбрали {match_data['consensus_score']}.")
        missing = match_data.get("missing_participants") or []
        if missing:
            lines.append("⌛ Без прогноза: " + ", ".join(missing))
        lines.append("")

    standings = context.get("standings") or []
    lines.extend(["📊 Таблица перед стартом:"])
    if standings:
        for row in standings:
            lines.append(f"{row['rank']}. {row['name']} — {row['points']} очк.")
    else:
        lines.append("Таблица пока ждёт первого участника.")

    form = context.get("recent_form") or []
    if form:
        lines.extend(["", "🔥 Форма · последние 3 завершённых прогноза:"])
        for item in form:
            lines.append(f"— {item['name']}: {_pregame_form_text(item)}")

    duels = context.get("close_duels") or []
    if duels:
        lines.extend(["", "⚔️ Интрига в таблице:"])
        for duel in duels[:3]:
            gap = int(duel.get("points_gap") or 0)
            lines.append(
                f"#{duel['higher_rank']} {duel['higher_name']} и #{duel['lower_rank']} {duel['lower_name']} "
                f"разделяет {gap} очк.; прогнозы в этом слоте разные."
            )

    lines.extend(["", "🧠 Разбор Отца:", commentary])
    return _trim_telegram_text("\n".join(lines))


def _pregame_slot_key(matches: list[Match]) -> str:
    """Stable grouping for matches that start at the exact same kickoff time."""
    first = min(matches, key=lambda item: (item.starts_at, item.id))
    starts_at = first.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    match_ids = "-".join(str(item.id) for item in sorted(matches, key=lambda item: item.id))
    return f"{starts_at.astimezone(timezone.utc).strftime('%Y%m%d%H%M')}-{match_ids}"


async def _send_league_pregame_analyses(db, now):
    """Deliver exactly one detailed forecast reveal per league and kickoff slot.

    A startup grace window is deliberate: deploying a release just after kickoff
    still delivers the new analysis instead of silently missing the slot.
    """
    if os.getenv("PREGAME_ANALYSIS_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return

    try:
        lookback_minutes = int(os.getenv("PREGAME_ANALYSIS_LOOKBACK_MINUTES", "30") or "30")
    except ValueError:
        lookback_minutes = 30
    lookback_minutes = max(2, min(120, lookback_minutes))
    window_start = now - timedelta(minutes=lookback_minutes)

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at <= now,
            Match.starts_at >= window_start,
            Match.is_finished == False,
        )
        .order_by(Match.starts_at.asc(), Match.id.asc())
        .all()
    )
    if not matches:
        return

    slots: dict[str, list[Match]] = {}
    for match in matches:
        key_time = match.starts_at
        if key_time.tzinfo is None:
            key_time = key_time.replace(tzinfo=timezone.utc)
        key = key_time.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
        slots.setdefault(key, []).append(match)

    from app.services.leagues import (
        get_active_league_chat_targets,
        get_default_league,
        get_unique_league_chat_destinations,
        normalize_telegram_chat_id,
    )

    destinations = get_unique_league_chat_destinations(db)
    configured_leagues = get_active_league_chat_targets(db)
    default_league = get_default_league(db)

    for slot_matches in slots.values():
        slot_key = _pregame_slot_key(slot_matches)

        for league, chat_id in destinations:
            # Older releases used one event key for GROUP_CHAT_ID and another one
            # for the same league chat. Respect either legacy key when a release
            # is deployed shortly after kickoff, so the chat is not replayed.
            compatible_league_ids = {
                item.id
                for item in configured_leagues
                if normalize_telegram_chat_id(getattr(item, "chat_id", None)) == chat_id
            }
            if default_league and normalize_telegram_chat_id(GROUP_CHAT_ID_RAW) == chat_id:
                compatible_league_ids.add(default_league.id)
            compatible_league_ids.add(league.id)
            compatible_keys = {
                f"pregame_analysis:{league_id}:{slot_key}:{chat_id}"
                for league_id in compatible_league_ids
            }
            if any(_app_event_sent(db, key) for key in compatible_keys):
                continue

            event_key = f"pregame_analysis:{league.id}:{slot_key}:{chat_id}"
            try:
                text = await build_league_pregame_analysis_text(db, league, slot_matches)
                await bot.send_message(chat_id=chat_id, text=text)
                _mark_app_event_sent(db, event_key)
                print(f"Pregame league analysis sent: league={league.id}, slot={slot_key}, chat={chat_id}")
            except Exception as error:
                print(f"Failed to send pregame league analysis for league {league.id}, slot {slot_key}: {error}")


async def _send_match_started_notifications(db, now, window_seconds: int):
    """Send private kickoff notices and one AI league analysis per started slot."""
    window_start = now - timedelta(seconds=window_seconds + 60)
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at <= now,
            Match.starts_at >= window_start,
        )
        .order_by(Match.starts_at.asc())
        .all()
    )

    if matches:
        from app.services.notifications import notify_private_users

        for match in matches:
            private_key = f"private_match_started:{match.id}"
            if _app_event_sent(db, private_key):
                continue
            text = build_private_match_started_text(match)
            try:
                await notify_private_users(
                    db,
                    notification_key="match_started",
                    title="⚽ Матч начался",
                    text=text,
                    url="/app",
                )
                _mark_app_event_sent(db, private_key)
            except Exception as error:
                print(f"Failed to send private match-start notifications: {error}")

    # Detailed league-chat analyses run in their own independent background loop.


async def pregame_analysis_loop():
    """Continuously reveal group-slot analyses, independently from personal reminders.

    This makes the feature work immediately after Railway deployment even when
    private reminder messages are deliberately disabled. Event keys make the
    loop idempotent across restarts.
    """
    if os.getenv("PREGAME_ANALYSIS_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        print("Pregame analysis loop is disabled")
        return

    try:
        interval_seconds = int(os.getenv("PREGAME_ANALYSIS_CHECK_INTERVAL_SECONDS", "30") or "30")
    except ValueError:
        interval_seconds = 30
    interval_seconds = max(20, min(300, interval_seconds))

    print(f"Pregame analysis loop started. Interval: {interval_seconds} seconds.")
    while True:
        db = SessionLocal()
        try:
            await _send_league_pregame_analyses(db, datetime.now(timezone.utc))
        except Exception as error:
            print(f"Pregame analysis loop error: {error}")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)


async def _send_match_finished_notifications(db):
    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.is_finished == True,
            Match.score_home.isnot(None),
            Match.score_away.isnot(None),
        )
        .order_by(Match.starts_at.desc())
        .limit(20)
        .all()
    )

    if not matches:
        return

    from app.services.leagues import (
        get_unique_league_chat_destinations,
        get_user_active_leagues_for_match,
        normalize_telegram_chat_id,
    )
    from app.services.notifications import notify_league_chat, notify_private_user

    league_chat_destinations = get_unique_league_chat_destinations(db)
    approved_users = db.query(User).filter(User.access_status == "approved").all()

    for match in matches:
        # Do not replay up to 20 historical result messages after this release is
        # deployed. Earlier builds stored one legacy event key per match; fresh
        # matches use the recipient+league keys below.
        legacy_private_key = f"private_match_finished:{match.id}"
        if not _app_event_sent(db, legacy_private_key):
            # A recipient can belong to several leagues. Send the full league result
            # separately for each one, so the participant list and personal position
            # always match the league that the message is about.
            for user in approved_users:
                leagues = get_user_active_leagues_for_match(db, user, match)
                if not leagues:
                    private_key = f"private_match_finished:{match.id}:user:{user.id}:no_league"
                    if not _app_event_sent(db, private_key):
                        try:
                            await notify_private_user(
                                db,
                                user=user,
                                notification_key="match_finished",
                                title="🏁 Матч окончен",
                                text=build_private_match_finished_text(match),
                                url="/app",
                            )
                        finally:
                            _mark_app_event_sent(db, private_key)
                    continue

                for league in leagues:
                    private_key = f"private_match_finished:{match.id}:user:{user.id}:league:{league.id}"
                    if _app_event_sent(db, private_key):
                        continue
                    try:
                        text = await build_private_match_finished_league_text(db, user, match, league)
                        await notify_private_user(
                            db,
                            user=user,
                            notification_key="match_finished",
                            title=f"🏁 Итоги · {league.name}",
                            text=text,
                            url="/app",
                        )
                    except Exception as error:
                        print(f"Failed to send private match-finish notification to {user.telegram_id} for league {league.id}: {error}")
                    finally:
                        _mark_app_event_sent(db, private_key)
        for league, chat_id in league_chat_destinations:
            generic_key = f"league_chat_match_finished:{chat_id}:{match.id}"
            legacy_keys = {
                generic_key,
                f"league_match_finished:{league.id}:{match.id}",
            }
            if normalize_telegram_chat_id(GROUP_CHAT_ID_RAW) == chat_id:
                legacy_keys.add(f"group_match_finished:{match.id}")
            if any(_app_event_sent(db, key) for key in legacy_keys):
                continue

            text = build_match_finished_group_notification_text(db, match, league=league)
            if await notify_league_chat(league, text):
                _mark_app_event_sent(db, generic_key)

async def send_match_reminders_once():
    """Handle asynchronous bot workflow for send_match_reminders_once."""
    from app.jobs.reminders import (
        get_reminder_check_interval_seconds,
        get_reminder_offsets_minutes,
        mark_reminder_sent,
        reminder_was_sent,
        reminders_enabled,
    )
    from app.services.predictions import user_has_prediction
    if not reminders_enabled():
        return

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        offsets = get_reminder_offsets_minutes()
        check_interval_seconds = get_reminder_check_interval_seconds()

        await _send_match_started_notifications(db, now, check_interval_seconds)
        await _send_match_finished_notifications(db)

        confidence_offset_minutes = int(os.getenv("CONFIDENCE_REMINDER_OFFSET_MINUTES", "60") or "60")
        max_offset = max(offsets + [confidence_offset_minutes])

        matches = db.query(Match).filter(
            Match.is_finished == False,
            Match.starts_at > now,
            Match.starts_at <= now + timedelta(minutes=max_offset + 10),
        ).order_by(Match.starts_at).all()

        if not matches:
            return

        users = db.query(User).filter(User.access_status == "approved").all()

        for match in matches:
            match_start = match.starts_at

            if match_start.tzinfo is None:
                match_start = match_start.replace(tzinfo=timezone.utc)

            # Personal confidence-check reminder: always sent 1 hour before kickoff,
            # regardless of whether a prediction already exists.
            confidence_due_at = match_start - timedelta(minutes=confidence_offset_minutes)
            confidence_window_end = confidence_due_at + timedelta(seconds=check_interval_seconds + 30)
            if confidence_due_at <= now <= confidence_window_end:
                from app.services.notifications import notify_private_user

                for user in users:
                    reminder_type = "match_confidence_check"
                    reminder_key = f"{confidence_offset_minutes}m"
                    if reminder_was_sent(
                        db=db,
                        user=user,
                        match=match,
                        reminder_type=reminder_type,
                        reminder_key=reminder_key,
                    ):
                        continue

                    prediction = (
                        db.query(Prediction)
                        .filter(Prediction.user_id == user.id, Prediction.match_id == match.id)
                        .first()
                    )

                    if prediction:
                        text = (
                            "⏰ До матча остался 1 час\n\n"
                            f"{format_match_label(match, include_id=False)}\n"
                            f"Старт: {format_datetime(match.starts_at)}\n\n"
                            f"Твой прогноз: {prediction.pred_home}:{prediction.pred_away}\n\n"
                            "Время еще есть. Уверен в счете или рискнешь что-то поменять?"
                        )
                        title = "⏰ Проверь прогноз"
                    else:
                        text = (
                            "⏰ До матча остался 1 час\n\n"
                            f"{format_match_label(match, include_id=False)}\n"
                            f"Старт: {format_datetime(match.starts_at)}\n\n"
                            "Прогноза пока нет. Еще успеешь выбрать счет до стартового свистка."
                        )
                        title = "⏰ Успей сделать прогноз"

                    try:
                        await notify_private_user(
                            db,
                            user=user,
                            notification_key="match_reminders",
                            title=title,
                            text=text,
                            url="/app",
                            reply_markup=build_prediction_reminder_keyboard(match, bool(prediction)),
                        )
                        mark_reminder_sent(
                            db=db,
                            user=user,
                            match=match,
                            reminder_type=reminder_type,
                            reminder_key=reminder_key,
                        )
                    except Exception as error:
                        print(f"Failed to send confidence reminder to {user.telegram_id}: {error}")

            for offset_minutes in offsets:
                # The one-hour confidence reminder already handles both users with and without a prediction.
                if offset_minutes == confidence_offset_minutes:
                    continue

                reminder_due_at = match_start - timedelta(minutes=offset_minutes)

                window_end = reminder_due_at + timedelta(
                    seconds=check_interval_seconds + 30
                )

                if not (reminder_due_at <= now <= window_end):
                    continue

                reminder_type = "match_missing_prediction"
                reminder_key = f"{offset_minutes}m"

                for user in users:
                    if user_has_prediction(db, user, match):
                        continue

                    if reminder_was_sent(
                            db=db,
                            user=user,
                            match=match,
                            reminder_type=reminder_type,
                            reminder_key=reminder_key,
                    ):
                        continue

                    text = (
                        f"⏰ Напоминание от Отца прогнозов\n\n"
                        f"До матча осталось: {format_reminder_offset(offset_minutes)}\n\n"
                        f"{format_match_label(match, include_id=False)}\n"
                        f"Старт: {format_datetime(match.starts_at)}\n\n"
                        f"У тебя еще нет прогноза на этот матч."
                    )

                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=text,
                            reply_markup=build_matches_keyboard([match]),
                        )

                        try:
                            from app.services.web_push import notify_web_push_subscribers_for_user_if_enabled

                            notify_web_push_subscribers_for_user_if_enabled(
                                db,
                                user_id=user.id,
                                notification_key="match_reminders",
                                title="⏰ Напоминание о прогнозе",
                                body=text[:220],
                                url="/app",
                            )
                        except Exception as push_error:
                            print(
                                f"Failed to send reminder web push to user "
                                f"{user.telegram_id}: {push_error}"
                            )

                        mark_reminder_sent(
                            db=db,
                            user=user,
                            match=match,
                            reminder_type=reminder_type,
                            reminder_key=reminder_key,
                        )

                    except Exception as error:
                        print(
                            f"Failed to send reminder to user "
                            f"{user.telegram_id}: {error}"
                        )

    finally:
        db.close()

