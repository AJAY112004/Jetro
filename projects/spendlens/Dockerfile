# SpendLens production Dockerfile

# ---------- Frontend ----------
  FROM node:20-alpine AS frontend-build

  WORKDIR /build
  
  COPY frontend/package*.json ./
  
  RUN npm ci --legacy-peer-deps || npm install --legacy-peer-deps
  
  COPY frontend/ .
  
  ENV VITE_API_URL=/api
  
  RUN npm run build
  
  
  # ---------- Backend ----------
  FROM python:3.12-slim
  
  WORKDIR /app
  
  RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc \
      && rm -rf /var/lib/apt/lists/*
  
  # Install Python packages
  COPY deploy/requirements.txt ./requirements.txt
  
  RUN pip install --upgrade pip && \
      pip install --no-cache-dir -r requirements.txt
  
  
  # Copy application
  COPY backend ./backend
  COPY scripts ./scripts
  COPY deploy ./deploy
  COPY data ./data
  
  # Copy frontend build
  COPY --from=frontend-build /build/dist ./frontend/dist
  
  ENV PORT=8080
  ENV PYTHONUNBUFFERED=1
  
  EXPOSE 8080
  
  HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health')" || exit 1
  
  CMD python deploy/server.py