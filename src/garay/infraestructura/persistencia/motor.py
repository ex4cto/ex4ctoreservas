"""Creacion del engine y de la fabrica de sesiones SQLAlchemy.

El engine se crea de forma explicita (nunca al importar el modulo) para no exigir una
base de datos disponible durante los tests o el arranque de partes que no la usan.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from garay.config import obtener_settings
from garay.dominio.comun.errores import ErrorDeConfiguracion


def crear_engine(url: str | None = None) -> Engine:
    """Crea el engine. Usa ``url`` o, si falta, ``database_url`` de la configuracion."""
    destino = url or obtener_settings().database_url
    if not destino:
        raise ErrorDeConfiguracion(
            "Falta la URL de la base de datos (GARAY_DATABASE_URL)."
        )
    return create_engine(destino, future=True)


def crear_fabrica_sesiones(engine: Engine) -> sessionmaker[Session]:
    """Devuelve una fabrica de sesiones ligada al ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False)
