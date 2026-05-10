def get_outcome(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def score_match_prediction(
    pred_home: int,
    pred_away: int,
    actual_home: int,
    actual_away: int,
) -> int:
    """
    Правила:
    - 3 очка за точный счет
    - 1 очко за угаданный исход
    - 0 очков иначе
    """

    if pred_home == actual_home and pred_away == actual_away:
        return 3

    predicted_outcome = get_outcome(pred_home, pred_away)
    actual_outcome = get_outcome(actual_home, actual_away)

    if predicted_outcome == actual_outcome:
        return 1

    return 0