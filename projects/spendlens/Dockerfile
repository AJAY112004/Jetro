# SpendLens production Dockerfile (Frontend + Flask in one container)

FROM node:20-alpine AS frontend-build
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps 2>/dev/null || npm install --legacy-peer-deps
COPY frontend/ ./

# Build-time env for Vite.
ENV VITE_API_URL=/api
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  gcc \
  && rm -rf /var/lib/apt/lists/*

COPY scripts/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Flask entrypoint (serves frontend/dist + /api/*)
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/
COPY data/ /app/data/
COPY --from=frontend-build /build/dist /app/frontend/dist

ENV PORT=8080
ENV FLASK_DEBUG=0
ENV AUTH_ENABLED=1
ENV SESSION_COOKIE_SECURE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')\" || exit 1

CMD [\"python\", \"/app/scripts/app.py\"]

