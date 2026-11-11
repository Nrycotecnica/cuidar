# syntax=docker/dockerfile:1
# Imagem única: frontend (React compilado) + backend (FastAPI) servidos pelo mesmo processo.

FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd --create-home --uid 1000 app
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY VERSION /app/VERSION
COPY --from=frontend /src/frontend/dist /app/frontend/dist
COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && mkdir -p /dados/arquivos && chown -R app:app /dados

ARG APP_VERSION=0.0.0-dev
ARG GIT_SHA=local
ARG BUILD_DATE=
ENV APP_VERSION=${APP_VERSION} GIT_SHA=${GIT_SHA} BUILD_DATE=${BUILD_DATE} \
    FRONTEND_DIST=/app/frontend/dist STORAGE_DIR=/dados/arquivos

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/saude', timeout=4)"]
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
