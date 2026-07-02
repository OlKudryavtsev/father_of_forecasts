"""Core engine for league-scoped synchronous quizzes.

Version 3.0.1 intentionally implements the reliable common layer first:
question bank, registration, server-side timer, multiple-choice answers and a
separate quiz leaderboard. Text-answer mechanics are modelled in the schema but
will be enabled by later question-type handlers.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    LeagueQuizAdminAction,
    LeagueQuizEvent,
    LeagueQuizQuestion,
    LeagueQuizQuestionAlias,
    LeagueQuizQuestionOption,
    LeagueQuizQuestionSource,
    LeagueQuizScoreEvent,
    LeagueQuizSession,
    LeagueQuizSessionAnswer,
    LeagueQuizSessionParticipant,
    LeagueQuizSessionQuestion,
    LeagueQuizSessionRound,
    User,
)
from app.services.leagues import require_manage_league, require_user_league


QUESTION_TYPES_STAGE_ONE = {"choice_2", "choice_4"}
QUESTION_STATUS_DRAFT = "draft"
QUESTION_STATUS_APPROVED = "approved"
QUESTION_STATUS_ARCHIVED = "archived"

SESSION_REGISTRATION_OPEN = "registration_open"
SESSION_RUNNING = "running"
SESSION_PAUSED = "paused"
SESSION_FINISHED = "finished"
SESSION_CANCELLED = "cancelled"

QUESTION_PENDING = "pending"
QUESTION_OPEN = "open"
QUESTION_REVEALED = "revealed"
QUESTION_CLOSED = "closed"


# A compact, idempotent starter pack for the first usable quiz formats. These
# facts are verified against FIFA match reports current on 2026-07-01. The
# records are intentionally created only after an administrator presses the
# explicit seed action for a particular league.
WC2026_STAGE_ONE_SEED_PREFIX = "seed:wc2026-stage-one:3.0.2"
WC2026_STAGE_ONE_SAMPLE_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "seed_key": "four-options-france-sweden",
        "question_type": "choice_4",
        "question_text": "ЧМ‑2026, 1/16 финала: кто оформил дубль в матче Франция — Швеция (3:0)?",
        "options": ("Килиан Мбаппе", "Брэдли Баркола", "Усман Дембеле", "Антуан Гризманн"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Килиан Мбаппе забил на 45-й и 74-й минутах. Ещё один мяч Франции забил Брэдли Баркола.",
        "source_title": "FIFA: France 3-0 Sweden | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/france-sweden-review-highlights",
    },
    {
        "seed_key": "true-false-brazil-japan",
        "question_type": "choice_2",
        "question_text": "Правда или ложь: Бразилия обыграла Японию 2:1 в 1/16 финала ЧМ‑2026.",
        "options": ("Правда", "Ложь"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Правда. Бразилия победила 2:1; решающий гол в концовке забил Габриэл Мартинелли.",
        "source_title": "FIFA: Brazil 2-1 Japan | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/brazil-japan-review-highlights",
    },
    {
        "seed_key": "more-less-england-congo",
        "question_type": "choice_2",
        "question_text": "Больше или меньше: в матче Англия — ДР Конго (2:1) Харри Кейн забил больше голов, чем Брайан Чипенга.",
        "options": ("Больше", "Меньше"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Больше. Чипенга забил один мяч за ДР Конго, а Кейн ответил дублем на 75-й и 86-й минутах.",
        "source_title": "FIFA: England 2-1 Congo DR | Match report and highlights",
        "source_url": "https://www.fifa.com/en/articles/england-congo-dr-review-highlights",
    },
    {
        "seed_key": "yes-no-morocco-netherlands",
        "question_type": "choice_2",
        "question_text": "Да или нет: Марокко вышло в 1/8 финала ЧМ‑2026, обыграв Нидерланды в серии пенальти.",
        "options": ("Да", "Нет"),
        "correct_index": 0,
        "points": 100,
        "explanation": "Да. Основное время завершилось со счётом 1:1, а в серии пенальти Марокко победило 3:2.",
        "source_title": "FIFA: Netherlands 1-1 Morocco (PSO 2-3)",
        "source_url": "https://www.fifa.com/en/articles/netherlands-morocco-review-highlights",
    },
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_manager(db: Session, user: User, league_id: int) -> bool:
    try:
        require_manage_league(db, user, league_id)
        return True
    except (ValueError, PermissionError):
        return False


def require_quiz_manager(db: Session, user: User, league_id: int):
    """Return an active league only when the user can run its quizzes."""
    return require_manage_league(db, user, league_id)


def _event(db: Session, quiz_session: LeagueQuizSession, event_type: str, payload: dict | None = None) -> None:
    db.add(
        LeagueQuizEvent(
            session_id=quiz_session.id,
            event_type=event_type,
            payload=payload or {},
        )
    )


def _admin_action(
    db: Session,
    quiz_session: LeagueQuizSession,
    actor: User,
    action_type: str,
    payload: dict | None = None,
) -> None:
    db.add(
        LeagueQuizAdminAction(
            session_id=quiz_session.id,
            actor_user_id=actor.id,
            action_type=action_type,
            payload=payload or {},
        )
    )


def _question_type_label(question_type: str) -> str:
    return {
        "choice_2": "Выбор из 2 вариантов",
        "choice_4": "Выбор из 4 вариантов",
    }.get(question_type, question_type)


def _validate_question_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]], int]:
    question_type = str(payload.get("question_type") or "").strip()
    if question_type not in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("В этапе 1 доступны только вопросы с 2 или 4 вариантами")

    text = str(payload.get("question_text") or "").strip()
    if len(text) < 3:
        raise ValueError("Текст вопроса слишком короткий")
    if len(text) > 6000:
        raise ValueError("Текст вопроса слишком длинный")

    options = payload.get("options") or []
    expected = 2 if question_type == "choice_2" else 4
    if not isinstance(options, list) or len(options) != expected:
        raise ValueError(f"Для этого вопроса нужно ровно {expected} варианта ответа")

    clean_options: list[dict[str, Any]] = []
    for index, raw in enumerate(options):
        option_text = str(raw.get("text") if isinstance(raw, dict) else raw or "").strip()
        if not option_text:
            raise ValueError(f"Не заполнен вариант ответа {index + 1}")
        if len(option_text) > 1000:
            raise ValueError(f"Вариант ответа {index + 1} слишком длинный")
        clean_options.append({"option_key": chr(65 + index), "text": option_text})

    correct_index = payload.get("correct_option_index")
    if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= expected:
        raise ValueError("Укажите правильный вариант ответа")

    return question_type, clean_options, correct_index


def seed_wc2026_stage_one_questions(
    db: Session,
    actor: User,
    league_id: int,
) -> dict[str, Any]:
    """Add one approved WC-2026 test question for every implemented choice format.

    The operation is idempotent per league: pressing the button again does not
    duplicate questions. It intentionally does not start a quiz or notify users.
    """
    require_quiz_manager(db, actor, league_id)

    existing_rows = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.tags.like(f"{WC2026_STAGE_ONE_SEED_PREFIX}:%"),
        )
        .all()
    )
    existing_keys = {
        str(question.tags).rsplit(":", 1)[-1]
        for question in existing_rows
        if question.tags
    }

    created: list[LeagueQuizQuestion] = []
    now = utcnow()
    for item in WC2026_STAGE_ONE_SAMPLE_QUESTIONS:
        seed_key = item["seed_key"]
        if seed_key in existing_keys:
            continue

        question = LeagueQuizQuestion(
            league_id=league_id,
            created_by_user_id=actor.id,
            approved_by_user_id=actor.id,
            question_type=item["question_type"],
            status=QUESTION_STATUS_APPROVED,
            question_text=item["question_text"],
            explanation=item["explanation"],
            default_points=int(item["points"]),
            tags=f"{WC2026_STAGE_ONE_SEED_PREFIX}:{seed_key}",
            approved_at=now,
        )
        db.add(question)
        db.flush()

        for index, option_text in enumerate(item["options"], start=1):
            db.add(
                LeagueQuizQuestionOption(
                    question_id=question.id,
                    option_key=chr(64 + index),
                    option_text=option_text,
                    position=index,
                    is_correct=(index - 1) == int(item["correct_index"]),
                )
            )

        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=item["source_title"],
                source_url=item["source_url"],
                source_note="Проверено для тестового набора v3.0.2 1 июля 2026 года.",
            )
        )
        created.append(question)

    db.commit()
    for question in created:
        db.refresh(question)

    return {
        "created": created,
        "created_count": len(created),
        "existing_count": len(WC2026_STAGE_ONE_SAMPLE_QUESTIONS) - len(created),
    }


def create_bank_question(db: Session, actor: User, league_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:
    """Create a draft question in a league-scoped question bank."""
    require_quiz_manager(db, actor, league_id)
    question_type, options, correct_index = _validate_question_payload(payload)

    points = int(payload.get("default_points") or 100)
    if points < 0 or points > 10000:
        raise ValueError("Количество баллов должно быть от 0 до 10 000")

    question = LeagueQuizQuestion(
        league_id=league_id,
        created_by_user_id=actor.id,
        question_type=question_type,
        status=QUESTION_STATUS_DRAFT,
        question_text=str(payload.get("question_text") or "").strip(),
        explanation=(str(payload.get("explanation") or "").strip() or None),
        default_points=points,
        tags=(str(payload.get("tags") or "").strip() or None),
    )
    db.add(question)
    db.flush()

    for index, option in enumerate(options):
        db.add(
            LeagueQuizQuestionOption(
                question_id=question.id,
                option_key=option["option_key"],
                option_text=option["text"],
                position=index + 1,
                is_correct=index == correct_index,
            )
        )

    source_url = str(payload.get("source_url") or "").strip()
    source_title = str(payload.get("source_title") or "").strip()
    if source_url or source_title:
        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=source_title or None,
                source_url=source_url or None,
                source_note=(str(payload.get("source_note") or "").strip() or None),
            )
        )

    db.commit()
    db.refresh(question)
    return question


def approve_bank_question(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:
    require_quiz_manager(db, actor, league_id)
    question = (
        db.query(LeagueQuizQuestion)
        .filter(LeagueQuizQuestion.id == question_id, LeagueQuizQuestion.league_id == league_id)
        .first()
    )
    if not question:
        raise ValueError("Вопрос не найден")
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Архивный вопрос нельзя одобрить")
    question.status = QUESTION_STATUS_APPROVED
    question.approved_at = utcnow()
    question.approved_by_user_id = actor.id
    db.commit()
    db.refresh(question)
    return question


def list_bank_questions(db: Session, actor: User, league_id: int, include_archived: bool = False) -> list[LeagueQuizQuestion]:
    require_quiz_manager(db, actor, league_id)
    query = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id)
    if not include_archived:
        query = query.filter(LeagueQuizQuestion.status != QUESTION_STATUS_ARCHIVED)
    return query.order_by(LeagueQuizQuestion.updated_at.desc(), LeagueQuizQuestion.id.desc()).all()


def _options_snapshot(question: LeagueQuizQuestion) -> list[dict[str, Any]]:
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    return [
        {
            "key": option.option_key,
            "text": option.option_text,
            "is_correct": bool(option.is_correct),
        }
        for option in options
    ]


def create_quiz_session(db: Session, actor: User, payload: dict[str, Any]) -> LeagueQuizSession:
    """Create a scheduled one-round Stage 1 quiz from approved bank questions."""
    league_id = int(payload.get("league_id") or 0)
    require_quiz_manager(db, actor, league_id)

    title = str(payload.get("title") or "").strip()
    if len(title) < 2 or len(title) > 160:
        raise ValueError("Название квиза должно содержать от 2 до 160 символов")

    question_ids = payload.get("question_ids") or []
    if not isinstance(question_ids, list) or not question_ids:
        raise ValueError("Выберите хотя бы один одобренный вопрос")
    if len(question_ids) > 60:
        raise ValueError("В одном квизе этапа 1 может быть не более 60 вопросов")
    normalized_ids = [int(value) for value in question_ids]
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("Один вопрос нельзя добавить в квиз дважды")

    questions = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.id.in_(normalized_ids),
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.status == QUESTION_STATUS_APPROVED,
        )
        .all()
    )
    if len(questions) != len(normalized_ids):
        raise ValueError("Можно использовать только одобренные вопросы текущей лиги")
    by_id = {question.id: question for question in questions}

    seconds_per_question = int(payload.get("seconds_per_question") or 30)
    reveal_seconds = int(payload.get("reveal_seconds") or 12)
    if not 10 <= seconds_per_question <= 300:
        raise ValueError("Время на вопрос должно быть от 10 до 300 секунд")
    if not 3 <= reveal_seconds <= 90:
        raise ValueError("Время показа ответа должно быть от 3 до 90 секунд")

    scheduled_start_at = ensure_utc(payload.get("scheduled_start_at"))
    if scheduled_start_at and scheduled_start_at < utcnow() - timedelta(minutes=1):
        raise ValueError("Нельзя планировать квиз в прошлом")

    quiz_session = LeagueQuizSession(
        league_id=league_id,
        created_by_user_id=actor.id,
        title=title,
        description=(str(payload.get("description") or "").strip() or None),
        status=SESSION_REGISTRATION_OPEN,
        scheduled_start_at=scheduled_start_at,
        registration_opened_at=utcnow(),
        seconds_per_question=seconds_per_question,
        reveal_seconds=reveal_seconds,
        allow_late_registration=bool(payload.get("allow_late_registration", False)),
        rounds_total=1,
    )
    db.add(quiz_session)
    db.flush()

    round_row = LeagueQuizSessionRound(
        session_id=quiz_session.id,
        round_order=1,
        round_type="choice",
        title=(str(payload.get("round_title") or "").strip() or "Раунд с вариантами"),
        status="pending",
        points_mode="positive",
    )
    db.add(round_row)
    db.flush()

    for order, question_id in enumerate(normalized_ids, start=1):
        question = by_id[question_id]
        db.add(
            LeagueQuizSessionQuestion(
                round_id=round_row.id,
                bank_question_id=question.id,
                question_order=order,
                question_type=question.question_type,
                question_text_snapshot=question.question_text,
                explanation_snapshot=question.explanation,
                options_snapshot=_options_snapshot(question),
                points=int(question.default_points or 0),
                negative_on_wrong=False,
                status=QUESTION_PENDING,
            )
        )
        question.last_used_at = utcnow()
        question.times_used = int(question.times_used or 0) + 1

    _event(db, quiz_session, "quiz_created", {"questions_total": len(normalized_ids)})
    _admin_action(db, quiz_session, actor, "quiz_created", {"questions_total": len(normalized_ids)})
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _get_session(db: Session, session_id: int) -> LeagueQuizSession:
    quiz_session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == session_id).first()
    if not quiz_session:
        raise ValueError("Квиз не найден")
    return quiz_session


def _registered_participants(db: Session, session_id: int) -> list[LeagueQuizSessionParticipant]:
    return (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSessionParticipant.joined_at.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )


def register_for_quiz(db: Session, actor: User, session_id: int) -> LeagueQuizSessionParticipant:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)

    if quiz_session.status not in {SESSION_REGISTRATION_OPEN, SESSION_RUNNING}:
        raise ValueError("Регистрация на этот квиз уже закрыта")
    if quiz_session.status == SESSION_RUNNING and not quiz_session.allow_late_registration:
        raise ValueError("Квиз уже начался: позднее подключение отключено")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
        )
        .first()
    )
    if participant:
        participant.status = "registered"
    else:
        participant = LeagueQuizSessionParticipant(
            session_id=quiz_session.id,
            user_id=actor.id,
            status="registered",
            joined_at=utcnow(),
            score_total=0,
        )
        db.add(participant)
    _event(db, quiz_session, "participant_registered", {"user_id": actor.id})
    db.commit()
    db.refresh(participant)
    return participant


def start_quiz_session(db: Session, actor: User, session_id: int, automatic: bool = False) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    if not automatic:
        require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_REGISTRATION_OPEN:
        raise ValueError("Квиз нельзя запустить в текущем состоянии")

    now = utcnow()
    quiz_session.status = SESSION_RUNNING
    quiz_session.started_at = now
    quiz_session.current_round_order = 1
    round_row = (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.round_order == 1)
        .first()
    )
    if not round_row:
        raise ValueError("У квиза отсутствует раунд")
    round_row.status = "running"
    round_row.started_at = now
    _event(db, quiz_session, "quiz_started", {"automatic": bool(automatic)})
    if not automatic:
        _admin_action(db, quiz_session, actor, "quiz_started")
    _open_next_question(db, quiz_session, now)
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def pause_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Поставить на паузу можно только идущий квиз")
    quiz_session.status = SESSION_PAUSED
    quiz_session.paused_at = utcnow()
    _event(db, quiz_session, "quiz_paused")
    _admin_action(db, quiz_session, actor, "quiz_paused")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def resume_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_PAUSED:
        raise ValueError("Продолжить можно только квиз на паузе")
    now = utcnow()
    pause_delta = now - ensure_utc(quiz_session.paused_at or now)
    current = _current_session_question(db, quiz_session.id)
    if current:
        if current.status == QUESTION_OPEN and current.closes_at:
            current.closes_at = ensure_utc(current.closes_at) + pause_delta
        if current.status == QUESTION_REVEALED and current.revealed_until:
            current.revealed_until = ensure_utc(current.revealed_until) + pause_delta
    quiz_session.status = SESSION_RUNNING
    quiz_session.paused_at = None
    _event(db, quiz_session, "quiz_resumed")
    _admin_action(db, quiz_session, actor, "quiz_resumed")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def cancel_quiz_session(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status in {SESSION_FINISHED, SESSION_CANCELLED}:
        raise ValueError("Завершенный квиз нельзя отменить")
    quiz_session.status = SESSION_CANCELLED
    quiz_session.cancelled_at = utcnow()
    _event(db, quiz_session, "quiz_cancelled")
    _admin_action(db, quiz_session, actor, "quiz_cancelled")
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _current_session_question(db: Session, session_id: int) -> LeagueQuizSessionQuestion | None:
    return (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == session_id,
            LeagueQuizSessionQuestion.status.in_([QUESTION_OPEN, QUESTION_REVEALED]),
        )
        .order_by(LeagueQuizSessionQuestion.id.desc())
        .first()
    )


def _open_next_question(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> LeagueQuizSessionQuestion | None:
    next_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == quiz_session.id,
            LeagueQuizSessionQuestion.status == QUESTION_PENDING,
        )
        .order_by(LeagueQuizSessionRound.round_order.asc(), LeagueQuizSessionQuestion.question_order.asc())
        .first()
    )
    if not next_question:
        _finish_quiz(db, quiz_session, now)
        return None

    next_question.status = QUESTION_OPEN
    next_question.opened_at = now
    next_question.closes_at = now + timedelta(seconds=int(quiz_session.seconds_per_question or 30))
    quiz_session.current_question_order = next_question.question_order
    _event(
        db,
        quiz_session,
        "question_opened",
        {"session_question_id": next_question.id, "question_order": next_question.question_order},
    )
    return next_question


def _finish_quiz(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> None:
    if quiz_session.status == SESSION_FINISHED:
        return
    for round_row in db.query(LeagueQuizSessionRound).filter(LeagueQuizSessionRound.session_id == quiz_session.id).all():
        if round_row.status != "finished":
            round_row.status = "finished"
            round_row.finished_at = now
    quiz_session.status = SESSION_FINISHED
    quiz_session.finished_at = now
    _event(db, quiz_session, "quiz_finished")


def _score_question(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion, now: datetime) -> None:
    # Text formats are accepted by the Telegram transport in Stage 2, but their
    # semantic checking belongs to their dedicated round handlers. Do not mark
    # them wrong merely because there is no selected option key.
    if session_question.question_type not in QUESTION_TYPES_STAGE_ONE:
        for answer in (
            db.query(LeagueQuizSessionAnswer)
            .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
            .all()
        ):
            answer.is_correct = None
            answer.points_awarded = 0
            answer.scored_at = now
        return

    correct_keys = {
        str(item.get("key"))
        for item in (session_question.options_snapshot or [])
        if bool(item.get("is_correct"))
    }
    answers = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
        .all()
    )
    for answer in answers:
        is_correct = str(answer.selected_option_key or "") in correct_keys
        points = int(session_question.points or 0) if is_correct else (-int(session_question.points or 0) if session_question.negative_on_wrong else 0)
        answer.is_correct = is_correct
        answer.points_awarded = points
        answer.scored_at = now

        participant = (
            db.query(LeagueQuizSessionParticipant)
            .filter(
                LeagueQuizSessionParticipant.session_id == quiz_session.id,
                LeagueQuizSessionParticipant.user_id == answer.user_id,
            )
            .first()
        )
        if participant:
            participant.score_total = int(participant.score_total or 0) + points
        db.add(
            LeagueQuizScoreEvent(
                session_id=quiz_session.id,
                round_id=session_question.round_id,
                session_question_id=session_question.id,
                user_id=answer.user_id,
                event_type="correct" if is_correct else "incorrect",
                delta_points=points,
                reason="Автоматическая проверка ответа",
                created_at=now,
            )
        )


def close_current_question(
    db: Session,
    quiz_session: LeagueQuizSession,
    now: datetime | None = None,
    actor: User | None = None,
    manual: bool = False,
) -> LeagueQuizSessionQuestion | None:
    now = ensure_utc(now) or utcnow()
    session_question = _current_session_question(db, quiz_session.id)
    if not session_question or session_question.status != QUESTION_OPEN:
        return session_question

    _score_question(db, quiz_session, session_question, now)
    session_question.status = QUESTION_REVEALED
    session_question.closed_at = now
    session_question.revealed_at = now
    session_question.revealed_until = now + timedelta(seconds=int(quiz_session.reveal_seconds or 12))
    _event(
        db,
        quiz_session,
        "question_revealed",
        {"session_question_id": session_question.id, "manual": bool(manual)},
    )
    if actor and manual:
        _admin_action(db, quiz_session, actor, "question_closed_manually", {"session_question_id": session_question.id})
    return session_question


def _all_registered_answered(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion) -> bool:
    participants = _registered_participants(db, quiz_session.id)
    if not participants:
        return False
    participant_ids = {participant.user_id for participant in participants}
    answered_ids = {
        row.user_id
        for row in db.query(LeagueQuizSessionAnswer.user_id)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
        .all()
    }
    return participant_ids.issubset(answered_ids)


def advance_quiz_state(db: Session, quiz_session: LeagueQuizSession, now: datetime | None = None, commit: bool = True) -> LeagueQuizSession:
    """Advance one quiz according to server time; safe to call frequently."""
    now = ensure_utc(now) or utcnow()
    if quiz_session.status == SESSION_REGISTRATION_OPEN:
        starts_at = ensure_utc(quiz_session.scheduled_start_at)
        if starts_at and starts_at <= now:
            # Automatic start does not require a user object and is intentionally
            # allowed even with zero registrations: late registration policy and
            # a visible empty game are preferable to a silently lost schedule.
            quiz_session.status = SESSION_RUNNING
            quiz_session.started_at = now
            quiz_session.current_round_order = 1
            round_row = (
                db.query(LeagueQuizSessionRound)
                .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.round_order == 1)
                .first()
            )
            if round_row:
                round_row.status = "running"
                round_row.started_at = now
            _event(db, quiz_session, "quiz_started", {"automatic": True})
            _open_next_question(db, quiz_session, now)

    if quiz_session.status == SESSION_RUNNING:
        current = _current_session_question(db, quiz_session.id)
        if current and current.status == QUESTION_OPEN:
            closes_at = ensure_utc(current.closes_at)
            if (closes_at and closes_at <= now) or _all_registered_answered(db, quiz_session, current):
                close_current_question(db, quiz_session, now=now)
        elif current and current.status == QUESTION_REVEALED:
            reveal_until = ensure_utc(current.revealed_until)
            if reveal_until and reveal_until <= now:
                current.status = QUESTION_CLOSED
                _open_next_question(db, quiz_session, now)
        elif current is None:
            _open_next_question(db, quiz_session, now)

    if commit:
        db.commit()
        db.refresh(quiz_session)
    return quiz_session


def advance_due_quizzes(db: Session) -> int:
    """Run scheduler tick for all active quiz sessions.

    Railway production currently runs a single web process. Row locks still make
    concurrent calls from a future worker deployment harmless at the session
    level when PostgreSQL is used.
    """
    sessions = (
        db.query(LeagueQuizSession)
        .filter(LeagueQuizSession.status.in_([SESSION_REGISTRATION_OPEN, SESSION_RUNNING]))
        .with_for_update(skip_locked=True)
        .all()
    )
    for quiz_session in sessions:
        advance_quiz_state(db, quiz_session, commit=False)
    if sessions:
        db.commit()
    return len(sessions)


def submit_choice_answer(
    db: Session,
    actor: User,
    session_id: int,
    session_question_id: int,
    selected_option_key: str,
) -> LeagueQuizSessionAnswer:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")

    session_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionQuestion.id == session_question_id,
            LeagueQuizSessionRound.session_id == quiz_session.id,
        )
        .first()
    )
    if not session_question or session_question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if session_question.question_type not in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("Для этого вопроса нужно ввести текстовый ответ")
    if ensure_utc(session_question.closes_at) and ensure_utc(session_question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")

    selected_key = str(selected_option_key or "").upper().strip()
    available_keys = {str(item.get("key")) for item in (session_question.options_snapshot or [])}
    if selected_key not in available_keys:
        raise ValueError("Выберите один из предложенных вариантов")

    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        )
        .first()
    )
    if answer:
        answer.selected_option_key = selected_key
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=session_question.id,
            user_id=actor.id,
            selected_option_key=selected_key,
            answered_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()

    if _all_registered_answered(db, quiz_session, session_question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit()
    db.refresh(answer)
    return answer


def submit_text_answer(
    db: Session,
    actor: User,
    session_id: int,
    session_question_id: int,
    answer_text: str,
) -> LeagueQuizSessionAnswer:
    """Store a Telegram text answer for future text-based round handlers.

    Stage 2 only transports the answer reliably.  Dedicated round handlers will
    later decide whether it is correct and how many points it earns.
    """
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")

    session_question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionQuestion.id == session_question_id,
            LeagueQuizSessionRound.session_id == quiz_session.id,
        )
        .first()
    )
    if not session_question or session_question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if session_question.question_type in QUESTION_TYPES_STAGE_ONE:
        raise ValueError("Для этого вопроса выберите вариант кнопкой")
    if ensure_utc(session_question.closes_at) and ensure_utc(session_question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")

    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")

    cleaned = " ".join(str(answer_text or "").strip().split())
    if not cleaned:
        raise ValueError("Введите ответ текстом")
    if len(cleaned) > 1000:
        raise ValueError("Ответ слишком длинный: максимум 1000 символов")

    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        )
        .first()
    )
    if answer:
        answer.answer_text = cleaned
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=session_question.id,
            user_id=actor.id,
            answer_text=cleaned,
            answered_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()

    if _all_registered_answered(db, quiz_session, session_question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit()
    db.refresh(answer)
    return answer


def manually_close_current_question(db: Session, actor: User, session_id: int) -> LeagueQuizSession:
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не идет")
    close_current_question(db, quiz_session, actor=actor, manual=True)
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _stable_options_for_user(options: list[dict[str, Any]], session_question_id: int, user_id: int) -> list[dict[str, Any]]:
    """Return a stable per-user option order so an answer never jumps on refresh."""
    public = [{"key": item.get("key"), "text": item.get("text")} for item in options]
    seed = hashlib.sha256(f"{session_question_id}:{user_id}".encode("utf-8")).hexdigest()
    random.Random(seed).shuffle(public)
    return public


def get_choice_question_options_for_user(
    session_question: LeagueQuizSessionQuestion,
    user_id: int,
) -> list[dict[str, Any]]:
    """Expose the same stable option order to Telegram and PWA clients."""
    return _stable_options_for_user(session_question.options_snapshot or [], session_question.id, user_id)


def _serialize_session_question(
    db: Session,
    session_question: LeagueQuizSessionQuestion | None,
    user_id: int,
    now: datetime,
) -> dict | None:
    if not session_question:
        return None
    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == user_id,
        )
        .first()
    )
    revealed = session_question.status in {QUESTION_REVEALED, QUESTION_CLOSED}
    raw_options = session_question.options_snapshot or []
    options = _stable_options_for_user(raw_options, session_question.id, user_id)
    if revealed:
        correct_keys = {str(item.get("key")) for item in raw_options if item.get("is_correct")}
        for option in options:
            option["is_correct"] = option["key"] in correct_keys

    deadline = ensure_utc(session_question.closes_at if session_question.status == QUESTION_OPEN else session_question.revealed_until)
    seconds_remaining = max(0, int((deadline - now).total_seconds())) if deadline else 0
    return {
        "id": session_question.id,
        "order": session_question.question_order,
        "type": session_question.question_type,
        "type_label": _question_type_label(session_question.question_type),
        "text": session_question.question_text_snapshot,
        "points": int(session_question.points or 0),
        "status": session_question.status,
        "options": options,
        "answer": {
            "selected_option_key": answer.selected_option_key if answer else None,
            "is_correct": answer.is_correct if revealed and answer else None,
            "points_awarded": answer.points_awarded if revealed and answer else None,
        },
        "explanation": session_question.explanation_snapshot if revealed else None,
        "seconds_remaining": seconds_remaining,
        "timer_seconds": get_question_timer_seconds(
            db.query(LeagueQuizSession).filter(LeagueQuizSession.id == round_row.session_id).first(),
            session_question,
            int(runtime.get("stage") or 1) if session_question.question_type == "countdown" else None,
        ) if round_row else 0,
        "deadline_at": deadline.isoformat() if deadline else None,
    }


def build_quiz_scoreboard(db: Session, session_id: int) -> list[dict[str, Any]]:
    participants = (
        db.query(LeagueQuizSessionParticipant, User)
        .join(User, User.id == LeagueQuizSessionParticipant.user_id)
        .filter(
            LeagueQuizSessionParticipant.session_id == session_id,
            LeagueQuizSessionParticipant.status == "registered",
        )
        .order_by(LeagueQuizSessionParticipant.score_total.desc(), User.display_name.asc(), LeagueQuizSessionParticipant.id.asc())
        .all()
    )
    rows: list[dict[str, Any]] = []
    for index, (participant, user) in enumerate(participants, start=1):
        rows.append(
            {
                "place": index,
                "user_id": user.id,
                "display_name": user.display_name,
                "score_total": int(participant.score_total or 0),
            }
        )
    return rows


def serialize_quiz_summary(db: Session, quiz_session: LeagueQuizSession, user: User) -> dict[str, Any]:
    current = _current_session_question(db, quiz_session.id)
    registered = _registered_participants(db, quiz_session.id)
    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == user.id,
        )
        .first()
    )
    total_questions = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id)
        .count()
    )
    return {
        "id": quiz_session.id,
        "league_id": quiz_session.league_id,
        "title": quiz_session.title,
        "description": quiz_session.description,
        "status": quiz_session.status,
        "scheduled_start_at": ensure_utc(quiz_session.scheduled_start_at).isoformat() if quiz_session.scheduled_start_at else None,
        "started_at": ensure_utc(quiz_session.started_at).isoformat() if quiz_session.started_at else None,
        "finished_at": ensure_utc(quiz_session.finished_at).isoformat() if quiz_session.finished_at else None,
        "seconds_per_question": int(quiz_session.seconds_per_question or 0),
        "reveal_seconds": int(quiz_session.reveal_seconds or 0),
        "registered_count": len(registered),
        "questions_total": total_questions,
        "current_question_order": current.question_order if current else int(quiz_session.current_question_order or 0),
        "is_registered": bool(participant and participant.status == "registered"),
        "my_user_id": user.id,
        "my_score": int(participant.score_total or 0) if participant else 0,
        "can_manage": _is_manager(db, user, quiz_session.league_id),
    }


def build_quiz_detail(db: Session, actor: User, session_id: int) -> dict[str, Any]:
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session)
    current = _current_session_question(db, quiz_session.id)
    summary = serialize_quiz_summary(db, quiz_session, actor)
    return {
        "quiz": summary,
        "current_question": _serialize_session_question(db, current, actor.id, utcnow()),
        "scoreboard": build_quiz_scoreboard(db, quiz_session.id),
        "server_time": utcnow().isoformat(),
    }


def list_quizzes_for_league(db: Session, actor: User, league_id: int) -> list[dict[str, Any]]:
    require_user_league(db, actor, league_id)
    sessions = (
        db.query(LeagueQuizSession)
        .filter(LeagueQuizSession.league_id == league_id)
        .order_by(
            LeagueQuizSession.status.in_([SESSION_RUNNING, SESSION_PAUSED]).desc(),
            LeagueQuizSession.scheduled_start_at.desc().nullslast(),
            LeagueQuizSession.id.desc(),
        )
        .limit(30)
        .all()
    )
    for quiz_session in sessions:
        advance_quiz_state(db, quiz_session, commit=False)
    if sessions:
        db.commit()
    return [serialize_quiz_summary(db, quiz_session, actor) for quiz_session in sessions]


def serialize_bank_question(question: LeagueQuizQuestion, include_correct: bool = True) -> dict[str, Any]:
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    return {
        "id": question.id,
        "question_type": question.question_type,
        "type_label": _question_type_label(question.question_type),
        "status": question.status,
        "question_text": question.question_text,
        "explanation": question.explanation,
        "default_points": int(question.default_points or 0),
        "tags": question.tags,
        "times_used": int(question.times_used or 0),
        "last_used_at": ensure_utc(question.last_used_at).isoformat() if question.last_used_at else None,
        "created_at": ensure_utc(question.created_at).isoformat() if question.created_at else None,
        "options": [
            {
                "key": option.option_key,
                "text": option.option_text,
                "is_correct": bool(option.is_correct) if include_correct else None,
            }
            for option in options
        ],
        "sources": [
            {"title": source.source_title, "url": source.source_url, "note": source.source_note}
            for source in sorted(question.sources, key=lambda item: item.id)
        ],
    }

# =============================================================================
# Stage 3 — complete round handlers (v3.2.0)
# =============================================================================
# The original Stage 1 functions above remain deliberately readable as the
# historical baseline.  The implementations below override their public names
# at module load and extend the same persisted entities without migrating old
# choice-only games.

import re
import unicodedata

CHOICE_QUESTION_TYPES = {"choice_2", "choice_4", "true_false", "more_less", "yes_no"}
TEXT_QUESTION_TYPES = {"jeopardy", "one_of_two", "what_where_when", "countdown", "hundred_to_one"}
QUESTION_TYPES_STAGE_THREE = CHOICE_QUESTION_TYPES | TEXT_QUESTION_TYPES

ROUND_TYPE_TITLES = {
    "millionaire": "Кто хочет стать миллионером?",
    "choice_4": "Кто хочет стать миллионером?",
    "choice_2": "Выбор из двух",
    "true_false": "Правда или ложь",
    "more_less": "Больше или меньше",
    "yes_no": "Да или нет",
    "jeopardy": "Своя игра",
    "one_of_two": "Один из двух",
    "what_where_when": "Что? Где? Когда?",
    "countdown": "Обратный отсчёт",
    "hundred_to_one": "Сто к одному",
}


# Canonical sequence for an automatically assembled full quiz. The backend
# enforces it as well, so the order does not depend on the PWA client.
CANONICAL_ROUND_ORDER = {
    "millionaire": 10,
    "choice_2": 15,
    "true_false": 20,
    "more_less": 30,
    "yes_no": 40,
    "countdown": 50,
    "jeopardy": 60,
    "one_of_two": 70,
    "what_where_when": 80,
    "hundred_to_one": 90,
}

# Timer defaults approved for the game design. Countdown uses a separate
# duration for each clue. A quiz stores a complete editable copy in the DB.
DEFAULT_QUIZ_TIMER_SETTINGS = {
    "choice_4": 30,
    "choice_2": 30,
    "true_false": 30,
    "more_less": 30,
    "yes_no": 30,
    "jeopardy": 60,
    "one_of_two": 60,
    "what_where_when": 90,
    "hundred_to_one": 90,
    "countdown_stage_1": 30,
    "countdown_stage_2": 30,
    "countdown_stage_3": 30,
}


def _normalize_timer_settings(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("timer_settings") or {}
    if not isinstance(raw, dict):
        raise ValueError("Настройки таймеров должны быть объектом")
    settings = dict(DEFAULT_QUIZ_TIMER_SETTINGS)
    # Explicit uniform mode is preserved for a host who deliberately wants the
    # same time everywhere. Legacy clients merely send seconds_per_question and
    # therefore use the differentiated defaults.
    if bool(payload.get("use_uniform_timer")):
        uniform = int(payload.get("seconds_per_question") or 30)
        if not 10 <= uniform <= 300:
            raise ValueError("Время на вопрос должно быть от 10 до 300 секунд")
        settings = {key: uniform for key in settings}
    for key, value in raw.items():
        if key not in settings:
            continue
        seconds = int(value)
        if not 10 <= seconds <= 300:
            raise ValueError("Таймер каждого формата должен быть от 10 до 300 секунд")
        settings[key] = seconds
    return settings


def get_question_timer_seconds(quiz_session: LeagueQuizSession, question: LeagueQuizSessionQuestion | str, stage: int | None = None) -> int:
    question_type = question if isinstance(question, str) else question.question_type
    if question_type == "countdown":
        stage_value = max(1, min(3, int(stage or 1)))
        key = f"countdown_stage_{stage_value}"
    else:
        key = str(question_type or "choice_4")
    settings = _payload_dict(getattr(quiz_session, "timer_settings", None))
    default = DEFAULT_QUIZ_TIMER_SETTINGS.get(key, int(getattr(quiz_session, "seconds_per_question", 30) or 30))
    try:
        value = int(settings.get(key, default))
    except (TypeError, ValueError):
        value = int(default)
    return min(300, max(10, value))


def is_choice_question_type(question_type: str | None) -> bool:
    return str(question_type or "") in CHOICE_QUESTION_TYPES


def _question_type_label(question_type: str) -> str:  # noqa: F811
    return {
        "choice_4": "4 варианта · Миллионер",
        "choice_2": "2 варианта",
        "true_false": "Правда / ложь",
        "more_less": "Больше / меньше",
        "yes_no": "Да / нет",
        "jeopardy": "Своя игра",
        "one_of_two": "Один из двух",
        "what_where_when": "Что? Где? Когда?",
        "countdown": "Обратный отсчёт",
        "hundred_to_one": "Сто к одному",
    }.get(question_type, question_type)


def _round_title(round_type: str) -> str:
    return ROUND_TYPE_TITLES.get(round_type, "Раунд квиза")


def _normalize_text(value: str | None) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "").lower().replace("ё", "е"))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r"[^0-9a-zа-я]+", " ", raw, flags=re.IGNORECASE)
    return " ".join(raw.split())


def _clean_aliases(raw: Any, *, minimum: int = 1, maximum: int = 60) -> list[str]:
    if isinstance(raw, str):
        values = re.split(r"[\n,;]+", raw)
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    clean: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = " ".join(str(item or "").strip().split())
        normalized = _normalize_text(text)
        if not text or not normalized or normalized in seen:
            continue
        if len(text) > 500:
            raise ValueError("Один вариант текстового ответа не может быть длиннее 500 символов")
        clean.append(text)
        seen.add(normalized)
    if len(clean) < minimum:
        raise ValueError("Добавьте хотя бы один допустимый вариант правильного ответа")
    if len(clean) > maximum:
        raise ValueError(f"Слишком много вариантов ответа: максимум {maximum}")
    return clean


def _payload_dict(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _validate_stage_three_question_payload(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]], int | None, dict[str, Any], int]:
    question_type = str(payload.get("question_type") or "").strip()
    if question_type not in QUESTION_TYPES_STAGE_THREE:
        raise ValueError("Неизвестный тип вопроса")

    text = " ".join(str(payload.get("question_text") or "").strip().split())
    if len(text) < 3:
        raise ValueError("Текст вопроса слишком короткий")
    if len(text) > 6000:
        raise ValueError("Текст вопроса слишком длинный")

    raw_config = _payload_dict(payload.get("question_payload"))
    points = int(payload.get("default_points") or 0)
    if points < 0 or points > 10000:
        raise ValueError("Количество баллов должно быть от 0 до 10 000")

    if is_choice_question_type(question_type):
        expected = 4 if question_type == "choice_4" else 2
        options = payload.get("options") or []
        if not isinstance(options, list) or len(options) != expected:
            raise ValueError(f"Для этого формата нужно ровно {expected} варианта ответа")
        clean_options: list[dict[str, Any]] = []
        for index, raw in enumerate(options):
            option_text = str(raw.get("text") if isinstance(raw, dict) else raw or "").strip()
            if not option_text:
                raise ValueError(f"Не заполнен вариант ответа {index + 1}")
            if len(option_text) > 1000:
                raise ValueError(f"Вариант ответа {index + 1} слишком длинный")
            clean_options.append({"option_key": chr(65 + index), "text": option_text})
        correct_index = payload.get("correct_option_index")
        if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= expected:
            raise ValueError("Укажите правильный вариант ответа")
        if points <= 0:
            points = 100
        return question_type, clean_options, correct_index, {}, points

    config: dict[str, Any] = {}
    if question_type == "jeopardy":
        topic = " ".join(str(raw_config.get("topic") or "").strip().split())
        if not topic:
            raise ValueError("Для «Своей игры» укажите тему")
        if len(topic) > 160:
            raise ValueError("Тема «Своей игры» слишком длинная")
        if points not in {100, 200, 300, 400, 500}:
            raise ValueError("Стоимость вопроса «Своей игры» должна быть 100, 200, 300, 400 или 500")
        config = {"topic": topic, "answer_aliases": _clean_aliases(raw_config.get("answer_aliases"))}
    elif question_type == "one_of_two":
        config = {"answer_aliases": _clean_aliases(raw_config.get("answer_aliases"), minimum=2)}
        points = 300
    elif question_type == "what_where_when":
        config = {"answer_aliases": _clean_aliases(raw_config.get("answer_aliases"))}
        points = 500
    elif question_type == "countdown":
        facts_raw = raw_config.get("facts") or raw_config.get("countdown_facts") or []
        if not isinstance(facts_raw, list) or len(facts_raw) != 3:
            raise ValueError("Для «Обратного отсчёта» нужны ровно три факта")
        facts = []
        for index, item in enumerate(facts_raw, start=1):
            fact = " ".join(str(item or "").strip().split())
            if len(fact) < 3:
                raise ValueError(f"Факт {index} слишком короткий")
            if len(fact) > 2000:
                raise ValueError(f"Факт {index} слишком длинный")
            facts.append(fact)
        config = {"facts": facts, "answer_aliases": _clean_aliases(raw_config.get("answer_aliases"))}
        points = 500
    elif question_type == "hundred_to_one":
        answers_raw = raw_config.get("top_answers") or raw_config.get("answers") or []
        if not isinstance(answers_raw, list) or len(answers_raw) != 10:
            raise ValueError("Для «Сто к одному» заполните все десять строк")
        top_answers: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, raw_answer in enumerate(answers_raw, start=1):
            if isinstance(raw_answer, dict):
                primary = " ".join(str(raw_answer.get("answer") or raw_answer.get("text") or "").strip().split())
                aliases = _clean_aliases([primary, *(raw_answer.get("aliases") or [])])
            else:
                primary = " ".join(str(raw_answer or "").strip().split())
                aliases = _clean_aliases([primary])
            norm_primary = _normalize_text(primary)
            if norm_primary in seen:
                raise ValueError("В топ-10 не должно быть одинаковых строк")
            seen.add(norm_primary)
            top_answers.append({"position": index, "answer": primary, "aliases": aliases})
        config = {"top_answers": top_answers}
        points = 1000

    return question_type, [], None, config, points


def _question_payload_snapshot(question: LeagueQuizQuestion) -> dict[str, Any]:
    return _payload_dict(getattr(question, "question_payload", None))


def _options_snapshot(question: LeagueQuizQuestion) -> list[dict[str, Any]]:  # noqa: F811
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    return [
        {"key": option.option_key, "text": option.option_text, "is_correct": bool(option.is_correct)}
        for option in options
    ]


def create_bank_question(db: Session, actor: User, league_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:  # noqa: F811
    require_quiz_manager(db, actor, league_id)
    question_type, options, correct_index, config, points = _validate_stage_three_question_payload(payload)
    question = LeagueQuizQuestion(
        league_id=league_id,
        created_by_user_id=actor.id,
        question_type=question_type,
        status=QUESTION_STATUS_DRAFT,
        question_text=" ".join(str(payload.get("question_text") or "").strip().split()),
        explanation=(str(payload.get("explanation") or "").strip() or None),
        default_points=points,
        tags=(str(payload.get("tags") or "").strip() or None),
        question_payload=config,
    )
    db.add(question)
    db.flush()
    for index, option in enumerate(options):
        db.add(
            LeagueQuizQuestionOption(
                question_id=question.id,
                option_key=option["option_key"],
                option_text=option["text"],
                position=index + 1,
                is_correct=(correct_index is not None and index == correct_index),
            )
        )
    aliases = config.get("answer_aliases") or []
    for alias in aliases:
        db.add(
            LeagueQuizQuestionAlias(
                question_id=question.id,
                alias_text=alias,
                normalized_alias=_normalize_text(alias),
            )
        )
    source_url = str(payload.get("source_url") or "").strip()
    source_title = str(payload.get("source_title") or "").strip()
    if source_url or source_title:
        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=source_title or None,
                source_url=source_url or None,
                source_note=(str(payload.get("source_note") or "").strip() or None),
            )
        )
    db.commit()
    db.refresh(question)
    return question


def _normalize_rounds_payload(payload: dict[str, Any], questions_by_id: dict[int, LeagueQuizQuestion]) -> list[dict[str, Any]]:
    raw_rounds = payload.get("rounds")
    if not raw_rounds:
        legacy_ids = [int(value) for value in (payload.get("question_ids") or [])]
        if not legacy_ids:
            raise ValueError("Выберите хотя бы один одобренный вопрос")
        return [{
            "title": (str(payload.get("round_title") or "").strip() or "Раунд квиза"),
            "round_type": "choice",
            "question_ids": legacy_ids,
        }]
    if not isinstance(raw_rounds, list) or not raw_rounds:
        raise ValueError("Добавьте хотя бы один раунд")
    if len(raw_rounds) > 20:
        raise ValueError("В одном квизе может быть не более 20 раундов")
    result: list[dict[str, Any]] = []
    all_ids: list[int] = []
    for index, raw in enumerate(raw_rounds, start=1):
        if not isinstance(raw, dict):
            raise ValueError("Некорректное описание раунда")
        question_ids = [int(value) for value in (raw.get("question_ids") or [])]
        if not question_ids:
            raise ValueError(f"В раунде {index} нет вопросов")
        title = " ".join(str(raw.get("title") or "").strip().split())
        requested_type = str(raw.get("round_type") or "").strip()
        inferred_types = {questions_by_id[qid].question_type for qid in question_ids if qid in questions_by_id}
        round_type = requested_type or (next(iter(inferred_types)) if len(inferred_types) == 1 else "mixed")
        if round_type == "jeopardy" and any(questions_by_id[qid].question_type != "jeopardy" for qid in question_ids):
            raise ValueError("В раунд «Своя игра» можно добавить только вопросы «Своей игры»")
        result.append({"title": title or _round_title(round_type), "round_type": round_type, "question_ids": question_ids})
        all_ids.extend(question_ids)
    if len(all_ids) > 100:
        raise ValueError("В одном квизе может быть не более 100 вопросов")
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("Один вопрос нельзя добавить в квиз дважды")
    # Stable full-quiz order regardless of bank selection order.
    return [row for _index, row in sorted(
        enumerate(result),
        key=lambda item: (CANONICAL_ROUND_ORDER.get(item[1]["round_type"], 999), item[0]),
    )]


def create_quiz_session(db: Session, actor: User, payload: dict[str, Any]) -> LeagueQuizSession:  # noqa: F811
    league_id = int(payload.get("league_id") or 0)
    require_quiz_manager(db, actor, league_id)
    title = " ".join(str(payload.get("title") or "").strip().split())
    if not 2 <= len(title) <= 160:
        raise ValueError("Название квиза должно содержать от 2 до 160 символов")
    candidate_ids = []
    for raw in (payload.get("rounds") or []):
        if isinstance(raw, dict):
            candidate_ids.extend(int(value) for value in (raw.get("question_ids") or []))
    if not candidate_ids:
        candidate_ids = [int(value) for value in (payload.get("question_ids") or [])]
    if not candidate_ids:
        raise ValueError("Выберите хотя бы один одобренный вопрос")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Один вопрос нельзя добавить в квиз дважды")
    questions = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.id.in_(candidate_ids),
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.status == QUESTION_STATUS_APPROVED,
        ).all()
    )
    if len(questions) != len(candidate_ids):
        raise ValueError("Можно использовать только одобренные вопросы текущей лиги")
    by_id = {question.id: question for question in questions}
    rounds_payload = _normalize_rounds_payload(payload, by_id)
    timer_settings = _normalize_timer_settings(payload)
    # Kept for old API consumers and existing sessions. New game flow reads
    # timer_settings unless the host explicitly selects uniform timing.
    seconds_per_question = int(payload.get("seconds_per_question") or 30)
    reveal_seconds = int(payload.get("reveal_seconds") or 12)
    if not 10 <= seconds_per_question <= 300:
        raise ValueError("Время на вопрос должно быть от 10 до 300 секунд")
    if not 3 <= reveal_seconds <= 90:
        raise ValueError("Время показа ответа должно быть от 3 до 90 секунд")
    scheduled_start_at = ensure_utc(payload.get("scheduled_start_at"))
    if scheduled_start_at and scheduled_start_at < utcnow() - timedelta(minutes=1):
        raise ValueError("Нельзя планировать квиз в прошлом")
    quiz_session = LeagueQuizSession(
        league_id=league_id,
        created_by_user_id=actor.id,
        title=title,
        description=(str(payload.get("description") or "").strip() or None),
        status=SESSION_REGISTRATION_OPEN,
        scheduled_start_at=scheduled_start_at,
        registration_opened_at=utcnow(),
        seconds_per_question=seconds_per_question,
        timer_settings=timer_settings,
        reveal_seconds=reveal_seconds,
        allow_late_registration=bool(payload.get("allow_late_registration", False)),
        rounds_total=len(rounds_payload),
    )
    db.add(quiz_session)
    db.flush()
    total = 0
    for round_order, round_data in enumerate(rounds_payload, start=1):
        round_type = round_data["round_type"]
        row = LeagueQuizSessionRound(
            session_id=quiz_session.id,
            round_order=round_order,
            round_type=round_type,
            title=round_data["title"],
            status="pending",
            points_mode="negative" if round_type == "jeopardy" else "positive",
        )
        db.add(row)
        db.flush()
        for question_order, question_id in enumerate(round_data["question_ids"], start=1):
            question = by_id[question_id]
            db.add(
                LeagueQuizSessionQuestion(
                    round_id=row.id,
                    bank_question_id=question.id,
                    question_order=question_order,
                    question_type=question.question_type,
                    question_text_snapshot=question.question_text,
                    explanation_snapshot=question.explanation,
                    options_snapshot=_options_snapshot(question),
                    payload_snapshot=_question_payload_snapshot(question),
                    runtime_state={},
                    points=int(question.default_points or 0),
                    negative_on_wrong=question.question_type == "jeopardy",
                    status=QUESTION_PENDING,
                )
            )
            question.last_used_at = utcnow()
            question.times_used = int(question.times_used or 0) + 1
            total += 1
    _event(db, quiz_session, "quiz_created", {"questions_total": total, "rounds_total": len(rounds_payload)})
    _admin_action(db, quiz_session, actor, "quiz_created", {"questions_total": total, "rounds_total": len(rounds_payload)})
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _get_round(db: Session, round_id: int) -> LeagueQuizSessionRound | None:
    return db.query(LeagueQuizSessionRound).filter(LeagueQuizSessionRound.id == round_id).first()


def _active_round(db: Session, quiz_session: LeagueQuizSession) -> LeagueQuizSessionRound | None:
    if quiz_session.current_round_order:
        row = (
            db.query(LeagueQuizSessionRound)
            .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.round_order == quiz_session.current_round_order)
            .first()
        )
        if row and row.status == "running":
            return row
    return (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.status == "running")
        .order_by(LeagueQuizSessionRound.round_order.asc())
        .first()
    )


def _next_pending_round(db: Session, quiz_session: LeagueQuizSession) -> LeagueQuizSessionRound | None:
    return (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id, LeagueQuizSessionRound.status == "pending")
        .order_by(LeagueQuizSessionRound.round_order.asc())
        .first()
    )


def _pending_in_round(db: Session, round_row: LeagueQuizSessionRound) -> list[LeagueQuizSessionQuestion]:
    return (
        db.query(LeagueQuizSessionQuestion)
        .filter(LeagueQuizSessionQuestion.round_id == round_row.id, LeagueQuizSessionQuestion.status == QUESTION_PENDING)
        .order_by(LeagueQuizSessionQuestion.question_order.asc())
        .all()
    )


def _start_next_round(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> LeagueQuizSessionQuestion | None:
    round_row = _next_pending_round(db, quiz_session)
    if not round_row:
        _finish_quiz(db, quiz_session, now)
        return None
    round_row.status = "running"
    round_row.started_at = now
    quiz_session.current_round_order = round_row.round_order
    quiz_session.current_question_order = None
    _event(db, quiz_session, "round_started", {"round_id": round_row.id, "round_order": round_row.round_order, "round_type": round_row.round_type, "title": round_row.title})
    if round_row.round_type == "jeopardy":
        return None
    return _open_next_question(db, quiz_session, now)


def _finish_round(db: Session, quiz_session: LeagueQuizSession, round_row: LeagueQuizSessionRound, now: datetime) -> None:
    if round_row.status == "finished":
        return
    round_row.status = "finished"
    round_row.finished_at = now
    _event(db, quiz_session, "round_finished", {"round_id": round_row.id, "round_order": round_row.round_order, "round_type": round_row.round_type, "title": round_row.title})


def _current_session_question(db: Session, session_id: int) -> LeagueQuizSessionQuestion | None:  # noqa: F811
    return (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(
            LeagueQuizSessionRound.session_id == session_id,
            LeagueQuizSessionQuestion.status.in_([QUESTION_OPEN, QUESTION_REVEALED]),
        )
        .order_by(LeagueQuizSessionQuestion.id.desc())
        .first()
    )


def _question_event_payload(
    db: Session,
    quiz_session: LeagueQuizSession,
    question: LeagueQuizSessionQuestion,
    *,
    stage: int | None = None,
) -> dict[str, Any]:
    round_row = _get_round(db, question.round_id)
    resolved_stage = max(1, min(3, int(stage or 1))) if question.question_type == "countdown" else None
    return {
        "session_question_id": question.id,
        "question_order": question.question_order,
        "question_type": question.question_type,
        "points": int(question.points or 0),
        "round_id": question.round_id,
        "round_order": round_row.round_order if round_row else None,
        "round_type": round_row.round_type if round_row else None,
        "round_title": round_row.title if round_row else "Раунд квиза",
        "countdown_stage": resolved_stage,
        # Immutable presentation snapshot: delayed Telegram delivery must still
        # show the original question/stage, never the current state of the DB.
        "display_text": get_question_display_text(question, stage=resolved_stage),
        "timer_seconds": get_question_timer_seconds(quiz_session, question, resolved_stage),
    }


def _open_question(db: Session, quiz_session: LeagueQuizSession, question: LeagueQuizSessionQuestion, now: datetime) -> LeagueQuizSessionQuestion:
    question.status = QUESTION_OPEN
    question.opened_at = now
    stage = 1 if question.question_type == "countdown" else None
    question.runtime_state = {"stage": stage} if stage else {}
    question.closes_at = now + timedelta(seconds=get_question_timer_seconds(quiz_session, question, stage))
    quiz_session.current_question_order = question.question_order
    _event(db, quiz_session, "question_opened", _question_event_payload(db, quiz_session, question, stage=stage))
    return question


def _open_next_question(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> LeagueQuizSessionQuestion | None:  # noqa: F811
    round_row = _active_round(db, quiz_session)
    if not round_row:
        return _start_next_round(db, quiz_session, now)
    pending = _pending_in_round(db, round_row)
    if not pending:
        _finish_round(db, quiz_session, round_row, now)
        return _start_next_round(db, quiz_session, now)
    if round_row.round_type == "jeopardy":
        # In «Своя игра» only the host may select an unopened cell.
        return None
    return _open_question(db, quiz_session, pending[0], now)


def open_jeopardy_question(db: Session, actor: User, session_id: int, session_question_id: int) -> LeagueQuizSession: 
    quiz_session = _get_session(db, session_id)
    require_quiz_manager(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не идет")
    if _current_session_question(db, quiz_session.id):
        raise ValueError("Сначала завершите текущий вопрос")
    round_row = _active_round(db, quiz_session)
    if not round_row or round_row.round_type != "jeopardy":
        raise ValueError("Сейчас не идет раунд «Своя игра»")
    question = (
        db.query(LeagueQuizSessionQuestion)
        .filter(LeagueQuizSessionQuestion.id == session_question_id, LeagueQuizSessionQuestion.round_id == round_row.id)
        .first()
    )
    if not question or question.status != QUESTION_PENDING:
        raise ValueError("Эта ячейка уже сыграна или недоступна")
    _open_question(db, quiz_session, question, utcnow())
    _admin_action(db, quiz_session, actor, "jeopardy_question_selected", {"session_question_id": question.id})
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def _answer_matches_aliases(answer_text: str | None, aliases: list[str], allow_embedded: bool = False) -> bool:
    answer = _normalize_text(answer_text)
    if not answer:
        return False
    normalized_aliases = [_normalize_text(item) for item in aliases]
    if answer in normalized_aliases:
        return True
    if allow_embedded:
        padded = f" {answer} "
        for alias in normalized_aliases:
            if len(alias) >= 4 and f" {alias} " in padded:
                return True
    return False


def _answer_result_for_text_question(question: LeagueQuizSessionQuestion, answer: LeagueQuizSessionAnswer) -> tuple[bool, int, str]:
    config = _payload_dict(getattr(question, "payload_snapshot", None))
    text = answer.answer_text or ""
    qtype = question.question_type
    if qtype == "hundred_to_one":
        for row in config.get("top_answers") or []:
            aliases = row.get("aliases") or [row.get("answer")]
            if _answer_matches_aliases(text, aliases, allow_embedded=True):
                position = int(row.get("position") or 0)
                answer.answer_payload = {**_payload_dict(answer.answer_payload), "position": position}
                return True, position * 100, f"Строка {position} из топ-10"
        return False, 0, "Ответ не вошёл в топ-10"
    aliases = list(config.get("answer_aliases") or [])
    is_correct = _answer_matches_aliases(text, aliases, allow_embedded=(qtype == "one_of_two"))
    if qtype == "countdown":
        stage = int(_payload_dict(answer.answer_payload).get("stage") or 3)
        points = {1: 500, 2: 300, 3: 100}.get(stage, 100) if is_correct else 0
        return is_correct, points, f"Ответ на подсказке {stage}"
    if is_correct:
        return True, int(question.points or 0), "Автоматическая проверка текстового ответа"
    return False, -int(question.points or 0) if question.negative_on_wrong else 0, "Автоматическая проверка текстового ответа"


def _score_question(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion, now: datetime) -> None:  # noqa: F811
    answers = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id)
        .all()
    )
    correct_keys = {
        str(item.get("key")) for item in (session_question.options_snapshot or []) if bool(item.get("is_correct"))
    }
    for answer in answers:
        if answer.scored_at:
            continue
        if is_choice_question_type(session_question.question_type):
            is_correct = str(answer.selected_option_key or "") in correct_keys
            points = int(session_question.points or 0) if is_correct else (-int(session_question.points or 0) if session_question.negative_on_wrong else 0)
            reason = "Автоматическая проверка варианта"
        else:
            is_correct, points, reason = _answer_result_for_text_question(session_question, answer)
        answer.is_correct = is_correct
        answer.points_awarded = points
        answer.scored_at = now
        participant = (
            db.query(LeagueQuizSessionParticipant)
            .filter(LeagueQuizSessionParticipant.session_id == quiz_session.id, LeagueQuizSessionParticipant.user_id == answer.user_id)
            .first()
        )
        if participant:
            participant.score_total = int(participant.score_total or 0) + points
        db.add(
            LeagueQuizScoreEvent(
                session_id=quiz_session.id,
                round_id=session_question.round_id,
                session_question_id=session_question.id,
                user_id=answer.user_id,
                event_type="correct" if is_correct else "incorrect",
                delta_points=points,
                reason=reason,
                created_at=now,
            )
        )


def close_current_question(db: Session, quiz_session: LeagueQuizSession, now: datetime | None = None, actor: User | None = None, manual: bool = False) -> LeagueQuizSessionQuestion | None:  # noqa: F811
    now = ensure_utc(now) or utcnow()
    session_question = _current_session_question(db, quiz_session.id)
    if not session_question or session_question.status != QUESTION_OPEN:
        return session_question
    _score_question(db, quiz_session, session_question, now)
    session_question.status = QUESTION_REVEALED
    session_question.closed_at = now
    session_question.revealed_at = now
    session_question.revealed_until = now + timedelta(seconds=int(quiz_session.reveal_seconds or 12))
    reveal_stage = int(_payload_dict(getattr(session_question, "runtime_state", None)).get("stage") or 1) if session_question.question_type == "countdown" else None
    reveal_payload = _question_event_payload(db, quiz_session, session_question, stage=reveal_stage)
    reveal_payload["manual"] = bool(manual)
    _event(db, quiz_session, "question_revealed", reveal_payload)
    if actor and manual:
        _admin_action(db, quiz_session, actor, "question_closed_manually", {"session_question_id": session_question.id})
    return session_question


def _all_registered_answered(db: Session, quiz_session: LeagueQuizSession, session_question: LeagueQuizSessionQuestion) -> bool:  # noqa: F811
    # The countdown always advances through all three facts.  An early answer
    # intentionally locks only that participant, not the whole question.
    if session_question.question_type == "countdown":
        return False
    participants = _registered_participants(db, quiz_session.id)
    if not participants:
        return False
    participant_ids = {participant.user_id for participant in participants}
    answered_ids = {
        row.user_id for row in db.query(LeagueQuizSessionAnswer.user_id)
        .filter(LeagueQuizSessionAnswer.session_question_id == session_question.id).all()
    }
    return participant_ids.issubset(answered_ids)


def _advance_countdown_stage(db: Session, quiz_session: LeagueQuizSession, question: LeagueQuizSessionQuestion, now: datetime) -> bool:
    runtime = _payload_dict(getattr(question, "runtime_state", None))
    stage = int(runtime.get("stage") or 1)
    if stage >= 3:
        close_current_question(db, quiz_session, now=now)
        return True
    stage += 1
    question.runtime_state = {**runtime, "stage": stage}
    question.closes_at = now + timedelta(seconds=get_question_timer_seconds(quiz_session, question, stage))
    _event(db, quiz_session, "countdown_stage_opened", _question_event_payload(db, quiz_session, question, stage=stage))
    return False


def _start_quiz_rounds(db: Session, quiz_session: LeagueQuizSession, now: datetime) -> None:
    quiz_session.status = SESSION_RUNNING
    quiz_session.started_at = now
    quiz_session.current_round_order = None
    _event(db, quiz_session, "quiz_started", {"automatic": False})
    _start_next_round(db, quiz_session, now)


def start_quiz_session(db: Session, actor: User, session_id: int, automatic: bool = False) -> LeagueQuizSession:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    if not automatic:
        require_quiz_manager(db, actor, quiz_session.league_id)
    if quiz_session.status != SESSION_REGISTRATION_OPEN:
        raise ValueError("Квиз нельзя запустить в текущем состоянии")
    now = utcnow()
    quiz_session.status = SESSION_RUNNING
    quiz_session.started_at = now
    quiz_session.current_round_order = None
    _event(db, quiz_session, "quiz_started", {"automatic": bool(automatic)})
    if not automatic:
        _admin_action(db, quiz_session, actor, "quiz_started")
    _start_next_round(db, quiz_session, now)
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def advance_quiz_state(db: Session, quiz_session: LeagueQuizSession, now: datetime | None = None, commit: bool = True) -> LeagueQuizSession:  # noqa: F811
    now = ensure_utc(now) or utcnow()
    if quiz_session.status == SESSION_REGISTRATION_OPEN:
        starts_at = ensure_utc(quiz_session.scheduled_start_at)
        if starts_at and starts_at <= now:
            quiz_session.status = SESSION_RUNNING
            quiz_session.started_at = now
            quiz_session.current_round_order = None
            _event(db, quiz_session, "quiz_started", {"automatic": True})
            _start_next_round(db, quiz_session, now)
    if quiz_session.status == SESSION_RUNNING:
        current = _current_session_question(db, quiz_session.id)
        if current and current.status == QUESTION_OPEN:
            closes_at = ensure_utc(current.closes_at)
            if current.question_type == "countdown":
                if closes_at and closes_at <= now:
                    _advance_countdown_stage(db, quiz_session, current, now)
            elif (closes_at and closes_at <= now) or _all_registered_answered(db, quiz_session, current):
                close_current_question(db, quiz_session, now=now)
        elif current and current.status == QUESTION_REVEALED:
            reveal_until = ensure_utc(current.revealed_until)
            if reveal_until and reveal_until <= now:
                current.status = QUESTION_CLOSED
                _open_next_question(db, quiz_session, now)
        else:
            round_row = _active_round(db, quiz_session)
            if round_row and round_row.round_type == "jeopardy" and _pending_in_round(db, round_row):
                pass  # Wait for the host to select a board cell.
            else:
                _open_next_question(db, quiz_session, now)
    if commit:
        db.commit()
        db.refresh(quiz_session)
    return quiz_session


def submit_choice_answer(db: Session, actor: User, session_id: int, session_question_id: int, selected_option_key: str) -> LeagueQuizSessionAnswer:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")
    session_question = (
        db.query(LeagueQuizSessionQuestion).join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionQuestion.id == session_question_id, LeagueQuizSessionRound.session_id == quiz_session.id).first()
    )
    if not session_question or session_question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if not is_choice_question_type(session_question.question_type):
        raise ValueError("Для этого вопроса нужно ввести текстовый ответ")
    if ensure_utc(session_question.closes_at) and ensure_utc(session_question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")
    participant = (
        db.query(LeagueQuizSessionParticipant).filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        ).first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")
    selected_key = str(selected_option_key or "").upper().strip()
    available_keys = {str(item.get("key")) for item in (session_question.options_snapshot or [])}
    if selected_key not in available_keys:
        raise ValueError("Выберите один из предложенных вариантов")
    answer = (
        db.query(LeagueQuizSessionAnswer).filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        ).first()
    )
    if answer:
        answer.selected_option_key = selected_key
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=session_question.id, user_id=actor.id,
            selected_option_key=selected_key, answered_at=utcnow(), updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()
    if _all_registered_answered(db, quiz_session, session_question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit(); db.refresh(answer)
    return answer


def submit_text_answer(db: Session, actor: User, session_id: int, session_question_id: int, answer_text: str) -> LeagueQuizSessionAnswer:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status != SESSION_RUNNING:
        raise ValueError("Квиз сейчас не принимает ответы")
    question = (
        db.query(LeagueQuizSessionQuestion).join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionQuestion.id == session_question_id, LeagueQuizSessionRound.session_id == quiz_session.id).first()
    )
    if not question or question.status != QUESTION_OPEN:
        raise ValueError("Этот вопрос уже закрыт")
    if is_choice_question_type(question.question_type):
        raise ValueError("Для этого вопроса выберите вариант кнопкой")
    if ensure_utc(question.closes_at) and ensure_utc(question.closes_at) < utcnow():
        advance_quiz_state(db, quiz_session)
        raise ValueError("Время ответа истекло")
    participant = (
        db.query(LeagueQuizSessionParticipant).filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == actor.id,
            LeagueQuizSessionParticipant.status == "registered",
        ).first()
    )
    if not participant:
        raise ValueError("Сначала зарегистрируйтесь для участия в квизе")
    cleaned = " ".join(str(answer_text or "").strip().split())
    if not cleaned:
        raise ValueError("Введите ответ текстом")
    if len(cleaned) > 1000:
        raise ValueError("Ответ слишком длинный: максимум 1000 символов")
    answer = (
        db.query(LeagueQuizSessionAnswer).filter(
            LeagueQuizSessionAnswer.session_question_id == question.id,
            LeagueQuizSessionAnswer.user_id == actor.id,
        ).first()
    )
    if answer and question.question_type == "countdown":
        raise ValueError("В «Обратном отсчёте» ответ можно отправить только один раз")
    runtime = _payload_dict(getattr(question, "runtime_state", None))
    answer_payload = {"stage": int(runtime.get("stage") or 1), "locked": question.question_type == "countdown"}
    if answer:
        answer.answer_text = cleaned
        answer.answer_payload = answer_payload
        answer.updated_at = utcnow()
    else:
        answer = LeagueQuizSessionAnswer(
            session_question_id=question.id, user_id=actor.id, answer_text=cleaned,
            answer_payload=answer_payload, answered_at=utcnow(), updated_at=utcnow(),
        )
        db.add(answer)
    db.flush()
    if _all_registered_answered(db, quiz_session, question):
        close_current_question(db, quiz_session, now=utcnow())
    db.commit(); db.refresh(answer)
    return answer


def get_question_display_text(question: LeagueQuizSessionQuestion, stage: int | None = None) -> str:
    if question.question_type != "countdown":
        return question.question_text_snapshot
    config = _payload_dict(getattr(question, "payload_snapshot", None))
    runtime = _payload_dict(getattr(question, "runtime_state", None))
    resolved_stage = max(1, min(3, int(stage or runtime.get("stage") or 1)))
    facts = config.get("facts") or []
    fact = facts[resolved_stage - 1] if len(facts) >= resolved_stage else "Подсказка готовится"
    prefix = question.question_text_snapshot.strip()
    return f"{prefix}\n\nПодсказка {resolved_stage}/3:\n{fact}" if prefix else f"Подсказка {resolved_stage}/3:\n{fact}"


def get_correct_answer_text(question: LeagueQuizSessionQuestion) -> str:
    if is_choice_question_type(question.question_type):
        rows = [f"{item.get('key')}. {item.get('text')}" for item in question.options_snapshot or [] if item.get("is_correct")]
        return ", ".join(rows) or "—"
    config = _payload_dict(getattr(question, "payload_snapshot", None))
    if question.question_type == "hundred_to_one":
        rows = []
        for item in config.get("top_answers") or []:
            rows.append(f"{item.get('position')}. {item.get('answer')}")
        return "\n".join(rows) or "—"
    aliases = config.get("answer_aliases") or []
    return str(aliases[0]) if aliases else "—"


def _serialize_session_question(db: Session, session_question: LeagueQuizSessionQuestion | None, user_id: int, now: datetime) -> dict | None:  # noqa: F811
    if not session_question:
        return None
    answer = (
        db.query(LeagueQuizSessionAnswer).filter(
            LeagueQuizSessionAnswer.session_question_id == session_question.id,
            LeagueQuizSessionAnswer.user_id == user_id,
        ).first()
    )
    revealed = session_question.status in {QUESTION_REVEALED, QUESTION_CLOSED}
    raw_options = session_question.options_snapshot or []
    options = _stable_options_for_user(raw_options, session_question.id, user_id) if is_choice_question_type(session_question.question_type) else []
    if revealed:
        correct_keys = {str(item.get("key")) for item in raw_options if item.get("is_correct")}
        for option in options:
            option["is_correct"] = option["key"] in correct_keys
    deadline = ensure_utc(session_question.closes_at if session_question.status == QUESTION_OPEN else session_question.revealed_until)
    seconds_remaining = max(0, int((deadline - now).total_seconds())) if deadline else 0
    runtime = _payload_dict(getattr(session_question, "runtime_state", None))
    config = _payload_dict(getattr(session_question, "payload_snapshot", None))
    round_row = _get_round(db, session_question.round_id)
    answer_payload = _payload_dict(answer.answer_payload) if answer else {}
    return {
        "id": session_question.id,
        "order": session_question.question_order,
        "type": session_question.question_type,
        "type_label": _question_type_label(session_question.question_type),
        "round_type": round_row.round_type if round_row else None,
        "round_title": round_row.title if round_row else None,
        "topic": config.get("topic"),
        "media": config.get("media") or [],
        "text": get_question_display_text(session_question),
        "points": int(session_question.points or 0),
        "status": session_question.status,
        "answer_mode": "choice" if is_choice_question_type(session_question.question_type) else "text",
        "options": options,
        "countdown_stage": int(runtime.get("stage") or 0) if session_question.question_type == "countdown" else None,
        "countdown_total_stages": 3 if session_question.question_type == "countdown" else None,
        "answer": {
            "selected_option_key": answer.selected_option_key if answer else None,
            "answer_text": answer.answer_text if answer else None,
            "is_locked": bool(answer_payload.get("locked")) if answer else False,
            "answer_stage": answer_payload.get("stage") if answer else None,
            "position": answer_payload.get("position") if answer else None,
            "is_correct": answer.is_correct if revealed and answer else None,
            "points_awarded": answer.points_awarded if revealed and answer else None,
        },
        "correct_answer": get_correct_answer_text(session_question) if revealed else None,
        "explanation": session_question.explanation_snapshot if revealed else None,
        "seconds_remaining": seconds_remaining,
        "deadline_at": deadline.isoformat() if deadline else None,
    }


def _serialize_round(db: Session, round_row: LeagueQuizSessionRound, include_board: bool = True) -> dict[str, Any]:
    result = {
        "id": round_row.id,
        "order": round_row.round_order,
        "title": round_row.title,
        "round_type": round_row.round_type,
        "status": round_row.status,
        "points_mode": round_row.points_mode,
    }
    if include_board and round_row.round_type == "jeopardy":
        rows = (
            db.query(LeagueQuizSessionQuestion).filter(LeagueQuizSessionQuestion.round_id == round_row.id)
            .order_by(LeagueQuizSessionQuestion.question_order.asc()).all()
        )
        result["board"] = [
            {
                "id": question.id,
                "topic": _payload_dict(getattr(question, "payload_snapshot", None)).get("topic") or "Тема",
                "points": int(question.points or 0),
                "status": question.status,
                "order": question.question_order,
            }
            for question in rows
        ]
    return result


def serialize_quiz_summary(db: Session, quiz_session: LeagueQuizSession, user: User) -> dict[str, Any]:  # noqa: F811
    current = _current_session_question(db, quiz_session.id)
    registered = _registered_participants(db, quiz_session.id)
    participant = (
        db.query(LeagueQuizSessionParticipant).filter(
            LeagueQuizSessionParticipant.session_id == quiz_session.id,
            LeagueQuizSessionParticipant.user_id == user.id,
        ).first()
    )
    total_questions = (
        db.query(LeagueQuizSessionQuestion).join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id).count()
    )
    active_round = _active_round(db, quiz_session)
    return {
        "id": quiz_session.id, "league_id": quiz_session.league_id, "title": quiz_session.title,
        "description": quiz_session.description, "status": quiz_session.status,
        "scheduled_start_at": ensure_utc(quiz_session.scheduled_start_at).isoformat() if quiz_session.scheduled_start_at else None,
        "started_at": ensure_utc(quiz_session.started_at).isoformat() if quiz_session.started_at else None,
        "finished_at": ensure_utc(quiz_session.finished_at).isoformat() if quiz_session.finished_at else None,
        "seconds_per_question": int(quiz_session.seconds_per_question or 0),
        "timer_settings": _payload_dict(getattr(quiz_session, "timer_settings", None)) or dict(DEFAULT_QUIZ_TIMER_SETTINGS),
        "reveal_seconds": int(quiz_session.reveal_seconds or 0),
        "registered_count": len(registered), "questions_total": total_questions,
        "rounds_total": int(quiz_session.rounds_total or 0),
        "current_round_order": active_round.round_order if active_round else int(quiz_session.current_round_order or 0),
        "current_round_title": active_round.title if active_round else None,
        "current_round_type": active_round.round_type if active_round else None,
        "current_question_order": current.question_order if current else int(quiz_session.current_question_order or 0),
        "is_registered": bool(participant and participant.status == "registered"),
        "my_user_id": user.id, "my_score": int(participant.score_total or 0) if participant else 0,
        "can_manage": _is_manager(db, user, quiz_session.league_id),
    }


def build_quiz_detail(db: Session, actor: User, session_id: int) -> dict[str, Any]:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session)
    current = _current_session_question(db, quiz_session.id)
    rounds = (
        db.query(LeagueQuizSessionRound).filter(LeagueQuizSessionRound.session_id == quiz_session.id)
        .order_by(LeagueQuizSessionRound.round_order.asc()).all()
    )
    return {
        "quiz": serialize_quiz_summary(db, quiz_session, actor),
        "current_question": _serialize_session_question(db, current, actor.id, utcnow()),
        "rounds": [_serialize_round(db, row) for row in rounds],
        "scoreboard": build_quiz_scoreboard(db, quiz_session.id),
        "server_time": utcnow().isoformat(),
    }


def serialize_bank_question(question: LeagueQuizQuestion, include_correct: bool = True) -> dict[str, Any]:  # noqa: F811
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    config = _question_payload_snapshot(question)
    safe_payload = config if include_correct else {key: value for key, value in config.items() if key in {"topic"}}
    return {
        "id": question.id,
        "question_type": question.question_type,
        "type_label": _question_type_label(question.question_type),
        "status": question.status,
        "question_text": question.question_text,
        "explanation": question.explanation,
        "default_points": int(question.default_points or 0),
        "tags": question.tags,
        "times_used": int(question.times_used or 0),
        "question_payload": safe_payload,
        "media": safe_payload.get("media") or [],
        "aliases": [alias.alias_text for alias in sorted(question.aliases, key=lambda item: item.id)],
        "options": [
            {"key": option.option_key, "text": option.option_text, "is_correct": bool(option.is_correct) if include_correct else None}
            for option in options
        ],
        "sources": [
            {"title": source.source_title, "url": source.source_url, "note": source.source_note}
            for source in sorted(question.sources, key=lambda item: item.id)
        ],
    }

# =============================================================================
# v3.4.2 — readiness layer: scoped roles, repeat protection and test runs.
# =============================================================================
from app.services.leagues import (
    is_quiz_admin,
    require_quiz_host,
)


def require_quiz_manager(db: Session, user: User, league_id: int):  # noqa: F811
    """Compatibility name for live-game operations; now requires host rights."""
    return require_quiz_host(db, user, league_id)


def _is_manager(db: Session, user: User, league_id: int) -> bool:  # noqa: F811
    try:
        require_quiz_host(db, user, league_id)
        return True
    except (ValueError, PermissionError):
        return False


def _quiz_test_access_allowed(db: Session, quiz_session: LeagueQuizSession, actor: User) -> bool:
    if not bool(getattr(quiz_session, "is_test_run", False)):
        return True
    if int(getattr(quiz_session, "test_host_user_id", 0) or 0) == int(actor.id):
        return True
    league = quiz_session.league or db.query(League).filter(League.id == quiz_session.league_id).first()
    return bool(league and is_quiz_admin(db, actor, league))


def _enforce_repeat_policy(db: Session, actor: User, league_id: int, questions: list[LeagueQuizQuestion], payload: dict[str, Any]) -> None:
    """Block accidental live reuse while retaining an explicit admin override."""
    if not bool(payload.get("enforce_repeat_policy", True)):
        league = db.query(League).filter(League.id == league_id).first()
        if not league or not is_quiz_admin(db, actor, league):
            raise PermissionError("Отключить защиту от повторов может только администратор лиги")
        return
    now = utcnow()
    blocked: list[str] = []
    for question in questions:
        cooldown_days = max(0, min(365, int(getattr(question, "repeat_after_days", 14) or 0)))
        last_used = ensure_utc(getattr(question, "last_used_at", None))
        if cooldown_days and last_used and last_used + timedelta(days=cooldown_days) > now:
            available_at = (last_used + timedelta(days=cooldown_days)).strftime("%d.%m %H:%M")
            blocked.append(f"#{question.id} до {available_at}")
    if blocked:
        raise ValueError(
            "Защита от повторов не позволяет использовать вопрос слишком рано: "
            + ", ".join(blocked[:5])
            + ". Администратор может создать квиз с отключённой защитой от повторов."
        )


def create_quiz_session(db: Session, actor: User, payload: dict[str, Any]) -> LeagueQuizSession:  # noqa: F811
    league_id = int(payload.get("league_id") or 0)
    require_quiz_host(db, actor, league_id)
    title = " ".join(str(payload.get("title") or "").strip().split())
    if not 2 <= len(title) <= 160:
        raise ValueError("Название квиза должно содержать от 2 до 160 символов")

    candidate_ids: list[int] = []
    for raw in (payload.get("rounds") or []):
        if isinstance(raw, dict):
            candidate_ids.extend(int(value) for value in (raw.get("question_ids") or []))
    if not candidate_ids:
        candidate_ids = [int(value) for value in (payload.get("question_ids") or [])]
    if not candidate_ids:
        raise ValueError("Выберите хотя бы один одобренный вопрос")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Один вопрос нельзя добавить в квиз дважды")

    questions = (
        db.query(LeagueQuizQuestion)
        .filter(
            LeagueQuizQuestion.id.in_(candidate_ids),
            LeagueQuizQuestion.league_id == league_id,
            LeagueQuizQuestion.status == QUESTION_STATUS_APPROVED,
        )
        .all()
    )
    if len(questions) != len(candidate_ids):
        raise ValueError("Можно использовать только одобренные вопросы текущей лиги")
    by_id = {question.id: question for question in questions}
    rounds_payload = _normalize_rounds_payload(payload, by_id)
    is_test_run = bool(payload.get("is_test_run", False))
    if not is_test_run:
        _enforce_repeat_policy(db, actor, league_id, questions, payload)

    timer_settings = _normalize_timer_settings(payload)
    seconds_per_question = int(payload.get("seconds_per_question") or 30)
    reveal_seconds = int(payload.get("reveal_seconds") or 12)
    if not 10 <= seconds_per_question <= 300:
        raise ValueError("Время на вопрос должно быть от 10 до 300 секунд")
    if not 3 <= reveal_seconds <= 90:
        raise ValueError("Время показа ответа должно быть от 3 до 90 секунд")
    scheduled_start_at = ensure_utc(payload.get("scheduled_start_at"))
    if is_test_run:
        # Rehearsals must only be started by their host, never from a stale schedule.
        scheduled_start_at = None
    elif scheduled_start_at and scheduled_start_at < utcnow() - timedelta(minutes=1):
        raise ValueError("Нельзя планировать квиз в прошлом")
    test_chat_id = str(payload.get("test_chat_id") or "").strip() or None
    if test_chat_id and len(test_chat_id) > 80:
        raise ValueError("Идентификатор тестового чата слишком длинный")

    quiz_session = LeagueQuizSession(
        league_id=league_id,
        created_by_user_id=actor.id,
        title=title,
        description=(str(payload.get("description") or "").strip() or None),
        status=SESSION_REGISTRATION_OPEN,
        scheduled_start_at=scheduled_start_at,
        registration_opened_at=utcnow(),
        seconds_per_question=seconds_per_question,
        timer_settings=timer_settings,
        reveal_seconds=reveal_seconds,
        allow_late_registration=bool(payload.get("allow_late_registration", False)) and not is_test_run,
        is_test_run=is_test_run,
        test_host_user_id=actor.id if is_test_run else None,
        test_chat_id=test_chat_id if is_test_run else None,
        rounds_total=len(rounds_payload),
    )
    db.add(quiz_session)
    db.flush()

    total = 0
    for round_order, round_data in enumerate(rounds_payload, start=1):
        round_type = round_data["round_type"]
        row = LeagueQuizSessionRound(
            session_id=quiz_session.id,
            round_order=round_order,
            round_type=round_type,
            title=round_data["title"],
            status="pending",
            points_mode="negative" if round_type == "jeopardy" else "positive",
        )
        db.add(row)
        db.flush()
        for question_order, question_id in enumerate(round_data["question_ids"], start=1):
            question = by_id[question_id]
            db.add(
                LeagueQuizSessionQuestion(
                    round_id=row.id,
                    bank_question_id=question.id,
                    question_order=question_order,
                    question_type=question.question_type,
                    question_text_snapshot=question.question_text,
                    explanation_snapshot=question.explanation,
                    options_snapshot=_options_snapshot(question),
                    payload_snapshot=_question_payload_snapshot(question),
                    runtime_state={},
                    points=int(question.default_points or 0),
                    negative_on_wrong=question.question_type == "jeopardy",
                    status=QUESTION_PENDING,
                )
            )
            if not is_test_run:
                question.last_used_at = utcnow()
                question.times_used = int(question.times_used or 0) + 1
            total += 1

    if is_test_run:
        # Host is the sole rehearsal participant. This makes answers work in
        # PWA and Telegram without exposing the session to league members.
        db.add(
            LeagueQuizSessionParticipant(
                session_id=quiz_session.id,
                user_id=actor.id,
                status="registered",
                score_total=0,
            )
        )
    _event(
        db,
        quiz_session,
        "quiz_created",
        {"questions_total": total, "rounds_total": len(rounds_payload), "is_test_run": is_test_run},
    )
    _admin_action(
        db,
        quiz_session,
        actor,
        "test_run_created" if is_test_run else "quiz_created",
        {"questions_total": total, "rounds_total": len(rounds_payload), "is_test_run": is_test_run},
    )
    db.commit()
    db.refresh(quiz_session)
    return quiz_session


def register_for_quiz(db: Session, actor: User, session_id: int) -> LeagueQuizSessionParticipant:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    if not _quiz_test_access_allowed(db, quiz_session, actor):
        raise PermissionError("Это тестовый прогон: участвовать может только ведущий")
    if bool(getattr(quiz_session, "is_test_run", False)) and quiz_session.test_host_user_id == actor.id:
        row = (
            db.query(LeagueQuizSessionParticipant)
            .filter(LeagueQuizSessionParticipant.session_id == quiz_session.id, LeagueQuizSessionParticipant.user_id == actor.id)
            .first()
        )
        if row:
            return row
    # Original member/register checks are retained for live quizzes.
    require_user_league(db, actor, quiz_session.league_id)
    advance_quiz_state(db, quiz_session, commit=False)
    if quiz_session.status not in {SESSION_REGISTRATION_OPEN, SESSION_RUNNING}:
        raise ValueError("Регистрация на этот квиз уже закрыта")
    if quiz_session.status == SESSION_RUNNING and not quiz_session.allow_late_registration:
        raise ValueError("Квиз уже начался: позднее подключение отключено")
    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(LeagueQuizSessionParticipant.session_id == quiz_session.id, LeagueQuizSessionParticipant.user_id == actor.id)
        .first()
    )
    if participant:
        participant.status = "registered"
    else:
        participant = LeagueQuizSessionParticipant(session_id=quiz_session.id, user_id=actor.id, status="registered")
        db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def list_quizzes_for_league(db: Session, actor: User, league_id: int) -> list[dict[str, Any]]:  # noqa: F811
    league = require_user_league(db, actor, league_id)
    query = db.query(LeagueQuizSession).filter(LeagueQuizSession.league_id == league_id)
    if not is_quiz_admin(db, actor, league):
        query = query.filter(
            (LeagueQuizSession.is_test_run == False) | (LeagueQuizSession.test_host_user_id == actor.id)  # noqa: E712
        )
    sessions = (
        query.order_by(
            LeagueQuizSession.status.in_([SESSION_RUNNING, SESSION_PAUSED]).desc(),
            LeagueQuizSession.scheduled_start_at.desc().nullslast(),
            LeagueQuizSession.id.desc(),
        )
        .limit(30)
        .all()
    )
    for quiz_session in sessions:
        advance_quiz_state(db, quiz_session, commit=False)
    if sessions:
        db.commit()
    return [serialize_quiz_summary(db, quiz_session, actor) for quiz_session in sessions]


# Capture the v3.4.1 serializer before extending it below.
_serialize_quiz_summary_v342_base = serialize_quiz_summary

def serialize_quiz_summary(db: Session, quiz_session: LeagueQuizSession, user: User) -> dict[str, Any]:  # noqa: F811
    data = _serialize_quiz_summary_v342_base(db, quiz_session, user)
    data["is_test_run"] = bool(getattr(quiz_session, "is_test_run", False))
    data["test_host_user_id"] = getattr(quiz_session, "test_host_user_id", None) if data["is_test_run"] else None
    data["is_test_host"] = bool(data["is_test_run"] and int(getattr(quiz_session, "test_host_user_id", 0) or 0) == int(user.id))
    return data


def build_quiz_detail(db: Session, actor: User, session_id: int) -> dict[str, Any]:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    require_user_league(db, actor, quiz_session.league_id)
    if not _quiz_test_access_allowed(db, quiz_session, actor):
        raise PermissionError("Тестовый прогон доступен только ведущему")
    advance_quiz_state(db, quiz_session)
    current = _current_session_question(db, quiz_session.id)
    rounds = (
        db.query(LeagueQuizSessionRound)
        .filter(LeagueQuizSessionRound.session_id == quiz_session.id)
        .order_by(LeagueQuizSessionRound.round_order.asc())
        .all()
    )
    return {
        "quiz": serialize_quiz_summary(db, quiz_session, actor),
        "current_question": _serialize_session_question(db, current, actor.id, utcnow()),
        "rounds": [_serialize_round(db, row) for row in rounds],
        "scoreboard": build_quiz_scoreboard(db, quiz_session.id),
        "server_time": utcnow().isoformat(),
    }


# Preserve the immediately preceding summary implementation as a base before
# its name is overridden. The assignment must happen after the existing v3.4.0
# definition has loaded, therefore it appears at the end of this module.

_submit_choice_answer_v342_base = submit_choice_answer
_submit_text_answer_v342_base = submit_text_answer


def submit_choice_answer(db: Session, actor: User, session_id: int, session_question_id: int, selected_option_key: str) -> LeagueQuizSessionAnswer:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    if not _quiz_test_access_allowed(db, quiz_session, actor):
        raise PermissionError("Тестовый прогон доступен только ведущему")
    return _submit_choice_answer_v342_base(db, actor, session_id, session_question_id, selected_option_key)


def submit_text_answer(db: Session, actor: User, session_id: int, session_question_id: int, answer_text: str) -> LeagueQuizSessionAnswer:  # noqa: F811
    quiz_session = _get_session(db, session_id)
    if not _quiz_test_access_allowed(db, quiz_session, actor):
        raise PermissionError("Тестовый прогон доступен только ведущему")
    return _submit_text_answer_v342_base(db, actor, session_id, session_question_id, answer_text)

# v3.4.2: expose question readiness metadata from the canonical quiz serializer.
_serialize_bank_question_v342_engine_base = serialize_bank_question

def serialize_bank_question(question: LeagueQuizQuestion, include_correct: bool = True) -> dict[str, Any]:  # noqa: F811
    data = _serialize_bank_question_v342_engine_base(question, include_correct=include_correct)
    difficulty_labels = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
    data.update({
        "topics": list(getattr(question, "topics", None) or []),
        "difficulty": getattr(question, "difficulty", None),
        "difficulty_label": difficulty_labels.get(getattr(question, "difficulty", None)),
        "repeat_after_days": int(getattr(question, "repeat_after_days", 14) or 0),
        "last_used_at": question.last_used_at.isoformat() if question.last_used_at else None,
    })
    return data

# Hosts need to browse approved questions for quiz assembly; editors need the
# same list for content work. Editing/approval remains enforced in the content
# service separately.
from app.services.leagues import has_quiz_permission as _has_quiz_permission_v342

def list_bank_questions(db: Session, actor: User, league_id: int, include_archived: bool = False) -> list[LeagueQuizQuestion]:  # noqa: F811
    if not (_has_quiz_permission_v342(db, actor, league_id, "host") or _has_quiz_permission_v342(db, actor, league_id, "editor")):
        raise PermissionError("Недостаточно прав для просмотра банка вопросов")
    query = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id)
    if not include_archived:
        query = query.filter(LeagueQuizQuestion.status != QUESTION_STATUS_ARCHIVED)
    return query.order_by(LeagueQuizQuestion.updated_at.desc(), LeagueQuizQuestion.id.desc()).all()
