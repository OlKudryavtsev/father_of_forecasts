from datetime import datetime

from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import Base, SessionLocal, engine
from app.models import Match, Prediction, TournamentPrediction, User
from app.scoring import score_match_prediction, score_tournament_prediction
from app.admin import require_admin_api_token

app = FastAPI(title="Отец прогнозов")

Base.metadata.create_all(bind=engine)

from app.api.webapp import router as webapp_router

MINIAPP_STATIC_DIR = Path(__file__).resolve().parent / "miniapp_static"

app.include_router(webapp_router)

if MINIAPP_STATIC_DIR.exists():
    app.mount(
        "/miniapp-static",
        StaticFiles(directory=str(MINIAPP_STATIC_DIR)),
        name="miniapp-static",
    )


@app.get("/app")
def telegram_mini_app(
    web_token: str | None = Query(default=None),
    ff_web_session: str | None = Cookie(default=None),
):
    """Serve Telegram Mini App/PWA frontend.

    When /app is opened with ?web_token=..., persist it into a cookie.
    This is important for iOS Home Screen/PWA mode: iOS starts the saved
    icon from the manifest start_url (/app), so query params/localStorage
    from Safari are not reliable enough.
    """
    index_path = MINIAPP_STATIC_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Mini App frontend is not built")

    response = FileResponse(index_path)

    if web_token:
        response.set_cookie(
            key="ff_web_session",
            value=web_token,
            max_age=60 * 60 * 24 * 180,
            httponly=False,
            secure=True,
            samesite="lax",
            path="/",
        )

    return response



class MatchCreate(BaseModel):
    home_team: str
    away_team: str
    starts_at: datetime
    stage: str = "group"
    tournament_code: str = "wc2026"


class MatchResultUpdate(BaseModel):
    score_home: int
    score_away: int
    winner_side: str | None = None

class TournamentResultUpdate(BaseModel):
    champion: str
    runner_up: str
    third_place: str
    top_scorer: str
    tournament_code: str = "wc2026"

@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"health": "green"}


@app.get("/users")
def get_users():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id).all()
        return [
            {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "display_name": user.display_name,
            }
            for user in users
        ]
    finally:
        db.close()


@app.get("/matches")
def get_matches():
    db = SessionLocal()
    try:
        matches = db.query(Match).order_by(Match.starts_at).all()
        return [
            {
                "id": match.id,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "stage": match.stage,
                "starts_at": match.starts_at,
                "score_home": match.score_home,
                "score_away": match.score_away,
                "is_finished": match.is_finished,
            }
            for match in matches
        ]
    finally:
        db.close()


@app.post("/admin/matches", dependencies=[Depends(require_admin_api_token)])
def create_match(payload: MatchCreate):
    db = SessionLocal()
    try:
        match = Match(
            home_team=payload.home_team,
            away_team=payload.away_team,
            starts_at=payload.starts_at,
            stage=payload.stage,
            tournament_code=payload.tournament_code,
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        return {
            "id": match.id,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "starts_at": match.starts_at,
        }
    finally:
        db.close()


@app.post("/admin/matches/{match_id}/result")
def set_match_result(match_id: int, payload: MatchResultUpdate):
    db = SessionLocal()

    try:
        match = db.query(Match).filter(Match.id == match_id).first()

        if not match:
            raise HTTPException(status_code=404, detail="Match not found")

        if payload.winner_side not in (None, "home", "away"):
            raise HTTPException(
                status_code=400,
                detail="winner_side must be 'home', 'away' or null",
            )

        match.score_home = payload.score_home
        match.score_away = payload.score_away
        match.winner_side = payload.winner_side
        match.is_finished = True

        predictions = db.query(Prediction).filter(
            Prediction.match_id == match.id
        ).all()

        recalculated = []

        for prediction in predictions:
            result = score_match_prediction(
                pred_home=prediction.pred_home,
                pred_away=prediction.pred_away,
                actual_home=payload.score_home,
                actual_away=payload.score_away,
                advancement_bet_enabled=prediction.advancement_bet_enabled,
                predicted_advancing_side=prediction.predicted_advancing_side,
                actual_winner_side=payload.winner_side,
            )

            prediction.score_points = result["score_points"]
            prediction.advancement_points = result["advancement_points"]
            prediction.points = result["total_points"]

            recalculated.append(
                {
                    "user": prediction.user.display_name,
                    "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                    "advancement_bet_enabled": prediction.advancement_bet_enabled,
                    "predicted_advancing_side": prediction.predicted_advancing_side,
                    "score_points": prediction.score_points,
                    "advancement_points": prediction.advancement_points,
                    "total_points": prediction.points,
                }
            )

        db.commit()

        return {
            "match": f"{match.home_team} — {match.away_team}",
            "result": f"{payload.score_home}:{payload.score_away}",
            "winner_side": payload.winner_side,
            "recalculated_predictions": recalculated,
        }

    finally:
        db.close()

@app.post("/admin/recalculate", dependencies=[Depends(require_admin_api_token)])
def recalculate_all_finished_matches():
    db = SessionLocal()

    try:
        finished_matches = db.query(Match).filter(
            Match.is_finished == True
        ).all()

        recalculated_matches = []

        for match in finished_matches:
            if match.score_home is None or match.score_away is None:
                continue

            predictions = db.query(Prediction).filter(
                Prediction.match_id == match.id
            ).all()

            recalculated_predictions = []

            for prediction in predictions:
                result = score_match_prediction(
                    pred_home=prediction.pred_home,
                    pred_away=prediction.pred_away,
                    actual_home=match.score_home,
                    actual_away=match.score_away,
                    advancement_bet_enabled=prediction.advancement_bet_enabled,
                    predicted_advancing_side=prediction.predicted_advancing_side,
                    actual_winner_side=match.winner_side,
                )

                prediction.score_points = result["score_points"]
                prediction.advancement_points = result["advancement_points"]
                prediction.points = result["total_points"]

                recalculated_predictions.append(
                    {
                        "user": prediction.user.display_name,
                        "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                        "score_points": prediction.score_points,
                        "advancement_points": prediction.advancement_points,
                        "total_points": prediction.points,
                    }
                )

            recalculated_matches.append(
                {
                    "match_id": match.id,
                    "match": f"{match.home_team} — {match.away_team}",
                    "result": f"{match.score_home}:{match.score_away}",
                    "winner_side": match.winner_side,
                    "predictions": recalculated_predictions,
                }
            )

        db.commit()

        return {
            "status": "ok",
            "recalculated_matches_count": len(recalculated_matches),
            "matches": recalculated_matches,
        }

    finally:
        db.close()

@app.get("/predictions")
def get_predictions():
    db = SessionLocal()
    try:
        predictions = db.query(Prediction).all()

        return [
            {
                "id": prediction.id,
                "user": prediction.user.display_name,
                "match": f"{prediction.match.home_team} — {prediction.match.away_team}",
                "prediction": f"{prediction.pred_home}:{prediction.pred_away}",
                "points": prediction.points,
            }
            for prediction in predictions
        ]
    finally:
        db.close()


@app.get("/table")
def get_table():
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.display_name).all()

        table = []

        for user in users:
            predictions = db.query(Prediction).filter(
                Prediction.user_id == user.id
            ).all()

            match_points = sum(prediction.points or 0 for prediction in predictions)

            tournament_prediction = db.query(TournamentPrediction).filter(
                TournamentPrediction.user_id == user.id,
                TournamentPrediction.tournament_code == "wc2026",
            ).first()

            tournament_points = (
                tournament_prediction.points
                if tournament_prediction
                else 0
            )

            total_points = match_points + tournament_points
            exact_scores = sum(
                1
                for prediction in predictions
                if prediction.points == 3
            )
            outcomes = sum(
                1
                for prediction in predictions
                if prediction.points == 1
            )

            table.append(
                {
                    "user": user.display_name,
                    "points": total_points,
                    "exact_scores": exact_scores,
                    "outcomes": outcomes,
                    "predictions_count": len(predictions),
                    "match_points": match_points,
                    "tournament_points": tournament_points,
                }
            )

        table.sort(
            key=lambda row: (
                row["points"],
                row["exact_scores"],
                row["outcomes"],
            ),
            reverse=True,
        )

        return table

    finally:
        db.close()

@app.get("/tournament-predictions")
def get_tournament_predictions():
    db = SessionLocal()

    try:
        predictions = db.query(TournamentPrediction).all()

        return [
            {
                "id": prediction.id,
                "user": prediction.user.display_name,
                "tournament_code": prediction.tournament_code,
                "champion": prediction.champion,
                "runner_up": prediction.runner_up,
                "third_place": prediction.third_place,
                "top_scorer": prediction.top_scorer,
                "champion_points": prediction.champion_points,
                "runner_up_points": prediction.runner_up_points,
                "third_place_points": prediction.third_place_points,
                "top_scorer_points": prediction.top_scorer_points,
                "points": prediction.points,
            }
            for prediction in predictions
        ]

    finally:
        db.close()


@app.post(
    "/admin/tournament-result",
    dependencies=[Depends(require_admin_api_token)],
)
def set_tournament_result(payload: TournamentResultUpdate):
    db = SessionLocal()

    try:
        predictions = db.query(TournamentPrediction).filter(
            TournamentPrediction.tournament_code == payload.tournament_code
        ).all()

        recalculated = []

        for prediction in predictions:
            result = score_tournament_prediction(
                pred_champion=prediction.champion,
                pred_runner_up=prediction.runner_up,
                pred_third_place=prediction.third_place,
                pred_top_scorer=prediction.top_scorer,
                actual_champion=payload.champion,
                actual_runner_up=payload.runner_up,
                actual_third_place=payload.third_place,
                actual_top_scorer=payload.top_scorer,
            )

            prediction.champion_points = result["champion_points"]
            prediction.runner_up_points = result["runner_up_points"]
            prediction.third_place_points = result["third_place_points"]
            prediction.top_scorer_points = result["top_scorer_points"]
            prediction.points = result["total_points"]

            recalculated.append(
                {
                    "user": prediction.user.display_name,
                    "champion": prediction.champion,
                    "runner_up": prediction.runner_up,
                    "third_place": prediction.third_place,
                    "top_scorer": prediction.top_scorer,
                    "champion_points": prediction.champion_points,
                    "runner_up_points": prediction.runner_up_points,
                    "third_place_points": prediction.third_place_points,
                    "top_scorer_points": prediction.top_scorer_points,
                    "total_points": prediction.points,
                }
            )

        db.commit()

        return {
            "status": "ok",
            "tournament_code": payload.tournament_code,
            "actual_result": {
                "champion": payload.champion,
                "runner_up": payload.runner_up,
                "third_place": payload.third_place,
                "top_scorer": payload.top_scorer,
            },
            "recalculated_predictions": recalculated,
        }

    finally:
        db.close()