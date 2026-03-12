FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY apps ./apps
COPY libs ./libs
COPY migrations ./migrations
COPY services ./services
COPY data ./data

RUN uv sync --no-dev

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN groupadd --system app && useradd --system --create-home --gid app app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/apps /app/apps
COPY --from=builder /app/libs /app/libs
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/services /app/services
COPY --from=builder /app/data /app/data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
