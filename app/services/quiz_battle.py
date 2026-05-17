"""Timed multi-question quiz battle service for group chats."""

from datetime import datetime, timezone

from sqlalchemy import func

from app.formatters.quiz import format_quiz_battle_question
from app.keyboards.quiz import build_quiz_battle_answer_keyboard
from app.runtime import (
    GroupQuizGame,
    GroupQuizGameAnswer,
    GroupQuizGameQuestion,
    QuizQuestion,
    SessionLocal,
    asyncio,
    bot,
)


ALLOWED_QUIZ_BATTLE_SIZES = {3, 5, 10}
DEFAULT_QUIZ_BATTLE_SECONDS = 60


def get_active_quiz_battle(db, chat_id: int) -> GroupQuizGame | None:
    """Return active quiz battle for a chat, if one exists."""
    return (
        db.query(GroupQuizGame)
        .filter(
            GroupQuizGame.chat_id == chat_id,
            GroupQuizGame.status.in_(["setup", "running"]),
        )
        .first()
    )


def create_quiz_battle(
    db,
    chat_id: int,
    started_by_user_id: int,
    questions_total: int,
    seconds_per_question: int = DEFAULT_QUIZ_BATTLE_SECONDS,
) -> GroupQuizGame:
    """Create a quiz battle and preselect random active questions."""
    if questions_total not in ALLOWED_QUIZ_BATTLE_SIZES:
        raise ValueError("Unsupported quiz battle size")

    questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.is_active == True)
        .order_by(func.random())
        .limit(questions_total)
        .all()
    )

    if len(questions) < questions_total:
        raise ValueError("Not enough active quiz questions")

    game = GroupQuizGame(
        chat_id=chat_id,
        status="running",
        questions_total=questions_total,
        current_question_index=0,
        seconds_per_question=seconds_per_question,
        started_by_user_id=started_by_user_id,
    )

    db.add(game)
    db.commit()
    db.refresh(game)

    for index, question in enumerate(questions, start=1):
        db.add(
            GroupQuizGameQuestion(
                game_id=game.id,
                quiz_question_id=question.id,
                question_order=index,
                status="pending",
            )
        )

    db.commit()
    db.refresh(game)

    return game


def build_quiz_battle_question_result_text(db, game_question_id: int) -> str:
    """Build result text for one closed quiz battle question."""
    game_question = (
        db.query(GroupQuizGameQuestion)
        .filter(GroupQuizGameQuestion.id == game_question_id)
        .first()
    )

    if not game_question:
        return "Вопрос не найден."

    question = game_question.question

    answers = (
        db.query(GroupQuizGameAnswer)
        .filter(GroupQuizGameAnswer.game_question_id == game_question.id)
        .order_by(GroupQuizGameAnswer.answered_at.asc())
        .all()
    )

    correct_answers = [answer.display_name for answer in answers if answer.is_correct]

    correct_option = question.correct_option.upper()
    correct_text = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }.get(correct_option, "")

    lines = [
        f"⏱ Время вышло: вопрос {game_question.question_order}",
        "",
        f"Правильный ответ: {correct_option}) {correct_text}",
    ]

    if question.explanation:
        lines.extend(["", question.explanation])

    lines.append("")

    if correct_answers:
        lines.append("✅ Верно ответили:")
        lines.append(", ".join(correct_answers))
    else:
        lines.append("✅ Верно не ответил никто. Красиво упали всей командой.")

    return "\n".join(lines)


def build_quiz_battle_results_text(db, game_id: int) -> str:
    """Build final leaderboard for a completed quiz battle."""
    game = db.query(GroupQuizGame).filter(GroupQuizGame.id == game_id).first()

    if not game:
        return "Квиз-баттл не найден."

    answers = (
        db.query(GroupQuizGameAnswer)
        .filter(GroupQuizGameAnswer.game_id == game_id)
        .all()
    )

    stats: dict[int | str, dict] = {}

    for answer in answers:
        key = answer.user_id or f"tg:{answer.telegram_id}"

        if key not in stats:
            stats[key] = {
                "display_name": answer.display_name or f"User {answer.telegram_id}",
                "correct": 0,
                "answered": 0,
                "total_seconds": 0,
            }

        row = stats[key]
        row["answered"] += 1
        row["total_seconds"] += answer.answer_seconds or game.seconds_per_question

        if answer.is_correct:
            row["correct"] += 1

    rows = list(stats.values())
    rows.sort(key=lambda row: (-row["correct"], row["total_seconds"], -row["answered"]))

    lines = [
        "🏁 Квиз-баттл завершен",
        "",
        f"Вопросов: {game.questions_total}",
        "",
        "Итоги:",
    ]

    if not rows:
        lines.append("Никто не ответил. Отец прогнозов видел и осуждает.")
        return "\n".join(lines)

    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. {row['display_name']} — "
            f"{row['correct']}/{game.questions_total} "
            f"({row['total_seconds']} сек.)"
        )

    return "\n".join(lines)


async def run_quiz_battle_game(chat_id: int, game_id: int) -> None:
    """Run a timed quiz battle: publish each question, wait, close and continue."""
    while True:
        db = SessionLocal()
        next_question_id = None
        sleep_seconds = DEFAULT_QUIZ_BATTLE_SECONDS

        try:
            game = db.query(GroupQuizGame).filter(GroupQuizGame.id == game_id).first()

            if not game or game.status != "running":
                return

            game_question = (
                db.query(GroupQuizGameQuestion)
                .filter(
                    GroupQuizGameQuestion.game_id == game.id,
                    GroupQuizGameQuestion.status == "pending",
                )
                .order_by(GroupQuizGameQuestion.question_order.asc())
                .first()
            )

            if not game_question:
                game.status = "finished"
                game.finished_at = datetime.now(timezone.utc)
                db.commit()

                result_text = build_quiz_battle_results_text(db, game.id)
                await bot.send_message(chat_id=chat_id, text=result_text)
                return

            question = game_question.question

            now = datetime.now(timezone.utc)
            game_question.status = "open"
            game_question.opened_at = now
            game.current_question_index = game_question.question_order
            db.commit()
            db.refresh(game_question)

            text = format_quiz_battle_question(
                game=game,
                game_question=game_question,
                question=question,
            )

            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=build_quiz_battle_answer_keyboard(game_question.id),
            )

            game_question.message_id = sent_message.message_id
            db.commit()

            next_question_id = game_question.id
            sleep_seconds = game.seconds_per_question

        finally:
            db.close()

        await asyncio.sleep(sleep_seconds)

        db = SessionLocal()

        try:
            game_question = (
                db.query(GroupQuizGameQuestion)
                .filter(GroupQuizGameQuestion.id == next_question_id)
                .first()
            )

            if game_question and game_question.status == "open":
                game_question.status = "closed"
                game_question.closed_at = datetime.now(timezone.utc)
                db.commit()

                answer_text = build_quiz_battle_question_result_text(
                    db,
                    game_question.id,
                )

                await bot.send_message(chat_id=chat_id, text=answer_text)

        finally:
            db.close()
