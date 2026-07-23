"""Base declarativa comun a todos los modelos ORM."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa. Todos los modelos ORM heredan de aca.

    Su ``metadata`` es lo que Alembic usa para generar migraciones.
    """
