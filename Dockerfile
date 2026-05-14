FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps from pyproject only first (better layer caching).
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install \
       "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
       "pydantic-settings>=2.6" "sqlalchemy>=2.0" "asyncpg>=0.30" \
       "alembic>=1.13" "httpx>=0.27" "openai>=1.54" "anthropic>=0.39" \
       "langgraph>=0.2.50" "langgraph-checkpoint-postgres>=2.0" \
       "langsmith>=0.1.140" "tenacity>=9.0" "structlog>=24.4" \
       "prometheus-client>=0.21" "cryptography>=43" \
       "python-jose[cryptography]>=3.3" "jinja2>=3.1" "sse-starlette>=2.1" \
       "pyyaml>=6.0" "python-multipart>=0.0.20" \
       "bcrypt>=4.2" "itsdangerous>=2.2" \
       "mcp>=1.0"

# Copy source. Compose mounts override these in dev for hot reload.
COPY app ./app
COPY evals ./evals
COPY config ./config
COPY alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
