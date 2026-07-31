"""TDD RED — WU-3: FSM CANAL_ORIGEN state, DIGITAL branch, edit guards, catalog messages."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ"),
]
PUNTOS_TEST: list[str] = ["Marie Real"]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


def _ctx_completo_con_canal(canal: str | None = "WhatsApp") -> ContextoVenta:
    """Return a fully-filled context for DIGITAL sale with an optional canal."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.DIGITAL
    ctx.canal_origen = canal
    ctx.punto_de_venta_nombre = "Marie Real"
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


def _ctx_externo_completo() -> ContextoVenta:
    """Return a fully-filled context for EXTERNO sale (no canal_origen)."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.EXTERNO
    ctx.canal_origen = None
    ctx.punto_de_venta_nombre = "Marie Real"
    ctx.destinos_numeros = [1]
    ctx.cliente_nombre = "Pedro López"
    ctx.cliente_telefono = "+57301111111"
    ctx.cliente_email = "pedro@test.com"
    ctx.cliente_identificacion = "87654321"
    ctx.fecha_salida = datetime.datetime(2026, 8, 10)
    ctx.adultos = 1
    ctx.ninos = 0
    ctx.valor = Decimal("150000")
    ctx.abono = Decimal("0")
    ctx.neto = Decimal("150000")
    ctx.rol_registrante = "ambos"
    return ctx


class TestTipoReservaDigitalVaACanalOrigen:
    def test_tipo_reserva_digital_va_a_canal_origen(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "DIGITAL", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANAL_ORIGEN

    def test_tipo_reserva_digital_muestra_6_opciones(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "DIGITAL", ctx)
        assert len(salida.opciones) == 6

    def test_tipo_reserva_interno_no_va_a_canal_origen(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA

    def test_tipo_reserva_externo_no_va_a_canal_origen(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA


class TestCanalOrigenHandler:
    def test_canal_valido_va_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "WhatsApp", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_canal_invalido_re_pregunta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "TELEGRAM", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANAL_ORIGEN

    def test_canal_guarda_en_contexto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "Instagram", ctx)
        assert salida.contexto.canal_origen == "Instagram"

    def test_canal_origen_muestra_6_opciones(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.tipo_cliente = TipoCliente.DIGITAL
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "TELEGRAM", ctx)
        assert len(salida.opciones) == 6

    def test_canal_en_modo_edicion_va_a_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx.tipo_cliente = TipoCliente.DIGITAL
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "Facebook", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


class TestCanalOrigenEnResumen:
    def test_confirmacion_muestra_canal_para_digital(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo_con_canal("WhatsApp")
        resumen = fsm._construir_resumen(ctx)
        assert "WhatsApp" in resumen

    def test_confirmacion_no_muestra_canal_none_literal_para_interno(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_externo_completo()
        resumen = fsm._construir_resumen(ctx)
        assert "Canal: None" not in resumen

    def test_construir_resumen_canal_sin_dato_muestra_guion(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo_con_canal(None)
        resumen = fsm._construir_resumen(ctx)
        assert "—" in resumen

    def test_construir_resumen_no_digital_con_canal_none_no_crashea(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_externo_completo()
        result = fsm._construir_resumen(ctx)
        assert isinstance(result, str)
        assert "Canal: None" not in result


class TestEditorSelectorCanalOrigen:
    def test_editar_selector_muestra_canal_para_digital(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo_con_canal("TikTok")
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert "Canal" in salida.opciones

    def test_editar_selector_oculta_canal_para_interno(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_externo_completo()
        ctx.tipo_cliente = TipoCliente.INTERNO
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert "Canal" not in salida.opciones

    def test_editar_selector_rechaza_canal_para_tipo_no_digital_via_texto(
        self, fsm: FSMTiquetera
    ) -> None:
        """JD-W1: Guard fires BEFORE campo_map.get; Canal for INTERNO stays in EDITAR_SELECTOR."""
        ctx = _ctx_externo_completo()
        ctx.tipo_cliente = TipoCliente.INTERNO
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Canal", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR


class TestEditarTipoLimpiaCanal:
    def test_editar_tipo_digital_a_interno_limpia_canal(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo_con_canal("Google")
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.contexto.canal_origen is None


class TestFotoModoDigitalConCanal:
    def test_foto_modo_digital_flujo_completo_canal_a_participante_rol(
        self, fsm: FSMTiquetera
    ) -> None:
        """JD-W2: foto_modo=True + DIGITAL → CANAL_ORIGEN → Instagram → PUNTO_DE_VENTA
        (then photo shortcut)."""
        ctx = ContextoVenta()
        ctx.foto_modo = True
        ctx.tipo_cliente = TipoCliente.DIGITAL
        ctx.punto_de_venta_nombre = "Marie Real"
        ctx.destinos_numeros = [1]
        ctx.neto = Decimal("100000")
        salida = fsm.procesar_foto(EstadoFSM.CANAL_ORIGEN, "Instagram", ctx)
        assert salida.contexto.canal_origen == "Instagram"
        assert salida.contexto.foto_modo is False
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL


class TestValidacionConfirmacionCanal:
    def test_validar_confirmacion_exige_canal_para_digital(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_completo_con_canal(None)
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert any("canal" in f.lower() for f in faltantes)

    def test_validar_confirmacion_no_exige_canal_para_externo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_externo_completo()
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert not any("canal" in f.lower() for f in faltantes)
