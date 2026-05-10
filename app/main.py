from fastapi import FastAPI

from app.db import Base, engine

# импорт обязателен для регистрации моделей
from app.models import User

app = FastAPI(title="Отец прогнозов")

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"health": "green"}