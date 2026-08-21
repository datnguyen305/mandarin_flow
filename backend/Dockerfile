FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.deno/bin:${PATH}"

ARG INSTALL_DEV=false

COPY requirements*.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip \
    && DENO_INSTALL=/usr/local curl -fsSL https://deno.land/install.sh | sh \
    && apt-get purge -y --auto-remove unzip \
    && rm -rf /var/lib/apt/lists/*
RUN if [ "$INSTALL_DEV" = "true" ]; then \
      pip install --no-cache-dir -r requirements-dev.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
