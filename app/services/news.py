"""RSS-first humorous World Cup news for Resources and league chats.

Discovery is intentionally cheap: configurable RSS feeds are fetched on a
small schedule. One shared OpenAI request may select and phrase a single story
for all leagues; it never performs web search and never runs per participant.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import html
import json
import os
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import Numeric, cast, func
from sqlalchemy.orm import Session

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - deployment fallback
    OpenAI = None

from app.models import AiUsageLog, AppSetting, LeagueNewsDelivery, WorldCupNewsItem


DEFAULT_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=%28FIFA+World+Cup+2026%29+%28fans+OR+funny+OR+weird+OR+viral+OR+unusual+OR+record%29&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%28%D0%A7%D0%9C-2026+OR+%D1%87%D0%B5%D0%BC%D0%BF%D0%B8%D0%BE%D0%BD%D0%B0%D1%82+%D0%BC%D0%B8%D1%80%D0%B0+2026%29+%28%D0%B1%D0%BE%D0%BB%D0%B5%D0%BB%D1%8C%D1%89%D0%B8%D0%BA%D0%B8+OR+%D0%BA%D1%83%D1%80%D1%8C%D1%91%D0%B7+OR+%D0%BC%D0%B5%D0%BC+OR+%D1%81%D1%82%D1%80%D0%B0%D0%BD%D0%BD%D0%BE%29&hl=ru&gl=RU&ceid=RU:ru",
]

NEWS_SCHEMA = {
    "name": "father_world_cup_news_curation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "selected_index": {"type": "integer", "minimum": 0, "maximum": 12},
            "category": {"type": "string", "minLength": 0, "maxLength": 48},
            "summary": {"type": "string", "minLength": 0, "maxLength": 440},
            "commentary": {"type": "string", "minLength": 0, "maxLength": 260},
            "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["selected_index", "category", "summary", "commentary", "relevance_score"],
    },
    "strict": True,
}


def _enabled() -> bool:
    return os.getenv("NEWS_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _timezone() -> ZoneInfo:
    name = os.getenv("NEWS_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _scan_hours() -> list[int]:
    raw = os.getenv("NEWS_SCAN_HOURS", "9,15,21")
    parsed: list[int] = []
    for item in raw.split(","):
        try:
            hour = int(item.strip())
        except ValueError:
            continue
        if 0 <= hour <= 23 and hour not in parsed:
            parsed.append(hour)
    return sorted(parsed) or [9, 15, 21]


def _feeds() -> list[str]:
    raw = os.getenv("NEWS_RSS_FEEDS", "").strip()
    if raw:
        items = [value.strip() for value in re.split(r"[\n;]+", raw) if value.strip()]
        if items:
            return items[:12]
    return DEFAULT_NEWS_FEEDS


def _clean_text(value: str | None, limit: int = 900) -> str:
    raw = html.unescape(value or "")
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:limit]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, *names: str) -> str:
    names_set = {item.lower() for item in names}
    for child in list(node):
        if _local_name(child.tag) in names_set and (child.text or "").strip():
            return _clean_text(child.text)
    return ""


def _child_attr(node: ET.Element, name: str, attr: str) -> str:
    for child in list(node):
        if _local_name(child.tag) == name.lower():
            value = child.attrib.get(attr) or ""
            if value:
                return value.strip()
    return ""


def _normalize_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
    except Exception:
        return url.strip()


def _parse_date(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        result = parsedate_to_datetime(raw)
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        result = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)
    except Exception:
        return None


def _source_from_title(title: str) -> tuple[str, str]:
    # Google News titles commonly append " - Source". Keep the visible article
    # title compact but only split the final delimiter.
    if " - " in title:
        article, source = title.rsplit(" - ", 1)
        if 2 <= len(source) <= 90:
            return article.strip(), source.strip()
    return title.strip(), ""


def _looks_world_cup_related(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    tournament = any(token in text for token in ("world cup", "worldcup", "fifa", "чемпионат мира", "чм-2026", "чм 2026"))
    year_or_fifa = "2026" in text or "fifa" in text or "чм" in text
    return tournament and year_or_fifa


def _local_fun_score(title: str, description: str) -> int:
    text = f"{title} {description}".lower()
    fun_tokens = (
        "fan", "fans", "supporter", "viral", "funny", "weird", "strange", "bizarre", "odd", "meme", "record", "mascot",
        "болельщик", "болельщики", "фанат", "фанаты", "курьез", "курьёз", "мем", "забав", "смешн", "странн", "рекорд", "талисман",
    )
    sensitive_tokens = (
        "death", "dead", "injury", "hospital", "killed", "war", "politic", "racism", "discrimination",
        "смерт", "погиб", "травм", "больниц", "войн", "полит", "расизм", "дискриминац",
    )
    score = sum(15 for token in fun_tokens if token in text)
    score -= sum(60 for token in sensitive_tokens if token in text)
    return score


def _parse_rss_document(content: bytes, feed_url: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    output: list[dict[str, Any]] = []
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        raw_title = _child_text(node, "title")
        if not raw_title:
            continue
        link = _child_text(node, "link") or _child_attr(node, "link", "href")
        if not link:
            continue
        description = _child_text(node, "description", "summary", "content")
        source = _child_text(node, "source", "author")
        title, title_source = _source_from_title(raw_title)
        if not source:
            source = title_source
        if not _looks_world_cup_related(title, description):
            continue
        normalized_url = _normalize_url(link)
        external_id = hashlib.sha256(f"{normalized_url}|{title.lower()}".encode("utf-8")).hexdigest()
        published = _parse_date(_child_text(node, "pubdate", "published", "updated"))
        output.append({
            "external_id": external_id,
            "title": title[:360],
            "description": description[:900],
            "source_name": source[:160] or "RSS",
            "source_url": normalized_url,
            "published_at": published,
            "feed_url": feed_url,
            "local_score": _local_fun_score(title, description),
        })
    return output


def collect_rss_candidates() -> list[dict[str, Any]]:
    """Fetch small RSS batches without any paid web search or page scraping."""
    items: list[dict[str, Any]] = []
    headers = {"User-Agent": "FatherPredictionsNews/2.8 (+RSS curator)"}
    timeout_seconds = max(5, min(30, int(os.getenv("NEWS_RSS_TIMEOUT_SECONDS", "12") or "12")))
    for feed_url in _feeds():
        try:
            response = requests.get(feed_url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            items.extend(_parse_rss_document(response.content, feed_url))
        except Exception as error:
            print(f"News RSS fetch failed for {feed_url}: {error}")

    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        existing = unique.get(item["external_id"])
        if not existing or int(item.get("local_score") or 0) > int(existing.get("local_score") or 0):
            unique[item["external_id"]] = item
    return sorted(
        unique.values(),
        key=lambda item: (int(item.get("local_score") or 0), item.get("published_at") or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )


def _estimate_cost(input_tokens: int, output_tokens: int) -> str:
    try:
        input_rate = float(os.getenv("NEWS_INPUT_COST_PER_1M_USD", "0.75"))
        output_rate = float(os.getenv("NEWS_OUTPUT_COST_PER_1M_USD", "4.50"))
        total = (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
        return f"{total:.6f}"
    except Exception:
        return "0"


def _log_usage(db: Session, *, model: str, input_tokens: int, output_tokens: int) -> None:
    db.add(AiUsageLog(
        purpose="rss_news_curation",
        model=model,
        input_tokens=max(0, int(input_tokens or 0)),
        output_tokens=max(0, int(output_tokens or 0)),
        estimated_cost_usd=_estimate_cost(input_tokens, output_tokens),
    ))


def _ai_budget_available(db: Session, local_today) -> bool:
    max_calls = max(0, int(os.getenv("NEWS_MAX_AI_CALLS_PER_DAY", "3") or "3"))
    if max_calls == 0:
        return False
    tz = _timezone()
    start = datetime.combine(local_today, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(local_today, datetime.max.time(), tzinfo=tz).astimezone(timezone.utc)
    calls = db.query(AiUsageLog).filter(
        AiUsageLog.purpose == "rss_news_curation",
        AiUsageLog.created_at >= start,
        AiUsageLog.created_at <= end,
    ).count()
    return calls < max_calls


def _fallback_selection(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if not candidates:
        return {"selected_index": 0, "category": "", "summary": "", "commentary": "", "relevance_score": 0}
    candidate = candidates[0]
    if int(candidate.get("local_score") or 0) < 15:
        return {"selected_index": 0, "category": "", "summary": "", "commentary": "", "relevance_score": 0}
    return {
        "selected_index": 1,
        "category": "Вокруг турнира",
        "summary": _clean_text(candidate.get("description") or candidate.get("title"), 420),
        "commentary": "Отец изучил новостную ленту: футбол идёт по расписанию, а всё вокруг него — по вдохновению.",
        "relevance_score": min(80, 40 + int(candidate.get("local_score") or 0)),
    }


def curate_candidates_with_openai(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, int | str]]:
    """Select at most one story with one compact structured-output call."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("NEWS_AI_MODEL") or os.getenv("OPENAI_GAMIFICATION_MODEL") or os.getenv("OPENAI_FORECAST_MODEL") or "gpt-5.4-mini"
    enabled = os.getenv("NEWS_AI_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if not enabled or not api_key or OpenAI is None:
        return _fallback_selection(candidates), {"model": model, "input_tokens": 0, "output_tokens": 0}

    compact = [
        {
            "index": index,
            "title": candidate["title"],
            "description": candidate.get("description") or "",
            "source": candidate.get("source_name") or "RSS",
            "published_at": candidate.get("published_at").isoformat() if candidate.get("published_at") else None,
        }
        for index, candidate in enumerate(candidates, start=1)
    ]
    prompt = f"""
Ты редактор рубрики «Новости Отца» для дружеского приложения прогнозов на ЧМ-2026.
Выбери ровно одну новость, только если она действительно связана с ЧМ-2026 и выглядит забавной, необычной, фанатской, мемной, организационно странной или с неожиданной статистикой. Если достойной новости нет, верни selected_index=0 и пустые строки.

Запрещено выбирать темы о трагедиях, смерти, травмах, болезнях, политике, войне, дискриминации, личных бедах или непроверенных слухах. Не выдумывай факты за пределами title/description. Не сообщай результат матча как главный сюжет.

Для выбранной новости:
- summary: 1–2 коротких фактических предложения, до 440 символов;
- commentary: одна свежая футбольная шутка Отца, до 260 символов; можно остро, но нельзя оскорблять людей;
- category: одна из «Фанаты и атмосфера», «Вокруг матчей», «Неожиданная статистика», «Организационный курьёз», «Странное на ЧМ»;
- relevance_score: 0–100.
Верни только JSON по схеме.

Кандидаты:\n{json.dumps(compact, ensure_ascii=False)}
"""
    try:
        client = OpenAI(api_key=api_key, timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")), max_retries=1)
        response = client.responses.create(
            model=model,
            input=prompt,
            text={"format": {"type": "json_schema", "name": NEWS_SCHEMA["name"], "schema": NEWS_SCHEMA["schema"], "strict": True}},
        )
        payload = json.loads(response.output_text)
        usage = getattr(response, "usage", None)
        return payload, {
            "model": model,
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        }
    except Exception as error:
        print(f"News OpenAI curation fallback: {error}")
        return _fallback_selection(candidates), {"model": model, "input_tokens": 0, "output_tokens": 0}


def _setting_exists(db: Session, key: str) -> bool:
    return db.query(AppSetting).filter(AppSetting.setting_key == key).first() is not None


def _mark_setting(db: Session, key: str, value: str) -> None:
    current = db.query(AppSetting).filter(AppSetting.setting_key == key).first()
    if current:
        current.setting_value = value
    else:
        db.add(AppSetting(setting_key=key, setting_value=value))


def _latest_due_slot(db: Session, now: datetime) -> tuple[str, int] | None:
    local_now = now.astimezone(_timezone())
    # Only one missed slot is processed after deploy: the most recent one. This
    # prevents a restart at 21:00 from consuming three AI calls at once.
    for hour in sorted(_scan_hours(), reverse=True):
        if local_now.hour < hour:
            continue
        key = f"rss_news_scan:{local_now.date().isoformat()}:{hour:02d}"
        if not _setting_exists(db, key):
            return key, hour
    return None


def _mark_older_slots_skipped(db: Session, local_day, processed_hour: int) -> None:
    """Avoid replaying every missed daily scan after a deploy or restart."""
    for hour in _scan_hours():
        if hour >= processed_hour:
            continue
        key = f"rss_news_scan:{local_day.isoformat()}:{hour:02d}"
        if not _setting_exists(db, key):
            _mark_setting(db, key, "skipped_after_catchup")


def _daily_limit_reached(db: Session, local_day) -> bool:
    limit = max(0, int(os.getenv("NEWS_MAX_POSTS_PER_DAY", "1") or "1"))
    if limit == 0:
        return True
    return db.query(WorldCupNewsItem).filter(
        WorldCupNewsItem.selection_status == "selected",
        WorldCupNewsItem.published_for_date == local_day,
    ).count() >= limit


def _store_curation_result(
    db: Session,
    candidates: list[dict[str, Any]],
    curation: dict[str, Any],
    local_day,
) -> WorldCupNewsItem | None:
    selected_index = int(curation.get("selected_index") or 0)
    selected_candidate = candidates[selected_index - 1] if 1 <= selected_index <= len(candidates) else None
    selected_item: WorldCupNewsItem | None = None
    for index, candidate in enumerate(candidates, start=1):
        is_selected = selected_candidate is not None and index == selected_index
        row = WorldCupNewsItem(
            external_id=candidate["external_id"],
            source_name=candidate.get("source_name") or "RSS",
            source_url=candidate["source_url"],
            title=candidate["title"],
            summary=_clean_text(curation.get("summary"), 440) if is_selected else None,
            father_commentary=_clean_text(curation.get("commentary"), 260) if is_selected else None,
            category=_clean_text(curation.get("category"), 64) if is_selected else None,
            relevance_score=int(curation.get("relevance_score") or 0) if is_selected else 0,
            published_at=candidate.get("published_at"),
            selected_at=datetime.now(timezone.utc) if is_selected else None,
            published_for_date=local_day if is_selected else None,
            selection_status="selected" if is_selected else "rejected",
        )
        db.add(row)
        if is_selected:
            selected_item = row
    db.commit()
    if selected_item:
        db.refresh(selected_item)
    return selected_item


def _news_message(item: WorldCupNewsItem) -> str:
    lines = [
        "😂 Новости Отца · ЧМ-2026",
        "",
        str(item.title or "Новости вокруг турнира"),
    ]
    if item.summary:
        lines.extend(["", str(item.summary)])
    if item.father_commentary:
        lines.extend(["", f"🎙️ Отец: {item.father_commentary}"])
    source = str(item.source_name or "Источник")
    lines.extend(["", f"Источник: {source}", str(item.source_url)])
    return "\n".join(lines)[:3900]


async def _deliver_to_league_chats(db: Session, item: WorldCupNewsItem) -> int:
    """Post the same already-curated story to configured league chats once."""
    from app.runtime import GROUP_CHAT_ID_RAW, bot
    from app.services.leagues import get_active_league_chat_targets, get_default_league

    default_league = get_default_league(db)
    destinations: list[tuple[Any, str]] = []
    seen_chat_ids: set[str] = set()
    if default_league and str(GROUP_CHAT_ID_RAW or "").strip():
        chat = str(GROUP_CHAT_ID_RAW).strip()
        destinations.append((default_league, chat))
        seen_chat_ids.add(chat)
    for league in get_active_league_chat_targets(db):
        chat = str(getattr(league, "chat_id", "") or "").strip()
        if not chat or chat in seen_chat_ids:
            continue
        destinations.append((league, chat))
        seen_chat_ids.add(chat)

    sent = 0
    text = _news_message(item)
    for league, chat_id in destinations:
        exists = db.query(LeagueNewsDelivery).filter(
            LeagueNewsDelivery.league_id == league.id,
            LeagueNewsDelivery.news_item_id == item.id,
        ).first()
        if exists:
            continue
        try:
            await bot.send_message(chat_id=int(chat_id), text=text, disable_web_page_preview=True)
            db.add(LeagueNewsDelivery(league_id=league.id, news_item_id=item.id, chat_id=chat_id))
            db.commit()
            sent += 1
        except Exception as error:
            db.rollback()
            print(f"Failed to send RSS news item {item.id} to league {league.id}: {error}")
    return sent


async def _deliver_pending_selected_news(db: Session, local_day) -> int:
    """Retry today's selected story after a transient Telegram failure."""
    rows = (
        db.query(WorldCupNewsItem)
        .filter(
            WorldCupNewsItem.selection_status == "selected",
            WorldCupNewsItem.published_for_date == local_day,
        )
        .order_by(WorldCupNewsItem.selected_at.asc())
        .limit(3)
        .all()
    )
    sent = 0
    for item in rows:
        sent += await _deliver_to_league_chats(db, item)
    return sent


async def run_scheduled_news_scan(db: Session, now: datetime | None = None) -> dict[str, Any]:
    """Run at most one RSS scan for the current scheduled slot."""
    now = now or datetime.now(timezone.utc)
    if not _enabled():
        return {"status": "disabled"}

    local_day = now.astimezone(_timezone()).date()
    retry_deliveries = await _deliver_pending_selected_news(db, local_day)
    due = _latest_due_slot(db, now)
    if not due:
        return {"status": "not_due", "retry_deliveries": retry_deliveries}
    slot_key, slot_hour = due
    _mark_older_slots_skipped(db, local_day, slot_hour)

    if _daily_limit_reached(db, local_day):
        _mark_setting(db, slot_key, "daily_limit")
        db.commit()
        return {"status": "daily_limit"}
    if not _ai_budget_available(db, local_day):
        _mark_setting(db, slot_key, "ai_budget")
        db.commit()
        return {"status": "ai_budget"}

    collected = await asyncio.to_thread(collect_rss_candidates)
    if not collected:
        _mark_setting(db, slot_key, "no_candidates")
        db.commit()
        return {"status": "no_candidates"}

    known_ids = {
        value[0]
        for value in db.query(WorldCupNewsItem.external_id)
        .filter(WorldCupNewsItem.external_id.in_([item["external_id"] for item in collected]))
        .all()
    }
    fresh = [item for item in collected if item["external_id"] not in known_ids]
    max_candidates = max(1, min(12, int(os.getenv("NEWS_MAX_CANDIDATES_PER_SCAN", "10") or "10")))
    fresh = fresh[:max_candidates]
    if not fresh:
        _mark_setting(db, slot_key, "no_fresh_candidates")
        db.commit()
        return {"status": "no_fresh_candidates"}

    curation, usage = await asyncio.to_thread(curate_candidates_with_openai, fresh)
    _log_usage(db, model=str(usage.get("model") or ""), input_tokens=int(usage.get("input_tokens") or 0), output_tokens=int(usage.get("output_tokens") or 0))
    item = _store_curation_result(db, fresh, curation, local_day)
    _mark_setting(db, slot_key, "selected" if item else "rejected")
    db.commit()
    if not item:
        return {"status": "rejected", "candidates": len(fresh), "slot_hour": slot_hour}

    sent = await _deliver_to_league_chats(db, item)
    print(f"RSS news selected: id={item.id}, source={item.source_name}, chats={sent}")
    return {"status": "sent", "news_item_id": item.id, "league_chats": sent, "retry_deliveries": retry_deliveries, "candidates": len(fresh), "slot_hour": slot_hour}


async def news_loop() -> None:
    """Background scheduler for the low-cost RSS news workflow."""
    if not _enabled():
        print("RSS news loop is disabled")
        return
    try:
        interval = int(os.getenv("NEWS_POLL_INTERVAL_SECONDS", "300") or "300")
    except ValueError:
        interval = 300
    interval = max(60, min(3600, interval))
    print(f"RSS news loop started. Interval: {interval} seconds. Scan hours: {_scan_hours()}.")
    while True:
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            result = await run_scheduled_news_scan(db)
            if result.get("status") not in {"not_due", "daily_limit"}:
                print(f"RSS news scan: {result}")
        except Exception as error:
            print(f"RSS news loop error: {error}")
        finally:
            db.close()
        await asyncio.sleep(interval)


def serialize_news_item(item: WorldCupNewsItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "summary": item.summary,
        "father_commentary": item.father_commentary,
        "category": item.category,
        "source_name": item.source_name,
        "source_url": item.source_url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "selected_at": item.selected_at.isoformat() if item.selected_at else None,
    }


def get_news_usage_summary(db: Session, days: int = 30) -> dict[str, Any]:
    days = max(1, min(90, int(days)))
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(
        func.count(AiUsageLog.id),
        func.coalesce(func.sum(AiUsageLog.input_tokens), 0),
        func.coalesce(func.sum(AiUsageLog.output_tokens), 0),
        func.coalesce(func.sum(cast(AiUsageLog.estimated_cost_usd, Numeric)), 0),
    ).filter(
        AiUsageLog.purpose == "rss_news_curation",
        AiUsageLog.created_at >= start,
    ).one()
    return {
        "days": days,
        "calls": int(rows[0] or 0),
        "input_tokens": int(rows[1] or 0),
        "output_tokens": int(rows[2] or 0),
        "estimated_cost_usd": float(rows[3] or 0),
    }
