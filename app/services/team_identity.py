"""Canonical team identity for Mini App payloads.

UI code must not guess club logos or mutate API responses.  This module is the
single server-side place that translates known club aliases, resolves the
association flag, and constructs an API-Sports crest URL from the team id that
is already stored on the Match row.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from app.constants.teams import TEAM_FLAG_CODES, TEAM_FLAGS
from app.team_names import get_team_name_ru


# name_ru, association flag code, aliases used by imported/API fixtures.
# Logo ids intentionally do NOT live here: the real Match.external_team_id is
# the source of truth for crests.
CLUB_IDENTITIES = (
    ("АЕК Афины", "gr", ("AEK Athens", "AEK", "AEK Athens FC", "АЕК Афины")),
    ("Арсенал", "gb-eng", ("Arsenal", "Arsenal FC", "Арсенал")),
    ("Астон Вилла", "gb-eng", ("Aston Villa", "Aston Villa FC", "Астон Вилла")),
    ("Атлетико Мадрид", "es", ("Atletico Madrid", "Atlético Madrid", "Atleti", "Atl. Madrid", "Атлетико Мадрид")),
    ("Барселона", "es", ("Barcelona", "FC Barcelona", "Барселона")),
    ("Бавария", "de", ("Bayern Munich", "Bayern München", "FC Bayern Munich", "Bayern", "Бавария")),
    ("Будё-Глимт", "no", ("Bodo/Glimt", "Bodø/Glimt", "Bodoe/Glimt", "Bodo Glimt", "Будё-Глимт")),
    ("Боруссия Дортмунд", "de", ("Borussia Dortmund", "Dortmund", "B. Dortmund", "Боруссия Дортмунд")),
    ("Брюгге", "be", ("Club Brugge", "Club Brugge KV", "Brugge", "Брюгге")),
    ("Комо", "it", ("Como", "Como 1907", "Комо")),
    ("Фенербахче", "tr", ("Fenerbahce", "Fenerbahçe", "Fenerbahce SK", "Фенербахче")),
    ("Фейеноорд", "nl", ("Feyenoord", "Feyenoord Rotterdam", "Фейеноорд")),
    ("Галатасарай", "tr", ("Galatasaray", "Galatasaray SK", "Галатасарай")),
    ("Интер", "it", ("Inter", "Inter Milan", "Internazionale", "Интер")),
    ("ЛАСК", "at", ("LASK", "Lask Linz", "LASK Linz", "ЛАСК")),
    ("Ланс", "fr", ("Lens", "RC Lens", "Ланс")),
    ("Лейпциг", "de", ("Leipzig", "RB Leipzig", "RasenBallsport Leipzig", "Лейпциг")),
    ("Лилль", "fr", ("Lille", "LOSC Lille", "Лилль")),
    ("Ливерпуль", "gb-eng", ("Liverpool", "Liverpool FC", "Ливерпуль")),
    ("Манчестер Сити", "gb-eng", ("Manchester City", "Man City", "Манчестер Сити")),
    ("Манчестер Юнайтед", "gb-eng", ("Manchester United", "Man Utd", "Manchester Utd", "Манчестер Юнайтед")),
    ("Наполи", "it", ("Napoli", "SSC Napoli", "Наполи")),
    ("Нанси", "fr", ("Nancy", "AS Nancy", "Nancy Lorraine", "Нанси")),
    ("ПСЖ", "fr", ("Paris Saint-Germain", "Paris SG", "PSG", "Paris", "ПСЖ")),
    ("Порту", "pt", ("Porto", "FC Porto", "Порту")),
    ("ПСВ", "nl", ("PSV Eindhoven", "PSV", "ПСВ")),
    ("Бетис", "es", ("Real Betis", "Betis", "Бетис")),
    ("Реал Мадрид", "es", ("Real Madrid", "Real Madrid CF", "Реал Мадрид")),
    ("Рома", "it", ("Roma", "AS Roma", "Рома")),
    ("Сабах", "az", ("Sabah", "Sabah FA", "Sabah FK", "Сабах")),
    ("Славия Прага", "cz", ("Slavia Praha", "Slavia Prague", "SK Slavia Praha", "Славия Прага")),
    ("Спортинг", "pt", ("Sporting CP", "Sporting Lisbon", "Sporting", "Спортинг")),
    ("Тоттенхэм", "gb-eng", ("Tottenham", "Tottenham Hotspur", "Spurs", "Тоттенхэм")),
    ("Викинг", "no", ("Viking", "Viking FK", "Викинг")),
    ("Вильярреал", "es", ("Villarreal", "Villarreal CF", "Вильярреал")),
    ("Висла Краков", "pl", ("Wisla Krakow", "Wisła Kraków", "Wisla Kraków", "Wisla Krakow SA", "Висла Краков")),
    ("Шахтёр", "ua", ("Shakhtar Donetsk", "Shakhtar", "FC Shakhtar Donetsk", "Шахтер", "Шахтёр")),
    ("Штутгарт", "de", ("VfB Stuttgart", "Stuttgart", "Штутгарт")),
    ("Слован Братислава", "sk", ("Slovan Bratislava", "ŠK Slovan Bratislava", "SK Slovan Bratislava", "Слован", "Слован Братислава")),
    ("Карабах", "az", ("Qarabag", "Qarabağ", "Qarabag FK", "Карабах")),
    ("Бенфика", "pt", ("Benfica", "SL Benfica", "Бенфика")),
    ("Аякс", "nl", ("Ajax", "Ajax Amsterdam", "Аякс")),
    ("Ювентус", "it", ("Juventus", "Juventus FC", "Ювентус")),
    ("Аталанта", "it", ("Atalanta", "Atalanta BC", "Аталанта")),
    ("Монако", "fr", ("Monaco", "AS Monaco", "Монако")),
    ("Марсель", "fr", ("Marseille", "Olympique Marseille", "Olympique de Marseille", "Марсель")),
    ("Олимпиакос", "gr", ("Olympiakos", "Olympiacos", "Olympiacos Piraeus", "Олимпиакос")),
    ("Селтик", "gb-sct", ("Celtic", "Celtic FC", "Селтик")),
    ("Ньюкасл", "gb-eng", ("Newcastle", "Newcastle United", "Ньюкасл")),
    ("Челси", "gb-eng", ("Chelsea", "Chelsea FC", "Челси")),
)


def normalize_team_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("ё", "е")
    text = re.sub(r"[«»\"'`]", "", text)
    text = re.sub(r"\b(fc|cf|sc|sk|fk|kv|sa|club|football|team)\b", " ", text)
    return re.sub(r"[^a-zа-я0-9]+", " ", text).strip()


_CLUB_BY_ALIAS: dict[str, dict] = {}
for _name_ru, _flag_code, _aliases in CLUB_IDENTITIES:
    _meta = {"name": _name_ru, "flag_code": _flag_code}
    for _alias in _aliases:
        _CLUB_BY_ALIAS[normalize_team_name(_alias)] = _meta


def _flag_emoji(flag_code: str) -> str:
    code = (flag_code or "").lower()
    if len(code) == 2 and code.isalpha():
        return "".join(chr(127397 + ord(char.upper())) for char in code)
    # Subdivision flags are rendered from flagcdn in the client.  This is
    # only an emoji fallback for clients where that image cannot load.
    if code.startswith("gb-"):
        return "🏴"
    return ""


def api_sports_team_logo(external_team_id: int | str | None) -> str:
    try:
        team_id = int(external_team_id or 0)
    except (TypeError, ValueError):
        return ""
    if team_id <= 0:
        return ""
    return f"https://media.api-sports.io/football/teams/{team_id}.png"


@lru_cache(maxsize=512)
def get_team_identity(
    team_name: str | None,
    api_name: str | None = None,
    external_team_id: int | str | None = None,
    tournament_code: str | None = None,
) -> dict:
    club = _CLUB_BY_ALIAS.get(normalize_team_name(api_name)) or _CLUB_BY_ALIAS.get(normalize_team_name(team_name))
    if club:
        display_name = club["name"]
        flag_code = club["flag_code"]
        flag = _flag_emoji(flag_code)
    else:
        display_name = get_team_name_ru(team_name)
        flag = TEAM_FLAGS.get(api_name or "") or TEAM_FLAGS.get(display_name) or TEAM_FLAGS.get(team_name or "") or ""
        flag_code = TEAM_FLAG_CODES.get(api_name or "") or TEAM_FLAG_CODES.get(display_name) or TEAM_FLAG_CODES.get(team_name or "") or ""

    code = str(tournament_code or "").casefold()
    is_club_tournament = bool(club) or code.startswith("ucl_") or code.startswith("ucl-")
    logo = api_sports_team_logo(external_team_id) if is_club_tournament else ""

    return {
        "name": display_name,
        "flag": flag,
        "flag_code": flag_code,
        "logo": logo,
    }
