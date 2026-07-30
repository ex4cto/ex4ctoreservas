web: uv run alembic upgrade head && uv run uvicorn garay.infraestructura.webhook.main:app --host 0.0.0.0 --port $PORT
worker: uv run python -m garay.infraestructura.telegram.main
