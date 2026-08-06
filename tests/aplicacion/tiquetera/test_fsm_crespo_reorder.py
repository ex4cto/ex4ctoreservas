"""Tests for REQ-05: FSM Crespo suppression — MODALIDAD_VENTA new state + reorder.

T7: Crespo punto skips TIPO_RESERVA, sets tipo_cliente=EXTERNO.
T8: Non-Crespo puntos go to TIPO_RESERVA with options {INTERNO, EXTERNO} only (no DIGITAL).

Strict TDD: these tests are written FIRST (RED) before any implementation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import (
    EstadoFSM,
    FSMTiquetera,
)
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARU"),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS"),
    (3, "City Tour", None, None, "ISLAS"),
]

# Puntos including Crespo
PUNTOS_TEST: list[str] = ["Crespo", "Marie Real", "Mama Waldi", "Sin punto"]

F1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
F2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

FREELANCERS_TEST: list[tuple[uuid.UUID, str, bool]] = [
    (F1_ID, "Ana", True),
    (F2_ID, "Luis", True),
]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


# ── MODALIDAD_VENTA state ────────────────────────────────────────────────────

class TestModalidadVentaEstado:
    """The new MODALIDAD_VENTA state is inserted between METODO_INPUT and the next step."""

    def test_metodo_input_manual_avanza_a_modalidad_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """Manual choice must now go to MODALIDAD_VENTA, not TIPO_RESERVA."""
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA

    def test_modalidad_venta_muestra_dos_opciones(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert "Presencial" in salida.opciones
        assert "Digital" in salida.opciones

    def test_modalidad_venta_presencial_avanza_a_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA

    def test_modalidad_venta_digital_avanza_a_canal_origen(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Digital", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANAL_ORIGEN

    def test_modalidad_venta_digital_setea_tipo_cliente_digital(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Digital", ctx)
        assert salida.contexto.tipo_cliente == TipoCliente.DIGITAL

    def test_modalidad_venta_invalida_repregunta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "DIGITAL", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA


# ── T7: Crespo suppression ───────────────────────────────────────────────────

class TestCrespoSuppression:
    """T7: PUNTO_DE_VENTA 'Crespo' must skip TIPO_RESERVA and set tipo_cliente=EXTERNO."""

    def test_t7_crespo_salta_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.nuevo_estado != EstadoFSM.TIPO_RESERVA

    def test_t7_crespo_avanza_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_t7_crespo_setea_tipo_cliente_externo(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.contexto.tipo_cliente == TipoCliente.EXTERNO

    def test_t7_crespo_registra_nombre_punto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.contexto.punto_de_venta_nombre == "Crespo"


# ── T8: Non-Crespo routes to TIPO_RESERVA ────────────────────────────────────

class TestNonCrespoRoutesToTipoReserva:
    """T8: Non-Crespo puntos must go to TIPO_RESERVA with options {INTERNO, EXTERNO} only."""

    def test_t8_marie_real_va_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_t8_sin_punto_va_a_tipo_reserva(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Sin punto", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_t8_tipo_reserva_opciones_sin_digital(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """After non-Crespo punto, TIPO_RESERVA options must NOT include DIGITAL."""
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert "DIGITAL" not in salida.opciones

    def test_t8_tipo_reserva_opciones_tiene_interno_externo(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert "INTERNO" in salida.opciones
        assert "EXTERNO" in salida.opciones

    def test_t8_tipo_reserva_desde_punto_avanza_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """After non-Crespo punto → TIPO_RESERVA → INTERNO → FAMILIA (no second PUNTO_DE_VENTA)."""
        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s.contexto)
        assert s2.nuevo_estado == EstadoFSM.FAMILIA


# ── Validation guard ─────────────────────────────────────────────────────────

class TestValidacionCrespo:
    """_validar_datos_confirmacion must not report 'Tipo de reserva' missing for Crespo."""

    def _ctx_crespo_casi_completo(self, fsm: FSMTiquetera) -> ContextoVenta:
        """Context for a Crespo sale that has been driven to just before CONFIRMACION."""
        ctx = ContextoVenta()
        # Simulate: MODALIDAD_VENTA → Presencial → PUNTO_DE_VENTA → Crespo → FAMILIA ...
        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        ctx = s.contexto
        # tipo_cliente must be EXTERNO (sentinel) — that satisfies the guard
        assert ctx.tipo_cliente == TipoCliente.EXTERNO
        return ctx

    def test_crespo_tipo_cliente_no_es_none_en_contexto(
        self, fsm: FSMTiquetera
    ) -> None:
        """Driving through Crespo must leave tipo_cliente != None so validation passes."""
        ctx = self._ctx_crespo_casi_completo(fsm)
        # Call the private method directly — public behavior test
        faltantes = fsm._validar_datos_confirmacion(ctx)
        assert "Tipo de reserva" not in faltantes


# ── Editable options guard ────────────────────────────────────────────────────

class TestOpcionesEditablesCrespo:
    """_opciones_editables must hide 'Tipo reserva' for Crespo sales."""

    def _ctx_crespo(self) -> ContextoVenta:
        ctx = ContextoVenta()
        ctx.punto_de_venta_nombre = "Crespo"
        ctx.tipo_cliente = TipoCliente.EXTERNO  # sentinel
        return ctx

    def test_crespo_oculta_tipo_reserva_en_editables(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = self._ctx_crespo()
        opciones = fsm._opciones_editables(ctx)
        assert "Tipo reserva" not in opciones

    def test_crespo_muestra_modalidad_en_editables(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = self._ctx_crespo()
        opciones = fsm._opciones_editables(ctx)
        assert "Modalidad" in opciones

    def test_no_crespo_muestra_tipo_reserva_en_editables(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta()
        ctx.punto_de_venta_nombre = "Marie Real"
        ctx.tipo_cliente = TipoCliente.INTERNO
        opciones = fsm._opciones_editables(ctx)
        assert "Tipo reserva" in opciones


# ── EDITAR_SELECTOR bounce guard ──────────────────────────────────────────────

class TestEditarSelectorCrespoGuard:
    """EDITAR_SELECTOR must bounce 'Tipo reserva' edit when punto is Crespo."""

    def _ctx_crespo(self) -> ContextoVenta:
        ctx = ContextoVenta()
        ctx.punto_de_venta_nombre = "Crespo"
        ctx.tipo_cliente = TipoCliente.EXTERNO
        return ctx

    def test_editar_tipo_reserva_en_crespo_rebota(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = self._ctx_crespo()
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Tipo reserva", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR

    def test_editar_modalidad_en_crespo_avanza(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = self._ctx_crespo()
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Modalidad", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA


# ── _opciones_para_estado guard ───────────────────────────────────────────────

class TestOpcionesParaEstadoTipoReserva:
    """_opciones_para_estado must return [INTERNO, EXTERNO] only for TIPO_RESERVA (no DIGITAL)."""

    def test_tipo_reserva_opciones_sin_digital(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        opciones = fsm._opciones_para_estado(EstadoFSM.TIPO_RESERVA, ctx)
        assert "DIGITAL" not in opciones
        assert "INTERNO" in opciones
        assert "EXTERNO" in opciones

    def test_modalidad_venta_opciones_en_opciones_para_estado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        opciones = fsm._opciones_para_estado(EstadoFSM.MODALIDAD_VENTA, ctx)
        assert "Presencial" in opciones
        assert "Digital" in opciones


# ── Photo entry ───────────────────────────────────────────────────────────────

class TestFotoEntryModalidad:
    """Photo flow must start at MODALIDAD_VENTA, not TIPO_RESERVA.

    This tests the FSM side only (not the Telegram handler side).
    MODALIDAD_VENTA must be in _ESTADOS_FOTO_AVANZAR set so photo auto-advance
    can pass through it.
    """

    def test_modalidad_venta_en_estados_foto_avanzar(self) -> None:
        from garay.aplicacion.tiquetera.fsm import _ESTADOS_FOTO_AVANZAR
        assert EstadoFSM.MODALIDAD_VENTA in _ESTADOS_FOTO_AVANZAR

    def test_tipo_reserva_no_en_estados_foto_avanzar(self) -> None:
        """TIPO_RESERVA is presencial-only and depends on punto — not auto-advanceable."""
        from garay.aplicacion.tiquetera.fsm import _ESTADOS_FOTO_AVANZAR
        assert EstadoFSM.TIPO_RESERVA not in _ESTADOS_FOTO_AVANZAR


# ── Catalog keys ─────────────────────────────────────────────────────────────

class TestCatalogoModalidadVenta:
    """Catalog must have pregunta_modalidad_venta and error_modalidad_invalida keys."""

    def test_pregunta_modalidad_venta_existe(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje
        msg = obtener_mensaje("pregunta_modalidad_venta")
        assert isinstance(msg, str) and len(msg) > 0

    def test_pregunta_modalidad_venta_menciona_modalidad_o_tipo(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje
        msg = obtener_mensaje("pregunta_modalidad_venta")
        assert any(kw in msg.lower() for kw in ("modalidad", "presencial", "digital", "venta"))

    def test_error_modalidad_invalida_existe(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje
        msg = obtener_mensaje("error_modalidad_invalida")
        assert isinstance(msg, str) and len(msg) > 0

    def test_error_modalidad_invalida_menciona_opciones(self) -> None:
        from garay.mensajes.catalogo import obtener_mensaje
        msg = obtener_mensaje("error_modalidad_invalida")
        # Must mention the valid options
        assert "Presencial" in msg or "Digital" in msg
