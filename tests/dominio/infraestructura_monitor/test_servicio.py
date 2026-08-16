from __future__ import annotations

import datetime

from garay.dominio.infraestructura_monitor.entidades import ServicioInfraestructura
from garay.dominio.infraestructura_monitor.servicio import (
    banda_alerta_de_hoy,
    dias_restantes,
)

_RENOVACION = datetime.date(2027, 3, 15)
_BANDAS_DEFAULT = (60, 30, 7, 1)


def _servicio(
    fecha: datetime.date = _RENOVACION,
    bandas: tuple[int, ...] = _BANDAS_DEFAULT,
) -> ServicioInfraestructura:
    return ServicioInfraestructura(
        nombre="Dominio garaytours.com",
        fecha_renovacion=fecha,
        bandas_aviso=bandas,
    )


class TestDiasRestantes:
    def test_fecha_futura_60_dias(self) -> None:
        s = _servicio()
        assert dias_restantes(s, datetime.date(2027, 1, 14)) == 60

    def test_fecha_vencida_negativa(self) -> None:
        s = _servicio()
        assert dias_restantes(s, datetime.date(2027, 3, 20)) == -5

    def test_mismo_dia_cero(self) -> None:
        s = _servicio()
        assert dias_restantes(s, datetime.date(2027, 3, 15)) == 0


class TestBandaAlertaDeHoy:
    # --- Exact hits on default bands ---
    def test_hit_exacto_banda_60(self) -> None:
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 1, 14)) == 60

    def test_hit_exacto_banda_30(self) -> None:
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 2, 13)) == 30

    def test_hit_exacto_banda_7(self) -> None:
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 8)) == 7

    def test_hit_exacto_banda_1(self) -> None:
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 14)) == 1

    # --- Off-by-one around band 60 ---
    def test_off_by_one_arriba_banda_60(self) -> None:
        # dias=61 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 1, 13)) is None

    def test_off_by_one_abajo_banda_60(self) -> None:
        # dias=59 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 1, 15)) is None

    # --- Off-by-one around band 30 ---
    def test_off_by_one_arriba_banda_30(self) -> None:
        # dias=31 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 2, 12)) is None

    def test_off_by_one_abajo_banda_30(self) -> None:
        # dias=29 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 2, 14)) is None

    # --- Off-by-one around band 7 ---
    def test_off_by_one_arriba_banda_7(self) -> None:
        # dias=8 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 7)) is None

    def test_off_by_one_abajo_banda_7(self) -> None:
        # dias=6 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 9)) is None

    # --- Off-by-one around band 1 ---
    def test_off_by_one_arriba_banda_1(self) -> None:
        # dias=2 → no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 13)) is None

    def test_off_by_one_abajo_banda_1(self) -> None:
        # dias=0 → renewal day, no alert
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 15)) is None

    # --- Expired (negative) ---
    def test_vencido_negativo_no_alerta(self) -> None:
        s = _servicio()
        assert banda_alerta_de_hoy(s, datetime.date(2027, 3, 20)) is None

    # --- Non-default bands ---
    def test_bandas_no_default_hit_exacto_90(self) -> None:
        s = _servicio(bandas=(90, 45))
        # 90 days before 2027-03-15 = 2026-12-15
        assert banda_alerta_de_hoy(s, datetime.date(2026, 12, 15)) == 90

    def test_bandas_no_default_off_by_one_89(self) -> None:
        s = _servicio(bandas=(90, 45))
        assert banda_alerta_de_hoy(s, datetime.date(2026, 12, 16)) is None

    def test_bandas_no_default_hit_exacto_45(self) -> None:
        s = _servicio(bandas=(90, 45))
        # 45 days before 2027-03-15 = 2027-01-29
        assert banda_alerta_de_hoy(s, datetime.date(2027, 1, 29)) == 45

    # --- Empty bands ---
    def test_bandas_vacias_no_alerta(self) -> None:
        s = _servicio(bandas=())
        assert banda_alerta_de_hoy(s, datetime.date(2027, 1, 14)) is None
