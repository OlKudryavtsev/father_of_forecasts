def get_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def score_match_result_points(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
) -> int:
    """
    3 очка — точный счет
    1 очко — угаданный исход
    0 очков — иначе
    """

    if pred_home == actual_home and pred_away == actual_away:
        return 3

    if get_outcome(pred_home, pred_away) == get_outcome(actual_home, actual_away):
        return 1

    return 0


def score_advancement_points(
    advancement_bet_enabled: bool,
    predicted_advancing_side: str | None,
    actual_winner_side: str | None,
) -> int:
    """
    Плей-офф:
    если участник НЕ ставил на проход — 0
    если ставил и угадал — +1
    если ставил и не угадал — -1
    """

    # ``predicted_advancing_side`` is the authoritative user choice.  Early
    # playoff rows created during the rollout can contain the side while the
    # auxiliary Boolean remains false; treating those as “no bet” silently
    # drops a deserved +1 / -1 during recalculation.
    has_advancement_pick = bool(advancement_bet_enabled) or predicted_advancing_side in {"home", "away"}

    if not has_advancement_pick:
        return 0

    if predicted_advancing_side not in {"home", "away"} or actual_winner_side not in {"home", "away"}:
        return 0

    if predicted_advancing_side == actual_winner_side:
        return 1

    return -1


def score_match_prediction(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
    advancement_bet_enabled: bool = False,
    predicted_advancing_side: str | None = None,
    actual_winner_side: str | None = None,
) -> dict:
    score_points = score_match_result_points(
        pred_home=pred_home,
        pred_away=pred_away,
        actual_home=actual_home,
        actual_away=actual_away,
    )

    advancement_points = score_advancement_points(
        advancement_bet_enabled=advancement_bet_enabled,
        predicted_advancing_side=predicted_advancing_side,
        actual_winner_side=actual_winner_side,
    )

    return {
        "score_points": score_points,
        "advancement_points": advancement_points,
        "total_points": score_points + advancement_points,
    }

def normalize_text(value: str | None) -> str:
    """Normalize user/API text for stable prediction scoring."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-zа-я0-9]+", " ", normalized.casefold().replace("ё", "е")).strip()


_TEAM_ALIASES = {
    "argentina": "аргентина",
    "australia": "австралия",
    "austria": "австрия",
    "belgium": "бельгия",
    "bosnia herzegovina": "босния и герцеговина",
    "bosnia and herzegovina": "босния и герцеговина",
    "brazil": "бразилия",
    "canada": "канада",
    "cape verde": "кабо верде",
    "cape verde islands": "кабо верде",
    "colombia": "колумбия",
    "congo dr": "др конго",
    "dr congo": "др конго",
    "croatia": "хорватия",
    "ecuador": "эквадор",
    "egypt": "египет",
    "england": "англия",
    "france": "франция",
    "germany": "германия",
    "ghana": "гана",
    "ivory coast": "кот д ивуар",
    "cote d ivoire": "кот д ивуар",
    "japan": "япония",
    "mexico": "мексика",
    "morocco": "марокко",
    "netherlands": "нидерланды",
    "holland": "нидерланды",
    "norway": "норвегия",
    "paraguay": "парагваи",
    "portugal": "португалия",
    "south africa": "юар",
    "spain": "испания",
    "sweden": "швеция",
    "switzerland": "швейцария",
    "usa": "сша",
    "united states": "сша",
}


def _team_key(value: str | None) -> str:
    normalized = normalize_text(value)
    return _TEAM_ALIASES.get(normalized, normalized)


_PLAYER_ALIASES = {
    "эрлинг холанд": "erling haaland",
    "холанд": "erling haaland",
    "erling braut haaland": "erling haaland",
    "erling haaland": "erling haaland",
    "haaland": "erling haaland",
    "килиан мбаппе": "kylian mbappe",
    "мбаппе": "kylian mbappe",
    "kylian mbappe": "kylian mbappe",
    "харри кеин": "harry kane",
    "харри кейн": "harry kane",
    "гарри кеин": "harry kane",
    "гарри кейн": "harry kane",
    "кеин": "harry kane",
    "кейн": "harry kane",
    "harry kane": "harry kane",
    "ламин ямаль": "lamine yamal",
    "ламин ямал": "lamine yamal",
    "ямаль": "lamine yamal",
    "ямал": "lamine yamal",
    "yamal": "lamine yamal",
    "lamine yamal": "lamine yamal",
    "винисиус жуниор": "vinicius junior",
    "vinicius jr": "vinicius junior",
    "vinicius junior": "vinicius junior",
    "лаутаро мартинес": "lautaro martinez",
    "криштиану роналду": "cristiano ronaldo",
    "ромелу лукаку": "romelu lukaku",
    "усман дембеле": "ousmane dembele",
    "лионель месси": "lionel messi",
    "джуд беллингем": "jude bellingham",
    "рафинья": "raphinha",
}


def _player_key(value: str | None) -> str:
    normalized = normalize_text(value)
    return _PLAYER_ALIASES.get(normalized, normalized)


def _same_team(left: str | None, right: str | None) -> bool:
    return bool(_team_key(left) and _team_key(left) == _team_key(right))


def _same_player(left: str | None, right: str | None) -> bool:
    left_key = _player_key(left)
    right_key = _player_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    left_parts = left_key.split()
    right_parts = right_key.split()
    return (
        len(left_parts) >= 2
        and len(right_parts) >= 2
        and left_parts[-1] == right_parts[-1]
        and left_parts[0][:1] == right_parts[0][:1]
    )


def score_tournament_prediction(
    pred_champion: str,
    pred_runner_up: str,
    pred_third_place: str,
    pred_top_scorer: str,
    actual_champion: str,
    actual_runner_up: str,
    actual_third_place: str,
    actual_top_scorer: str,
) -> dict:
    champion_points = 0
    runner_up_points = 0
    third_place_points = 0
    top_scorer_points = 0

    if _same_team(pred_champion, actual_champion):
        champion_points = 15

    if _same_team(pred_runner_up, actual_runner_up):
        runner_up_points = 10

    if _same_team(pred_third_place, actual_third_place):
        third_place_points = 5

    if _same_player(pred_top_scorer, actual_top_scorer):
        top_scorer_points = 15

    total_points = (
        champion_points
        + runner_up_points
        + third_place_points
        + top_scorer_points
    )

    return {
        "champion_points": champion_points,
        "runner_up_points": runner_up_points,
        "third_place_points": third_place_points,
        "top_scorer_points": top_scorer_points,
        "total_points": total_points,
    }