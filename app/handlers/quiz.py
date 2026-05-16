"""Real implementation extracted from the former bot_runtime monolith."""

from app.runtime import *
from app.constants.teams import *
from app.constants.texts import *
from app.constants.categories import *
from app.constants.commands import *
from app.states import *

async def quiz_handler(message: Message):
    """Handle asynchronous bot workflow for quiz_handler."""
    if is_group_chat(message):
        await group_quiz_start_handler(message)
        return

    await private_quiz_handler(message)


async def quiz_answer_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for quiz_answer_callback."""
    db = SessionLocal()

    try:
        _, question_id_text, selected_option = callback.data.split(":")

        question = db.query(QuizQuestion).filter(
            QuizQuestion.id == int(question_id_text)
        ).first()

        if not question:
            await callback.answer("Вопрос не найден", show_alert=True)
            return

        user, _ = get_or_create_user(db, callback.from_user)

        selected_option = selected_option.upper()
        correct_option = question.correct_option.upper()

        is_correct = selected_option == correct_option

        answer = QuizAnswer(
            quiz_question_id=question.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            selected_option=selected_option,
            is_correct=is_correct,
        )

        db.add(answer)
        db.commit()

        selected_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }[selected_option]

        correct_text = {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        }[correct_option]

        if is_correct:
            result_text = "✅ Верно!"
            roast_text = "Отец прогнозов доволен. Такое бы еще в точный счет перенести."
        else:
            result_text = "❌ Мимо."
            roast_text = "Ничего страшного. Некоторые так целые турниры прогнозируют."

        explanation = question.explanation or ""

        await callback.message.answer(
            f"{result_text}\n\n"
            f"Твой ответ: {selected_option}. {selected_text}\n"
            f"Правильный ответ: {correct_option}. {correct_text}\n\n"
            f"{explanation}\n\n"
            f"🔥 {roast_text}"
        )

        await callback.answer()

    finally:
        db.close()


async def quiz_stats_handler(message: Message):
    """Handle asynchronous bot workflow for quiz_stats_handler."""
    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, message.from_user)

        answers = db.query(QuizAnswer).filter(
            QuizAnswer.user_id == user.id
        ).all()

        total = len(answers)
        correct = sum(1 for answer in answers if answer.is_correct)

        if total == 0:
            await message.answer(
                "Ты еще не отвечал на вопросы.\n\n"
                "Попробуй: /quiz"
            )
            return

        accuracy = correct / total * 100

        await message.answer(
            "📊 Твоя статистика квиза\n\n"
            f"Ответов: {total}\n"
            f"Верных: {correct}\n"
            f"Точность: {accuracy:.0f}%\n\n"
            "Новый вопрос: /quiz"
        )

    finally:
        db.close()


async def quiz_category_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for quiz_category_callback."""
    db = SessionLocal()

    try:
        category = callback.data.split(":")[1]

        if category == "any":
            category = None

        query = db.query(QuizQuestion).filter(
            QuizQuestion.is_active == True,
        )

        if category:
            query = query.filter(QuizQuestion.category == category)

        questions = query.all()

        if not questions:
            await callback.message.answer(
                "Вопросов по такой категории пока нет.\n\n"
                "Попробуй другую категорию: /quiz"
            )
            await callback.answer()
            return

        question = random.choice(questions)

        category_text = FACT_QUIZ_CATEGORIES.get(
            category or "any",
            "🎲 Любая категория",
        )

        await callback.message.answer(
            f"{category_text}\n\n"
            f"{format_quiz_question(question)}",
            reply_markup=build_quiz_keyboard(question),
        )

        await callback.answer()

    finally:
        db.close()


async def group_quiz_answer_callback(callback: CallbackQuery):
    """Handle asynchronous bot workflow for group_quiz_answer_callback."""
    db = SessionLocal()

    try:
        _, session_id_text, selected_option = callback.data.split(":")
        session_id = int(session_id_text)

        session = db.query(GroupQuizSession).filter(
            GroupQuizSession.id == session_id
        ).first()

        if not session:
            await callback.answer(
                "Квиз не найден.",
                show_alert=True,
            )
            return

        if session.status != "open":
            await callback.answer(
                "Этот вопрос уже завершен.",
                show_alert=True,
            )
            return

        user, _ = get_or_create_user(db, callback.from_user)

        existing_answer = db.query(GroupQuizAnswer).filter(
            GroupQuizAnswer.session_id == session.id,
            GroupQuizAnswer.user_id == user.id,
        ).first()

        if existing_answer:
            await callback.answer(
                "Ты уже ответил на этот вопрос. Переобуться не получится 😈",
                show_alert=True,
            )
            return

        question = session.question

        selected_option = selected_option.upper()
        correct_option = question.correct_option.upper()
        is_correct = selected_option == correct_option

        answer = GroupQuizAnswer(
            session_id=session.id,
            quiz_question_id=question.id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=user.display_name,
            selected_option=selected_option,
            is_correct=is_correct,
        )

        db.add(answer)
        db.commit()

        await callback.answer(
            "Ответ принят ✅",
            show_alert=False,
        )

    finally:
        db.close()


async def group_quiz_finish_handler(message: Message):
    """Handle asynchronous bot workflow for group_quiz_finish_handler."""
    if not is_group_chat(message):
        await message.answer("Эта команда нужна для группового квиза.")
        return

    db = SessionLocal()

    try:
        session = db.query(GroupQuizSession).filter(
            GroupQuizSession.chat_id == message.chat.id,
            GroupQuizSession.status == "open",
        ).first()

        if not session:
            await message.answer("В этом чате сейчас нет активного квиза.")
            return

        text = finish_group_quiz_and_build_result_text(db, session)

        await message.answer(text)

    finally:
        db.close()


async def group_quiz_table_handler(message: Message):
    """Handle asynchronous bot workflow for group_quiz_table_handler."""
    db = SessionLocal()

    try:
        query = db.query(GroupQuizAnswer)

        if is_group_chat(message):
            session_ids = [
                row.id
                for row in db.query(GroupQuizSession)
                .filter(GroupQuizSession.chat_id == message.chat.id)
                .all()
            ]

            if not session_ids:
                await message.answer("В этом чате еще не было групповых квизов.")
                return

            query = query.filter(GroupQuizAnswer.session_id.in_(session_ids))

        answers = query.all()

        if not answers:
            await message.answer("Ответов по квизу пока нет.")
            return

        stats = {}

        for answer in answers:
            key = answer.user_id

            if key not in stats:
                stats[key] = {
                    "name": answer.display_name or f"User {answer.telegram_id}",
                    "total": 0,
                    "correct": 0,
                }

            stats[key]["total"] += 1

            if answer.is_correct:
                stats[key]["correct"] += 1

        rows = list(stats.values())

        rows.sort(
            key=lambda row: (
                row["correct"],
                row["correct"] / row["total"],
                row["total"],
            ),
            reverse=True,
        )

        lines = [
            "🏆 Рейтинг группового квиза",
            "",
        ]

        for index, row in enumerate(rows, start=1):
            accuracy = row["correct"] / row["total"] * 100

            lines.append(
                f"{index}. {row['name']} — "
                f"{row['correct']}/{row['total']} "
                f"({accuracy:.0f}%)"
            )

        await message.answer("\n".join(lines))

    finally:
        db.close()

