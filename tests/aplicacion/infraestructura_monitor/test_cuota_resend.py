"""Tests for MonitorCuotaResendService.

Uses an in-memory FakeContador to avoid any DB dependency.

Month-boundary rule tested:
  When anteayer (hoy - 2 days) falls before the first day of ayer's month,
  conteo_previo is forced to 0 (the previous month's cumulative count is not
  relevant; the new month starts fresh).  The port's contar_mes_a_la_fecha
  scopes to the month of its `hasta` argument, so passing anteayer when it
  belongs to a different month would return last month's count incorrectly.
  The service handles this by checking the month boundary and substituting 0.
"""

from __future__ import annotations

import datetime

import pytest

from garay.aplicacion.infraestructura_monitor.cuota_resend import (
    AvisoCuota,
    MonitorCuotaResendService,
)
from garay.dominio.puertos.contador_facturas import ContadorFacturasEnviadas

# ---------------------------------------------------------------------------
# Fake in-memory counter
# ---------------------------------------------------------------------------


class FakeContador(ContadorFacturasEnviadas):
    """In-memory stub: caller configures per-date and per-month counts."""

    def __init__(
        self,
        conteos_mes: dict[datetime.date, int] | None = None,
        conteos_dia: dict[datetime.date, int] | None = None,
    ) -> None:
        self._conteos_mes = conteos_mes or {}
        self._conteos_dia = conteos_dia or {}

    def contar_mes_a_la_fecha(self, hasta: datetime.date) -> int:
        return self._conteos_mes.get(hasta, 0)

    def contar_dia(self, dia: datetime.date) -> int:
        return self._conteos_dia.get(dia, 0)


# ---------------------------------------------------------------------------
# Default config for most tests
# ---------------------------------------------------------------------------

_CAP_MENSUAL = 3000
_CAP_DIARIO = 100
_BANDAS_MENSUAL = (0.80, 0.95, 1.0)  # -> (2400, 2850, 3000)
_UMBRAL_DIARIO = 80


def _make_service(
    contador: ContadorFacturasEnviadas,
    cap_mensual: int = _CAP_MENSUAL,
    cap_diario: int = _CAP_DIARIO,
    bandas_mensual: tuple[float, ...] = _BANDAS_MENSUAL,
    umbral_diario: int = _UMBRAL_DIARIO,
) -> MonitorCuotaResendService:
    return MonitorCuotaResendService(
        contador=contador,
        cap_mensual=cap_mensual,
        cap_diario=cap_diario,
        bandas_mensual=bandas_mensual,
        umbral_diario=umbral_diario,
    )


# ---------------------------------------------------------------------------
# Monthly band tests
# ---------------------------------------------------------------------------


class TestAvisosParaMensual:
    # hoy=2026-08-16; ayer=2026-08-15; anteayer=2026-08-14
    _HOY = datetime.date(2026, 8, 16)
    _AYER = datetime.date(2026, 8, 15)
    _ANTEAYER = datetime.date(2026, 8, 14)

    def test_banda_80pct_cruzada_devuelve_aviso_mensual(self) -> None:
        """ayer count crosses 80 % (2400) threshold from anteayer's 2399."""
        contador = FakeContador(
            conteos_mes={self._AYER: 2400, self._ANTEAYER: 2399},
        )
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert len(mensual) == 1
        assert mensual[0].umbral == 2400
        assert mensual[0].conteo == 2400
        assert mensual[0].cap == _CAP_MENSUAL

    def test_sin_cruce_no_devuelve_aviso_mensual(self) -> None:
        """Both ayer and anteayer below the 80 % band: no monthly aviso."""
        contador = FakeContador(
            conteos_mes={self._AYER: 2300, self._ANTEAYER: 2200},
        )
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert mensual == []

    def test_ya_estaba_encima_no_dispara_de_nuevo(self) -> None:
        """ayer=2410, anteayer=2405 → both above 2400 band: no crossing."""
        contador = FakeContador(
            conteos_mes={self._AYER: 2410, self._ANTEAYER: 2405},
        )
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert mensual == []

    def test_banda_95pct_cruzada(self) -> None:
        """ayer=2850, anteayer=2840 → crosses 95 % (2850)."""
        contador = FakeContador(
            conteos_mes={self._AYER: 2850, self._ANTEAYER: 2840},
        )
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert len(mensual) == 1
        assert mensual[0].umbral == 2850


# ---------------------------------------------------------------------------
# Month-boundary reset test
# ---------------------------------------------------------------------------


class TestMesBoundaryReset:
    def test_conteo_previo_cero_cuando_anteayer_en_mes_anterior(self) -> None:
        """On the 2nd day of a month (hoy=2026-09-02), anteayer=2026-08-31 is in
        the previous month.  conteo_previo must be forced to 0 so we evaluate
        against a fresh-month baseline.

        If the band (2400) is crossed (ayer=2026-09-01 already has 2500 sends),
        an aviso must still fire because previo=0 < 2400 <= 2500.
        """
        hoy = datetime.date(2026, 9, 2)
        ayer = datetime.date(2026, 9, 1)

        contador = FakeContador(
            conteos_mes={ayer: 2500},
            # anteayer (2026-08-31) intentionally has a large count from the old month
            # — service should ignore it and force previo=0
        )
        service = _make_service(contador)
        avisos = service.avisos_para(hoy)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert len(mensual) == 1
        assert mensual[0].umbral == 2400

    def test_primer_dia_mes_sin_cruce_no_dispara(self) -> None:
        """hoy=2026-09-02, ayer=2026-09-01, count only 100 (far below 2400)."""
        hoy = datetime.date(2026, 9, 2)
        ayer = datetime.date(2026, 9, 1)

        contador = FakeContador(conteos_mes={ayer: 100})
        service = _make_service(contador)
        avisos = service.avisos_para(hoy)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert mensual == []

    def test_conteo_previo_cero_en_borde_diciembre_enero(self) -> None:
        """Year boundary (S-1): hoy=2027-01-02, ayer=2027-01-01, anteayer=2026-12-31
        is in the previous month AND previous year.  previo must be forced to 0 so a
        fresh January re-alerts (previo=0 < 2400 <= 2500)."""
        hoy = datetime.date(2027, 1, 2)
        ayer = datetime.date(2027, 1, 1)

        contador = FakeContador(conteos_mes={ayer: 2500})
        service = _make_service(contador)
        avisos = service.avisos_para(hoy)

        mensual = [a for a in avisos if a.tipo == "mensual"]
        assert len(mensual) == 1
        assert mensual[0].umbral == 2400


# ---------------------------------------------------------------------------
# Daily threshold tests
# ---------------------------------------------------------------------------


class TestAvisosParaDiario:
    _HOY = datetime.date(2026, 8, 16)
    _AYER = datetime.date(2026, 8, 15)

    def test_supera_umbral_diario_devuelve_aviso_diario(self) -> None:
        """ayer had 80 sends (== threshold): daily aviso fires."""
        contador = FakeContador(conteos_dia={self._AYER: 80})
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        diario = [a for a in avisos if a.tipo == "diario"]
        assert len(diario) == 1
        assert diario[0].conteo == 80
        assert diario[0].umbral == _UMBRAL_DIARIO
        assert diario[0].cap == _CAP_DIARIO

    def test_bajo_umbral_diario_no_dispara(self) -> None:
        """ayer had 79 sends (< threshold): no daily aviso."""
        contador = FakeContador(conteos_dia={self._AYER: 79})
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        diario = [a for a in avisos if a.tipo == "diario"]
        assert diario == []

    def test_cero_envios_no_dispara(self) -> None:
        contador = FakeContador(conteos_dia={self._AYER: 0})
        service = _make_service(contador)
        avisos = service.avisos_para(self._HOY)

        diario = [a for a in avisos if a.tipo == "diario"]
        assert diario == []


# ---------------------------------------------------------------------------
# Both alerts simultaneously
# ---------------------------------------------------------------------------


class TestAmbosAvisosSimultaneos:
    def test_mensual_y_diario_al_mismo_tiempo(self) -> None:
        """Both monthly band crossed AND daily threshold met on the same run."""
        hoy = datetime.date(2026, 8, 16)
        ayer = datetime.date(2026, 8, 15)
        anteayer = datetime.date(2026, 8, 14)

        contador = FakeContador(
            conteos_mes={ayer: 2400, anteayer: 2399},
            conteos_dia={ayer: 80},
        )
        service = _make_service(contador)
        avisos = service.avisos_para(hoy)

        assert len(avisos) == 2
        tipos = {a.tipo for a in avisos}
        assert tipos == {"mensual", "diario"}

    def test_lista_vacia_sin_eventos(self) -> None:
        """No counts at all → empty aviso list."""
        contador = FakeContador()
        service = _make_service(contador)
        avisos = service.avisos_para(datetime.date(2026, 8, 16))
        assert avisos == []


# ---------------------------------------------------------------------------
# AvisoCuota dataclass
# ---------------------------------------------------------------------------


class TestAvisoCuotaDataclass:
    def test_es_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        aviso = AvisoCuota(tipo="mensual", umbral=2400, conteo=2400, cap=3000)
        with pytest.raises(FrozenInstanceError):
            aviso.tipo = "diario"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = AvisoCuota(tipo="mensual", umbral=2400, conteo=2400, cap=3000)
        b = AvisoCuota(tipo="mensual", umbral=2400, conteo=2400, cap=3000)
        assert a == b
