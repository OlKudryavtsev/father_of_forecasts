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
from sqlalchemy.orm import Session

from app.models import Match, MatchVideo
from app.runtime import TOURNAMENT_CODE
from app.team_names import get_team_name_ru

MATCHTV_WC_VIDEO_URL = os.getenv(
    "MATCHTV_WC_VIDEO_URL",
    "https://matchtv.ru/football/worldcup/video",
)

REQUEST_TIMEOUT_SECONDS = int(os.getenv("MATCHTV_VIDEO_REQUEST_TIMEOUT", "15"))
DEFAULT_LOOKBACK_DAYS = int(os.getenv("MATCHTV_VIDEO_LOOKBACK_DAYS", "3"))
DEFAULT_LOOKAHEAD_DAYS = int(os.getenv("MATCHTV_VIDEO_LOOKAHEAD_DAYS", "2"))

VIDEO_TYPE_PRIORITY = {
    "live": 10,
    "highlights": 20,
    "review": 30,
    "full_replay": 40,
    "goal": 60,
    "moment": 70,
    "other": 100,
}

TEAM_ALIASES_EXTRA = {
    "Южная Корея": ["Корея"],
    "ЮАР": ["Южная Африка"],
    "США": ["Соединенные Штаты", "Сша"],
    "ДР Конго": ["ДР Конго", "Конго"],
    "Кот-д’Ивуар": ["Кот-д'Ивуар", "Кот-д’Ивуар", "Кот д Ивуар"],
    "Кабо-Верде": ["Кабо Верде"],
    "Нидерланды": ["Голландия"],
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
    value = re.sub(r"[^a-zа-я0-9\-\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _team_aliases(name: str | None) -> list[str]:
    ru_name = get_team_name_ru(name)
    aliases = [name or "", ru_name]
    aliases.extend(TEAM_ALIASES_EXTRA.get(ru_name, []))
    seen: set[str] = set()
    result: list[str] = []
    for item in aliases:
        normalized = _normalize_text(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _contains_any(text: str, aliases: Iterable[str]) -> bool:
    return any(alias and alias in text for alias in aliases)


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
    return "moment" if any(word in text for word in ["момент", "удар", "спасает", "столкновение", "пенальти"]) else "other"


def _extract_cards(html_text: str, base_url: str = MATCHTV_WC_VIDEO_URL) -> list[DiscoveredVideo]:
    """Extract candidate video cards from Match TV HTML.

    Match TV markup changes often, so this parser is intentionally heuristic:
    it collects links that point to matchtv.ru pages and keeps visible text near
    those links. Admin review remains available in the UI.
    """
    candidates: dict[str, DiscoveredVideo] = {}

    # Prefer anchor text when available.
    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, flags=re.I | re.S):
        href, inner = match.group(1), match.group(2)
        url = urljoin(base_url, html.unescape(href))
        if "matchtv.ru" not in url:
            continue
        if "/video" not in url and "/football/worldcup" not in url:
            continue
        text = re.sub(r"<[^>]+>", " ", inner)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if len(text) < 5:
            continue
        vtype = _classify_video(text)
        if vtype == "other" and "чемпионат мира" not in _normalize_text(text):
            continue
        candidates[url] = DiscoveredVideo(
            title=text[:200],
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
        nearby = html.unescape(re.sub(r"<[^>]+>", " ", html_text[start:end]))
        nearby = re.sub(r"\s+", " ", nearby).strip()
        title = nearby[:200]
        if len(title) < 5:
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
    home_aliases = _team_aliases(match.home_team)
    away_aliases = _team_aliases(match.away_team)

    has_home = _contains_any(text, home_aliases)
    has_away = _contains_any(text, away_aliases)
    if not (has_home and has_away):
        return 0

    score = 70
    if "чемпионат мира" in text or "чм" in text:
        score += 10
    if video.video_type in {"highlights", "review", "live", "full_replay"}:
        score += 10
    if "молодеж" in text or "отбороч" in text:
        score -= 30
    return max(0, min(100, score))


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

    matches = (
        db.query(Match)
        .filter(
            Match.tournament_code == TOURNAMENT_CODE,
            Match.starts_at >= start_at,
            Match.starts_at <= end_at,
        )
        .order_by(Match.starts_at.asc())
        .all()
    )

    discovered = fetch_matchtv_worldcup_videos()
    created = 0
    updated = 0
    matched = 0
    skipped_low_confidence = 0

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
            continue

        matched += 1

        video_type = video.video_type
        # The upcoming/live cards on Match TV can be plain "Team A - Team B"
        # without the word "трансляция". If a high-confidence card matches a
        # nearby not-yet-finished game, show it as a live link.
        if video_type == "other" and not bool(best_match.is_finished) and best_match.starts_at <= now + timedelta(days=lookahead_days):
            video_type = "live"
            best_score = min(100, best_score + 10)

        existing = (
            db.query(MatchVideo)
            .filter(MatchVideo.url == video.url)
            .first()
        )

        if existing:
            existing.match_id = best_match.id
            existing.title = video.title
            existing.video_type = video_type
            existing.source = "matchtv"
            existing.priority = VIDEO_TYPE_PRIORITY.get(video_type, 100)
            existing.discovery_status = "verified" if best_score >= activate_min_confidence else "found"
            existing.confidence = best_score
            existing.external_id = video.external_id or video.url
            existing.discovered_at = now
            existing.updated_at = now
            updated += 1
            continue

        db.add(MatchVideo(
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
        ))
        created += 1

    db.commit()
    return {
        "source_url": MATCHTV_WC_VIDEO_URL,
        "matches_checked": len(matches),
        "videos_found_on_source": len(discovered),
        "videos_matched": matched,
        "created": created,
        "updated": updated,
        "skipped_low_confidence": skipped_low_confidence,
        "lookback_days": lookback_days,
        "lookahead_days": lookahead_days,
    }
