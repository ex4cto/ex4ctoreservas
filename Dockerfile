FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

# Install uv
RUN pip install --upgrade pip uv

# Install Python dependencies (layer cached by uv.lock)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Application source
COPY src/ ./src/
COPY assets/ ./assets/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/

CMD ["/bin/sh", "-c", "uv run streamlit run /app/dashboard/app.py --server.port ${PORT:-8501} --server.headless true --server.address 0.0.0.0"]
