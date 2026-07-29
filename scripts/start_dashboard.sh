#!/bin/sh
exec uv run streamlit run dashboard/app.py --server.port "${PORT:-8501}"
