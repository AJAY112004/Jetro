# SpendLens — Render Docker Deployment
# Build context: projects/spendlens/

# ---------- Frontend Build ----------
  FROM node:20-alpine AS frontend-build

  WORKDIR /build
  
  COPY frontend/package*.json ./
  
  RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps
  
  COPY frontend/ .
  
  ENV VITE_API_URL=/api
  
  RUN npm run build
  
  
  # ---------- Backend Runtime ----------
  FROM python:3.12-slim
  
  WORKDIR /app
  
  RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      && rm -rf /var/lib/apt/lists/*
  
  # Install dependencies
  COPY deploy/requirements.txt ./deploy/requirements.txt
  
  RUN pip install --upgrade pip && \
      pip install --no-cache-dir -r deploy/requirements.txt
  
  # Copy application files
  COPY scripts ./scripts
  COPY data ./data
  COPY deploy ./deploy
  
  # Copy built frontend
  COPY --from=frontend-build /build/dist ./frontend/dist
  
  # Environment
  ENV PORT=8080
  # ENV FLASK_DEBUG=0
  # ENV USE_GUNICORN=1
  # ENV SESSION_COOKIE_SECURE=1
  # ENV PYTHONUNBUFFERED=1
  
  EXPOSE 8080
  
  # Healthcheck
  HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')" || exit 1
  
  # Start application
  CMD python /app/deploy/server.py