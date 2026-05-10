import asyncio
import os
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.db import SessionLocal
from app.models import Match, Prediction, TournamentPrediction, TournamentResult, User
from app.admin import is_admin_telegram_id

from zoneinfo import ZoneInfo

from app.scoring import score_match_prediction, score_tournament_prediction


TOKEN = os.getenv("BOT_TOKEN")
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Europe/Moscow"))
TOURNAMENT_CODE = os.getenv("TOURNAMENT_CODE", "wc2026")
TOURNAMENT_STARTS_AT_RAW = os.getenv(
    "TOURNAMENT_STARTS_AT",
    "2026-06-11T21:00:00+03:00",
)


def get_tournament_starts_at():
    dt = datetime.fromisoformat(
        TOURNAMENT_STARTS_AT_RAW.replace("Z", "+00:00")
    )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=APP_TIMEZONE)

    return dt.astimezone(timezone.utc)


def is_tournament_started() -> bool:
    return datetime.now(timezone.utc) >= get_tournament_starts_at()

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=TOKEN)
dp = Dispatcher()


def get_or_create_user(db, telegram_user):
    admin_status = is_admin_telegram_id(telegram_user.id)

    existing_user = db.query(User).filter(
        User.telegram_id == telegram_user.id
    ).first()

    if existing_user:
        changed = False

        if existing_user.username != telegram_user.username:
            existing_user.username = telegram_user.username
            changed = True

        if existing_user.display_name != telegram_user.full_name:
            existing_user.display_name = telegram_user.full_name
            changed = True

        if existing_user.is_admin != admin_status:
            existing_user.is_admin = admin_status
            changed = True

        if changed:
            db.commit()
            db.refresh(existing_user)

        return existing_user, False

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        display_name=telegram_user.full_name,
        is_admin=admin_status,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user, True

PLAYOFF_STAGES = {
    "round_of_32",
    "round_of_16",
    "quarterfinal",
    "semifinal",
    "third_place",
    "final",
}


def is_playoff_match(match: Match) -> bool:
    return match.stage in PLAYOFF_STAGES


def parse_advancement_choice(choice: str | None):
    if choice is None:
        return False, None

    normalized = choice.lower().strip()

    if normalized in ("none", "no", "нет", "не"):
        return False, None

    if normalized in ("home", "1", "хозяин", "хозяева"):
        return True, "home"

    if normalized in ("away", "2", "гость", "гости"):
        return True, "away"

    raise ValueError("Invalid advancement choice")


def format_advancement_prediction(prediction: Prediction, match: Match) -> str:
    if not prediction.advancement_bet_enabled:
        return "проход: не ставил"

    if prediction.predicted_advancing_side == "home":
        return f"проход: {match.home_team}"

    if prediction.predicted_advancing_side == "away":
        return f"проход: {match.away_team}"

    return "проход: не указан"

def parse_score(score_text: str):
    normalized = score_text.replace("-", ":").replace(" ", "")

    if ":" not in normalized:
        raise ValueError("Score must contain ':'")

    home_raw, away_raw = normalized.split(":", 1)

    if not home_raw.isdigit() or not away_raw.isdigit():
        raise ValueError("Score must contain numbers")

    return int(home_raw), int(away_raw)


def format_match(match: Match):
    start_text = format_datetime(match.starts_at)
    return (
        f"#{match.id} {match.home_team} — {match.away_team}\n"
        f"Стадия: {match.stage}\n"
        f"Старт: {start_text}"
    )

def format_datetime(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    local_dt = dt.astimezone(APP_TIMEZONE)
    return local_dt.strftime("%d.%m.%Y %H:%M")

def is_user_admin(user: User) -> bool:
    return bool(user.is_admin)

def ensure_admin_or_reply(user: User) -> bool:
    return bool(user.is_admin)


def parse_admin_match_payload(text: str):
    payload = text.replace("/admin_add_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (4, 5):
        raise ValueError("Invalid admin match format")

    home_team = parts[0]
    away_team = parts[1]
    starts_at_raw = parts[2]
    stage = parts[3]
    tournament_code = parts[4] if len(parts) == 5 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return home_team, away_team, starts_at, stage, tournament_code

def parse_admin_edit_match_payload(text: str):
    payload = text.replace("/admin_edit_match", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) not in (5, 6):
        raise ValueError("Invalid admin edit match format")

    match_id_raw = parts[0]

    if not match_id_raw.isdigit():
        raise ValueError("Match ID must be number")

    match_id = int(match_id_raw)
    home_team = parts[1]
    away_team = parts[2]
    starts_at_raw = parts[3]
    stage = parts[4]
    tournament_code = parts[5] if len(parts) == 6 else TOURNAMENT_CODE

    starts_at = datetime.fromisoformat(
        starts_at_raw.replace("Z", "+00:00")
    )

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=APP_TIMEZONE)

    starts_at = starts_at.astimezone(timezone.utc)

    return match_id, home_team, away_team, starts_at, stage, tournament_code


def parse_match_id_command(text: str, command: str) -> int:
    payload = text.replace(command, "", 1).strip()

    if not payload.isdigit():
        raise ValueError("Match ID must be number")

    return int(payload)

def parse_result_payload(text: str):
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

@dp.message(Command("start"))
async def start_handler(message: Message):
    db = SessionLocal()

    try:
        user, created = get_or_create_user(db, message.from_user)

        if created:
            await message.answer(
                f"Добро пожаловать в Отец прогнозов, {user.display_name} 🏆"
            )
        else:
            await message.answer(
                f"С возвращением, {user.display_name} ⚽"
            )

    finally:
        db.close()


@dp.message(Command("matches"))
async def matches_handler(message: Message):
    db = SessionLocal()

    try:
        matches = db.query(Match).order_by(Match.starts_at).all()

        if not matches:
            await message.answer("Пока матчей нет.")
            return

        text = "📅 Матчи:\n\n"
        text += "\n\n".join(format_match(match) for match in matches)

        text += (
            "\n\nЧтобы сделать прогноз:\n"
            "/predict ID СЧЕТ\n\n"
            "Например:\n"
            "/predict 1 2:1\n\n"
            "Для плей-офф можно добавить ставку на проход:\n"
            "/predict ID СЧЕТ home\n"
            "/predict ID СЧЕТ away\n"
            "/predict ID СЧЕТ none\n\n"
            "home — пройдет первая команда\n"
            "away — пройдет вторая команда\n"
            "none — не рисковать ставкой на проход\n\n"
            "Чтобы посмотреть прогнозы по матчу:\n"
            "/predictions ID"
        )

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("predict"))
async def predict_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        parts = message.text.split()

        if len(parts) not in (3, 4):
            await message.answer(
                "Формат прогноза:\n"
                "/predict ID СЧЕТ\n\n"
                "Например:\n"
                "/predict 1 2:1\n\n"
                "Для плей-офф:\n"
                "/predict ID СЧЕТ home\n"
                "/predict ID СЧЕТ away\n"
                "/predict ID СЧЕТ none"
            )
            return

        _, match_id_raw, score_raw, *advancement_raw = parts

        if not match_id_raw.isdigit():
            await message.answer("ID матча должен быть числом.")
            return

        match_id = int(match_id_raw)

        try:
            pred_home, pred_away = parse_score(score_raw)
        except ValueError:
            await message.answer(
                "Не понял счет. Используй формат 2:1 или 2-1."
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        if now >= match_start:
            await message.answer(
                "Ставки на этот матч уже закрыты. "
                "Отец прогнозов суров, но справедлив."
            )
            return

        advancement_bet_enabled = False
        predicted_advancing_side = None

        if is_playoff_match(match):
            choice = advancement_raw[0] if advancement_raw else "none"

            try:
                advancement_bet_enabled, predicted_advancing_side = (
                    parse_advancement_choice(choice)
                )
            except ValueError:
                await message.answer(
                    "Не понял ставку на проход.\n\n"
                    "Используй:\n"
                    "home — пройдет первая команда\n"
                    "away — пройдет вторая команда\n"
                    "none — не ставить на проход\n\n"
                    "Пример:\n"
                    "/predict 5 1:1 home"
                )
                return
        else:
            if advancement_raw:
                await message.answer(
                    "Это не матч плей-офф. "
                    "Ставка на проход доступна только в матчах на вылет."
                )
                return

        existing_prediction = db.query(Prediction).filter(
            Prediction.user_id == user.id,
            Prediction.match_id == match.id,
        ).first()

        if existing_prediction:
            existing_prediction.pred_home = pred_home
            existing_prediction.pred_away = pred_away
            existing_prediction.advancement_bet_enabled = advancement_bet_enabled
            existing_prediction.predicted_advancing_side = predicted_advancing_side
            db.commit()

            text = (
                f"Прогноз обновлен:\n"
                f"{match.home_team} — {match.away_team}: "
                f"{pred_home}:{pred_away}"
            )

            if is_playoff_match(match):
                text += f"\n{format_advancement_prediction(existing_prediction, match)}"

            await message.answer(text)
            return

        prediction = Prediction(
            user_id=user.id,
            match_id=match.id,
            pred_home=pred_home,
            pred_away=pred_away,
            advancement_bet_enabled=advancement_bet_enabled,
            predicted_advancing_side=predicted_advancing_side,
        )

        db.add(prediction)
        db.commit()
        db.refresh(prediction)

        text = (
            f"Прогноз принят:\n"
            f"{match.home_team} — {match.away_team}: "
            f"{pred_home}:{pred_away}"
        )

        if is_playoff_match(match):
            text += f"\n{format_advancement_prediction(prediction, match)}"

        await message.answer(text)

    finally:
        db.close()


@dp.message(Command("mybets"))
async def mybets_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        predictions = db.query(Prediction).filter(
            Prediction.user_id == user.id
        ).all()

        if not predictions:
            await message.answer("У тебя пока нет прогнозов.")
            return

        lines = ["🎯 Мои прогнозы:\n"]

        for prediction in predictions:
            match = prediction.match

            line = (
                f"{match.home_team} — {match.away_team}: "
                f"{prediction.pred_home}:{prediction.pred_away}"
            )

            if is_playoff_match(match):
                line += f" ({format_advancement_prediction(prediction, match)})"

            lines.append(line)

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("predictions"))
async def predictions_handler(message: Message):
    db = SessionLocal()

    try:
        parts = message.text.split()

        if len(parts) != 2:
            await message.answer(
                "Формат команды:\n"
                "/predictions ID_МАТЧА\n\n"
                "Например:\n"
                "/predictions 1"
            )
            return

        _, match_id_raw = parts

        if not match_id_raw.isdigit():
            await message.answer("ID матча должен быть числом.")
            return

        match_id = int(match_id_raw)

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        now = datetime.now(timezone.utc)

        match_start = match.starts_at
        if match_start.tzinfo is None:
            match_start = match_start.replace(tzinfo=timezone.utc)

        is_revealed = now >= match_start

        users = db.query(User).order_by(User.display_name).all()

        predictions = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).all()

        predictions_by_user_id = {
            prediction.user_id: prediction
            for prediction in predictions
        }

        start_text = format_datetime(match.starts_at)

        lines = [
            f"🔮 Прогнозы на матч #{match.id}",
            f"{match.home_team} — {match.away_team}",
            f"Старт: {start_text}",
            "",
        ]

        if is_revealed:
            lines.append("Матч уже начался — прогнозы открыты:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    line = (
                        f"{user.display_name}: "
                        f"{prediction.pred_home}:{prediction.pred_away}"
                    )

                    if is_playoff_match(match):
                        line += f" ({format_advancement_prediction(prediction, match)})"

                    lines.append(line)
                else:
                    lines.append(f"{user.display_name}: прогноза нет")

        else:
            lines.append("До старта матча прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    lines.append(f"{user.display_name}: ✅ прогноз сделан")
                else:
                    lines.append(f"{user.display_name}: ❌ прогноза нет")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("table"))
async def table_handler(message: Message):
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        if not users:
            await message.answer("Пока нет участников.")
            return

        rows = []

        for user in users:
            predictions = db.query(Prediction).filter(
                Prediction.user_id == user.id
            ).all()

            match_points = sum(prediction.points or 0 for prediction in predictions)

            tournament_prediction = db.query(TournamentPrediction).filter(
                TournamentPrediction.user_id == user.id,
                TournamentPrediction.tournament_code == TOURNAMENT_CODE,
            ).first()

            tournament_points = (
                tournament_prediction.points
                if tournament_prediction
                else 0
            )

            total_points = match_points + tournament_points

            exact_scores = sum(
                1
                for prediction in predictions
                if prediction.score_points == 3
            )

            outcomes = sum(
                1
                for prediction in predictions
                if prediction.score_points == 1
            )

            advancement_plus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == 1
            )

            advancement_minus = sum(
                1
                for prediction in predictions
                if prediction.advancement_points == -1
            )

            rows.append(
                {
                    "name": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "predictions_count": len(predictions),
                    "advancement_plus": advancement_plus,
                    "advancement_minus": advancement_minus,
                    "match_points": match_points,
                    "tournament_points": tournament_points,
                }
            )

        rows.sort(
            key=lambda row: (
                row["points"],
                row["exact_scores"],
                row["outcomes"],
            ),
            reverse=True,
        )

        lines = ["🏆 Таблица «Отец прогнозов»", ""]

        for index, row in enumerate(rows, start=1):
            lines.append(
                f"{index}. {row['name']} — {row['points']} очк. "
                f"🎯 {row['exact_scores']} | ✅ {row['outcomes']} | "
                f"🟢 {row['advancement_plus']} | 🔴 {row['advancement_minus']} | "
                f"🏆 {row['tournament_points']} | "
                f"📋 {row['predictions_count']}"
            )

        lines.append("")
        lines.append("🎯 точные счета")
        lines.append("✅ угаданные исходы")
        lines.append("🟢 угаданные проходы")
        lines.append("🔴 неугаданные проходы")
        lines.append("📋 всего прогнозов")
        lines.append("🏆 очки за прогноз на турнир")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("rules"))
async def rules_handler(message: Message):
    await message.answer(
        "📜 Правила «Отец прогнозов»\n\n"
        "За каждый матч:\n"
        "🎯 3 очка — точный счет\n"
        "✅ 1 очко — угаданный исход\n"
        "❌ 0 очков — если не угадан ни счет, ни исход\n\n"
        "В матчах плей-офф можно дополнительно рискнуть "
        "и поставить, кто пройдет дальше:\n"
        "🟢 +1 очко — если проход угадан\n"
        "🔴 -1 очко — если проход не угадан\n"
        "⚪ 0 очков — если участник решил не ставить на проход\n\n"
        "Прогноз на итоги турнира:\n"
        "🏆 Чемпион — 15 очков\n"
        "🥈 Финалист — 10 очков\n"
        "🥉 3 место — 5 очков\n"
        "⚽ Бомбардир — 15 очков\n\n"
        "Формат прогноза на турнир:\n"
        "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
        "Пример:\n"
        "/tournament_set Аргентина; Франция; Бразилия; Мбаппе\n\n"
        "Прогнозы можно менять только до стартового свистка."
    )

def parse_tournament_prediction_payload(text: str):
    payload = text.replace("/tournament_set", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament prediction format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer

def parse_tournament_result_payload(text: str):
    payload = text.replace("/admin_set_tournament_result", "", 1).strip()
    parts = [part.strip() for part in payload.split(";")]

    if len(parts) != 4 or any(not part for part in parts):
        raise ValueError("Invalid tournament result format")

    champion, runner_up, third_place, top_scorer = parts

    return champion, runner_up, third_place, top_scorer

@dp.message(Command("tournament_set"))
async def tournament_set_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if is_tournament_started():
            await message.answer(
                "Прогнозы на итоги турнира уже закрыты. "
                "Турнир стартовал."
            )
            return

        try:
            champion, runner_up, third_place, top_scorer = (
                parse_tournament_prediction_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат прогноза на турнир:\n\n"
                "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        existing_prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        if existing_prediction:
            existing_prediction.champion = champion
            existing_prediction.runner_up = runner_up
            existing_prediction.third_place = third_place
            existing_prediction.top_scorer = top_scorer
            existing_prediction.champion_points = 0
            existing_prediction.runner_up_points = 0
            existing_prediction.third_place_points = 0
            existing_prediction.top_scorer_points = 0
            existing_prediction.points = 0

            db.commit()

            await message.answer(
                "Турнирный прогноз обновлен 🏆\n\n"
                f"1 место: {champion}\n"
                f"2 место: {runner_up}\n"
                f"3 место: {third_place}\n"
                f"Бомбардир: {top_scorer}"
            )
            return

        prediction = TournamentPrediction(
            user_id=user.id,
            tournament_code=TOURNAMENT_CODE,
            champion=champion,
            runner_up=runner_up,
            third_place=third_place,
            top_scorer=top_scorer,
        )

        db.add(prediction)
        db.commit()

        await message.answer(
            "Турнирный прогноз принят 🏆\n\n"
            f"1 место: {champion}\n"
            f"2 место: {runner_up}\n"
            f"3 место: {third_place}\n"
            f"Бомбардир: {top_scorer}"
        )

    finally:
        db.close()

@dp.message(Command("tournament"))
async def tournament_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        prediction = db.query(TournamentPrediction).filter(
            TournamentPrediction.user_id == user.id,
            TournamentPrediction.tournament_code == TOURNAMENT_CODE,
        ).first()

        if not prediction:
            await message.answer(
                "У тебя пока нет прогноза на итоги турнира.\n\n"
                "Создать прогноз:\n"
                "/tournament_set Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/tournament_set Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        await message.answer(
            "🏆 Твой прогноз на итоги турнира:\n\n"
            f"1 место: {prediction.champion}\n"
            f"2 место: {prediction.runner_up}\n"
            f"3 место: {prediction.third_place}\n"
            f"Бомбардир: {prediction.top_scorer}\n\n"
            f"Очки за турнир: {prediction.points}"
        )

    finally:
        db.close()

@dp.message(Command("tournament_predictions"))
async def tournament_predictions_handler(message: Message):
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        predictions_by_user_id = {
            prediction.user_id: prediction
            for prediction in predictions
        }

        tournament_started = is_tournament_started()

        start_text = format_datetime(get_tournament_starts_at())

        lines = [
            "🏆 Прогнозы на итоги турнира",
            f"Старт турнира: {start_text}",
            "",
        ]

        if tournament_started:
            lines.append("Турнир уже стартовал — прогнозы открыты:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if not prediction:
                    lines.append(f"{user.display_name}: прогноза нет")
                    continue

                lines.append(
                    f"{user.display_name}:\n"
                    f"1 место: {prediction.champion}\n"
                    f"2 место: {prediction.runner_up}\n"
                    f"3 место: {prediction.third_place}\n"
                    f"Бомбардир: {prediction.top_scorer}\n"
                    f"Очки: {prediction.points}"
                )
                lines.append("")

        else:
            lines.append("До старта турнира прогнозы скрыты.")
            lines.append("Видно только, кто уже сделал прогноз:")
            lines.append("")

            for user in users:
                prediction = predictions_by_user_id.get(user.id)

                if prediction:
                    lines.append(f"{user.display_name}: ✅ прогноз сделан")
                else:
                    lines.append(f"{user.display_name}: ❌ прогноза нет")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not is_user_admin(user):
            await message.answer(
                "У тебя нет админских прав.\n"
                "Отец прогнозов не выдал тебе свисток судьи."
            )
            return

        await message.answer(
            "🛠 Админ-панель\n\n"
            "Список матчей:\n"
            "/admin_matches\n\n"
            "Добавить матч:\n"
            "/admin_add_match Мексика; ЮАР; 2026-06-11T21:00:00+03:00; group\n\n"
            "Редактировать матч:\n"
            "/admin_edit_match 5; Аргентина; Франция; 2026-06-30T21:00:00+03:00; round_of_16\n\n"
            "Удалить матч без прогнозов:\n"
            "/admin_delete_match 5\n\n"
            "Удалить матч вместе с прогнозами:\n"
            "/admin_force_delete_match 5\n\n"
            "Внести результат группового матча:\n"
            "/admin_set_result 1 2:1\n\n"
            "Внести результат плей-офф:\n"
            "/admin_set_result 5 1:1 home\n"
            "/admin_set_result 5 1:1 away\n\n"
            "Пересчитать все завершенные матчи:\n"
            "/admin_recalculate\n\n"
            "Внести итоги турнира:\n"
            "/admin_set_tournament_result Аргентина; Франция; Бразилия; Мбаппе\n\n"
            "Пересчитать турнирные прогнозы:\n"
            "/admin_tournament_recalculate\n\n"
            "Стадии:\n"
            "group, round_of_32, round_of_16, quarterfinal, semifinal, "
            "third_place, final"
        )

    finally:
        db.close()

@dp.message(Command("admin_add_match"))
async def admin_add_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer(
                "У тебя нет админских прав."
            )
            return

        try:
            home_team, away_team, starts_at, stage, tournament_code = (
                parse_admin_match_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат добавления матча:\n\n"
                "/admin_add_match Команда1; Команда2; Дата; Стадия\n\n"
                "Пример:\n"
                "/admin_add_match Мексика; ЮАР; 2026-06-11T21:00:00+03:00; group\n\n"
                "Стадии:\n"
                "group, round_of_32, round_of_16, quarterfinal, "
                "semifinal, third_place, final"
            )
            return

        match = Match(
            home_team=home_team,
            away_team=away_team,
            starts_at=starts_at,
            stage=stage,
            tournament_code=tournament_code,
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        await message.answer(
            "Матч добавлен ✅\n\n"
            f"#{match.id} {match.home_team} — {match.away_team}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage}"
        )

    finally:
        db.close()

@dp.message(Command("admin_set_result"))
async def admin_set_result_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer(
                "У тебя нет админских прав."
            )
            return

        try:
            match_id, score_home, score_away, winner_side = (
                parse_result_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат результата:\n\n"
                "/admin_set_result ID СЧЕТ\n\n"
                "Пример для группового матча:\n"
                "/admin_set_result 1 2:1\n\n"
                "Пример для плей-офф:\n"
                "/admin_set_result 5 1:1 home\n"
                "/admin_set_result 5 1:1 away\n\n"
                "home — прошла первая команда\n"
                "away — прошла вторая команда"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        if is_playoff_match(match) and winner_side is None:
            await message.answer(
                "Это матч плей-офф. Нужно указать, кто прошел дальше:\n\n"
                f"/admin_set_result {match.id} {score_home}:{score_away} home\n"
                f"/admin_set_result {match.id} {score_home}:{score_away} away"
            )
            return

        if not is_playoff_match(match) and winner_side is not None:
            await message.answer(
                "Это не матч плей-офф. Для группового матча не нужно "
                "указывать home/away."
            )
            return

        match.score_home = score_home
        match.score_away = score_away
        match.winner_side = winner_side
        match.is_finished = True

        predictions = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).all()

        recalculated = []

        for prediction in predictions:
            from app.scoring import score_match_prediction

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
            f"{match.home_team} — {match.away_team}: {score_home}:{score_away}",
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

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("admin_recalculate"))
async def admin_recalculate_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        finished_matches = db.query(Match).filter(
            Match.is_finished == True
        ).all()

        recalculated_predictions_count = 0

        for match in finished_matches:
            if match.score_home is None or match.score_away is None:
                continue

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            for prediction in predictions:
                from app.scoring import score_match_prediction

                result = score_match_prediction(
                    pred_home=prediction.pred_home,
                    pred_away=prediction.pred_away,
                    actual_home=match.score_home,
                    actual_away=match.score_away,
                    advancement_bet_enabled=prediction.advancement_bet_enabled,
                    predicted_advancing_side=prediction.predicted_advancing_side,
                    actual_winner_side=match.winner_side,
                )

                prediction.score_points = result["score_points"]
                prediction.advancement_points = result["advancement_points"]
                prediction.points = result["total_points"]

                recalculated_predictions_count += 1

        db.commit()

        await message.answer(
            "Пересчет завершен ✅\n\n"
            f"Матчей обработано: {len(finished_matches)}\n"
            f"Прогнозов пересчитано: {recalculated_predictions_count}"
        )

    finally:
        db.close()

@dp.message(Command("admin_set_tournament_result"))
async def admin_set_tournament_result_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            champion, runner_up, third_place, top_scorer = (
                parse_tournament_result_payload(message.text)
            )
        except ValueError:
            await message.answer(
                "Формат итогов турнира:\n\n"
                "/admin_set_tournament_result Чемпион; Финалист; Третье место; Бомбардир\n\n"
                "Пример:\n"
                "/admin_set_tournament_result Аргентина; Франция; Бразилия; Мбаппе"
            )
            return

        tournament_result = db.query(TournamentResult).filter(
            TournamentResult.tournament_code == TOURNAMENT_CODE
        ).first()

        if tournament_result:
            tournament_result.champion = champion
            tournament_result.runner_up = runner_up
            tournament_result.third_place = third_place
            tournament_result.top_scorer = top_scorer
        else:
            tournament_result = TournamentResult(
                tournament_code=TOURNAMENT_CODE,
                champion=champion,
                runner_up=runner_up,
                third_place=third_place,
                top_scorer=top_scorer,
            )
            db.add(tournament_result)

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        recalculated = []

        for prediction in predictions:
            result = score_tournament_prediction(
                pred_champion=prediction.champion,
                pred_runner_up=prediction.runner_up,
                pred_third_place=prediction.third_place,
                pred_top_scorer=prediction.top_scorer,
                actual_champion=champion,
                actual_runner_up=runner_up,
                actual_third_place=third_place,
                actual_top_scorer=top_scorer,
            )

            prediction.champion_points = result["champion_points"]
            prediction.runner_up_points = result["runner_up_points"]
            prediction.third_place_points = result["third_place_points"]
            prediction.top_scorer_points = result["top_scorer_points"]
            prediction.points = result["total_points"]

            recalculated.append(
                {
                    "user": prediction.user.display_name,
                    "champion": prediction.champion,
                    "runner_up": prediction.runner_up,
                    "third_place": prediction.third_place,
                    "top_scorer": prediction.top_scorer,
                    "champion_points": prediction.champion_points,
                    "runner_up_points": prediction.runner_up_points,
                    "third_place_points": prediction.third_place_points,
                    "top_scorer_points": prediction.top_scorer_points,
                    "total_points": prediction.points,
                }
            )

        db.commit()

        lines = [
            "Итоги турнира сохранены ✅",
            "",
            f"🏆 Чемпион: {champion}",
            f"🥈 Финалист: {runner_up}",
            f"🥉 3 место: {third_place}",
            f"⚽ Бомбардир: {top_scorer}",
            "",
            "Пересчет турнирных прогнозов:",
            "",
        ]

        if not recalculated:
            lines.append("Турнирных прогнозов пока нет.")
        else:
            for item in recalculated:
                lines.append(
                    f"{item['user']} — {item['total_points']} очк.\n"
                    f"🏆 {item['champion_points']} | "
                    f"🥈 {item['runner_up_points']} | "
                    f"🥉 {item['third_place_points']} | "
                    f"⚽ {item['top_scorer_points']}"
                )
                lines.append("")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("admin_tournament_recalculate"))
async def admin_tournament_recalculate_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        tournament_result = db.query(TournamentResult).filter(
            TournamentResult.tournament_code == TOURNAMENT_CODE
        ).first()

        if not tournament_result:
            await message.answer(
                "Итоги турнира еще не внесены.\n\n"
                "Сначала используй:\n"
                "/admin_set_tournament_result Чемпион; Финалист; Третье место; Бомбардир"
            )
            return

        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == TOURNAMENT_CODE
        ).all()

        recalculated_count = 0

        for prediction in predictions:
            result = score_tournament_prediction(
                pred_champion=prediction.champion,
                pred_runner_up=prediction.runner_up,
                pred_third_place=prediction.third_place,
                pred_top_scorer=prediction.top_scorer,
                actual_champion=tournament_result.champion,
                actual_runner_up=tournament_result.runner_up,
                actual_third_place=tournament_result.third_place,
                actual_top_scorer=tournament_result.top_scorer,
            )

            prediction.champion_points = result["champion_points"]
            prediction.runner_up_points = result["runner_up_points"]
            prediction.third_place_points = result["third_place_points"]
            prediction.top_scorer_points = result["top_scorer_points"]
            prediction.points = result["total_points"]

            recalculated_count += 1

        db.commit()

        await message.answer(
            "Турнирные прогнозы пересчитаны ✅\n\n"
            f"Турнир: {TOURNAMENT_CODE}\n"
            f"Прогнозов пересчитано: {recalculated_count}\n\n"
            f"🏆 Чемпион: {tournament_result.champion}\n"
            f"🥈 Финалист: {tournament_result.runner_up}\n"
            f"🥉 3 место: {tournament_result.third_place}\n"
            f"⚽ Бомбардир: {tournament_result.top_scorer}"
        )

    finally:
        db.close()

@dp.message(Command("admin_matches"))
async def admin_matches_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        matches = db.query(Match).order_by(Match.starts_at).all()

        if not matches:
            await message.answer("Матчей пока нет.")
            return

        lines = ["🛠 Матчи в базе:", ""]

        for match in matches:
            status = "✅ завершен" if match.is_finished else "⏳ не завершен"

            result = ""
            if match.score_home is not None and match.score_away is not None:
                result = f" | счет {match.score_home}:{match.score_away}"

            winner = ""
            if match.winner_side == "home":
                winner = f" | прошла {match.home_team}"
            elif match.winner_side == "away":
                winner = f" | прошла {match.away_team}"

            predictions_count = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).count()

            lines.append(
                f"#{match.id} {match.home_team} — {match.away_team}\n"
                f"Старт: {format_datetime(match.starts_at)}\n"
                f"Стадия: {match.stage} | {status}{result}{winner}\n"
                f"Прогнозов: {predictions_count}"
            )
            lines.append("")

        await message.answer("\n".join(lines))

    finally:
        db.close()

@dp.message(Command("admin_edit_match"))
async def admin_edit_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            (
                match_id,
                home_team,
                away_team,
                starts_at,
                stage,
                tournament_code,
            ) = parse_admin_edit_match_payload(message.text)
        except ValueError:
            await message.answer(
                "Формат редактирования матча:\n\n"
                "/admin_edit_match ID; Команда1; Команда2; Дата; Стадия\n\n"
                "Пример:\n"
                "/admin_edit_match 5; Аргентина; Франция; "
                "2026-06-30T21:00:00+03:00; round_of_16\n\n"
                "Стадии:\n"
                "group, round_of_32, round_of_16, quarterfinal, "
                "semifinal, third_place, final"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        old_text = (
            f"Было:\n"
            f"#{match.id} {match.home_team} — {match.away_team}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage}"
        )

        match.home_team = home_team
        match.away_team = away_team
        match.starts_at = starts_at
        match.stage = stage
        match.tournament_code = tournament_code

        db.commit()
        db.refresh(match)

        new_text = (
            f"Стало:\n"
            f"#{match.id} {match.home_team} — {match.away_team}\n"
            f"Старт: {format_datetime(match.starts_at)}\n"
            f"Стадия: {match.stage}"
        )

        await message.answer(
            "Матч обновлен ✅\n\n"
            f"{old_text}\n\n"
            f"{new_text}"
        )

    finally:
        db.close()

@dp.message(Command("admin_delete_match"))
async def admin_delete_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            match_id = parse_match_id_command(
                message.text,
                "/admin_delete_match",
            )
        except ValueError:
            await message.answer(
                "Формат удаления матча:\n\n"
                "/admin_delete_match ID\n\n"
                "Пример:\n"
                "/admin_delete_match 5"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        predictions_count = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).count()

        if predictions_count > 0:
            await message.answer(
                "Матч не удален, потому что на него уже есть прогнозы.\n\n"
                f"Матч: #{match.id} {match.home_team} — {match.away_team}\n"
                f"Прогнозов: {predictions_count}\n\n"
                "Если это тестовый или ошибочный матч, используй:\n"
                f"/admin_force_delete_match {match.id}\n\n"
                "Осторожно: эта команда удалит и матч, и все прогнозы на него."
            )
            return

        match_text = f"#{match.id} {match.home_team} — {match.away_team}"

        db.delete(match)
        db.commit()

        await message.answer(
            "Матч удален ✅\n\n"
            f"{match_text}"
        )

    finally:
        db.close()

@dp.message(Command("admin_force_delete_match"))
async def admin_force_delete_match_handler(message: Message):
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        if not ensure_admin_or_reply(user):
            await message.answer("У тебя нет админских прав.")
            return

        try:
            match_id = parse_match_id_command(
                message.text,
                "/admin_force_delete_match",
            )
        except ValueError:
            await message.answer(
                "Формат принудительного удаления матча:\n\n"
                "/admin_force_delete_match ID\n\n"
                "Пример:\n"
                "/admin_force_delete_match 5"
            )
            return

        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            await message.answer("Матч с таким ID не найден.")
            return

        predictions = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).all()

        predictions_count = len(predictions)

        match_text = f"#{match.id} {match.home_team} — {match.away_team}"

        for prediction in predictions:
            db.delete(prediction)

        db.delete(match)
        db.commit()

        await message.answer(
            "Матч и прогнозы удалены ✅\n\n"
            f"{match_text}\n"
            f"Удалено прогнозов: {predictions_count}"
        )

    finally:
        db.close()

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())