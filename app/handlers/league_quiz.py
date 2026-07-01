"""Telegram entry points for the league-scoped quiz (v3.1.0)."""

from __future__ import annotations

import re

from app.handlers.miniapp import get_miniapp_url
from app.keyboards.league_quiz import (
    build_group_quiz_open_keyboard,
    build_private_quiz_open_keyboard,
    build_private_quiz_question_keyboard,
    build_private_quiz_registration_keyboard,
    build_private_quiz_text_keyboard,
)
from app.models import (
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizSessionRound,
)
from app.runtime import CallbackQuery, FSMContext, Message, SessionLocal
from app.services.league_quiz import (
    QUESTION_OPEN,
    QUESTION_TYPES_STAGE_ONE,
    SESSION_REGISTRATION_OPEN,
    SESSION_RUNNING,
    get_choice_question_options_for_user,
    register_for_quiz,
    submit_choice_answer,
    submit_text_answer,
)
from app.services.leagues import get_default_or_first_user_league, get_league_by_chat_id
from app.services.users import get_or_create_user
from app.states import LeagueQuizTextAnswerForm

_START_QUIZ_RE = re.compile(r"^quiz_(\d+)$", re.IGNORECASE)


def extract_quiz_session_id_from_start_text(text: str | None) -> int | None:
    parts = (text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    match = _START_QUIZ_RE.fullmatch(parts[1].strip())
    return int(match.group(1)) if match else None


def _current_question(db, session_id: int) -> LeagueQuizSessionQuestion | None:
    return (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == session_id,
            LeagueQuizSessionQuestion.status == QUESTION_OPEN,
        )
        .order_by(LeagueQuizSessionQuestion.id.desc())
        .first()
    )


def _session_question_text(session: LeagueQuizSession, question: LeagueQuizSessionQuestion) -> str:
    return (
        f"🧠 {session.title}\n"
        f"Вопрос {question.question_order}\n"
        f"⏱ На ответ: {session.seconds_per_question} сек. · {question.points} очк.\n\n"
        f"{question.question_text_snapshot}\n\n"
        "Можно изменить вариант до закрытия вопроса."
    )


async def _send_quiz_lobby(message: Message, session: LeagueQuizSession) -> None:
    miniapp_url = get_miniapp_url()
    if session.status == SESSION_REGISTRATION_OPEN:
        await message.answer(
            f"🧠 {session.title}\n\nРегистрация открыта. Нажми кнопку ниже, чтобы участвовать.",
            reply_markup=build_private_quiz_registration_keyboard(session.id, miniapp_url),
        )
        return
    await message.answer(
        f"🧠 {session.title}\n\nКвиз уже идёт. Открой его в приложении, чтобы увидеть текущий вопрос.",
        reply_markup=build_private_quiz_open_keyboard(session.id, miniapp_url),
    )


async def _send_current_question(message: Message, db, user, session: LeagueQuizSession) -> bool:
    question = _current_question(db, session.id)
    if not question:
        return False
    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == question.id,
            LeagueQuizSessionAnswer.user_id == user.id,
        )
        .first()
    )
    if question.question_type in QUESTION_TYPES_STAGE_ONE:
        options = get_choice_question_options_for_user(question, user.id)
        keyboard = build_private_quiz_question_keyboard(
            session.id,
            question.id,
            options,
            answer.selected_option_key if answer else None,
            get_miniapp_url(),
        )
    else:
        keyboard = build_private_quiz_text_keyboard(session.id, question.id, get_miniapp_url())
    await message.answer(_session_question_text(session, question), reply_markup=keyboard)
    return True


async def league_quiz_handler(message: Message):
    """Show current league quiz from a private chat or its configured group."""
    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, message.from_user)
        league = (
            get_league_by_chat_id(db, message.chat.id)
            if message.chat.type in {"group", "supergroup"}
            else get_default_or_first_user_league(db, user)
        )
        if not league:
            await message.answer("Для квиза нужна активная лига. Открой приложение и выбери или создай лигу.")
            return

        sessions = (
            db.query(LeagueQuizSession)
            .filter(
                LeagueQuizSession.league_id == league.id,
                LeagueQuizSession.status.in_([SESSION_REGISTRATION_OPEN, SESSION_RUNNING, "paused"]),
            )
            .order_by(LeagueQuizSession.status == SESSION_RUNNING, LeagueQuizSession.id.desc())
            .all()
        )
        if not sessions:
            await message.answer(f"🧠 В лиге «{league.name}» сейчас нет активного квиза.")
            return

        for session in sessions[:3]:
            if message.chat.type in {"group", "supergroup"}:
                from app.handlers.miniapp import get_bot_username
                username = await get_bot_username()
                await message.answer(
                    f"🧠 {session.title}\nСтатус: {session.status}\n\nУчастие и ответы — в личном диалоге с ботом или в приложении.",
                    reply_markup=build_group_quiz_open_keyboard(username, session.id),
                )
                continue

            participant = (
                db.query(LeagueQuizSessionParticipant)
                .filter(
                    LeagueQuizSessionParticipant.session_id == session.id,
                    LeagueQuizSessionParticipant.user_id == user.id,
                    LeagueQuizSessionParticipant.status == "registered",
                )
                .first()
            )
            if session.status == SESSION_RUNNING and participant and await _send_current_question(message, db, user, session):
                continue
            await _send_quiz_lobby(message, session)
    finally:
        db.close()


async def league_quiz_register_callback(callback: CallbackQuery):
    try:
        session_id = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Некорректная кнопка квиза.", show_alert=True)
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, callback.from_user)
        participant = register_for_quiz(db, user, session_id)
        session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == session_id).first()
        await callback.answer("Вы зарегистрированы!", show_alert=False)
        if callback.message:
            try:
                await callback.message.edit_text(
                    f"✅ Вы зарегистрированы на квиз\n\n{session.title}\n\nЖдём старта игры.",
                    reply_markup=build_private_quiz_open_keyboard(session.id, get_miniapp_url()),
                )
            except Exception:
                pass
        if session and session.status == SESSION_RUNNING and callback.message:
            await _send_current_question(callback.message, db, user, session)
    except (ValueError, PermissionError) as error:
        await callback.answer(str(error), show_alert=True)
    finally:
        db.close()


async def league_quiz_answer_callback(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный ответ.", show_alert=True)
        return
    try:
        _prefix, session_id_raw, question_id_raw, option_key = parts
        session_id = int(session_id_raw)
        question_id = int(question_id_raw)
    except ValueError:
        await callback.answer("Некорректный ответ.", show_alert=True)
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, callback.from_user)
        answer = submit_choice_answer(db, user, session_id, question_id, option_key)
        session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == session_id).first()
        question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
        await callback.answer("Ответ принят. Его можно изменить до закрытия вопроса.")
        if callback.message and session and question and question.status == QUESTION_OPEN:
            try:
                options = get_choice_question_options_for_user(question, user.id)
                await callback.message.edit_reply_markup(
                    reply_markup=build_private_quiz_question_keyboard(
                        session_id,
                        question_id,
                        options,
                        answer.selected_option_key,
                        get_miniapp_url(),
                    )
                )
            except Exception:
                pass
    except (ValueError, PermissionError) as error:
        await callback.answer(str(error), show_alert=True)
    finally:
        db.close()


async def league_quiz_text_callback(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Некорректная кнопка.", show_alert=True)
        return
    try:
        _prefix, session_id_raw, question_id_raw = parts
        session_id = int(session_id_raw)
        question_id = int(question_id_raw)
    except ValueError:
        await callback.answer("Некорректная кнопка.", show_alert=True)
        return

    await state.set_state(LeagueQuizTextAnswerForm.waiting_for_answer)
    await state.update_data(league_quiz_session_id=session_id, league_quiz_question_id=question_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer("✍️ Пришли ответ следующим сообщением. Он будет сохранён до закрытия вопроса.")


async def league_quiz_text_answer_message(message: Message, state: FSMContext):
    data = await state.get_data()
    session_id = int(data.get("league_quiz_session_id") or 0)
    question_id = int(data.get("league_quiz_question_id") or 0)
    await state.clear()
    if not session_id or not question_id:
        await message.answer("Не удалось определить вопрос. Открой квиз заново.")
        return

    db = SessionLocal()
    try:
        user, _ = get_or_create_user(db, message.from_user)
        submit_text_answer(db, user, session_id, question_id, message.text or "")
        await message.answer("✅ Текстовый ответ принят. Чтобы изменить его до закрытия вопроса, снова нажми «Ввести ответ».")
    except (ValueError, PermissionError) as error:
        await message.answer(f"Ответ не принят: {error}")
    finally:
        db.close()
