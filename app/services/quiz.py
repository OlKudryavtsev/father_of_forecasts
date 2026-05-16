"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.categories import FACT_QUIZ_CATEGORIES, QUIZ_SEED_PATH
from app.formatters.quiz import format_group_quiz_question, format_quiz_question
from app.keyboards.facts import build_category_keyboard
from app.keyboards.quiz import build_group_quiz_keyboard, build_quiz_keyboard
from app.runtime import (
    GroupQuizAnswer,
    GroupQuizSession,
    Message,
    QuizQuestion,
    SessionLocal,
    WorldCupFact,
    datetime,
    json,
    random,
    timezone,
)
from app.services.users import get_or_create_user

def get_random_quiz_question(db, category: str | None = None) -> QuizQuestion | None:
    """Provide bot helper logic for get_random_quiz_question."""
    query = db.query(QuizQuestion).filter(
        QuizQuestion.is_active == True,
    )

    if category:
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        return None

    return random.choice(questions)


async def private_quiz_handler(message: Message):
    """Handle asynchronous bot workflow for private_quiz_handler."""
    db = SessionLocal()

    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) == 1:
            await message.answer(
                "❓ Выбери категорию квиза:",
                reply_markup=build_category_keyboard("quiz_category"),
            )
            return

        category = parts[1].strip().lower()

        if category == "any":
            category = None

        await send_quiz_by_category(
            message=message,
            db=db,
            category=category,
        )

    finally:
        db.close()


async def group_quiz_start_handler(message: Message):
    """Handle asynchronous bot workflow for group_quiz_start_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        existing_session = db.query(GroupQuizSession).filter(
            GroupQuizSession.chat_id == message.chat.id,
            GroupQuizSession.status == "open",
        ).first()

        if existing_session:
            await message.answer(
                "В этом чате уже идет квиз ❓\n\n"
                "Сначала завершите текущий вопрос: /quiz_finish"
            )
            return

        parts = message.text.split(maxsplit=1)
        category = parts[1].strip().lower() if len(parts) > 1 else None

        if category == "any":
            category = None

        question = get_random_quiz_question(db, category=category)

        if not question:
            await message.answer(
                "Вопросов по такой категории пока нет.\n\n"
                "Попробуй просто /quiz"
            )
            return

        session = GroupQuizSession(
            chat_id=message.chat.id,
            quiz_question_id=question.id,
            status="open",
            started_by_user_id=user.id,
            category=category,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        sent_message = await message.answer(
            format_group_quiz_question(question),
            reply_markup=build_group_quiz_keyboard(session.id),
        )

        session.message_id = sent_message.message_id
        db.commit()

    finally:
        db.close()


def finish_group_quiz_and_build_result_text(db, session: GroupQuizSession) -> str:
    """Provide bot helper logic for finish_group_quiz_and_build_result_text."""
    question = session.question

    answers = db.query(GroupQuizAnswer).filter(
        GroupQuizAnswer.session_id == session.id,
    ).all()

    session.status = "finished"
    session.finished_at = datetime.now(timezone.utc)
    db.commit()

    option_texts = {
        "A": question.option_a,
        "B": question.option_b,
        "C": question.option_c,
        "D": question.option_d,
    }

    correct_option = question.correct_option.upper()
    correct_text = option_texts[correct_option]

    correct_answers = [
        answer.display_name
        for answer in answers
        if answer.is_correct
    ]

    wrong_answers = [
        f"{answer.display_name} ({answer.selected_option})"
        for answer in answers
        if not answer.is_correct
    ]

    lines = [
        "🏁 Квиз завершен",
        "",
        f"Вопрос: {question.question_text}",
        "",
        f"Правильный ответ: {correct_option}) {correct_text}",
    ]

    if question.explanation:
        lines.extend(["", question.explanation])

    lines.extend(["", "✅ Верно ответили:"])

    if correct_answers:
        lines.append(", ".join(correct_answers))
    else:
        lines.append("Никто. Очень мощно, господа.")

    lines.extend(["", "❌ Мимо:"])

    if wrong_answers:
        lines.append(", ".join(wrong_answers))
    else:
        lines.append("Никто.")

    if not answers:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Вопрос был настолько сложный, что чат сделал вид, будто занят.",
            ]
        )
    elif correct_answers:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Кто ответил верно — красавчики. Кто мимо — добро пожаловать в зону прогнозов 1:1.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "🔥 Отец прогнозов:",
                "Коллективный ноль. Архив Отца прогнозов уже заинтересовался.",
            ]
        )

    return "\n".join(lines)


def build_quiz_teaser_for_fact(fact: WorldCupFact) -> str:
    """Provide bot helper logic for build_quiz_teaser_for_fact."""
    if fact.tournament_year:
        return f"Какой факт связан с ЧМ-{fact.tournament_year}?"

    category_questions = {
        "wc2026": "Что необычного будет в формате ЧМ-2026?",
        "record": "Какой рекорд чемпионатов мира связан с этим фактом?",
        "team": "Какая сборная связана с этим фактом?",
        "player": "Какой футболист связан с этим фактом?",
        "trophy": "Какой трофей или награда связаны с этим фактом?",
        "host": "Какая страна или турнир связаны с этим фактом?",
        "history": "Что произошло в истории чемпионатов мира?",
        "funny": "Какой необычный эпизод связан с этим фактом?",
    }

    return category_questions.get(
        fact.category,
        "Что интересного произошло в истории чемпионатов мира?",
    )


def import_quiz_questions_from_seed(db) -> dict:
    """Provide bot helper logic for import_quiz_questions_from_seed."""
    if not QUIZ_SEED_PATH.exists():
        raise FileNotFoundError(f"Файл не найден: {QUIZ_SEED_PATH}")

    payload = json.loads(QUIZ_SEED_PATH.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    created = 0
    updated = 0
    skipped = 0

    for item in questions:
        external_id = item.get("id")

        if not external_id:
            skipped += 1
            continue

        options = item.get("options") or {}

        required_options = ["A", "B", "C", "D"]

        if any(option not in options for option in required_options):
            skipped += 1
            continue

        question = db.query(QuizQuestion).filter(
            QuizQuestion.external_id == external_id
        ).first()

        if not question:
            question = QuizQuestion(external_id=external_id)
            db.add(question)
            created += 1
        else:
            updated += 1

        question.question_text = item["question_text"]
        question.option_a = options["A"]
        question.option_b = options["B"]
        question.option_c = options["C"]
        question.option_d = options["D"]
        question.correct_option = item["correct_option"]
        question.explanation = item.get("explanation")
        question.category = item.get("category")
        question.tournament_year = item.get("tournament_year")
        question.is_active = bool(item.get("is_active", True))

    db.commit()

    return {
        "total": len(questions),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


async def send_quiz_by_category(
    message: Message,
    db,
    category: str | None,
):
    """Handle asynchronous bot workflow for send_quiz_by_category."""
    query = db.query(QuizQuestion).filter(
        QuizQuestion.is_active == True,
    )

    if category:
        query = query.filter(QuizQuestion.category == category)

    questions = query.all()

    if not questions:
        await message.answer(
            "Вопросов по такой категории пока нет.\n\n"
            "Попробуй выбрать другую категорию: /quiz"
        )
        return

    question = random.choice(questions)

    category_text = FACT_QUIZ_CATEGORIES.get(category or "any", "🎲 Любая категория")

    await message.answer(
        f"{category_text}\n\n"
        f"{format_quiz_question(question)}",
        reply_markup=build_quiz_keyboard(question),
    )

