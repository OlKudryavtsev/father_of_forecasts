FROM node:20-slim AS miniapp-build
WORKDIR /miniapp
COPY app/miniapp_frontend/package.json ./
RUN npm install
COPY app/miniapp_frontend ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=miniapp-build /miniapp/dist /app/app/miniapp_static

CMD sh -c "python bot.py & uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
