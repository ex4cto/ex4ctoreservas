# Garay Tours — Claude Code Project Instructions

## Engram Project Key

**CRÍTICO**: El proyecto vive en `github.com/ex4cto/ex4ctoreservas.git`.
Engram auto-detecta el proyecto como `ex4ctoreservas` (desde el git remote).

- Siempre buscar en engram con `project: "ex4ctoreservas"`
- Siempre guardar en engram con `project: "ex4ctoreservas"`
- **NUNCA usar `project: "garay tours"`** — ese bucket tiene observaciones pre-agosto 2026 desactualizadas

Regla de arranque de sesión: llamar `mem_context` o `mem_search` con `project: "ex4ctoreservas"` antes de cualquier trabajo.

## Stack

- Python 3.12, arquitectura hexagonal (dominio → aplicación → infraestructura)
- Telegram bot (python-telegram-bot), FastAPI webhook, SQLAlchemy + PostgreSQL
- `uv run pytest -q` — TDD estricto: RED → GREEN → mypy --strict → ruff
- Deploy en Railway (auto-deploy desde main)

## Estándares clave

- Leer `docs/ESTANDARES.md` antes de cualquier cambio de código
- `from __future__ import annotations` en todos los archivos Python
- `fmt_cop()` para montos, `parsear_monto()` para input, `html.escape()` para strings de usuario
- Mensajes siempre en `garay.mensajes.catalogo` — ningún string suelto en la lógica
- Commits convencionales, sin "Co-Authored-By"

## Backlog

El backlog vivo está en engram: `topic: "roadmap/garay-bot-backlog"`, `project: "ex4ctoreservas"`.
Última actualización: 2026-10-07.
