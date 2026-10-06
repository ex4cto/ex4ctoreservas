#!/bin/sh
uv run alembic upgrade head && \
    exec uv run uvicorn garay.infraestructura.webhook.main:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}"
