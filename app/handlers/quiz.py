"""Real implementation extracted from the former bot_runtime monolith."""


from app.constants.categories import FACT_QUIZ_CATEGORIES
from app.formatters.quiz import format_quiz_question
from app.keyboards.quiz import build_quiz_battle_size_keyboard, build_quiz_keyboard
from app.runtime import (
    CallbackQuery,
    GroupQuizAnswer,
    GroupQuizSession,
    GroupQuizGameAnswer,
    GroupQuizGameQuestion,
    Message,
    QuizAnswer,
    QuizQuestion,
    SessionLocal,
    asyncio,
    datetime,
    random,
    timezone,
)
from app.services.quiz import finish_group_quiz_and_build_result_text, finish_group_quiz_if_all_answered, group_quiz_start_handler, private_quiz_handler
from app.services.quiz_battle import create_quiz_battle, get_active_quiz_battle, run_quiz_battle_game
from app.services.users import get_or_create_user, is_group_chat



async def quiz_battle_handler(message: Message):
    """Start setup for a timed group quiz battle."""
    if not is_group_chat(message):
        await message.answer(
            "Квиз-баттл работает в общем чате.\n\n"
            "В личке можно играть обычный квиз: /quiz"
        )
        return

    await message.answer(
        "🏆 Квиз-баттл\n\n"
        "Сколько вопросов играем?",
        reply_markup=build_quiz_battle_size_keyboard(),
    )


async def quiz_battle_size_callback(callback: CallbackQuery):
    """Create a timed group quiz battle after question-count selection."""
    if not callback.message or not is_group_chat(callback.message):
        await callback.answer(
            "Квиз-баттл работает только в группе.",
            show_alert=True,
        )
        return

    parts = callback.data.split(":")

    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer("Некорректное количество вопросов.", show_alert=True)
        return

    questions_total = int(parts[1])

    if questions_total not in (3, 5, 10):
        await callback.answer("Можно выбрать только 3, 5 или 10 вопросов.", show_alert=True)
        return

    db = SessionLocal()

    try:
        user, _ = get_or_create_user(db, callback.from_user)

        if get_active_quiz_battle(db, callback.message.chat.id):
            await callback.answer(
                "В этом чате уже идет квиз-баттл.",
                show_alert=True,
            )
            return

        try:
            game = create_quiz_battle(
                db=db,
                chat_id=callback.message.chat.id,
                started_by_user_id=user.id,
                questions_total=questions_total,
                seconds_per_question=60,
            )
        except ValueError as error:
            await callback.answer(str(error), show_alert=True)
            return

        await callback.message.answer(
            "🏁 Квиз-баттл стартует!\n\n"
            f"Вопросов: {questions_total}\n"
            "Время на каждый: 60 секунд"
        )

        await callback.answer()

        asyncio.create_task(
            run_quiz_battle_game(
                chat_id=callback.message.chat.id,
                game_id=game.id,
            )
        )

    finally:
        db.close()


async def quiz_battle_answer_callback(callback: CallbackQuery):
    """Save a user's answer for the currently open quiz battle question."""
    parts = callback.data.split(":")

    if len(parts) != 3 or not parts[1].isdigit():
        await callback.answer("Некорректный ответ.", show_alert=True)
        return

    game_question_id = int(parts[1])
    selected_option = parts[2].upper()

    if selected_option not in {"A", "B", "C", "D"}:
        await callback.answer("Некорректный вариант ответа.", show_alert=True)
        return

    db = SessionLocal()

    try:
        game_question = (
            db.query(GroupQuizGameQuestion)
            .filter(GroupQuizGameQuestion.id == game_question_id)
            .first()
        )

        if not game_question:
            await callback.answer("Вопрос не найден.", show_alert=True)
            return

        if game_question.status != "open":
            await callback.answer(
                "Время на этот вопрос уже вышло.",
                show_alert=True,
            )
            return

        user, _ = get_or_create_user(db, callback.from_user)

        existing_answer = (
            db.query(GroupQuizGameAnswer)
            .filter(
                GroupQuizGameAnswer.game_question_id == game_question.id,
                GroupQuizGameAnswer.user_id == user.id,
            )
            .first()
        )

        if existing_answer:
            await callback.answer(
                "Ты уже ответил на этот вопрос.",
                show_alert=True,
            )
            return

        question = game_question.question
        is_correct = selected_option == question.correct_option.upper()
        answer_seconds = None

        if game_question.opened_at:
            opened_at = game_question.opened_at

            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)

            answer_seconds = int(
                (datetime.now(timezone.utc) - opened_at.astimezone(timezone.utc)).total_seconds()
            )

        answer = GroupQuizGameAnswer(
            game_id=game_question.game_id,
            game_question_id=game_question.id,
            quiz_question_id=question.id,
            user_id=user.id,
            telegram_id=callback.from_user.id,
            display_name=user.display_name,
            selected_option=selected_option,
            is_correct=is_correct,
            answer_seconds=answer_seconds,
        )

        db.add(answer)
        db.commit()

        await callback.answer("Ответ принят ✅")

        if callback.message:
            try:
                await callback.message.answer(
                    f"✅ {user.display_name} сделал свой выбор"
                )
            except Exception as notify_error:
                print(f"quiz battle answer notify error: {notify_error}")

    except Exception as error:
        db.rollback()
        print(f"quiz battle answer error: {error}")
        await callback.answer("Не удалось сохранить ответ.", show_alert=True)

    finally:
        db.close()


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

        chat_id = callback.message.chat.id if callback.message else None
        session_id = session.id

    finally:
        db.close()

    if chat_id is not None:
        await finish_group_quiz_if_all_answered(
            chat_id=chat_id,
            session_id=session_id,
        )


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

