# Peblo TV Mini — API image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is used by the container healthcheck. psycopg2-binary and Pillow ship
# manylinux wheels, so no compiler/system libs are needed at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App source.
COPY . .
RUN chmod +x docker-entrypoint.sh

# Local storage backend writes here; mounted as a volume in docker-compose.
RUN mkdir -p /data/storage
ENV STORAGE_LOCAL_DIR=/data/storage

EXPOSE 8000

# Entrypoint runs migrations + idempotent seed/demo-publish, then starts uvicorn.
ENTRYPOINT ["./docker-entrypoint.sh"]
