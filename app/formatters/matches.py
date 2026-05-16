"""Real implementation extracted from the former bot_runtime monolith."""


from app.formatters.misc import format_team_with_flag
from app.formatters.predictions import format_advancement_prediction
from app.runtime import (
    APP_TIMEZONE,
    MATCHDAY_TIMEZONE,
    MATCHDAY_TIMEZONE_NAME,
    Match,
    Prediction,
    get_team_name_ru,
    timezone,
)

def format_match(match: Match):
    """Provide bot helper logic for format_match."""
    from app.services.matches import get_default_match_round

    start_text = format_datetime(match.starts_at)

    round_text = match.match_round or get_default_match_round(match.stage)

    group_text = ""
    if match.group_code:
        group_text = f"\nГруппа: {match.group_code}"

    return (
        f"#{match.id} {match.home_team} — {match.away_team}\n"
        f"Стадия: {match.stage}\n"
        f"Тур/стадия: {round_text}"
        f"{group_text}\n"
        f"Старт: {start_text}"
    )


def format_match_short_for_group(match: Match) -> str:
    """Provide bot helper logic for format_match_short_for_group."""
    return format_match_label(match, include_id=True)


def format_datetime(dt):
    """Provide bot helper logic for format_datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(APP_TIMEZONE)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def format_match(match: Match):
    """Provide bot helper logic for format_match."""
    start_text = format_datetime(match.starts_at)

    group_text = ""
    if match.group_code:
        group_text = f"\nГруппа: {match.group_code}"

    venue_text = ""
    if match.venue or match.city:
        venue_parts = [part for part in [match.venue, match.city] if part]
        venue_text = f"\nСтадион: {', '.join(venue_parts)}"

    return (
        f"{format_match_label(match, include_id=True)}\n"
        f"Стадия: {match.stage}"
        f"{group_text}\n"
        f"Старт: {start_text}"
        f"{venue_text}"
    )


def format_ranking_fact(team_name: str, ranking: dict | None) -> str:
    """Provide bot helper logic for format_ranking_fact."""
    if not ranking:
        return f"{team_name}: рейтинг не найден"

    rank = ranking.get("rank")
    total_points = ranking.get("total_points")

    if total_points is not None:
        return f"{team_name}: #{rank}, {total_points} очк."

    return f"{team_name}: #{rank}"


def format_short_matches_fact(team_name: str, rows: list[dict]) -> str:
    """Provide bot helper logic for format_short_matches_fact."""
    if not rows:
        return f"{team_name}: нет данных"

    lines = [f"{team_name}:"]

    for row in rows[-3:]:
        lines.append(
            f"— {row.get('date')}: {row.get('match')} {row.get('score')}"
        )

    return "\n".join(lines)


def format_h2h_fact(rows: list[dict]) -> str:
    """Provide bot helper logic for format_h2h_fact."""
    if not rows:
        return "Личных встреч в данных не найдено."

    lines = []

    for row in rows[-5:]:
        lines.append(
            f"— {row.get('date')}: {row.get('match')} {row.get('score')}"
        )

    return "\n".join(lines)


def format_match_label(match: Match, include_id: bool = False) -> str:
    """Provide bot helper logic for format_match_label."""
    from app.services.matches import get_default_match_round
    home_name = get_team_name_ru(match.home_team)
    away_name = get_team_name_ru(match.away_team)

    home_text = format_team_with_flag(
        display_name=home_name,
        api_name=getattr(match, "home_team_api_name", None),
        flag_before=False,
    )

    away_text = format_team_with_flag(
        display_name=away_name,
        api_name=getattr(match, "away_team_api_name", None),
        flag_before=True,
    )

    team_text = f"{home_text} — {away_text}"

    postfix_parts = []

    if match.stage == "group":
        round_text = match.match_round or get_default_match_round(match.stage)

        if round_text:
            postfix_parts.append(f"Тур {round_text}")

        if match.group_code:
            postfix_parts.append(f"Группа {match.group_code}")

    else:
        round_text = match.match_round or get_default_match_round(match.stage)

        if round_text:
            postfix_parts.append(round_text.capitalize())

    postfix = ". ".join(postfix_parts)

    if postfix:
        label = f"{team_text}. {postfix}"
    else:
        label = team_text

    if include_id:
        return f"#{match.id}. {label}"

    return label


def format_matches_list(matches: list[Match], title: str) -> str:
    """Provide bot helper logic for format_matches_list."""
    lines = [title, ""]

    current_date = None

    for match in matches:
        matchday_dt = match.starts_at.astimezone(MATCHDAY_TIMEZONE)
        matchday_date = matchday_dt.date()

        if current_date != matchday_date:
            current_date = matchday_date
            lines.append(
                f"📅 Игровой день {matchday_dt.strftime('%d.%m.%Y')} "
                f"({MATCHDAY_TIMEZONE_NAME})"
            )

        status = "✅ завершен" if match.is_finished else "⏳ открыт"

        if match.score_home is not None and match.score_away is not None:
            status = f"🏁 {match.score_home}:{match.score_away}"

        lines.append(
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage} | {status}"
        )
        lines.append("")

    lines.append(
        "Сделать прогноз кнопками: /predict\n"
        "Посмотреть все будущие матчи: /matches_all"
    )

    return "\n".join(lines)


def format_missing_matches_list(matches: list[Match], title: str) -> str:
    """Provide bot helper logic for format_missing_matches_list."""
    lines = [title, ""]

    if not matches:
        lines.append("Все прогнозы сделаны ✅")
        return "\n".join(lines)

    current_date = None

    for match in matches:
        local_dt = match.starts_at.astimezone(APP_TIMEZONE)
        local_date = local_dt.date()

        if current_date != local_date:
            current_date = local_date
            lines.append(f"📅 {local_dt.strftime('%d.%m.%Y')}")
            lines.append("")

        lines.append(
            f"{format_match_label(match, include_id=True)}\n"
            f"Старт: {format_datetime(match.starts_at)}"
        )
        lines.append("")

    lines.append("Сделать прогноз: /predict")

    return "\n".join(lines)


def format_match_result(match: Match) -> str:
    """Provide bot helper logic for format_match_result."""
    if match.score_home is None or match.score_away is None:
        return "Результат: еще не внесен"

    result = f"Результат: {match.score_home}:{match.score_away}"

    if match.winner_side == "home":
        result += f"\nПрошла команда: {match.home_team}"
    elif match.winner_side == "away":
        result += f"\nПрошла команда: {match.away_team}"

    return result


def format_user_match_prediction(
        prediction: Prediction | None,
        match: Match,
        reveal: bool = True,
) -> str:
    """Provide bot helper logic for format_user_match_prediction."""
    if not prediction:
        return "прогноза нет"

    if not reveal:
        return "✅ прогноз сделан"

    text = f"{prediction.pred_home}:{prediction.pred_away}"

    if is_playoff_match(match):
        text += f" ({format_advancement_prediction(prediction, match)})"

    if match.is_finished:
        text += f" — {get_prediction_points_breakdown(prediction)}"

    return text

