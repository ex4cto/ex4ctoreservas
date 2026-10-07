"""Tests for external operator detection and notification formatting."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.dominio.comun.dinero import Dinero


class TestDetectarOperador:
    def test_isla_palma_tierra_y_lancha(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["ISLA PALMA (TIERRA Y LANCHA)"]) == "isla_palma"

    def test_isla_palma_directo(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["ISLA PALMA (DIRECTO)"]) == "isla_palma"

    def test_palmarito(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["DAY TOUR PALMARITO"]) == "palmarito"

    def test_bonavida(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["CATAMARAN BONAVIDA"]) == "bonavida"

    def test_bonavida_con_espacio(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["CATAMARAN BONA VIDA-ISLAS DEL ROSARIO"]) == "bonavida"

    def test_no_match_returns_none(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["ROSARIO ISLAND", "SAN BERNARDO"]) is None

    def test_case_insensitive(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador(["isla palma directo"]) == "isla_palma"

    def test_empty_list_returns_none(self) -> None:
        from garay.aplicacion.operadores.notificaciones import detectar_operador
        assert detectar_operador([]) is None


def _make_datos(
    servicio_nombres: list[str] | None = None,
    cliente_nombre: str = "Juan Pérez",
    cedula: str = "12345678",
    telefono: str = "3001234567",
    email: str = "juan@test.com",
    adultos: int = 2,
    ninos: int = 1,
    valor_venta: Dinero | None = None,
    abono: Dinero | None = None,
    ganancia: Dinero | None = None,
) -> object:
    from garay.aplicacion.operadores.notificaciones import DatosNotificacion
    return DatosNotificacion(
        servicio_nombres=servicio_nombres or ["ISLA PALMA (DIRECTO)"],
        fecha=datetime.date(2026, 10, 7),
        cliente_nombre=cliente_nombre,
        cliente_cedula=cedula,
        cliente_telefono=telefono,
        cliente_email=email,
        adultos=adultos,
        ninos=ninos,
        valor_venta=valor_venta or Dinero(300_000),
        abono=abono,
        ganancia=ganancia or Dinero(50_000),
    )


class TestFormatearNotificacion:
    def test_palmarito_includes_formato_pasadia_header(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(servicio_nombres=["DAY TOUR PALMARITO"])
        msg = formatear_notificacion("palmarito", datos)
        assert msg is not None
        assert "FORMATO PASADÍA" in msg

    def test_palmarito_includes_cedula(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(servicio_nombres=["DAY TOUR PALMARITO"], cedula="98765432")
        msg = formatear_notificacion("palmarito", datos)
        assert msg is not None
        assert "98765432" in msg

    def test_palmarito_includes_reservo_agencia_garay(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(servicio_nombres=["DAY TOUR PALMARITO"])
        msg = formatear_notificacion("palmarito", datos)
        assert msg is not None
        assert "Agencia Garay Tour" in msg

    def test_palmarito_saldo_computed(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(
            servicio_nombres=["DAY TOUR PALMARITO"],
            valor_venta=Dinero(300_000),
            abono=Dinero(100_000),
        )
        msg = formatear_notificacion("palmarito", datos)
        assert msg is not None
        # saldo = 300_000 - 100_000 = 200_000
        assert "200" in msg  # fmt_cop produces "$200.000"

    def test_isla_palma_includes_recordatorio(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(servicio_nombres=["ISLA PALMA (TIERRA Y LANCHA)"])
        msg = formatear_notificacion("isla_palma", datos)
        assert msg is not None
        assert "cuenta de cobro" in msg

    def test_bonavida_mentions_7_dias_habiles(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos(servicio_nombres=["BONAVIDA TOUR"])
        msg = formatear_notificacion("bonavida", datos)
        assert msg is not None
        assert "7 días hábiles" in msg

    def test_unknown_operador_returns_none(self) -> None:
        from garay.aplicacion.operadores.notificaciones import formatear_notificacion
        datos = _make_datos()
        assert formatear_notificacion("desconocido", datos) is None
