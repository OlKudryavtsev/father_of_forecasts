"""Match TV video discovery for World Cup match center.

This module intentionally stores only official page links. It does not download,
proxy, or extract video streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import os
import re
from typing import Iterable
from urllib.parse import urljoin

import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Match, MatchVideo
from app.runtime import TOURNAMENT_CODE
from app.team_names import get_team_name_ru
from app.services.web_push import notify_active_web_push_subscribers_for_notification

MATCHTV_WC_VIDEO_URL = os.getenv(
    "MATCHTV_WC_VIDEO_URL",
    "https://matchtv.ru/football/worldcup/video",
)

REQUEST_TIMEOUT_SECONDS = int(os.getenv("MATCHTV_VIDEO_REQUEST_TIMEOUT", "15"))
DEFAULT_LOOKBACK_DAYS = int(os.getenv("MATCHTV_VIDEO_LOOKBACK_DAYS", "5"))
DEFAULT_LOOKAHEAD_DAYS = int(os.getenv("MATCHTV_VIDEO_LOOKAHEAD_DAYS", "7"))

VIDEO_TYPE_PRIORITY = {
    "live": 10,
    "highlights": 20,
    "review": 30,
    "full_replay": 40,
    "goal": 60,
    "moment": 70,
    "other": 100,
}

# Match TV and API-Football use different naming variants. Keep this list
# deliberately practical: it is used only for matching official video page titles
# to already imported World Cup fixtures.
TEAM_RU_OVERRIDES = {
    "algeria": "Алжир",
    "bosnia and herzegovina": "Босния и Герцеговина",
    "bosnia & herzegovina": "Босния и Герцеговина",
    "bosnia-herzegovina": "Босния и Герцеговина",
    "bosnia": "Босния и Герцеговина",
    "czechia": "Чехия",
    "czech republic": "Чехия",
    "cote d ivoire": "Кот-д'Ивуар",
    "côte d ivoire": "Кот-д'Ивуар",
    "ivory coast": "Кот-д'Ивуар",
    "congo dr": "ДР Конго",
    "dr congo": "ДР Конго",
    "d r congo": "ДР Конго",
    "curacao": "Кюрасао",
    "curaçao": "Кюрасао",
    "korea republic": "Корея",
    "south korea": "Корея",
    "republic of korea": "Корея",
    "united states": "США",
    "usa": "США",
    "u s a": "США",
    "cape verde islands": "Кабо-Верде",
    "cape verde": "Кабо-Верде",
    "saudi arabia": "Саудовская Аравия",
    "new zealand": "Новая Зеландия",
    "turkiye": "Турция",
    "türkiye": "Турция",
    "qatar": "Катар",
}

TEAM_ALIASES_EXTRA = {
    "Алжир": ["Алжир"],
    "Англия": ["England"],
    "Аргентина": ["Argentina"],
    "Австралия": ["Australia"],
    "Австрия": ["Austria"],
    "Бельгия": ["Belgium"],
    "Босния и Герцеговина": ["Босния", "БиГ", "Bosnia", "Bosnia and Herzegovina", "Bosnia & Herzegovina"],
    "Бразилия": ["Brazil"],
    "Гаити": ["Haiti"],
    "Гана": ["Ghana"],
    "Германия": ["Germany"],
    "ДР Конго": ["ДР Конго", "Конго", "Congo DR", "DR Congo"],
    "Египет": ["Egypt"],
    "Иордания": ["Jordan"],
    "Ирак": ["Iraq"],
    "Иран": ["Iran"],
    "Испания": ["Spain"],
    "Кабо-Верде": ["Кабо Верде", "Cape Verde", "Cape Verde Islands"],
    "Канада": ["Canada"],
    "Катар": ["Qatar"],
    "Колумбия": ["Colombia"],
    "Корея": ["Южная Корея", "Korea", "South Korea", "Korea Republic", "Republic of Korea"],
    "Южная Корея": ["Корея", "Korea", "South Korea", "Korea Republic", "Republic of Korea"],
    "Кот-д’Ивуар": ["Кот-д'Ивуар", "Кот д Ивуар", "Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
    "Кот-д'Ивуар": ["Кот-д’Ивуар", "Кот д Ивуар", "Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
    "Кюрасао": ["Курасао", "Curacao", "Curaçao"],
    "Марокко": ["Morocco"],
    "Мексика": ["Mexico"],
    "Нидерланды": ["Голландия", "Netherlands", "Holland"],
    "Новая Зеландия": ["New Zealand"],
    "Норвегия": ["Norway"],
    "Панама": ["Panama"],
    "Парагвай": ["Paraguay"],
    "Португалия": ["Portugal"],
    "Саудовская Аравия": ["Saudi Arabia"],
    "Сенегал": ["Senegal"],
    "США": ["Соединенные Штаты", "Сша", "USA", "United States", "USMNT"],
    "Тунис": ["Tunisia"],
    "Турция": ["Turkey", "Türkiye", "Turkiye"],
    "Узбекистан": ["Uzbekistan"],
    "Уругвай": ["Uruguay"],
    "Франция": ["France"],
    "Хорватия": ["Croatia"],
    "Чехия": ["Czechia", "Czech Republic"],
    "Швейцария": ["Switzerland"],
    "Швеция": ["Sweden"],
    "Шотландия": ["Scotland"],
    "Эквадор": ["Ecuador"],
    "ЮАР": ["Южная Африка", "South Africa", "RSA"],
    "Япония": ["Japan"],
}


@dataclass(frozen=True)
class DiscoveredVideo:
    title: str
    url: str
    video_type: str
    source: str = "matchtv"
    confidence: int = 0
    external_id: str | None = None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(str(value)).lower()
    value = value.replace("ё", "е").replace("й", "и")
    value = re.sub(r"[\u2010-\u2015—–−]+", "-", value)
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-zа-я0-9\-\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _ru_team_name(name: str | None) -> str:
    if not name:
        return ""
    normalized = _normalize_text(name)
    if normalized in TEAM_RU_OVERRIDES:
        return TEAM_RU_OVERRIDES[normalized]
    direct = get_team_name_ru(name)
    if direct != name:
        return direct
    title_name = str(name).strip().title()
    direct_title = get_team_name_ru(title_name)
    return direct_title if direct_title != title_name else str(name).strip()


def _team_aliases(*names: str | None) -> list[str]:
    aliases: list[str] = []
    ru_names: list[str] = []
    for name in names:
        if not name:
            continue
        ru_name = _ru_team_name(name)
        ru_names.append(ru_name)
        aliases.extend([name, ru_name])
        aliases.extend(TEAM_ALIASES_EXTRA.get(ru_name, []))

    # Some API names translate to "Южная Корея", while Match TV writes "Корея".
    if any(_normalize_text(item) in {"корея", "южная корея"} for item in ru_names + aliases):
        aliases.extend(TEAM_ALIASES_EXTRA.get("Корея", []))
        aliases.append("Корея")

    seen: set[str] = set()
    result: list[str] = []
    for item in aliases:
        normalized = _normalize_text(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    # Prefer longer aliases first to avoid accidental short matches.
    return sorted(result, key=len, reverse=True)


def _contains_any(text: str, aliases: Iterable[str]) -> bool:
    padded = f" {text} "
    for alias in aliases:
        if not alias:
            continue
        # For one-word country names substring matching is fine after strict
        # normalization; for very short aliases require token boundaries.
        if len(alias) <= 3:
            if re.search(rf"(?<![a-zа-я0-9]){re.escape(alias)}(?![a-zа-я0-9])", text):
                return True
            continue
        if alias in padded or alias in text:
            return True
    return False


def _classify_video(title: str) -> str:
    text = _normalize_text(title)
    if any(word in text for word in ["прямая трансляция", "трансляция", "эфир"]):
        return "live"
    if any(word in text for word in ["голы и лучшие моменты", "все голы", "лучшие моменты", "хаилаит", "хайлайт"]):
        return "highlights"
    if "обзор" in text:
        return "review"
    if any(word in text for word in ["полная запись", "запись матча", "матч полностью"]):
        return "full_replay"
    if text.startswith("гол ") or " гол " in f" {text} ":
        return "goal"
    if re.search(r"[а-яa-z]+\s+-\s+[а-яa-z]+", text) and "чемпионат мира" in text:
        return "live"
    return "moment" if any(word in text for word in ["момент", "удар", "спасает", "столкновение", "пенальти"]) else "other"


def _clean_anchor_text(inner_html: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", inner_html, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_cards(html_text: str, base_url: str = MATCHTV_WC_VIDEO_URL) -> list[DiscoveredVideo]:
    """Extract candidate video cards from Match TV HTML.

    Match TV markup changes often, so this parser is intentionally heuristic:
    it collects links that point to matchtv.ru pages and keeps visible text near
    those links. Admin review remains available in the UI.
    """
    candidates: dict[str, DiscoveredVideo] = {}

    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, flags=re.I | re.S):
        href, inner = match.group(1), match.group(2)
        url = urljoin(base_url, html.unescape(href))
        if "matchtv.ru" not in url:
            continue
        if "/video" not in url and "/football/worldcup" not in url:
            continue
        text = _clean_anchor_text(inner)
        if len(text) < 5:
            continue
        normalized = _normalize_text(text)
        # Keep program/video cards, skip navigation/logo/filter noise.
        looks_like_wc_video = (
            "чемпионат мира" in normalized
            or "чм-2026" in normalized
            or "чм 2026" in normalized
            or "голы и лучшие моменты" in normalized
            or "обзор" in normalized
            or re.search(r"[а-яa-z]+\s+-\s+[а-яa-z]+", normalized)
        )
        if not looks_like_wc_video:
            continue
        vtype = _classify_video(text)
        previous = candidates.get(url)
        # Prefer the longest human-readable text for duplicate anchors to the
        # same page, but avoid replacing a good match title with navigation text.
        if previous and len(previous.title) >= len(text):
            continue
        candidates[url] = DiscoveredVideo(
            title=text[:240],
            url=url,
            video_type=vtype,
            external_id=url,
        )

    # Fallback for JSON blobs / escaped URLs with titles nearby.
    for match in re.finditer(r'(https?:\\?/\\?/matchtv\.ru[^"\s<]+|/[^"\s<]*(?:video|football/worldcup)[^"\s<]*)', html_text, flags=re.I):
        raw = match.group(1).replace('\\/', '/')
        url = urljoin(base_url, html.unescape(raw))
        if "matchtv.ru" not in url:
            continue
        start = max(0, match.start() - 260)
        end = min(len(html_text), match.end() + 260)
        nearby = _clean_anchor_text(html_text[start:end])
        title = nearby[:240]
        if len(title) < 5:
            continue
        normalized = _normalize_text(title)
        if "чемпионат мира" not in normalized and not re.search(r"[а-яa-z]+\s+-\s+[а-яa-z]+", normalized):
            continue
        candidates.setdefault(url, DiscoveredVideo(title=title, url=url, video_type=_classify_video(title), external_id=url))

    return list(candidates.values())


def fetch_matchtv_worldcup_videos() -> list[DiscoveredVideo]:
    response = requests.get(
        MATCHTV_WC_VIDEO_URL,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; OtecPrognozovBot/1.0; +https://t.me/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    return _extract_cards(response.text, MATCHTV_WC_VIDEO_URL)


def _match_video_score(video: DiscoveredVideo, match: Match) -> int:
    text = _normalize_text(video.title)
    home_aliases = _team_aliases(
        match.home_team,
        getattr(match, "home_team_api_name", None),
    )
    away_aliases = _team_aliases(
        match.away_team,
        getattr(match, "away_team_api_name", None),
    )

    has_home = _contains_any(text, home_aliases)
    has_away = _contains_any(text, away_aliases)
    if not (has_home and has_away):
        return 0

    score = 72
    if "чемпионат мира" in text or "чм" in text:
        score += 8
    if video.video_type in {"highlights", "review", "live", "full_replay"}:
        score += 10
    if re.search(r"[а-яa-z]+\s+-\s+[а-яa-z]+", text):
        score += 5
    # Avoid linking historical archive videos unless the teams and WC-2026 text
    # strongly point to the current tournament.
    if any(word in text for word in ["чм-2022", "чм 2022", "чм-2018", "чм 2018", "чм-2014", "чм 2014", "чм-2010", "чм 2010", "чм-2006", "чм 2006"]):
        score -= 40
    if "молодеж" in text or "отбороч" in text:
        score -= 30
    return max(0, min(100, score))


def _load_candidate_matches(db: Session, start_at: datetime, end_at: datetime) -> list[Match]:
    filters = [Match.starts_at >= start_at, Match.starts_at <= end_at]
    matches = (
        db.query(Match)
        .filter(Match.tournament_code == TOURNAMENT_CODE, *filters)
        .order_by(Match.starts_at.asc())
        .all()
    )
    if matches:
        return matches

    # Be tolerant if older imports have empty/different tournament_code.
    matches = (
        db.query(Match)
        .filter(*filters)
        .order_by(Match.starts_at.asc())
        .all()
    )
    if matches:
        return matches

    # Last fallback: if server date/time is off or the admin intentionally wants
    # to rescan old/current cards, compare to all imported WC fixtures.
    return (
        db.query(Match)
        .filter(or_(Match.tournament_code == TOURNAMENT_CODE, Match.tournament_code.is_(None)))
        .order_by(Match.starts_at.asc())
        .all()
    )




NOTIFIABLE_VIDEO_TYPES = {"highlights"}


def _video_push_title(video_type: str) -> str:
    return "Появился обзор матча"


def _match_push_label(match: Match) -> str:
    home = _ru_team_name(getattr(match, "home_team", None)) or str(getattr(match, "home_team", "") or "").strip()
    away = _ru_team_name(getattr(match, "away_team", None)) or str(getattr(match, "away_team", "") or "").strip()
    return f"{home} — {away}".strip(" —")


def _notify_new_match_videos(db: Session, videos: list[MatchVideo]) -> int:
    """Send one PWA push per newly active highlights video."""
    sent_total = 0
    now = datetime.now(timezone.utc)
    for video in videos:
        if not video or not getattr(video, "id", None):
            continue
        if not bool(getattr(video, "is_active", False)):
            continue
        if getattr(video, "notification_sent_at", None):
            continue
        video_type = (getattr(video, "video_type", None) or "other").lower()
        if video_type not in NOTIFIABLE_VIDEO_TYPES:
            continue
        match = getattr(video, "match", None)
        if match is None and getattr(video, "match_id", None):
            match = db.query(Match).filter(Match.id == video.match_id).first()
        match_label = _match_push_label(match) if match else "матча"
        body = f"🎥 {_video_push_title(video_type)} {match_label}"
        sent_total += notify_active_web_push_subscribers_for_notification(
            db,
            "match_videos",
            title="Отец прогнозов",
            body=body,
            url=f"/app?match_id={getattr(video, 'match_id', '')}",
        )
        video.notification_sent_at = now
        video.updated_at = now
    if videos:
        db.commit()
    return sent_total


def sync_matchtv_videos(
    db: Session,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    lookahead_days: int = DEFAULT_LOOKAHEAD_DAYS,
    activate_min_confidence: int = 85,
) -> dict:
    """Discover Match TV videos and upsert links for nearby World Cup matches."""
    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=lookback_days)
    end_at = now + timedelta(days=lookahead_days)

    matches = _load_candidate_matches(db, start_at, end_at)
    discovered = fetch_matchtv_worldcup_videos()

    created = 0
    updated = 0
    matched = 0
    skipped_low_confidence = 0
    duplicate_count = 0
    push_notifications_sent = 0
    notify_candidates: list[MatchVideo] = []
    unmatched_samples: list[str] = []
    best_debug: list[dict] = []

    for video in discovered:
        best_match: Match | None = None
        best_score = 0
        for match in matches:
            score = _match_video_score(video, match)
            if score > best_score:
                best_score = score
                best_match = match

        if not best_match or best_score < 70:
            skipped_low_confidence += 1
            if len(unmatched_samples) < 8:
                unmatched_samples.append(video.title[:160])
            continue

        matched += 1
        if len(best_debug) < 10:
            best_debug.append({
                "title": video.title[:160],
                "match_id": best_match.id,
                "match": f"{best_match.home_team} — {best_match.away_team}",
                "score": best_score,
            })

        video_type = video.video_type
        if video_type == "other" and not bool(best_match.is_finished) and best_match.starts_at <= now + timedelta(days=lookahead_days):
            video_type = "live"
            best_score = min(100, best_score + 10)

        existing = db.query(MatchVideo).filter(MatchVideo.url == video.url).first()

        if existing:
            was_active = bool(existing.is_active)
            was_hidden = (getattr(existing, "discovery_status", None) or "").lower() == "hidden"
            should_be_active = (best_score >= activate_min_confidence) and not was_hidden
            new_discovery_status = "hidden" if was_hidden else ("verified" if should_be_active else "found")
            changed = any([
                existing.match_id != best_match.id,
                existing.title != video.title,
                existing.video_type != video_type,
                getattr(existing, "confidence", None) != best_score,
                bool(existing.is_active) != should_be_active,
            ])
            existing.match_id = best_match.id
            existing.title = video.title
            existing.video_type = video_type
            existing.source = "matchtv"
            existing.priority = VIDEO_TYPE_PRIORITY.get(video_type, 100)
            existing.discovery_status = new_discovery_status
            existing.confidence = best_score
            existing.is_active = should_be_active
            existing.external_id = video.external_id or video.url
            existing.discovered_at = now
            existing.updated_at = now
            if not was_active and should_be_active and not getattr(existing, "notification_sent_at", None):
                notify_candidates.append(existing)
            updated += 1 if changed else 0
            duplicate_count += 0 if changed else 1
            continue

        match_video = MatchVideo(
            match_id=best_match.id,
            source="matchtv",
            video_type=video_type,
            title=video.title,
            url=video.url,
            is_active=best_score >= activate_min_confidence,
            priority=VIDEO_TYPE_PRIORITY.get(video_type, 100),
            discovery_status="verified" if best_score >= activate_min_confidence else "found",
            confidence=best_score,
            external_id=video.external_id or video.url,
            discovered_at=now,
        )
        db.add(match_video)
        if bool(match_video.is_active):
            notify_candidates.append(match_video)
        created += 1

    db.commit()
    push_notifications_sent = _notify_new_match_videos(db, notify_candidates)
    return {
        "source_url": MATCHTV_WC_VIDEO_URL,
        "matches_checked": len(matches),
        "videos_found_on_source": len(discovered),
        "videos_matched": matched,
        "created": created,
        "updated": updated,
        "duplicates_unchanged": duplicate_count,
        "push_notifications_sent": push_notifications_sent,
        "skipped_low_confidence": skipped_low_confidence,
        "lookback_days": lookback_days,
        "lookahead_days": lookahead_days,
        "activate_min_confidence": activate_min_confidence,
        "unmatched_samples": unmatched_samples,
        "matched_samples": best_debug,
    }
