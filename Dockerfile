# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + serve frontend
FROM python:3.12-slim

# Install system deps for crawl4ai / playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy everything needed for pip install (src/, README, pyproject)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir . && \
    playwright install --with-deps chromium

# Copy remaining application code
COPY api_server.py ./
COPY baulkandcastle_scraper.py ./
COPY domain_estimator_helper.py ./
COPY ml/ ./ml/
COPY migrations/ ./migrations/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy entrypoint and cron
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY crontab /etc/cron.d/scraper-cron
RUN chmod +x /docker-entrypoint.sh && \
    chmod 0644 /etc/cron.d/scraper-cron && \
    crontab /etc/cron.d/scraper-cron

# Data volume for SQLite DB persistence
VOLUME ["/app/data"]

# Environment defaults
ENV BAULKANDCASTLE_DB_PATH=/app/data/baulkandcastle_properties.db \
    BAULKANDCASTLE_API_HOST=0.0.0.0 \
    BAULKANDCASTLE_API_PORT=5000 \
    BAULKANDCASTLE_FRONTEND_DIR=/app/frontend/dist \
    BAULKANDCASTLE_DEBUG=false

EXPOSE 5000

ENTRYPOINT ["/docker-entrypoint.sh"]
