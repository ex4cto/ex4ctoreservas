#!/usr/bin/env python
"""Seed script — populates the database with initial reference data.

Run after alembic upgrade head:
    python scripts/seed.py

Requires GARAY_DATABASE_URL set in environment or .env file.
Idempotent: uses deterministic UUIDs (uuid5) so re-running is safe.
"""

from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from garay.config import obtener_settings
from garay.dominio.comun.tipos import TipoCliente
from garay.infraestructura.persistencia.modelos import (
    CategoriaEgresoModel,
    FreelancerModel,
    PuntoDeVentaModel,
    ReglasComisionModel,
    ServicioModel,
)
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones

ROOT = Path(__file__).parent.parent
SERVICIOS_JSON = ROOT / "servicios_seed.json"

# Fixed namespace — deterministic UUIDs ensure idempotency across runs.
SEED_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# ---------------------------------------------------------------------------
# Neto string parser
# ---------------------------------------------------------------------------

_MIL_RE = re.compile(r"(\d[\d.,]*)\s*MIL", re.IGNORECASE)
# Require at least 2 digits to avoid single-digit age numbers being treated as prices
_NUM_RE = re.compile(r"\d[\d.,]+")


def _parse_neto(texto: str | int | float | None) -> Decimal | None:
    """Parse a dirty neto price string into a Decimal, or None if unparseable."""
    if texto is None:
        return None
    if not isinstance(texto, str):
        texto = str(texto)
    texto = texto.strip()
    if not texto:
        return None
    # Children not allowed or free — treat as 0 regardless of digit presence
    if re.search(r"no\s+pagan|no\s+ingresan|no\s+se\s+aceptan", texto, re.IGNORECASE):
        return Decimal("0")
    # Strings with no digits at all
    if not re.search(r"\d", texto):
        return None
    # "50 MIL" → 50000
    mil_match = _MIL_RE.search(texto)
    if mil_match:
        base = mil_match.group(1).replace(".", "").replace(",", "")
        try:
            return Decimal(base) * 1000
        except InvalidOperation:
            return None
    # First multi-digit number (>= 2 digits to ignore single-digit age noise)
    num_match = _NUM_RE.search(texto)
    if num_match:
        limpio = num_match.group(0).replace(".", "").replace(",", "")
        try:
            return Decimal(limpio)
        except InvalidOperation:
            return None
    return None


def _neto_semilla(texto: str | int | float | None) -> Decimal | None:
    """Parse neto for the seed context, where plain numbers are in miles de pesos.

    "180" → 180,000 COP; "80.000" and "50 MIL" already parse to ≥ 1000 and are not scaled.
    """
    valor = _parse_neto(texto)
    if valor is not None and valor < 1000:
        return valor * 1000
    return valor


def seed_id(key: str) -> uuid.UUID:
    """Return a deterministic UUID for the given seed key."""
    return uuid.uuid5(SEED_NS, key)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

PUNTOS: list[dict[str, object]] = [
    {"nombre": "Marie Real", "porcentaje_capa": Decimal("0")},
    {"nombre": "Mama Waldi", "porcentaje_capa": Decimal("0")},
    {"nombre": "Dora Hostal", "porcentaje_capa": Decimal("0")},
    {"nombre": "Crespo", "porcentaje_capa": Decimal("20")},
]

REGLAS: list[dict[str, object]] = [
    {
        "tipo_cliente": TipoCliente.INTERNO,
        "vendedor": Decimal("20"),
        "cerrador": Decimal("20"),
        "referido_max": Decimal("10"),
    },
    {
        "tipo_cliente": TipoCliente.EXTERNO,
        "vendedor": Decimal("30"),
        "cerrador": Decimal("30"),
        "referido_max": Decimal("10"),
    },
    {
        "tipo_cliente": TipoCliente.DIGITAL,
        "vendedor": Decimal("15"),
        "cerrador": Decimal("15"),
        "referido_max": Decimal("10"),
    },
]

FREELANCERS: list[str] = [
    "Tania",
    "Eduardo",
    "David",
    "Yolimar",
    "Mairelis",
    "Maximo",
    "Zaida",
    "Kike",
]

CATEGORIAS_EGRESO: list[tuple[str, str, int]] = [
    ("arriendo", "Arriendo de local u oficina", 1),
    ("nomina", "Sueldos y honorarios", 2),
    ("uniformes", "Uniformes y dotacion", 3),
    ("papeleria", "Papeleria y materiales", 4),
    ("proveedor", "Pagos a proveedores de tours", 5),
    ("ocasional", "Gastos ocasionales no recurrentes", 6),
    ("otro", "Otros gastos", 7),
]

FREELANCERS_ADMIN: list[tuple[str, int | None]] = [
    ("Garay", None),  # TODO: set real Telegram ID
    ("Sharimel", None),  # TODO: set real Telegram ID
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def seed_servicios(session: Session) -> None:
    """Load services from servicios_seed.json into the database."""
    raw = json.loads(SERVICIOS_JSON.read_text(encoding="utf-8"))
    for entry in raw:
        numero: int = int(entry["numero"])
        session.merge(
            ServicioModel(
                id=seed_id(f"servicio:{numero}"),
                numero=numero,
                nombre=str(entry["nombre"]),
                descripcion="",
                activo=bool(entry["activo"]),
                precio_neto_adulto=_neto_semilla(entry.get("neto_adulto")),
                precio_neto_nino=_neto_semilla(entry.get("neto_nino")),
            )
        )


def seed_puntos_de_venta(session: Session) -> None:
    """Insert the four physical sales points."""
    for punto in PUNTOS:
        nombre = str(punto["nombre"])
        porcentaje = Decimal(str(punto["porcentaje_capa"]))
        session.merge(
            PuntoDeVentaModel(
                id=seed_id(f"punto:{nombre}"),
                nombre=nombre,
                porcentaje_capa=porcentaje,
            )
        )


def seed_reglas_comision(session: Session) -> None:
    """Insert one commission rule per client type."""
    for regla in REGLAS:
        tipo = regla["tipo_cliente"]
        assert isinstance(tipo, TipoCliente)
        vendedor = Decimal(str(regla["vendedor"]))
        cerrador = Decimal(str(regla["cerrador"]))
        referido_max = Decimal(str(regla["referido_max"]))
        session.merge(
            ReglasComisionModel(
                id=seed_id(f"regla:{tipo.value}"),
                tipo_cliente=tipo.value,
                porcentaje_vendedor=vendedor,
                porcentaje_cerrador=cerrador,
                porcentaje_referido_maximo=referido_max,
            )
        )


def seed_freelancers(session: Session) -> None:
    """Insert the eight initial freelancers."""
    for nombre in FREELANCERS:
        session.merge(
            FreelancerModel(
                id=seed_id(f"freelancer:{nombre}"),
                nombre=nombre,
                activo=True,
                telegram_user_id=None,
            )
        )


def seed_categorias_egreso(session: Session) -> None:
    """Insert the initial expense categories (idempotent via primary key merge)."""
    for nombre, descripcion, orden in CATEGORIAS_EGRESO:
        session.merge(
            CategoriaEgresoModel(
                nombre=nombre,
                descripcion=descripcion,
                activo=True,
                orden=orden,
            )
        )


def seed_freelancers_admin(session: Session) -> None:
    """Insert admin freelancers with es_admin=True."""
    for nombre, telegram_user_id in FREELANCERS_ADMIN:
        session.merge(
            FreelancerModel(
                id=seed_id(f"freelancer:{nombre}"),
                nombre=nombre,
                activo=True,
                telegram_user_id=telegram_user_id,
                es_admin=True,
            )
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    settings = obtener_settings()
    if not settings.database_url:
        raise SystemExit(
            "ERROR: GARAY_DATABASE_URL not configured. Create .env from env.example."
        )

    engine = crear_engine(settings.database_url)
    sf: sessionmaker[Session] = crear_fabrica_sesiones(engine)

    with sf.begin() as session:
        seed_servicios(session)
        seed_puntos_de_venta(session)
        seed_reglas_comision(session)
        seed_freelancers(session)
        seed_freelancers_admin(session)
        seed_categorias_egreso(session)

    print("Seed completed.")


if __name__ == "__main__":
    main()
