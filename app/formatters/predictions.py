"""Real implementation extracted from the former bot_runtime monolith."""


from app.runtime import Match, Prediction

def format_advancement_prediction(prediction: Prediction, match: Match) -> str:
    """Provide bot helper logic for format_advancement_prediction."""
    if not prediction.advancement_bet_enabled:
        return "проход: не ставил"

    if prediction.predicted_advancing_side == "home":
        return f"проход: {match.home_team}"

    if prediction.predicted_advancing_side == "away":
        return f"проход: {match.away_team}"

    return "проход: не указан"

