"""Entorno de migraciones Alembic.

La URL de la base y el metadata objetivo se resuelven desde la aplicacion:
- URL: configuracion centralizada (GARAY_DATABASE_URL), nunca hardcodeada.
- metadata: Base.metadata. A medida que se creen modelos (Etapa 1+), importarlos aca
  para que autogenerate los detecte.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from garay.config import obtener_settings
from garay.infraestructura.persistencia.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", obtener_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migraciones en modo 'offline' (sin conexion, genera SQL)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migraciones en modo 'online' (con conexion a la base)."""
    seccion = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        seccion,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
