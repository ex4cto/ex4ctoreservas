"""Tests for MonitorCostoRailwayService.

Uses an in-memory FakeProveedorUsoRailway to avoid any external dependency.

Month-boundary rule tested:
  When anteayer (hoy - 2 days) falls before the first day of ayer's month,
  costo_previo is forced to 0.0 (the previous month's cost is not relevant;
  the new month starts fresh, enabling a clean re-alert).
  This mirrors the same rule in MonitorCuotaResendService.
"""

from __future__ import annotations

import datetime
from dataclasses import FrozenInstanceError

import pytest

from garay.aplicacion.infraestructura_monitor.costo_railway import (
    AvisoCostoRailway,
    MonitorCostoRailwayService,
)
from garay.dominio.infraestructura_monitor.costo_railway import PreciosRailway
from garay.dominio.puertos.proveedor_uso_railway import ProveedorUsoRailway

# ---------------------------------------------------------------------------
# Standard prices and thresholds for most tests
# ---------------------------------------------------------------------------

_PRECIOS = PreciosRailway(
    precio_memoria_gb_min=0.000231,
    precio_cpu_vcpu_min=0.000463,
    precio_egress_gb=0.05,
    precio_volumen_gb_min=0.000003,
)
_UMBRAL = 20.0
_PLAN_FEE = 5.0

# A "big" resource measurement that yields cost > _UMBRAL (e.g. 100 GB egress = $5; need >$20)
# 500 GB egress * $0.05 = $25.0
_RECURSOS_CAROS: dict[str, float] = {"NETWORK_TX_GB": 500.0}  # $25.0

# A "cheap" measurement that stays below _UMBRAL
_RECURSOS_BARATOS: dict[str, float] = {"NETWORK_TX_GB": 10.0}  # $0.50


# ---------------------------------------------------------------------------
# Fake in-memory proveedor
# ---------------------------------------------------------------------------


class FakeProveedorUsoRailway(ProveedorUsoRailway):
    """In-memory stub: caller configures per-date usage dicts."""

    def __init__(
        self,
        uso_por_fecha: dict[datetime.date, dict[str, float]] | None = None,
        estimado: dict[str, float] | None = None,
    ) -> None:
        self._uso_por_fecha = uso_por_fecha or {}
        self._estimado = estimado or {}

    def uso_mes_a_la_fecha(self, hasta: datetime.date) -> dict[str, float]:
        return self._uso_por_fecha.get(hasta, {})

    def estimado_mes(self, hoy: datetime.date) -> dict[str, float]:
        return self._estimado


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    proveedor: ProveedorUsoRailway,
    precios: PreciosRailway = _PRECIOS,
    umbral: float = _UMBRAL,
    plan_fee: float = _PLAN_FEE,
) -> MonitorCostoRailwayService:
    return MonitorCostoRailwayService(
        proveedor=proveedor,
        precios=precios,
        umbral=umbral,
        plan_fee=plan_fee,
    )


# Reference dates for mid-month tests
_HOY = datetime.date(2026, 8, 16)  # hoy
_AYER = datetime.date(2026, 8, 15)  # hoy - 1
_ANTEAYER = datetime.date(2026, 8, 14)  # hoy - 2


# ---------------------------------------------------------------------------
# Threshold crossing fires
# ---------------------------------------------------------------------------


class TestCruceDePrecio:
    def test_cruce_umbral_devuelve_aviso(self) -> None:
        """Cost crosses $20 threshold: aviso returned with costo_actual and umbral."""
        # ayer = $25 (above), anteayer = $0.50 (below)
        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={_AYER: _RECURSOS_CAROS, _ANTEAYER: _RECURSOS_BARATOS},
            estimado=_RECURSOS_CAROS,
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)

        assert len(avisos) == 1
        aviso = avisos[0]
        assert aviso.costo_actual == pytest.approx(25.0)
        assert aviso.umbral == pytest.approx(_UMBRAL)

    def test_estimado_factura_incluido_en_aviso(self) -> None:
        """When aviso fires, estimado_factura = max(plan_fee, costo_estimado)."""
        # estimado also $25 → factura = max(5, 25) = 25
        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={_AYER: _RECURSOS_CAROS, _ANTEAYER: _RECURSOS_BARATOS},
            estimado=_RECURSOS_CAROS,
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)

        assert avisos[0].estimado_factura == pytest.approx(25.0)

    def test_estimado_factura_floored_at_plan_fee(self) -> None:
        """When estimado_uso < plan_fee, estimado_factura = plan_fee."""
        # actual crosses ($25), but estimado is very cheap ($0.10)
        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={_AYER: _RECURSOS_CAROS, _ANTEAYER: _RECURSOS_BARATOS},
            estimado={"NETWORK_TX_GB": 2.0},  # $0.10
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)

        assert avisos[0].estimado_factura == pytest.approx(_PLAN_FEE)


# ---------------------------------------------------------------------------
# No crossing: empty result
# ---------------------------------------------------------------------------


class TestSinCruce:
    def test_ambos_por_debajo_no_devuelve_aviso(self) -> None:
        """Both ayer and anteayer below threshold: no aviso."""
        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={_AYER: _RECURSOS_BARATOS, _ANTEAYER: _RECURSOS_BARATOS},
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)
        assert avisos == []

    def test_ya_estaba_encima_no_dispara_de_nuevo(self) -> None:
        """Both ayer and anteayer above threshold: no re-fire."""
        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={_AYER: _RECURSOS_CAROS, _ANTEAYER: _RECURSOS_CAROS},
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)
        assert avisos == []

    def test_sin_datos_no_dispara(self) -> None:
        """No usage data: cost = 0.0, below threshold, no aviso."""
        proveedor = FakeProveedorUsoRailway()
        service = _make_service(proveedor)
        avisos = service.avisos_para(_HOY)
        assert avisos == []


# ---------------------------------------------------------------------------
# Month-boundary reset: previo forced to 0
# ---------------------------------------------------------------------------


class TestMesBoundaryReset:
    def test_primer_dia_mes_previo_cero_dispara(self) -> None:
        """hoy=2026-09-02; ayer=2026-09-01; anteayer=2026-08-31 (prev month).
        costo_previo must be forced to 0 so a crossing can fire on the new month."""
        hoy = datetime.date(2026, 9, 2)
        ayer = datetime.date(2026, 9, 1)

        proveedor = FakeProveedorUsoRailway(
            # ayer = $25 (new month, above threshold)
            # anteayer (2026-08-31) is NOT configured → would return {} → cost 0.0
            # but since we force previo=0, this should fire correctly
            uso_por_fecha={ayer: _RECURSOS_CAROS},
            estimado=_RECURSOS_CAROS,
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(hoy)

        assert len(avisos) == 1
        assert avisos[0].costo_actual == pytest.approx(25.0)

    def test_primer_dia_mes_sin_cruce_no_dispara(self) -> None:
        """hoy=2026-09-02; ayer=2026-09-01; cost only $0.50 (below $20)."""
        hoy = datetime.date(2026, 9, 2)
        ayer = datetime.date(2026, 9, 1)

        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={ayer: _RECURSOS_BARATOS},
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(hoy)
        assert avisos == []

    def test_borde_diciembre_enero_dispara(self) -> None:
        """Year boundary: hoy=2027-01-02, ayer=2027-01-01, anteayer=2026-12-31.
        previo must be 0 so the new year's cost can trigger the alert."""
        hoy = datetime.date(2027, 1, 2)
        ayer = datetime.date(2027, 1, 1)

        proveedor = FakeProveedorUsoRailway(
            uso_por_fecha={ayer: _RECURSOS_CAROS},
            estimado=_RECURSOS_CAROS,
        )
        service = _make_service(proveedor)
        avisos = service.avisos_para(hoy)

        assert len(avisos) == 1
        assert avisos[0].costo_actual == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# AvisoCostoRailway dataclass
# ---------------------------------------------------------------------------


class TestAvisoCostoRailwayDataclass:
    def test_es_frozen(self) -> None:
        aviso = AvisoCostoRailway(
            costo_actual=25.0, umbral=20.0, estimado_factura=25.0
        )
        with pytest.raises(FrozenInstanceError):
            aviso.costo_actual = 99.0  # type: ignore[misc]

    def test_igualdad_por_valor(self) -> None:
        a = AvisoCostoRailway(costo_actual=25.0, umbral=20.0, estimado_factura=25.0)
        b = AvisoCostoRailway(costo_actual=25.0, umbral=20.0, estimado_factura=25.0)
        assert a == b
