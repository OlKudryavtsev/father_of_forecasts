"""Telegram delivery adapter for the league quiz engine.

The quiz engine writes durable ``LeagueQuizEvent`` rows.  This module consumes
those rows from the bot process and records every destination in a separate
ledger, so a deploy/restart cannot duplicate or silently lose quiz messages.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.handlers.miniapp import get_bot_username, get_miniapp_url
from app.keyboards.league_quiz import (
    build_group_quiz_open_keyboard,
    build_private_quiz_question_keyboard,
    build_private_quiz_registration_keyboard,
    build_private_quiz_open_keyboard,
    build_private_quiz_text_keyboard,
)
from app.models import (
    League,
    LeagueMember,
    LeagueQuizEvent,
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizTelegramDelivery,
    User,
)
from app.runtime import APP_TIMEZONE, bot
from app.services.league_quiz import (
    QUESTION_OPEN,
    build_quiz_scoreboard,
    ensure_utc,
    get_choice_question_options_for_user,
    get_correct_answer_text,
    get_question_display_text,
    is_choice_question_type,
)

DELIVERY_DONE_KEY = "event:dispatched"
SUPPORTED_EVENT_TYPES = {
    "quiz_created",
    "quiz_started",
    "question_opened",
    "question_revealed",
    "countdown_stage_opened",
    "round_finished",
    "quiz_finished",
    "quiz_cancelled",
    "quiz_paused",
    "quiz_resumed",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _event_skipped(event: LeagueQuizEvent) -> bool:
    payload = event.payload or {}
    return bool(payload.get("telegram_skip"))


def _delivery_exists(db: Session, event_id: int, destination_key: str) -> bool:
    return bool(
        db.query(LeagueQuizTelegramDelivery.id)
        .filter(
            LeagueQuizTelegramDelivery.event_id == event_id,
            LeagueQuizTelegramDelivery.destination_key == destination_key,
        )
        .first()
    )


def _store_delivery(
    db: Session,
    event: LeagueQuizEvent,
    destination_key: str,
    message_kind: str,
    *,
    recipient_user_id: int | None = None,
    chat_id: str | None = None,
    status: str = "sent",
    error_text: str | None = None,
) -> None:
    if _delivery_exists(db, event.id, destination_key):
        return
    db.add(
        LeagueQuizTelegramDelivery(
            event_id=event.id,
            destination_key=destination_key,
            recipient_user_id=recipient_user_id,
            chat_id=chat_id,
            message_kind=message_kind,
            status=status,
            error_text=error_text,
            delivered_at=_utcnow(),
        )
    )
    db.commit()


async def _send_private(
    db: Session,
    event: LeagueQuizEvent,
    user: User,
    text: str,
    message_kind: str,
    reply_markup=None,
) -> None:
    destination_key = f"user:{user.id}"
    if _delivery_exists(db, event.id, destination_key):
        return
    try:
        await bot.send_message(chat_id=user.telegram_id, text=text, reply_markup=reply_markup)
        _store_delivery(
            db,
            event,
            destination_key,
            message_kind,
            recipient_user_id=user.id,
            chat_id=str(user.telegram_id),
        )
    except Exception as error:
        print(f"League quiz Telegram DM failed: event={event.id} user={user.id} error={error}")
        _store_delivery(
            db,
            event,
            destination_key,
            message_kind,
            recipient_user_id=user.id,
            chat_id=str(user.telegram_id),
            status="failed",
            error_text=str(error)[:2000],
        )


async def _send_group(
    db: Session,
    event: LeagueQuizEvent,
    league: League,
    text: str,
    message_kind: str,
    reply_markup=None,
) -> None:
    chat_id = str(getattr(league, "chat_id", "") or "").strip()
    if not chat_id:
        return
    destination_key = f"chat:{chat_id}"
    if _delivery_exists(db, event.id, destination_key):
        return
    try:
        await bot.send_message(chat_id=int(chat_id), text=text, reply_markup=reply_markup)
        _store_delivery(db, event, destination_key, message_kind, chat_id=chat_id)
    except Exception as error:
        print(f"League quiz Telegram group delivery failed: event={event.id} chat={chat_id} error={error}")
        _store_delivery(
            db,
            event,
            destination_key,
            message_kind,
            chat_id=chat_id,
            status="failed",
            error_text=str(error)[:2000],
        )


def _active_league_users(db: Session, league_id: int) -> list[User]:
    return (
        db.query(User)
        .join(LeagueMember, LeagueMember.user_id == User.id)
        .filter(
            LeagueMember.league_id == league_id,
            LeagueMember.status == "active",
            User.access_status == "approved",
        )
        .order_by(User.display_name.asc(), User.id.asc())
        .all()
    )


def _registered_users(db: Session, session_id: int) -> list[User]:
    return (
        db.query(User)
        .join(LeagueQuizSessionParticipant, LeagueQuizSessionParticipant.user_id == User.id)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(User.display_name.asc(), User.id.asc())
        .all()
    )


def _session_and_league(db: Session, event: LeagueQuizEvent) -> tuple[LeagueQuizSession | None, League | None]:
    quiz_session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == event.session_id).first()
    if not quiz_session:
        return None, None
    league = db.query(League).filter(League.id == quiz_session.league_id).first()
    return quiz_session, league


def _scheduled_text(value) -> str:
    instant = ensure_utc(value)
    if not instant:
        return "Ведущий запустит игру вручную."
    local = instant.astimezone(APP_TIMEZONE).strftime("%d.%m в %H:%M")
    return f"Старт запланирован: {local}."


def _scoreboard_text(db: Session, session_id: int, limit: int = 10) -> str:
    rows = build_quiz_scoreboard(db, session_id)[:limit]
    if not rows:
        return "Пока нет зарегистрированных участников."
    lines = ["🏆 Таблица квиза"]
    for row in rows:
        lines.append(f"{row['place']}. {row['display_name']} — {row['score_total']} очк.")
    return "\n".join(lines)


def _correct_answer_text(question: LeagueQuizSessionQuestion) -> str:
    return get_correct_answer_text(question)


async def _dispatch_quiz_created(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    miniapp_url = get_miniapp_url()
    text = (
        "🧠 Новый квиз в лиге\n\n"
        f"Лига: {league.name}\n"
        f"{quiz.title}\n"
        f"Вопросов: {sum(len(round_row.questions) for round_row in quiz.rounds)}\n"
        f"{_scheduled_text(quiz.scheduled_start_at)}\n\n"
        "Нажми «Участвовать», чтобы войти в состав игроков."
    )
    keyboard = build_private_quiz_registration_keyboard(quiz.id, miniapp_url)
    for user in _active_league_users(db, league.id):
        await _send_private(db, event, user, text, "quiz_announcement", keyboard)

    username = await get_bot_username()
    group_text = (
        "🧠 Квиз объявлен\n\n"
        f"{quiz.title}\n"
        f"Вопросов: {sum(len(round_row.questions) for round_row in quiz.rounds)}\n"
        f"{_scheduled_text(quiz.scheduled_start_at)}\n\n"
        "Участие и ответы — в личном диалоге с ботом или в приложении."
    )
    await _send_group(
        db,
        event,
        league,
        group_text,
        "quiz_announcement",
        build_group_quiz_open_keyboard(username, quiz.id),
    )


async def _dispatch_quiz_started(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    username = await get_bot_username()
    await _send_group(
        db,
        event,
        league,
        f"▶️ Квиз начался\n\n{quiz.title}\n\nВопросы приходят участникам в личку. Удачи!",
        "quiz_started",
        build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть текущий квиз"),
    )


async def _send_question_to_user(
    db: Session,
    event: LeagueQuizEvent,
    quiz: LeagueQuizSession,
    question: LeagueQuizSessionQuestion,
    user: User,
    message_kind: str,
) -> None:
    miniapp_url = get_miniapp_url()
    payload = getattr(question, "runtime_state", None) or {}
    stage = int(payload.get("stage") or 0) if question.question_type == "countdown" else 0
    existing = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == question.id, LeagueQuizSessionAnswer.user_id == user.id)
        .first()
    )
    locked = bool(existing and question.question_type == "countdown")
    stage_line = f" · подсказка {stage}/3" if stage else ""
    text = (
        f"🧠 {quiz.title}\n"
        f"Вопрос {question.question_order}\n"
        f"⏱ На ответ: {quiz.seconds_per_question} сек. · {question.points} очк.{stage_line}\n\n"
        f"{get_question_display_text(question)}\n\n"
        + (
            "Ваш ответ уже зафиксирован. Ждём следующую подсказку."
            if locked
            else ("В «Обратном отсчёте» ответ можно отправить только один раз." if question.question_type == "countdown" else "Ответ можно изменить до закрытия вопроса.")
        )
    )
    if is_choice_question_type(question.question_type):
        options = get_choice_question_options_for_user(question, user.id)
        keyboard = build_private_quiz_question_keyboard(quiz.id, question.id, options, existing.selected_option_key if existing else None, miniapp_url)
    elif locked:
        keyboard = build_private_quiz_open_keyboard(quiz.id, miniapp_url)
    else:
        keyboard = build_private_quiz_text_keyboard(quiz.id, question.id, miniapp_url)
    await _send_private(db, event, user, text, message_kind, keyboard)


async def _dispatch_question_opened(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession) -> None:
    question_id = int((event.payload or {}).get("session_question_id") or 0)
    question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
    if not question or question.status != QUESTION_OPEN:
        return
    for user in _registered_users(db, quiz.id):
        await _send_question_to_user(db, event, quiz, question, user, "quiz_question")


async def _dispatch_countdown_stage_opened(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession) -> None:
    question_id = int((event.payload or {}).get("session_question_id") or 0)
    question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
    if not question or question.status != QUESTION_OPEN:
        return
    for user in _registered_users(db, quiz.id):
        await _send_question_to_user(db, event, quiz, question, user, "quiz_countdown_stage")


async def _dispatch_question_revealed(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    question_id = int((event.payload or {}).get("session_question_id") or 0)
    question = db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.id == question_id).first()
    if not question:
        return
    correct_text = _correct_answer_text(question)
    explanation = f"\n\n{question.explanation_snapshot}" if question.explanation_snapshot else ""

    for user in _registered_users(db, quiz.id):
        answer = (
            db.query(LeagueQuizSessionAnswer)
            .filter(
                LeagueQuizSessionAnswer.session_question_id == question.id,
                LeagueQuizSessionAnswer.user_id == user.id,
            )
            .first()
        )
        if answer and answer.is_correct:
            personal = f"Верно · +{answer.points_awarded or 0} очк."
        elif answer:
            personal = "Пока без очков."
        else:
            personal = "Ответ не получен."
        text = (
            f"✅ Ответ на вопрос {question.question_order}\n\n"
            f"Правильный ответ: {correct_text}\n"
            f"{personal}{explanation}"
        )
        await _send_private(db, event, user, text, "quiz_reveal")

    group_text = (
        f"✅ Квиз · вопрос {question.question_order}\n\n"
        f"Правильный ответ: {correct_text}{explanation}"
    )
    await _send_group(db, event, league, group_text, "quiz_reveal")


async def _dispatch_round_finished(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    payload = event.payload or {}
    title = str(payload.get("title") or "Раунд")
    await _send_group(
        db,
        event,
        league,
        f"📊 Раунд завершён: {title}\n\n{_scoreboard_text(db, quiz.id)}",
        "quiz_round_finished",
    )


async def _dispatch_quiz_finished(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    table = _scoreboard_text(db, quiz.id)
    username = await get_bot_username()
    await _send_group(
        db,
        event,
        league,
        f"🏁 Квиз завершён\n\n{quiz.title}\n\n{table}",
        "quiz_finished",
        build_group_quiz_open_keyboard(username, quiz.id, "🧠 Открыть результаты в приложении"),
    )
    rows = {row["user_id"]: row for row in build_quiz_scoreboard(db, quiz.id)}
    miniapp_url = get_miniapp_url()
    for user in _registered_users(db, quiz.id):
        row = rows.get(user.id)
        result = f"{row['place']}-е место · {row['score_total']} очк." if row else "Результат пока не найден."
        await _send_private(
            db,
            event,
            user,
            f"🏁 {quiz.title} завершён\n\nВаш результат: {result}\n\n{table}",
            "quiz_finished",
            build_private_quiz_open_keyboard(quiz.id, miniapp_url),
        )


async def _dispatch_status_change(db: Session, event: LeagueQuizEvent, quiz: LeagueQuizSession, league: League) -> None:
    labels = {
        "quiz_cancelled": "⛔ Квиз отменён",
        "quiz_paused": "⏸ Квиз поставлен на паузу",
        "quiz_resumed": "▶️ Квиз продолжен",
    }
    label = labels[event.event_type]
    users = _registered_users(db, quiz.id)
    for user in users:
        await _send_private(db, event, user, f"{label}\n\n{quiz.title}", event.event_type)
    await _send_group(db, event, league, f"{label}\n\n{quiz.title}", event.event_type)


async def dispatch_league_quiz_telegram_event(db: Session, event: LeagueQuizEvent) -> None:
    """Deliver one event, then write a completion marker even if a destination fails.

    Each failed send is recorded in the ledger.  We intentionally do not retry
    forever: a blocked bot chat must not keep the whole quiz queue busy.
    """
    if event.event_type not in SUPPORTED_EVENT_TYPES or _event_skipped(event):
        return
    if _delivery_exists(db, event.id, DELIVERY_DONE_KEY):
        return

    quiz, league = _session_and_league(db, event)
    if not quiz or not league:
        _store_delivery(db, event, DELIVERY_DONE_KEY, "event_complete", status="skipped", error_text="Quiz or league not found")
        return

    if event.event_type == "quiz_created":
        await _dispatch_quiz_created(db, event, quiz, league)
    elif event.event_type == "quiz_started":
        await _dispatch_quiz_started(db, event, quiz, league)
    elif event.event_type == "question_opened":
        await _dispatch_question_opened(db, event, quiz)
    elif event.event_type == "question_revealed":
        await _dispatch_question_revealed(db, event, quiz, league)
    elif event.event_type == "countdown_stage_opened":
        await _dispatch_countdown_stage_opened(db, event, quiz)
    elif event.event_type == "round_finished":
        await _dispatch_round_finished(db, event, quiz, league)
    elif event.event_type == "quiz_finished":
        await _dispatch_quiz_finished(db, event, quiz, league)
    elif event.event_type in {"quiz_cancelled", "quiz_paused", "quiz_resumed"}:
        await _dispatch_status_change(db, event, quiz, league)

    _store_delivery(db, event, DELIVERY_DONE_KEY, "event_complete")


async def process_league_quiz_telegram_events(db: Session, limit: int = 40) -> int:
    """Consume undelivered events in chronological order from the bot process."""
    events = (
        db.query(LeagueQuizEvent)
        .filter(LeagueQuizEvent.event_type.in_(SUPPORTED_EVENT_TYPES))
        .order_by(LeagueQuizEvent.id.asc())
        .limit(limit)
        .all()
    )
    processed = 0
    for event in events:
        if _event_skipped(event) or _delivery_exists(db, event.id, DELIVERY_DONE_KEY):
            continue
        try:
            await dispatch_league_quiz_telegram_event(db, event)
            processed += 1
        except Exception as error:
            db.rollback()
            print(f"League quiz Telegram event dispatch failed: event={event.id} error={error}")
    return processed
