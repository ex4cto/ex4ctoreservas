"""Sincronizacion quirurgica del catalogo de servicios desde servicios_seed.json.

A diferencia de ``seed_servicios`` (que reescribe todos los campos), este script
actualiza UNICAMENTE ``nombre``, ``activo`` y ``categoria`` para servicios
existentes. Para servicios nuevos (numero no en DB) inserta la fila completa con
valores por defecto para los campos de precio/horarios.

No toca ``horarios``, ``descripcion``, ``precio_neto_adulto``,
``precio_neto_nino`` ni ``permite_ninos``, de modo que las ediciones manuales
en produccion (precios, horarios, descripciones) sobreviven.

Empareja por ``numero`` (unico). Es idempotente y seguro de re-ejecutar.

Uso:
    railway run python -m scripts.sincronizar_catalogo --dry-run
    railway run python -m scripts.sincronizar_catalogo
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from garay.aplicacion.servicios.lista_precios import PublicarListaPreciosServicio, publicar_seguro
from garay.config import obtener_settings
from garay.infraestructura.imagenes.generador_playwright import PlaywrightGeneradorImagen
from garay.infraestructura.persistencia.modelos import ServicioModel
from garay.infraestructura.persistencia.motor import crear_engine, crear_fabrica_sesiones
from garay.infraestructura.persistencia.repositorios.servicios import SQLAServicioRepository
from garay.infraestructura.telegram.enviador_foto import EnviadorFotoTelegram
from scripts.seed import SERVICIOS_JSON, seed_id


@dataclass
class ResumenSincronizacion:
    """Numeros de servicio agrupados por resultado de la sincronizacion."""

    actualizados: list[int] = field(default_factory=list)
    insertados: list[int] = field(default_factory=list)
    sin_cambios: list[int] = field(default_factory=list)


def sincronizar_catalogo(session: Session, entries: list[Any]) -> ResumenSincronizacion:
    """Sincroniza nombre, activo y categoria desde las entradas del seed JSON.

    Para cada entrada:
    - Si el numero NO existe en DB: inserta con valores por defecto para precio y horarios.
    - Si el numero YA existe: actualiza solo nombre, activo y categoria.
    - Si no hubo cambio: registra como sin_cambios.

    Nunca toca horarios, descripcion, precio_neto_adulto, precio_neto_nino ni permite_ninos.
    """
    resumen = ResumenSincronizacion()
    for entry in entries:
        numero = int(entry["numero"])
        nombre = str(entry["nombre"])
        activo = bool(entry["activo"])
        categoria = str(entry.get("categoria") or "")

        row = session.execute(
            select(ServicioModel).where(ServicioModel.numero == numero)
        ).scalar_one_or_none()

        if row is None:
            nuevo = ServicioModel(
                id=seed_id(f"servicio:{numero}"),
                numero=numero,
                nombre=nombre,
                activo=activo,
                categoria=categoria,
                descripcion="",
                precio_neto_adulto=None,
                precio_neto_nino=None,
                permite_ninos=True,
            )
            session.add(nuevo)
            resumen.insertados.append(numero)
            continue

        # Check for actual changes in the three mutable fields
        if row.nombre == nombre and row.activo == activo and row.categoria == categoria:
            resumen.sin_cambios.append(numero)
            continue

        row.nombre = nombre
        row.activo = activo
        row.categoria = categoria
        resumen.actualizados.append(numero)

    return resumen


def cargar_entries() -> list[Any]:
    """Lee las entradas del catalogo desde servicios_seed.json."""
    data: list[Any] = json.loads(SERVICIOS_JSON.read_text(encoding="utf-8"))
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza nombre/activo/categoria de servicios.")
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
        resumen = sincronizar_catalogo(session, entries)
        if args.dry_run:
            session.rollback()
            modo = "DRY-RUN (sin cambios persistidos)"
        else:
            session.commit()
            modo = "APLICADO"

    print(f"[{modo}]")
    print(f"Insertados   : {len(resumen.insertados)} -> {resumen.insertados}")
    print(f"Actualizados : {len(resumen.actualizados)} -> {resumen.actualizados}")
    print(f"Sin cambios  : {len(resumen.sin_cambios)}")

    if not args.dry_run:
        servicio_repo = SQLAServicioRepository(sf)
        generador = PlaywrightGeneradorImagen()
        enviador = EnviadorFotoTelegram(token=settings.telegram_bot_token)
        publicar_service = PublicarListaPreciosServicio(
            repo=servicio_repo,
            generador=generador,
            enviador_foto=enviador,
            grupo_id=settings.grupo_id,
        )
        asyncio.run(publicar_seguro(publicar_service))


if __name__ == "__main__":
    main()
