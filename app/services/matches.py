"""Real implementation extracted from the former bot_runtime monolith."""


import re

from app.constants.categories import PLAYOFF_STAGES
from app.formatters.matches import format_datetime, format_match_label, format_match_result, format_user_match_prediction
from app.formatters.misc import format_reminder_offset
from app.keyboards.matches import build_matches_keyboard
from app.models import AppSetting, FatherMatchPrediction
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


def _get_match_predictions_with_users(db, match: Match):
    return (
        db.query(Prediction, User)
        .join(User, User.id == Prediction.user_id)
        .filter(Prediction.match_id == match.id)
        .order_by(User.display_name.asc())
        .all()
    )


def _format_participant_prediction_lines(db, match: Match, with_points: bool = False) -> list[str]:
    rows = _get_match_predictions_with_users(db, match)

    if not rows:
        return ["— прогнозов участников нет. Видимо, все оставили аналитику в черновиках."]

    lines = []
    for prediction, user in rows:
        text = f"— {user.display_name}: {prediction.pred_home}:{prediction.pred_away}"

        if is_playoff_match(match) and prediction.advancement_bet_enabled:
            if prediction.predicted_advancing_side == "home":
                text += f" · проход {match.home_team}"
            elif prediction.predicted_advancing_side == "away":
                text += f" · проход {match.away_team}"

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


def build_match_start_group_notification_text(db, match: Match) -> str:
    participant_lines = _format_participant_prediction_lines(db, match, with_points=False)
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


def build_daily_match_summary_text(db, now_local=None) -> str:
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
            predictions = _get_match_predictions_with_users(db, match)
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


async def _send_group_match_started_notifications(db, now, window_seconds: int):
    if not GROUP_CHAT_ID_RAW:
        return

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

    for match in matches:
        key = f"group_match_started:{match.id}"
        if _app_event_sent(db, key):
            continue

        text = build_match_start_group_notification_text(db, match)

        try:
            await bot.send_message(chat_id=int(GROUP_CHAT_ID_RAW), text=text)
            try:
                from app.services.web_push import notify_active_web_push_subscribers_for_notification

                notify_active_web_push_subscribers_for_notification(
                    db,
                    notification_key="match_started",
                    title="⚽ Матч начался",
                    body=text[:220],
                    url="/app",
                )
            except Exception as push_error:
                print(f"Failed to send match-start web push notifications: {push_error}")
            _mark_app_event_sent(db, key)
        except Exception as error:
            print(f"Failed to send group match-start notification: {error}")


async def _send_group_match_finished_notifications(db):
    if not GROUP_CHAT_ID_RAW:
        return

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

    for match in matches:
        key = f"group_match_finished:{match.id}"
        if _app_event_sent(db, key):
            continue

        predictions = db.query(Prediction, User).join(User, User.id == Prediction.user_id).filter(Prediction.match_id == match.id).all()
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

        text = (
            "🏁 Матч окончен. Отец достает красную ручку.\n\n"
            f"{format_match_label(match, include_id=False)}\n"
            f"Итог: {match.score_home}:{match.score_away}\n\n"
            f"🎯 Точный счет: {', '.join(exact) if exact else 'никто. Коллективное мимо, но с достоинством.'}\n"
            f"🔵 Исход: {', '.join(outcome) if outcome else 'никто.'}\n"
            f"🔴 Мимо: {', '.join(miss) if miss else 'никто не пострадал.'}\n\n"
            "Если ваш прогноз не зашел — это не ошибка, это авторская трактовка футбола."
        )

        try:
            await bot.send_message(chat_id=int(GROUP_CHAT_ID_RAW), text=text)
            try:
                from app.services.web_push import notify_active_web_push_subscribers_for_notification

                notify_active_web_push_subscribers_for_notification(
                    db,
                    notification_key="match_finished",
                    title="🏁 Матч окончен",
                    body=text[:220],
                    url="/app",
                )
            except Exception as push_error:
                print(f"Failed to send match-finish web push notifications: {push_error}")
            _mark_app_event_sent(db, key)
        except Exception as error:
            print(f"Failed to send group match-finish notification: {error}")

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

        await _send_group_match_started_notifications(db, now, check_interval_seconds)
        await _send_group_match_finished_notifications(db)

        if not offsets:
            return

        max_offset = max(offsets)

        matches = db.query(Match).filter(
            Match.is_finished == False,
            Match.starts_at > now,
            Match.starts_at <= now + timedelta(minutes=max_offset + 10),
        ).order_by(Match.starts_at).all()

        if not matches:
            return

        users = db.query(User).all()

        for match in matches:
            match_start = match.starts_at

            if match_start.tzinfo is None:
                match_start = match_start.replace(tzinfo=timezone.utc)

            for offset_minutes in offsets:
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

