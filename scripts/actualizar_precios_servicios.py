"""Actualizacion quirurgica de precios y permite_ninos de servicios desde el seed JSON.

A diferencia de ``seed_servicios`` (que reescribe nombre, categoria, activo y
descripcion), este script actualiza UNICAMENTE ``precio_neto_adulto``,
``precio_neto_nino`` y ``permite_ninos``. No toca ``activo``, ``nombre``,
``categoria``, ``descripcion`` ni ``horarios``, de modo que las ediciones
manuales en produccion (desactivaciones, renombres, horarios) sobreviven.

Empareja por ``numero`` (unico). Es idempotente y seguro de re-ejecutar.

Uso:
    railway run python -m scripts.actualizar_precios_servicios --dry-run
    railway run python -m scripts.actualizar_precios_servicios
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from garay.config import obtener_settings
from garay.infraestructura.persistencia.modelos import ServicioModel
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from scripts.seed import SERVICIOS_JSON, _neto_semilla


@dataclass
class ResumenActualizacion:
    """Numeros de servicio agrupados por resultado de la actualizacion."""

    actualizados: list[int] = field(default_factory=list)
    sin_cambios: list[int] = field(default_factory=list)
    no_encontrados: list[int] = field(default_factory=list)


def actualizar_precios(session: Session, entries: list[Any]) -> ResumenActualizacion:
    """Aplica precios y permite_ninos del JSON sobre los servicios existentes.

    Solo modifica los tres campos de precio/ninos; el resto queda intacto.
    """
    resumen = ResumenActualizacion()
    for entry in entries:
        numero = int(entry["numero"])
        row = session.execute(
            select(ServicioModel).where(ServicioModel.numero == numero)
        ).scalar_one_or_none()
        if row is None:
            resumen.no_encontrados.append(numero)
            continue

        nuevo_adulto = _neto_semilla(entry.get("neto_adulto"))
        nuevo_nino = _neto_semilla(entry.get("neto_nino"))
        nuevo_permite = bool(entry.get("permite_ninos", True))

        if (
            row.precio_neto_adulto == nuevo_adulto
            and row.precio_neto_nino == nuevo_nino
            and row.permite_ninos == nuevo_permite
        ):
            resumen.sin_cambios.append(numero)
            continue

        row.precio_neto_adulto = nuevo_adulto
        row.precio_neto_nino = nuevo_nino
        row.permite_ninos = nuevo_permite
        resumen.actualizados.append(numero)
    return resumen


def cargar_entries() -> list[Any]:
    """Lee las entradas del catalogo desde servicios_seed.json."""
    data: list[Any] = json.loads(SERVICIOS_JSON.read_text(encoding="utf-8"))
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Actualiza precios/permite_ninos de servicios.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Reporta los cambios sin persistirlos (rollback).",
    )
    args = parser.parse_args()

    settings = obtener_settings()
    if not settings.database_url:
        raise SystemExit("ERROR: GARAY_DATABASE_URL no configurada.")

    engine = crear_engine(settings.database_url)
    sf = crear_fabrica_sesiones(engine)
    entries = cargar_entries()

    with sf() as session:
        resumen = actualizar_precios(session, entries)
        if args.dry_run:
            session.rollback()
            modo = "DRY-RUN (sin cambios persistidos)"
        else:
            session.commit()
            modo = "APLICADO"

    print(f"[{modo}]")
    print(f"Actualizados : {len(resumen.actualizados)} -> {resumen.actualizados}")
    print(f"Sin cambios  : {len(resumen.sin_cambios)}")
    print(f"No encontrados: {resumen.no_encontrados}")


if __name__ == "__main__":
    main()
