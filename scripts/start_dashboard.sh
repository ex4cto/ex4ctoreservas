#!/bin/sh
exec uv run streamlit run dashboard/app.py \
    --server.port "${PORT:-8501}" \
    --server.headless true \
    --server.address 0.0.0.0
