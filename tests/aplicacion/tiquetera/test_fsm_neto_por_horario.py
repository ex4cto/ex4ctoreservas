"""Tests for FSM neto derivation with per-horario pricing.

TDD: RED phase — written before the implementation.
Covers T-10 scenarios: morning slot, afternoon slot, fallback, no horario.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta
from tests.aplicacion.tiquetera.conftest import catalogo_fsm


def _ctx_con_fecha_y_horario(numero: int, horario: str | None) -> ContextoVenta:
    """Return a ContextoVenta with one destino, date, and optional horario set."""
    ctx = ContextoVenta()
    ctx.destinos_numeros = [numero]
    ctx.destinos_nombres = ["City Tour"]
    ctx.fechas_por_servicio = {numero: datetime.date(2026, 12, 25)}
    ctx.fecha_salida = datetime.date(2026, 12, 25)
    ctx.adultos = 2
    ctx.ninos = 0
    if horario is not None:
        ctx.horarios_por_servicio = {numero: horario}
    return ctx


def _ctx_con_fecha_sin_horario(numero: int) -> ContextoVenta:
    """Return a ContextoVenta with one destino and date but NO horario selection."""
    ctx = ContextoVenta()
    ctx.destinos_numeros = [numero]
    ctx.destinos_nombres = ["City Tour"]
    ctx.fechas_por_servicio = {numero: datetime.date(2026, 12, 25)}
    ctx.fecha_salida = datetime.date(2026, 12, 25)
    ctx.adultos = 1
    ctx.ninos = 0
    # horarios_por_servicio intentionally left empty
    return ctx


_NETOS_CITY_TOUR: dict[str, Decimal] = {
    "08:00": Decimal("60000"),
    "13:00": Decimal("55000"),
}


class TestCalcularNetoConHorario:
    """_calcular_neto uses per-horario neto when available."""

    def test_horario_manana_usa_neto_especifico(self) -> None:
        """When 08:00 is selected and netos_por_horario has an entry, uses 60000 x adultos."""
        servicios = catalogo_fsm(
            {
                "numero": 130,
                "nombre": "City Tour Climatizado",
                "neto_a": Decimal("50000"),  # default fallback
                "neto_n": None,
                "horarios": ["08:00", "13:00"],
                "netos_por_horario": _NETOS_CITY_TOUR,
            }
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha_y_horario(numero=130, horario="08:00")
        ctx.adultos = 2
        neto = fsm._calcular_neto(ctx)
        assert neto == Decimal("120000")  # 60000 x 2

    def test_horario_tarde_usa_neto_especifico(self) -> None:
        """When 13:00 is selected and netos_por_horario has an entry, uses 55000 x adultos."""
        servicios = catalogo_fsm(
            {
                "numero": 130,
                "nombre": "City Tour Climatizado",
                "neto_a": Decimal("50000"),
                "neto_n": None,
                "horarios": ["08:00", "13:00"],
                "netos_por_horario": _NETOS_CITY_TOUR,
            }
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha_y_horario(numero=130, horario="13:00")
        ctx.adultos = 2
        neto = fsm._calcular_neto(ctx)
        assert neto == Decimal("110000")  # 55000 x 2

    def test_sin_netos_por_horario_usa_precio_neto_adulto(self) -> None:
        """When netos_por_horario is empty, falls back to precio_neto_adulto."""
        servicios = catalogo_fsm(
            {
                "numero": 1,
                "nombre": "Tour Sin Neto Horario",
                "neto_a": Decimal("50000"),
                "neto_n": None,
                "horarios": ["08:00"],
                "netos_por_horario": {},
            }
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha_y_horario(numero=1, horario="08:00")
        ctx.adultos = 1
        neto = fsm._calcular_neto(ctx)
        assert neto == Decimal("50000")

    def test_sin_horario_seleccionado_usa_precio_neto_adulto(self) -> None:
        """When no horario is in horarios_por_servicio, falls back to precio_neto_adulto."""
        servicios = catalogo_fsm(
            {
                "numero": 130,
                "nombre": "City Tour Climatizado",
                "neto_a": Decimal("50000"),
                "neto_n": None,
                "horarios": ["08:00", "13:00"],
                "netos_por_horario": _NETOS_CITY_TOUR,
            }
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha_sin_horario(numero=130)
        neto = fsm._calcular_neto(ctx)
        # No horario selected → fallback to precio_neto_adulto=50000 x 1
        assert neto == Decimal("50000")

    def test_tour_sin_netos_horario_comportamiento_identico_a_hoy(self) -> None:
        """Services without netos_por_horario behave exactly as before."""
        # catalogo_fsm without netos_por_horario key should default to {}
        servicios = catalogo_fsm(
            {"numero": 1, "neto_a": Decimal("50000"), "neto_n": None}
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha_sin_horario(numero=1)
        neto = fsm._calcular_neto(ctx)
        assert neto == Decimal("50000")


class TestRefrescarServiciosConNetos:
    """refrescar_servicios with netos_por_horario data updates internal catalog."""

    def test_refrescar_actualiza_netos_por_horario(self) -> None:
        """After refrescar_servicios, _calcular_neto uses the updated per-horario netos."""
        servicios_init = catalogo_fsm(
            {"numero": 130, "neto_a": Decimal("50000"), "neto_n": None}
        )
        fsm = FSMTiquetera(servicios=servicios_init, puntos_venta=["PDV"])

        # Refresh with per-horario data
        servicios_new = catalogo_fsm(
            {
                "numero": 130,
                "neto_a": Decimal("50000"),
                "neto_n": None,
                "netos_por_horario": {"08:00": Decimal("60000")},
            }
        )
        fsm.refrescar_servicios(servicios_new)

        ctx = _ctx_con_fecha_y_horario(numero=130, horario="08:00")
        ctx.adultos = 1
        neto = fsm._calcular_neto(ctx)
        assert neto == Decimal("60000")
