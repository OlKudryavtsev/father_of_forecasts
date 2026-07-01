"""Stage 4 content-quality tools for the league quiz platform.

This module deliberately keeps authoring and manual-review operations separate
from the live QuizEngine. Scheduled quiz questions remain immutable snapshots;
editing the bank only changes future sessions.
"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import (
    LeagueQuizAdminAction,
    LeagueQuizAnswerReview,
    LeagueQuizQuestion,
    LeagueQuizQuestionAlias,
    LeagueQuizQuestionAudit,
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
from app.services.league_quiz import (
    QUESTION_CLOSED,
    QUESTION_REVEALED,
    QUESTION_STATUS_APPROVED,
    QUESTION_STATUS_ARCHIVED,
    QUESTION_STATUS_DRAFT,
    _normalize_text,
    _question_payload_snapshot,
    _validate_stage_three_question_payload,
    require_quiz_manager,
    serialize_bank_question,
    utcnow,
)


WC2026_STAGE_FOUR_SEED_PREFIX = "seed:wc2026-stage-four:3.3.0"


def _clean_string(value: Any, limit: int, label: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) > limit:
        raise ValueError(f"{label} слишком длинный")
    return text


def _validate_url(value: Any, label: str = "Ссылка") -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError(f"{label} должна начинаться с http:// или https://")
    if len(url) > 2000:
        raise ValueError(f"{label} слишком длинная")
    return url


def _clean_sources(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_sources = payload.get("sources")
    if raw_sources is None:
        raw_sources = []
        if payload.get("source_title") or payload.get("source_url") or payload.get("source_note"):
            raw_sources.append({
                "title": payload.get("source_title"),
                "url": payload.get("source_url"),
                "note": payload.get("source_note"),
            })
    if not isinstance(raw_sources, list):
        raise ValueError("Источники должны быть списком")
    if len(raw_sources) > 10:
        raise ValueError("Можно добавить не более 10 источников")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_sources:
        if not isinstance(item, dict):
            raise ValueError("Некорректный источник")
        title = _clean_string(item.get("title"), 500, "Название источника")
        url = _validate_url(item.get("url"), "Ссылка на источник")
        note = _clean_string(item.get("note"), 6000, "Комментарий к источнику")
        if not title and not url and not note:
            continue
        key = f"{title}|{url}|{note}"
        if key in seen:
            continue
        seen.add(key)
        result.append({"title": title, "url": url, "note": note})
    return result


def _clean_media(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_config = payload.get("question_payload") if isinstance(payload.get("question_payload"), dict) else {}
    raw_media = payload.get("media", raw_config.get("media", []))
    if raw_media is None:
        return []
    if not isinstance(raw_media, list):
        raise ValueError("Медиа должны быть списком")
    if len(raw_media) > 3:
        raise ValueError("Для одного вопроса доступно не более 3 медиа")
    result: list[dict[str, str]] = []
    for item in raw_media:
        if not isinstance(item, dict):
            raise ValueError("Некорректное медиа")
        kind = str(item.get("kind") or "image").strip().lower()
        if kind != "image":
            raise ValueError("В этой версии поддерживаются только изображения по URL")
        url = _validate_url(item.get("url"), "Ссылка на изображение")
        if not url:
            raise ValueError("Укажите ссылку на изображение")
        caption = _clean_string(item.get("caption"), 500, "Подпись к изображению")
        result.append({"kind": "image", "url": url, "caption": caption})
    return result


def _question_snapshot(question: LeagueQuizQuestion) -> dict[str, Any]:
    return copy.deepcopy(serialize_bank_question(question, include_correct=True))


def _audit(
    db: Session,
    *,
    question: LeagueQuizQuestion,
    actor: User,
    action_type: str,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> None:
    db.add(
        LeagueQuizQuestionAudit(
            question_id=question.id,
            league_id=question.league_id,
            actor_user_id=actor.id,
            action_type=action_type,
            before_snapshot=before,
            after_snapshot=after,
            note=note or None,
        )
    )


def _write_question_content(
    db: Session,
    question: LeagueQuizQuestion,
    payload: dict[str, Any],
) -> None:
    question_type, options, correct_index, config, points = _validate_stage_three_question_payload(payload)
    media = _clean_media(payload)
    sources = _clean_sources(payload)
    if media:
        config = {**config, "media": media}
    question.question_type = question_type
    question.question_text = " ".join(str(payload.get("question_text") or "").strip().split())
    question.explanation = (str(payload.get("explanation") or "").strip() or None)
    question.default_points = int(points)
    question.tags = (str(payload.get("tags") or "").strip() or None)
    question.question_payload = config

    for row in list(question.options):
        db.delete(row)
    for row in list(question.aliases):
        db.delete(row)
    for row in list(question.sources):
        db.delete(row)
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
    for alias in config.get("answer_aliases") or []:
        db.add(
            LeagueQuizQuestionAlias(
                question_id=question.id,
                alias_text=alias,
                normalized_alias=_normalize_text(alias),
            )
        )
    for item in sources:
        db.add(
            LeagueQuizQuestionSource(
                question_id=question.id,
                source_title=item["title"] or None,
                source_url=item["url"] or None,
                source_note=item["note"] or None,
            )
        )


def create_bank_question_v4(db: Session, actor: User, league_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:
    require_quiz_manager(db, actor, league_id)
    question = LeagueQuizQuestion(
        league_id=league_id,
        created_by_user_id=actor.id,
        question_type="choice_4",
        status=QUESTION_STATUS_DRAFT,
        question_text="Черновик",
        default_points=100,
        question_payload={},
    )
    db.add(question)
    db.flush()
    _write_question_content(db, question, payload)
    db.flush()
    _audit(db, question=question, actor=actor, action_type="created", after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def get_bank_question_v4(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:
    require_quiz_manager(db, actor, league_id)
    question = (
        db.query(LeagueQuizQuestion)
        .filter(LeagueQuizQuestion.id == question_id, LeagueQuizQuestion.league_id == league_id)
        .first()
    )
    if not question:
        raise ValueError("Вопрос не найден")
    return question


def update_bank_question_v4(
    db: Session,
    actor: User,
    league_id: int,
    question_id: int,
    payload: dict[str, Any],
) -> LeagueQuizQuestion:
    question = get_bank_question_v4(db, actor, league_id, question_id)
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Сначала восстановите вопрос из архива")
    before = _question_snapshot(question)
    _write_question_content(db, question, payload)
    if question.status == QUESTION_STATUS_APPROVED:
        question.status = QUESTION_STATUS_DRAFT
        question.approved_at = None
        question.approved_by_user_id = None
    db.flush()
    _audit(db, question=question, actor=actor, action_type="updated", before=before, after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def set_bank_question_status_v4(
    db: Session,
    actor: User,
    league_id: int,
    question_id: int,
    status: str,
) -> LeagueQuizQuestion:
    question = get_bank_question_v4(db, actor, league_id, question_id)
    before = _question_snapshot(question)
    if status == QUESTION_STATUS_ARCHIVED:
        question.status = QUESTION_STATUS_ARCHIVED
        action = "archived"
    elif status == QUESTION_STATUS_DRAFT:
        question.status = QUESTION_STATUS_DRAFT
        question.approved_at = None
        question.approved_by_user_id = None
        action = "restored_to_draft"
    else:
        raise ValueError("Недопустимый статус вопроса")
    db.flush()
    _audit(db, question=question, actor=actor, action_type=action, before=before, after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def approve_bank_question_v4(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:
    question = get_bank_question_v4(db, actor, league_id, question_id)
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Архивный вопрос нельзя одобрить")
    before = _question_snapshot(question)
    question.status = QUESTION_STATUS_APPROVED
    question.approved_at = utcnow()
    question.approved_by_user_id = actor.id
    db.flush()
    _audit(db, question=question, actor=actor, action_type="approved", before=before, after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def question_history_v4(db: Session, actor: User, league_id: int, question_id: int) -> list[dict[str, Any]]:
    get_bank_question_v4(db, actor, league_id, question_id)
    rows = (
        db.query(LeagueQuizQuestionAudit)
        .filter(LeagueQuizQuestionAudit.question_id == question_id)
        .order_by(LeagueQuizQuestionAudit.created_at.desc(), LeagueQuizQuestionAudit.id.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "action_type": row.action_type,
            "actor_user_id": row.actor_user_id,
            "actor_name": row.actor.display_name if getattr(row, "actor", None) and row.actor.display_name else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "note": row.note,
            "before": row.before_snapshot,
            "after": row.after_snapshot,
        }
        for row in rows
    ]


def export_bank_v4(db: Session, actor: User, league_id: int) -> list[dict[str, Any]]:
    require_quiz_manager(db, actor, league_id)
    rows = (
        db.query(LeagueQuizQuestion)
        .filter(LeagueQuizQuestion.league_id == league_id)
        .order_by(LeagueQuizQuestion.id.asc())
        .all()
    )
    result: list[dict[str, Any]] = []
    for question in rows:
        data = serialize_bank_question(question, include_correct=True)
        data.pop("id", None)
        data.pop("times_used", None)
        data.pop("status", None)
        data.pop("type_label", None)
        payload = dict(data.get("question_payload") or {})
        data["question_payload"] = payload
        data["sources"] = data.get("sources") or []
        data["media"] = payload.get("media") or []
        if question.question_type in {"choice_2", "choice_4", "true_false", "more_less", "yes_no"}:
            for index, option in enumerate(data.get("options") or []):
                if option.get("is_correct"):
                    data["correct_option_index"] = index
                    break
        result.append(data)
    return result


def import_bank_v4(db: Session, actor: User, league_id: int, questions: list[dict[str, Any]]) -> dict[str, Any]:
    require_quiz_manager(db, actor, league_id)
    if not questions:
        raise ValueError("Файл импорта не содержит вопросов")
    if len(questions) > 100:
        raise ValueError("За один импорт можно добавить не более 100 вопросов")
    created: list[LeagueQuizQuestion] = []
    for raw in questions:
        if not isinstance(raw, dict):
            raise ValueError("Каждый импортируемый вопрос должен быть объектом")
        payload = dict(raw)
        if not payload.get("sources") and raw.get("source_url"):
            payload["sources"] = [{"title": raw.get("source_title"), "url": raw.get("source_url"), "note": raw.get("source_note")}]
        question = LeagueQuizQuestion(
            league_id=league_id,
            created_by_user_id=actor.id,
            question_type="choice_4",
            status=QUESTION_STATUS_DRAFT,
            question_text="Черновик",
            default_points=100,
            question_payload={},
        )
        db.add(question)
        db.flush()
        _write_question_content(db, question, payload)
        db.flush()
        _audit(db, question=question, actor=actor, action_type="imported", after=_question_snapshot(question))
        created.append(question)
    db.commit()
    return {"created_count": len(created), "questions": created}


def _session_question_for_review(db: Session, session_id: int, session_question_id: int) -> tuple[LeagueQuizSession, LeagueQuizSessionQuestion]:
    session = db.query(LeagueQuizSession).filter(LeagueQuizSession.id == session_id).first()
    if not session:
        raise ValueError("Квиз не найден")
    question = (
        db.query(LeagueQuizSessionQuestion)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .filter(LeagueQuizSessionQuestion.id == session_question_id, LeagueQuizSessionRound.session_id == session.id)
        .first()
    )
    if not question:
        raise ValueError("Вопрос квиза не найден")
    return session, question


def list_answer_reviews_v4(db: Session, actor: User, session_id: int, session_question_id: int) -> list[dict[str, Any]]:
    session, question = _session_question_for_review(db, session_id, session_question_id)
    require_quiz_manager(db, actor, session.league_id)
    if question.status not in {QUESTION_REVEALED, QUESTION_CLOSED}:
        raise ValueError("Проверять ответы можно после закрытия вопроса")
    rows = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.session_question_id == question.id)
        .order_by(LeagueQuizSessionAnswer.answered_at.asc(), LeagueQuizSessionAnswer.id.asc())
        .all()
    )
    review_map = {}
    reviews = (
        db.query(LeagueQuizAnswerReview)
        .filter(LeagueQuizAnswerReview.session_question_id == question.id)
        .order_by(LeagueQuizAnswerReview.created_at.desc(), LeagueQuizAnswerReview.id.desc())
        .all()
    )
    for review in reviews:
        review_map.setdefault(review.answer_id, review)
    result = []
    for answer in rows:
        review = review_map.get(answer.id)
        result.append({
            "answer_id": answer.id,
            "user_id": answer.user_id,
            "display_name": answer.user.display_name if answer.user and answer.user.display_name else f"Игрок {answer.user_id}",
            "selected_option_key": answer.selected_option_key,
            "answer_text": answer.answer_text,
            "is_correct": answer.is_correct,
            "points_awarded": int(answer.points_awarded or 0),
            "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
            "manual_review": ({
                "decision": review.decision,
                "reason": review.reason,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            } if review else None),
        })
    return result


def review_answer_v4(
    db: Session,
    actor: User,
    session_id: int,
    session_question_id: int,
    answer_id: int,
    accepted: bool,
    reason: str,
) -> LeagueQuizSessionAnswer:
    session, question = _session_question_for_review(db, session_id, session_question_id)
    require_quiz_manager(db, actor, session.league_id)
    if question.status not in {QUESTION_REVEALED, QUESTION_CLOSED}:
        raise ValueError("Проверять ответы можно после закрытия вопроса")
    clean_reason = _clean_string(reason, 2000, "Комментарий")
    if not clean_reason:
        raise ValueError("Для ручного решения укажите комментарий")
    answer = (
        db.query(LeagueQuizSessionAnswer)
        .filter(LeagueQuizSessionAnswer.id == answer_id, LeagueQuizSessionAnswer.session_question_id == question.id)
        .first()
    )
    if not answer:
        raise ValueError("Ответ не найден")
    previous_correct = answer.is_correct
    previous_points = int(answer.points_awarded or 0)
    new_points = int(question.points or 0) if accepted else (-int(question.points or 0) if question.negative_on_wrong else 0)
    delta = new_points - previous_points
    answer.is_correct = bool(accepted)
    answer.points_awarded = new_points
    answer.scored_at = utcnow()
    existing_payload = dict(answer.answer_payload or {})
    existing_payload["manual_review"] = {"accepted": bool(accepted), "reason": clean_reason, "actor_user_id": actor.id}
    answer.answer_payload = existing_payload
    participant = (
        db.query(LeagueQuizSessionParticipant)
        .filter(LeagueQuizSessionParticipant.session_id == session.id, LeagueQuizSessionParticipant.user_id == answer.user_id)
        .first()
    )
    if participant:
        participant.score_total = int(participant.score_total or 0) + delta
    db.add(
        LeagueQuizScoreEvent(
            session_id=session.id,
            round_id=question.round_id,
            session_question_id=question.id,
            user_id=answer.user_id,
            event_type="manual_review",
            delta_points=delta,
            reason=clean_reason,
            created_at=utcnow(),
        )
    )
    db.add(
        LeagueQuizAnswerReview(
            session_id=session.id,
            session_question_id=question.id,
            answer_id=answer.id,
            actor_user_id=actor.id,
            decision="accepted" if accepted else "rejected",
            previous_is_correct=previous_correct,
            previous_points=previous_points,
            new_is_correct=bool(accepted),
            new_points=new_points,
            reason=clean_reason,
        )
    )
    db.add(
        LeagueQuizAdminAction(
            session_id=session.id,
            actor_user_id=actor.id,
            action_type="answer_manually_reviewed",
            payload={"session_question_id": question.id, "answer_id": answer.id, "accepted": bool(accepted), "delta_points": delta, "reason": clean_reason},
        )
    )
    db.commit()
    db.refresh(answer)
    return answer


WC2026_STAGE_FOUR_SAMPLE_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "seed_key": "choice4-martinelli",
        "question_type": "choice_4",
        "question_text": "ЧМ‑2026, 1/16 финала: кто забил победный мяч Бразилии в матче с Японией (2:1)?",
        "options": [{"text": "Габриэл Мартинелли"}, {"text": "Каземиро"}, {"text": "Винисиус Жуниор"}, {"text": "Матеус Кунья"}],
        "correct_option_index": 0,
        "default_points": 100,
        "explanation": "Габриэл Мартинелли забил решающий мяч в концовке и вывел Бразилию в 1/8 финала.",
        "sources": [{"title": "FIFA: Brazil 2-1 Japan | Match report and highlights", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/brazil-japan-review-highlights", "note": "Проверено 2 июля 2026 года."}],
    },
    {
        "seed_key": "true-false-france",
        "question_type": "true_false",
        "question_text": "Правда или ложь: Франция обыграла Швецию 3:0 в 1/16 финала ЧМ‑2026.",
        "options": [{"text": "Правда"}, {"text": "Ложь"}],
        "correct_option_index": 0,
        "default_points": 100,
        "explanation": "Правда: Франция выиграла 3:0, а Килиан Мбаппе оформил дубль.",
        "sources": [{"title": "FIFA: France 3-0 Sweden | Match report and highlights", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/france-sweden-review-highlights", "note": "Проверено 2 июля 2026 года."}],
    },
    {
        "seed_key": "more-less-goals",
        "question_type": "more_less",
        "question_text": "Больше или меньше: Франция забила в матче со Швецией больше голов, чем Бразилия — Японии в 1/16 финала ЧМ‑2026.",
        "options": [{"text": "Больше"}, {"text": "Меньше"}],
        "correct_option_index": 0,
        "default_points": 100,
        "explanation": "Франция победила Швецию 3:0, Бразилия Японию — 2:1.",
        "sources": [
            {"title": "FIFA: France 3-0 Sweden", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/france-sweden-review-highlights", "note": ""},
            {"title": "FIFA: Brazil 2-1 Japan", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/brazil-japan-review-highlights", "note": ""},
        ],
    },
    {
        "seed_key": "yes-no-morocco",
        "question_type": "yes_no",
        "question_text": "Да или нет: Марокко прошло Нидерланды в 1/16 финала ЧМ‑2026 по пенальти.",
        "options": [{"text": "Да"}, {"text": "Нет"}],
        "correct_option_index": 0,
        "default_points": 100,
        "explanation": "Да. После 1:1 Марокко выиграло серию пенальти 3:2.",
        "sources": [{"title": "FIFA: Netherlands 1-1 Morocco (PSO 2-3)", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/netherlands-morocco-review-highlights", "note": "Проверено 2 июля 2026 года."}],
    },
    {
        "seed_key": "jeopardy-france-stadium",
        "question_type": "jeopardy",
        "question_text": "На каком стадионе прошёл матч Франция — Швеция (3:0) в 1/16 финала ЧМ‑2026?",
        "question_payload": {"topic": "Стадионы ЧМ‑2026", "answer_aliases": ["New York New Jersey Stadium", "Нью-Йорк Нью-Джерси Стэдиум", "Нью-Йорк Нью-Джерси", "MetLife Stadium", "Метлайф"]},
        "default_points": 300,
        "explanation": "Матч прошёл на New York New Jersey Stadium.",
        "sources": [{"title": "FIFA: France v Sweden highlights", "url": "https://www.fifa.com/en/watch/SQUgNGrNai36KI7q8vHo6", "note": ""}],
    },
    {
        "seed_key": "one-of-two-france-lineup",
        "question_type": "one_of_two",
        "question_text": "«Один из двух». ЧМ‑2026, 1/16 финала, Франция — Швеция. Стартовый состав Франции: Меньян; Кунде, Упамекано, Салиба, Динь; Тчуамени, [скрыт 1]; Дембеле, Олисе, [скрыт 2]; Мбаппе. Назовите хотя бы одного из двух скрытых игроков.",
        "question_payload": {"answer_aliases": ["Адриан Рабьо", "Рабьо", "Брэдли Баркола", "Баркола"]},
        "default_points": 300,
        "explanation": "Скрытыми игроками были Адриан Рабьо и Брэдли Баркола.",
        "sources": [{"title": "Reuters: France reshuffle left flank against Sweden", "url": "https://www.reuters.com/sports/soccer/france-reshuffle-left-flank-against-sweden-digne-barcola-start-2026-06-30/", "note": "Стартовый состав опубликован перед матчем."}],
    },
    {
        "seed_key": "www-france-logic",
        "question_type": "what_where_when",
        "question_text": "Что? Где? Когда? В 1/16 финала ЧМ‑2026 эта сборная победила 3:0, её лидер оформил дубль, а соперником в следующем раунде стала Парагвай. Назовите сборную.",
        "question_payload": {"answer_aliases": ["Франция", "France"]},
        "default_points": 500,
        "explanation": "Франция победила Швецию 3:0 и вышла на Парагвай.",
        "sources": [
            {"title": "FIFA: France 3-0 Sweden", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/france-sweden-review-highlights", "note": ""},
            {"title": "FIFA World Cup 2026 fixtures", "url": "https://www.fifa.com/worldcup/matches/", "note": "Сетка 1/8 финала."},
        ],
    },
    {
        "seed_key": "countdown-morocco",
        "question_type": "countdown",
        "question_text": "Обратный отсчёт: назовите сборную.",
        "question_payload": {"facts": ["В 1/16 финала ЧМ‑2026 эта сборная пропустила первой.", "Её соперником были Нидерланды.", "После 1:1 она выиграла серию пенальти 3:2."], "answer_aliases": ["Марокко", "Morocco"]},
        "default_points": 500,
        "explanation": "Марокко отыгралось после гола Коди Гакпо и прошло Нидерланды по пенальти.",
        "sources": [{"title": "FIFA: Netherlands 1-1 Morocco (PSO 2-3)", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/articles/netherlands-morocco-review-highlights", "note": ""}],
    },
    {
        "seed_key": "hundred-to-one-scorers",
        "question_type": "hundred_to_one",
        "question_text": "Сто к одному. Назовите любого из десяти игроков в актуальной таблице бомбардиров ЧМ‑2026 по состоянию на 2 июля. Чем ниже позиция в этом тестовом списке — тем больше баллов.",
        "question_payload": {"top_answers": [
            {"answer": "Лионель Месси", "aliases": ["Лионель Месси", "Месси", "Lionel Messi"]},
            {"answer": "Килиан Мбаппе", "aliases": ["Килиан Мбаппе", "Мбаппе", "Kylian Mbappe", "Kylian Mbappé"]},
            {"answer": "Харри Кейн", "aliases": ["Харри Кейн", "Кейн", "Harry Kane"]},
            {"answer": "Эрлинг Холанд", "aliases": ["Эрлинг Холанд", "Холанд", "Erling Haaland", "Haaland"]},
            {"answer": "Усман Дембеле", "aliases": ["Усман Дембеле", "Дембеле", "Ousmane Dembele", "Ousmane Dembélé"]},
            {"answer": "Винисиус Жуниор", "aliases": ["Винисиус Жуниор", "Винисиус", "Vinicius Junior", "Vinícius Júnior"]},
            {"answer": "Хулиан Киньонес", "aliases": ["Хулиан Киньонес", "Киньонес", "Julian Quinones", "Julián Quiñones"]},
            {"answer": "Исмаила Сарр", "aliases": ["Исмаила Сарр", "Сарр", "Ismaila Sarr"]},
            {"answer": "Исмаэль Сайбари", "aliases": ["Исмаэль Сайбари", "Сайбари", "Ismael Saibari"]},
            {"answer": "Матеус Кунья", "aliases": ["Матеус Кунья", "Кунья", "Matheus Cunha"]}
        ]},
        "default_points": 1000,
        "explanation": "Тестовый список сформирован по актуальной гонке бомбардиров; порядок внутри игроков с одинаковым количеством голов фиксирован для проверки механики начисления.",
        "sources": [{"title": "FIFA World Cup 2026 player statistics", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/statistics/player-statistics", "note": "Проверено 2 июля 2026 года. При равенстве голов порядок в тестовом наборе зафиксирован вручную."}],
    },
)


def seed_wc2026_all_rounds_v4(db: Session, actor: User, league_id: int) -> dict[str, Any]:
    require_quiz_manager(db, actor, league_id)
    rows = (
        db.query(LeagueQuizQuestion)
        .filter(LeagueQuizQuestion.league_id == league_id, LeagueQuizQuestion.tags.like(f"{WC2026_STAGE_FOUR_SEED_PREFIX}:%"))
        .all()
    )
    existing = {str(row.tags).rsplit(":", 1)[-1] for row in rows if row.tags}
    created: list[LeagueQuizQuestion] = []
    for item in WC2026_STAGE_FOUR_SAMPLE_QUESTIONS:
        if item["seed_key"] in existing:
            continue
        payload = dict(item)
        payload["tags"] = f"{WC2026_STAGE_FOUR_SEED_PREFIX}:{item['seed_key']}"
        payload.pop("seed_key", None)
        question = LeagueQuizQuestion(
            league_id=league_id,
            created_by_user_id=actor.id,
            approved_by_user_id=actor.id,
            question_type="choice_4",
            status=QUESTION_STATUS_DRAFT,
            question_text="Черновик",
            default_points=100,
            question_payload={},
        )
        db.add(question)
        db.flush()
        _write_question_content(db, question, payload)
        question.status = QUESTION_STATUS_APPROVED
        question.approved_at = utcnow()
        question.approved_by_user_id = actor.id
        db.flush()
        _audit(db, question=question, actor=actor, action_type="seeded_wc2026", after=_question_snapshot(question), note="Тестовый набор ЧМ‑2026 для всех типов раундов")
        created.append(question)
    db.commit()
    return {"created_count": len(created), "existing_count": len(WC2026_STAGE_FOUR_SAMPLE_QUESTIONS) - len(created), "questions": created}

# =============================================================================
# v3.4.2 — content readiness: required metadata, repeat governance and roles.
# =============================================================================
from sqlalchemy import func
from app.services.leagues import require_quiz_editor, require_quiz_moderator

QUESTION_DIFFICULTIES = {"easy", "medium", "hard"}
QUESTION_DIFFICULTY_LABELS = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}


def _clean_tag_list(value: Any, *, label: str, maximum: int = 12) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(";", ",").replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    items: list[str] = []
    seen: set[str] = set()
    for item in raw:
        clean = " ".join(str(item or "").strip().lstrip("#").split())
        key = clean.casefold()
        if not clean or key in seen:
            continue
        if len(clean) > 48:
            raise ValueError(f"{label}: один элемент не может быть длиннее 48 символов")
        items.append(clean)
        seen.add(key)
    if len(items) > maximum:
        raise ValueError(f"{label}: максимум {maximum}")
    return items


def _clean_difficulty(value: Any) -> str | None:
    clean = str(value or "").strip().lower()
    if not clean:
        return None
    if clean not in QUESTION_DIFFICULTIES:
        raise ValueError("Сложность вопроса: easy, medium или hard")
    return clean


def _clean_repeat_after_days(value: Any) -> int:
    try:
        result = int(14 if value is None or value == "" else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Интервал повтора должен быть числом дней") from exc
    if not 0 <= result <= 365:
        raise ValueError("Интервал повтора должен быть от 0 до 365 дней")
    return result


def _question_payload_for_validation(question: LeagueQuizQuestion) -> dict[str, Any]:
    options = sorted(question.options, key=lambda item: (item.position, item.id))
    correct_index = next((index for index, item in enumerate(options) if item.is_correct), None)
    return {
        "question_type": question.question_type,
        "question_text": question.question_text,
        "options": [{"text": item.option_text} for item in options],
        "correct_option_index": correct_index,
        "question_payload": dict(question.question_payload or {}),
        "default_points": int(question.default_points or 0),
    }


def validate_question_before_approval(question: LeagueQuizQuestion) -> None:
    """Validate the full publishing contract without blocking unfinished drafts."""
    # Core + type-specific validation: correct option/aliases, board topic,
    # three countdown facts and the full 100-to-1 top ten.
    _validate_stage_three_question_payload(_question_payload_for_validation(question))
    if not str(question.explanation or "").strip():
        raise ValueError("Перед одобрением добавьте пояснение правильного ответа")
    sources = list(question.sources or [])
    if not any(str(item.source_url or "").strip() for item in sources):
        raise ValueError("Перед одобрением добавьте хотя бы один источник со ссылкой")
    topics = _clean_tag_list(getattr(question, "topics", None), label="Темы")
    if not topics:
        raise ValueError("Перед одобрением укажите хотя бы одну тему")
    if not _clean_tag_list(question.tags, label="Теги"):
        raise ValueError("Перед одобрением укажите хотя бы один тег")
    if not _clean_difficulty(getattr(question, "difficulty", None)):
        raise ValueError("Перед одобрением укажите сложность: лёгкий, средний или сложный")
    _clean_repeat_after_days(getattr(question, "repeat_after_days", None))


def _write_question_content(db: Session, question: LeagueQuizQuestion, payload: dict[str, Any]) -> None:  # noqa: F811
    question_type, options, correct_index, config, points = _validate_stage_three_question_payload(payload)
    media = _clean_media(payload)
    sources = _clean_sources(payload)
    if media:
        config = {**config, "media": media}
    question.question_type = question_type
    question.question_text = " ".join(str(payload.get("question_text") or "").strip().split())
    question.explanation = (str(payload.get("explanation") or "").strip() or None)
    question.default_points = int(points)
    tag_items = _clean_tag_list(payload.get("tags"), label="Теги")
    question.tags = ", ".join(tag_items) or None
    question.topics = _clean_tag_list(payload.get("topics"), label="Темы")
    question.difficulty = _clean_difficulty(payload.get("difficulty"))
    question.repeat_after_days = _clean_repeat_after_days(payload.get("repeat_after_days"))
    question.question_payload = config

    for row in list(question.options):
        db.delete(row)
    for row in list(question.aliases):
        db.delete(row)
    for row in list(question.sources):
        db.delete(row)
    db.flush()

    for index, option in enumerate(options):
        db.add(LeagueQuizQuestionOption(
            question_id=question.id,
            option_key=option["option_key"],
            option_text=option["text"],
            position=index + 1,
            is_correct=(correct_index is not None and index == correct_index),
        ))
    for alias in config.get("answer_aliases") or []:
        db.add(LeagueQuizQuestionAlias(
            question_id=question.id,
            alias_text=alias,
            normalized_alias=_normalize_text(alias),
        ))
    for item in sources:
        db.add(LeagueQuizQuestionSource(
            question_id=question.id,
            source_title=item["title"] or None,
            source_url=item["url"] or None,
            source_note=item["note"] or None,
        ))


def get_bank_question_v4(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:  # noqa: F811
    require_quiz_editor(db, actor, league_id)
    question = db.query(LeagueQuizQuestion).filter(
        LeagueQuizQuestion.id == question_id,
        LeagueQuizQuestion.league_id == league_id,
    ).first()
    if not question:
        raise ValueError("Вопрос не найден")
    return question


def list_bank_questions(db: Session, actor: User, league_id: int, include_archived: bool = False) -> list[LeagueQuizQuestion]:  # noqa: F811
    require_quiz_editor(db, actor, league_id)
    query = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id)
    if not include_archived:
        query = query.filter(LeagueQuizQuestion.status != QUESTION_STATUS_ARCHIVED)
    return query.order_by(LeagueQuizQuestion.updated_at.desc(), LeagueQuizQuestion.id.desc()).all()


def create_bank_question_v4(db: Session, actor: User, league_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:  # noqa: F811
    require_quiz_editor(db, actor, league_id)
    question = LeagueQuizQuestion(
        league_id=league_id,
        created_by_user_id=actor.id,
        question_type="choice_4",
        status=QUESTION_STATUS_DRAFT,
        question_text="Черновик",
        default_points=100,
        question_payload={},
        topics=[],
        repeat_after_days=14,
    )
    db.add(question)
    db.flush()
    _write_question_content(db, question, payload)
    db.flush()
    _audit(db, question=question, actor=actor, action_type="created", after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def update_bank_question_v4(db: Session, actor: User, league_id: int, question_id: int, payload: dict[str, Any]) -> LeagueQuizQuestion:  # noqa: F811
    question = get_bank_question_v4(db, actor, league_id, question_id)
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Сначала восстановите вопрос из архива")
    before = _question_snapshot(question)
    _write_question_content(db, question, payload)
    if question.status == QUESTION_STATUS_APPROVED:
        question.status = QUESTION_STATUS_DRAFT
        question.approved_at = None
        question.approved_by_user_id = None
    db.flush()
    _audit(db, question=question, actor=actor, action_type="updated", before=before, after=_question_snapshot(question))
    db.commit()
    db.refresh(question)
    return question


def set_bank_question_status_v4(db: Session, actor: User, league_id: int, question_id: int, status: str) -> LeagueQuizQuestion:  # noqa: F811
    question = get_bank_question_v4(db, actor, league_id, question_id)
    before = _question_snapshot(question)
    if status == QUESTION_STATUS_ARCHIVED:
        question.status = QUESTION_STATUS_ARCHIVED
        action = "archived"
    elif status == QUESTION_STATUS_DRAFT:
        question.status = QUESTION_STATUS_DRAFT
        question.approved_at = None
        question.approved_by_user_id = None
        action = "restored_to_draft"
    else:
        raise ValueError("Недопустимый статус вопроса")
    db.flush()
    _audit(db, question=question, actor=actor, action_type=action, before=before, after=_question_snapshot(question))
    db.commit(); db.refresh(question)
    return question


def approve_bank_question_v4(db: Session, actor: User, league_id: int, question_id: int) -> LeagueQuizQuestion:  # noqa: F811
    question = get_bank_question_v4(db, actor, league_id, question_id)
    if question.status == QUESTION_STATUS_ARCHIVED:
        raise ValueError("Архивный вопрос нельзя одобрить")
    validate_question_before_approval(question)
    before = _question_snapshot(question)
    question.status = QUESTION_STATUS_APPROVED
    question.approved_at = utcnow()
    question.approved_by_user_id = actor.id
    db.flush()
    _audit(db, question=question, actor=actor, action_type="approved", before=before, after=_question_snapshot(question))
    db.commit(); db.refresh(question)
    return question


def export_bank_v4(db: Session, actor: User, league_id: int) -> list[dict[str, Any]]:  # noqa: F811
    require_quiz_editor(db, actor, league_id)
    rows = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id).order_by(LeagueQuizQuestion.id.asc()).all()
    result: list[dict[str, Any]] = []
    for question in rows:
        data = serialize_bank_question(question, include_correct=True)
        data.pop("id", None); data.pop("times_used", None); data.pop("last_used_at", None); data.pop("status", None); data.pop("type_label", None)
        data["sources"] = data.get("sources") or []
        data["media"] = (data.get("question_payload") or {}).get("media") or []
        if is_choice_question_type := question.question_type in {"choice_2", "choice_4", "true_false", "more_less", "yes_no"}:
            for index, option in enumerate(data.get("options") or []):
                if option.get("is_correct"):
                    data["correct_option_index"] = index
                    break
        result.append(data)
    return result


def import_bank_v4(db: Session, actor: User, league_id: int, questions: list[dict[str, Any]]) -> dict[str, Any]:  # noqa: F811
    require_quiz_editor(db, actor, league_id)
    if not questions:
        raise ValueError("Файл импорта не содержит вопросов")
    if len(questions) > 100:
        raise ValueError("За один импорт можно добавить не более 100 вопросов")
    created: list[LeagueQuizQuestion] = []
    try:
        for raw in questions:
            if not isinstance(raw, dict):
                raise ValueError("Каждый импортируемый вопрос должен быть объектом")
            payload = dict(raw)
            if not payload.get("sources") and raw.get("source_url"):
                payload["sources"] = [{"title": raw.get("source_title"), "url": raw.get("source_url"), "note": raw.get("source_note")}]
            question = LeagueQuizQuestion(
                league_id=league_id, created_by_user_id=actor.id, question_type="choice_4",
                status=QUESTION_STATUS_DRAFT, question_text="Черновик", default_points=100,
                question_payload={}, topics=[], repeat_after_days=14,
            )
            db.add(question); db.flush()
            _write_question_content(db, question, payload)
            _audit(db, question=question, actor=actor, action_type="imported", after=_question_snapshot(question))
            created.append(question)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"created_count": len(created), "questions": created}


def _usage_rows_v42(db: Session, question: LeagueQuizQuestion) -> list[dict[str, Any]]:
    rows = (
        db.query(LeagueQuizSessionQuestion, LeagueQuizSessionRound, LeagueQuizSession)
        .join(LeagueQuizSessionRound, LeagueQuizSessionRound.id == LeagueQuizSessionQuestion.round_id)
        .join(LeagueQuizSession, LeagueQuizSession.id == LeagueQuizSessionRound.session_id)
        .filter(
            LeagueQuizSessionQuestion.bank_question_id == question.id,
            LeagueQuizSession.is_test_run == False,  # noqa: E712
        )
        .order_by(LeagueQuizSession.started_at.desc().nullslast(), LeagueQuizSession.created_at.desc(), LeagueQuizSession.id.desc())
        .all()
    )
    result: list[dict[str, Any]] = []
    for session_question, round_row, session in rows:
        participant_count = db.query(func.count(LeagueQuizSessionParticipant.id)).filter(
            LeagueQuizSessionParticipant.session_id == session.id,
            LeagueQuizSessionParticipant.status == "registered",
        ).scalar() or 0
        answers = db.query(LeagueQuizSessionAnswer).filter(LeagueQuizSessionAnswer.session_question_id == session_question.id).all()
        answered_count = len(answers)
        correct_count = sum(1 for answer in answers if answer.is_correct is True)
        result.append({
            "session_id": session.id,
            "quiz_title": session.title,
            "quiz_status": session.status,
            "round_order": round_row.round_order,
            "round_title": round_row.title,
            "round_type": round_row.round_type,
            "question_order": session_question.question_order,
            "used_at": (session.started_at or session.created_at).isoformat() if (session.started_at or session.created_at) else None,
            "participants_count": int(participant_count),
            "answered_count": int(answered_count),
            "correct_count": int(correct_count),
            "correct_rate": round((correct_count / answered_count) * 100, 1) if answered_count else None,
        })
    return result


def question_history_v4(db: Session, actor: User, league_id: int, question_id: int) -> dict[str, Any]:  # noqa: F811
    question = get_bank_question_v4(db, actor, league_id, question_id)
    audits = (
        db.query(LeagueQuizQuestionAudit)
        .filter(LeagueQuizQuestionAudit.question_id == question.id)
        .order_by(LeagueQuizQuestionAudit.created_at.desc(), LeagueQuizQuestionAudit.id.desc()).all()
    )
    audit_rows = [{
        "id": row.id,
        "action_type": row.action_type,
        "actor_user_id": row.actor_user_id,
        "actor_name": row.actor.display_name if getattr(row, "actor", None) and row.actor.display_name else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "note": row.note,
        "before": row.before_snapshot,
        "after": row.after_snapshot,
    } for row in audits]
    usage = _usage_rows_v42(db, question)
    total_answered = sum(int(row["answered_count"]) for row in usage)
    total_correct = sum(int(row["correct_count"]) for row in usage)
    return {
        "history": audit_rows,
        "usage": usage,
        "usage_summary": {
            "live_uses": len(usage),
            "answered_count": total_answered,
            "correct_count": total_correct,
            "correct_rate": round((total_correct / total_answered) * 100, 1) if total_answered else None,
            "last_used_at": question.last_used_at.isoformat() if question.last_used_at else None,
            "repeat_after_days": int(getattr(question, "repeat_after_days", 14) or 0),
        },
    }


def list_answer_reviews_v4(db: Session, actor: User, session_id: int, session_question_id: int) -> list[dict[str, Any]]:  # noqa: F811
    session, question = _session_question_for_review(db, session_id, session_question_id)
    require_quiz_moderator(db, actor, session.league_id)
    if question.status not in {QUESTION_REVEALED, QUESTION_CLOSED}:
        raise ValueError("Проверять ответы можно после закрытия вопроса")
    rows = db.query(LeagueQuizSessionAnswer).filter(LeagueQuizSessionAnswer.session_question_id == question.id).order_by(LeagueQuizSessionAnswer.answered_at.asc(), LeagueQuizSessionAnswer.id.asc()).all()
    reviews = db.query(LeagueQuizAnswerReview).filter(LeagueQuizAnswerReview.session_question_id == question.id).order_by(LeagueQuizAnswerReview.created_at.desc(), LeagueQuizAnswerReview.id.desc()).all()
    review_map: dict[int, LeagueQuizAnswerReview] = {}
    for review in reviews:
        review_map.setdefault(review.answer_id, review)
    return [{
        "answer_id": answer.id,
        "user_id": answer.user_id,
        "display_name": answer.user.display_name if answer.user and answer.user.display_name else f"Игрок {answer.user_id}",
        "selected_option_key": answer.selected_option_key,
        "answer_text": answer.answer_text,
        "is_correct": answer.is_correct,
        "points_awarded": int(answer.points_awarded or 0),
        "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
        "manual_review": ({"decision": review_map[answer.id].decision, "reason": review_map[answer.id].reason, "created_at": review_map[answer.id].created_at.isoformat() if review_map[answer.id].created_at else None} if answer.id in review_map else None),
    } for answer in rows]


def review_answer_v4(db: Session, actor: User, session_id: int, session_question_id: int, answer_id: int, accepted: bool, reason: str) -> LeagueQuizSessionAnswer:  # noqa: F811
    session, question = _session_question_for_review(db, session_id, session_question_id)
    require_quiz_moderator(db, actor, session.league_id)
    if question.status not in {QUESTION_REVEALED, QUESTION_CLOSED}:
        raise ValueError("Проверять ответы можно после закрытия вопроса")
    clean_reason = _clean_string(reason, 2000, "Комментарий")
    if not clean_reason:
        raise ValueError("Для ручного решения укажите комментарий")
    answer = db.query(LeagueQuizSessionAnswer).filter(LeagueQuizSessionAnswer.id == answer_id, LeagueQuizSessionAnswer.session_question_id == question.id).first()
    if not answer:
        raise ValueError("Ответ не найден")
    previous_correct = answer.is_correct
    previous_points = int(answer.points_awarded or 0)
    new_points = int(question.points or 0) if accepted else (-int(question.points or 0) if question.negative_on_wrong else 0)
    delta = new_points - previous_points
    answer.is_correct = bool(accepted); answer.points_awarded = new_points; answer.scored_at = utcnow()
    answer.answer_payload = {**dict(answer.answer_payload or {}), "manual_review": {"accepted": bool(accepted), "reason": clean_reason, "actor_user_id": actor.id}}
    participant = db.query(LeagueQuizSessionParticipant).filter(LeagueQuizSessionParticipant.session_id == session.id, LeagueQuizSessionParticipant.user_id == answer.user_id).first()
    if participant:
        participant.score_total = int(participant.score_total or 0) + delta
    db.add(LeagueQuizScoreEvent(session_id=session.id, round_id=question.round_id, session_question_id=question.id, user_id=answer.user_id, event_type="manual_review", delta_points=delta, reason=clean_reason, created_at=utcnow()))
    db.add(LeagueQuizAnswerReview(session_id=session.id, session_question_id=question.id, answer_id=answer.id, actor_user_id=actor.id, decision="accepted" if accepted else "rejected", previous_is_correct=previous_correct, previous_points=previous_points, new_is_correct=bool(accepted), new_points=new_points, reason=clean_reason))
    db.add(LeagueQuizAdminAction(session_id=session.id, actor_user_id=actor.id, action_type="answer_manually_reviewed", payload={"session_question_id": question.id, "answer_id": answer.id, "accepted": bool(accepted), "delta_points": delta, "reason": clean_reason}))
    db.commit(); db.refresh(answer)
    return answer


_serialize_bank_question_v342_base = serialize_bank_question

def serialize_bank_question(question: LeagueQuizQuestion, include_correct: bool = True) -> dict[str, Any]:  # noqa: F811
    data = _serialize_bank_question_v342_base(question, include_correct=include_correct)
    data["topics"] = list(getattr(question, "topics", None) or [])
    data["difficulty"] = getattr(question, "difficulty", None)
    data["difficulty_label"] = QUESTION_DIFFICULTY_LABELS.get(data["difficulty"], None)
    data["repeat_after_days"] = int(getattr(question, "repeat_after_days", 14) or 0)
    data["last_used_at"] = question.last_used_at.isoformat() if question.last_used_at else None
    return data


# Keep the stage-4 serializer intact and extend its response only after the
# content functions above have been rebound.


def seed_wc2026_all_rounds_v4(db: Session, actor: User, league_id: int) -> dict[str, Any]:  # noqa: F811
    """Create the full sample bank with v3.4.2 mandatory metadata."""
    require_quiz_editor(db, actor, league_id)
    rows = db.query(LeagueQuizQuestion).filter(
        LeagueQuizQuestion.league_id == league_id,
        LeagueQuizQuestion.tags.like(f"{WC2026_STAGE_FOUR_SEED_PREFIX}:%"),
    ).all()
    existing = {str(row.tags).rsplit(":", 1)[-1] for row in rows if row.tags}
    created: list[LeagueQuizQuestion] = []
    try:
        for item in WC2026_STAGE_FOUR_SAMPLE_QUESTIONS:
            if item["seed_key"] in existing:
                continue
            payload = dict(item)
            payload["tags"] = f"{WC2026_STAGE_FOUR_SEED_PREFIX}:{item['seed_key']}"
            payload["topics"] = ["ЧМ-2026", "Тестовый набор"]
            payload["difficulty"] = "medium"
            payload["repeat_after_days"] = 0
            payload.pop("seed_key", None)
            question = LeagueQuizQuestion(
                league_id=league_id,
                created_by_user_id=actor.id,
                approved_by_user_id=actor.id,
                question_type="choice_4",
                status=QUESTION_STATUS_DRAFT,
                question_text="Черновик",
                default_points=100,
                question_payload={},
                topics=[],
                repeat_after_days=0,
            )
            db.add(question); db.flush()
            _write_question_content(db, question, payload)
            validate_question_before_approval(question)
            question.status = QUESTION_STATUS_APPROVED
            question.approved_at = utcnow()
            question.approved_by_user_id = actor.id
            db.flush()
            _audit(db, question=question, actor=actor, action_type="seeded_wc2026", after=_question_snapshot(question), note="Тестовый набор ЧМ‑2026 для всех типов раундов")
            created.append(question)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"created_count": len(created), "existing_count": len(WC2026_STAGE_FOUR_SAMPLE_QUESTIONS) - len(created), "questions": created}

# A host may select approved questions while composing a quiz but cannot edit
# or approve them. Editors retain full bank access.
from app.services.leagues import has_quiz_permission

def list_bank_questions(db: Session, actor: User, league_id: int, include_archived: bool = False) -> list[LeagueQuizQuestion]:  # noqa: F811
    if not (has_quiz_permission(db, actor, league_id, "editor") or has_quiz_permission(db, actor, league_id, "host")):
        raise PermissionError("Недостаточно прав для просмотра банка вопросов")
    query = db.query(LeagueQuizQuestion).filter(LeagueQuizQuestion.league_id == league_id)
    if not include_archived:
        query = query.filter(LeagueQuizQuestion.status != QUESTION_STATUS_ARCHIVED)
    return query.order_by(LeagueQuizQuestion.updated_at.desc(), LeagueQuizQuestion.id.desc()).all()
