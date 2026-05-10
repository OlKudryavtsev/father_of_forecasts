
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install fastapi uvicorn sqlalchemy psycopg2-binary aiogram
CMD -sh -c ["python bot.py & uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
