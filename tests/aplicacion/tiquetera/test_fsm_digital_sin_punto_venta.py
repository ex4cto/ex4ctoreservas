"""TDD RED — DIGITAL client flow: skip PUNTO_DE_VENTA, validation, editing guards.

Tests that verify DIGITAL clients go TIPO_RESERVA → CANAL_ORIGEN → DESTINO (no
PUNTO_DE_VENTA step) and that the editing/confirmation system handles the
absence of punto_de_venta gracefully.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS"),
]
PUNTOS_TEST: list[str] = ["Marie Real", "Mama Waldi"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


def _ctx_digital_completo_sin_punto(fsm: FSMTiquetera) -> ContextoVenta:
    """DIGITAL context with all required fields except punto_de_venta_nombre."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.DIGITAL
    ctx.canal_origen = "WhatsApp"
    # punto_de_venta_nombre intentionally left as None (default)
    ctx.destinos_numeros = [1]
    ctx.cliente_nombre = "Ana García"
    ctx.cliente_telefono = "+57300000000"
    ctx.cliente_email = "ana@test.com"
    ctx.cliente_identificacion = "12345678"
    ctx.fecha_salida = datetime.datetime(2026, 8, 15)
    ctx.adultos = 2
    ctx.ninos = 0
    ctx.valor = Decimal("200000")
    ctx.abono = Decimal("0")
    ctx.neto = Decimal("200000")
    ctx.rol_registrante = "ambos"
    return ctx


class TestCanalOrigenNormalVaAFamilia:
    """Cambio 1: _handle_canal_origen normal path must go to FAMILIA (destination picker)."""

    def test_canal_origen_normal_va_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta()
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "WhatsApp", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_canal_origen_normal_va_a_familia_con_diferentes_canales(
        self, fsm: FSMTiquetera
    ) -> None:
        """Triangulation: ensure same routing holds for other valid canal values."""
        ctx = ContextoVenta()
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "Instagram", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA


class TestCanalOrigenFotoModoVaAParticipanteRol:
    """Cambio 2: when foto_modo=True, _handle_canal_origen must go to PARTICIPANTE_ROL."""

    def test_canal_origen_foto_modo_va_a_participante_rol(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta()
        ctx.tipo_cliente = TipoCliente.DIGITAL
        ctx.foto_modo = True
        ctx.destinos_numeros = [1]
        ctx.adultos = 2
        ctx.ninos = 0
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "WhatsApp", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_canal_origen_foto_modo_desactiva_foto_modo(self, fsm: FSMTiquetera) -> None:
        """Triangulation: foto_modo flag is cleared after the transition."""
        ctx = ContextoVenta()
        ctx.tipo_cliente = TipoCliente.DIGITAL
        ctx.foto_modo = True
        ctx.destinos_numeros = [1]
        ctx.adultos = 2
        ctx.ninos = 0
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "Facebook", ctx)
        assert salida.contexto.foto_modo is False


class TestValidacionDigitalSinPuntoNoLoExige:
    """Cambio 3: _validar_datos_confirmacion must NOT require punto_de_venta for DIGITAL."""

    def test_validacion_digital_sin_punto_no_lo_exige(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_digital_completo_sin_punto(fsm)
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert "Punto de venta" not in faltantes

    def test_validacion_no_digital_sin_punto_si_lo_exige(self, fsm: FSMTiquetera) -> None:
        """Triangulation: non-DIGITAL without punto_de_venta MUST still report it as missing."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        ctx.tipo_cliente = TipoCliente.EXTERNO
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert "Punto de venta" in faltantes


class TestOpcionesEditablesExcluyePuntoParaDigital:
    """Cambio 4: _opciones_editables must exclude 'Punto de venta' for DIGITAL clients."""

    def test_opciones_editables_excluye_punto_para_digital(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_digital_completo_sin_punto(fsm)
        opciones = fsm._opciones_editables(ctx)
        assert "Punto de venta" not in opciones

    def test_opciones_editables_incluye_punto_para_externo(self, fsm: FSMTiquetera) -> None:
        """Triangulation: EXTERNO client must see Punto de venta in editable options."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        ctx.tipo_cliente = TipoCliente.EXTERNO
        opciones = fsm._opciones_editables(ctx)
        assert "Punto de venta" in opciones


class TestGuardEditarSelectorPuntoVentaEnDigital:
    """Cambio 5: editing 'Punto de venta' for DIGITAL must bounce back to EDITAR_SELECTOR."""

    def test_guard_editar_selector_punto_venta_en_digital(self, fsm: FSMTiquetera) -> None:
        ctx = _ctx_digital_completo_sin_punto(fsm)
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Punto de venta", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR

    def test_guard_editar_selector_punto_venta_en_digital_no_activa_modo_edicion(
        self, fsm: FSMTiquetera
    ) -> None:
        """Triangulation: the returned context must NOT have modo_edicion=True
        (guard fires before it)."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Punto de venta", ctx)
        assert salida.contexto.modo_edicion is False


class TestTipoReservaRoutingInteligente:
    """Cambio 6: _handle_tipo_reserva modo_edicion must do smart routing."""

    def test_tipo_reserva_digital_a_externo_va_a_punto_de_venta(
        self, fsm: FSMTiquetera
    ) -> None:
        """Changing from DIGITAL to EXTERNO with no punto_de_venta → PUNTO_DE_VENTA."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        ctx.tipo_cliente = TipoCliente.DIGITAL  # currently DIGITAL
        ctx.modo_edicion = True
        ctx.punto_de_venta_nombre = None  # no punto set
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA

    def test_tipo_reserva_externo_a_digital_va_a_canal_origen(
        self, fsm: FSMTiquetera
    ) -> None:
        """Changing from EXTERNO to DIGITAL with no canal_origen → CANAL_ORIGEN."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        ctx.tipo_cliente = TipoCliente.EXTERNO
        ctx.canal_origen = None  # non-DIGITAL: no canal
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "DIGITAL", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANAL_ORIGEN


class TestConstruirResumenDigitalMuestraGuion:
    """Cambio 7: _construir_resumen must show '—' for DIGITAL when punto_de_venta is None."""

    def test_construir_resumen_digital_muestra_guion_para_punto(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_digital_completo_sin_punto(fsm)
        resumen = fsm._construir_resumen(ctx)
        # Should contain the em-dash for the punto_de_venta field
        assert "—" in resumen

    def test_construir_resumen_no_digital_sin_punto_muestra_sin_punto(
        self, fsm: FSMTiquetera
    ) -> None:
        """Triangulation: non-DIGITAL without punto_de_venta shows 'Sin punto', not '—'."""
        ctx = _ctx_digital_completo_sin_punto(fsm)
        ctx.tipo_cliente = TipoCliente.EXTERNO
        resumen = fsm._construir_resumen(ctx)
        assert "Sin punto" in resumen
