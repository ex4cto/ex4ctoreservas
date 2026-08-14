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

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARU", []),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS", []),
    (3, "City Tour", None, None, "ISLAS", []),
]

# Puntos including Crespo
PUNTOS_TEST: list[str] = ["Crespo", "Marie Real", "Mama Waldi"]

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


# ── Review-fix tests (rows 1-10 + hardening) ─────────────────────────────────
#
# These tests cover the invariant: NO path may reach CONFIRMACION (or
# PARTICIPANTE_ROL in foto mode) with tipo_cliente is None.


@pytest.fixture()
def fsm_with_fl() -> FSMTiquetera:
    return FSMTiquetera(
        servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST, freelancers=FREELANCERS_TEST
    )


def _ctx_presencial_crespo_digital() -> ContextoVenta:
    """Starting context simulating a completed Digital sale (canal set, no punto)."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.DIGITAL
    ctx.canal_origen = "WhatsApp"
    ctx.punto_de_venta_nombre = None
    return ctx


def _ctx_presencial_non_crespo() -> ContextoVenta:
    """Starting context simulating a completed Presencial non-Crespo sale."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.INTERNO
    ctx.punto_de_venta_nombre = "Marie Real"
    ctx.canal_origen = None
    return ctx


def _ctx_presencial_crespo() -> ContextoVenta:
    """Starting context simulating a completed Presencial Crespo sale."""
    ctx = ContextoVenta()
    ctx.tipo_cliente = TipoCliente.EXTERNO
    ctx.punto_de_venta_nombre = "Crespo"
    ctx.canal_origen = None
    return ctx


class TestEditModeCascade:
    """Edit-mode cascade: rows 1-7 — tipo_cliente must never be None at CONFIRMACION."""

    # Row 1: Edit Digital→Presencial, punto already == "Crespo"
    def test_row1_edit_digital_to_presencial_punto_crespo_ends_externo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = "Crespo"  # already had Crespo from previous presencial era
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.tipo_cliente == TipoCliente.EXTERNO

    # Row 2: Edit Digital→Presencial, punto set and non-Crespo — must RE-ASK TIPO_RESERVA
    def test_row2_edit_digital_to_presencial_punto_non_crespo_asks_tipo_reserva(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = "Marie Real"
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA
        assert salida.contexto.tipo_cliente is None

    def test_row2_edit_after_tipo_reserva_reaches_confirmacion_with_tipo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = "Marie Real"
        ctx.modo_edicion = True
        s1 = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        # TIPO_RESERVA handler in edit mode must return CONFIRMACION with tipo set
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s2.contexto.tipo_cliente == TipoCliente.EXTERNO

    # Row 3: Edit Digital→Presencial, no punto — ask PUNTO_DE_VENTA
    def test_row3_edit_digital_to_presencial_no_punto_asks_punto(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = None
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert salida.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA

    def test_row3_punto_crespo_after_edit_digital_ends_externo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = None
        ctx.modo_edicion = True
        s1 = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert s1.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA
        # Answer with Crespo → must reach CONFIRMACION with EXTERNO
        s2 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s2.contexto.tipo_cliente == TipoCliente.EXTERNO

    def test_row3_punto_non_crespo_after_edit_digital_asks_tipo_reserva(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo_digital()
        ctx.punto_de_venta_nombre = None
        ctx.modo_edicion = True
        s1 = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        s2 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s3 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s3.contexto.tipo_cliente == TipoCliente.INTERNO

    # Row 4: Edit Presencial→Digital, canal already set: tipo=DIGITAL, punto cleared, CONFIRMACION
    def test_row4_edit_presencial_to_digital_canal_set_ends_digital(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_non_crespo()
        ctx.canal_origen = "WhatsApp"  # simulate context where canal was previously captured
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Digital", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.tipo_cliente == TipoCliente.DIGITAL
        assert salida.contexto.punto_de_venta_nombre is None

    # Row 5: Edit Punto "Crespo"→non-Crespo in edit mode — re-ask TIPO_RESERVA
    def test_row5_edit_punto_crespo_to_non_crespo_asks_tipo_reserva(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo()
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_row5_after_tipo_reserva_reaches_confirmacion_with_tipo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_crespo()
        ctx.modo_edicion = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s2.contexto.tipo_cliente == TipoCliente.INTERNO

    # Row 6: Edit Punto non-Crespo→"Crespo" in edit mode — set EXTERNO, CONFIRMACION
    def test_row6_edit_punto_non_crespo_to_crespo_sets_externo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_non_crespo()
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.tipo_cliente == TipoCliente.EXTERNO
        assert salida.contexto.punto_de_venta_nombre == "Crespo"

    # Row 7: Edit Punto non-Crespo→non-Crespo — keep existing tipo, CONFIRMACION
    def test_row7_edit_punto_non_crespo_to_non_crespo_keeps_tipo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = _ctx_presencial_non_crespo()
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Mama Waldi", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.tipo_cliente == TipoCliente.INTERNO  # kept
        assert salida.contexto.punto_de_venta_nombre == "Mama Waldi"


class TestPhotoFlow:
    """Photo flow: rows 8-10 — tipo_cliente must be set before PARTICIPANTE_ROL."""

    # Row 8: Photo presencial + punto "Crespo" → tipo=EXTERNO, state=PARTICIPANTE_ROL
    def test_row8_photo_presencial_crespo_ends_externo_participante_rol(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta()
        ctx.foto_modo = True
        # simulate photo-extracted punto
        ctx.punto_de_venta_nombre = "Crespo"
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.tipo_cliente == TipoCliente.EXTERNO
        assert not salida.contexto.foto_modo  # consumed

    # Row 9a: Photo presencial + non-Crespo → ask TIPO_RESERVA (keep foto_modo=True)
    def test_row9_photo_presencial_non_crespo_asks_tipo_reserva_keeps_foto_modo(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta()
        ctx.foto_modo = True
        ctx.punto_de_venta_nombre = "Marie Real"
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA
        assert salida.contexto.foto_modo  # must be preserved for TIPO_RESERVA handler

    # Row 9b: After TIPO_RESERVA in foto_modo → PARTICIPANTE_ROL with tipo set
    def test_row9_tipo_reserva_in_foto_mode_jumps_to_participante_rol(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta()
        ctx.foto_modo = True
        ctx.punto_de_venta_nombre = "Marie Real"
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        assert s1.contexto.foto_modo
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert s2.contexto.tipo_cliente == TipoCliente.EXTERNO
        assert not s2.contexto.foto_modo  # consumed

    # Row 10: Photo digital — unchanged (reaches PARTICIPANTE_ROL via CANAL_ORIGEN, tipo=DIGITAL)
    def test_row10_photo_digital_via_canal_origen(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta()
        ctx.foto_modo = True
        ctx.tipo_cliente = TipoCliente.DIGITAL
        # canal_origen not yet set — simulate what photo-auto-advance leaves
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "WhatsApp", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.tipo_cliente == TipoCliente.DIGITAL
        assert not salida.contexto.foto_modo


# ── Hardening tests ───────────────────────────────────────────────────────────

class TestHardeningT7Stronger:
    """Stronger T7: Crespo→FAMILIA AND tipo_cliente==EXTERNO.

    Previously tests only asserted != TIPO_RESERVA; this pins the exact outcome.
    """

    def test_t7_crespo_tipo_cliente_is_exactly_externo(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Crespo", ctx)
        assert salida.contexto.tipo_cliente == TipoCliente.EXTERNO
        assert salida.nuevo_estado == EstadoFSM.FAMILIA


class TestHardeningE2EDigital:
    """End-to-end digital path via new MODALIDAD_VENTA entry."""

    def test_e2e_digital_manual_entry(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        s1 = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert s1.nuevo_estado == EstadoFSM.MODALIDAD_VENTA
        s2 = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Digital", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.CANAL_ORIGEN
        s3 = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "WhatsApp", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.FAMILIA
        assert s3.contexto.tipo_cliente == TipoCliente.DIGITAL
        assert s3.contexto.canal_origen == "WhatsApp"
        assert s3.contexto.punto_de_venta_nombre is None


class TestHardeningModalidadVentaInvalidInput:
    """Invalid/blank input at MODALIDAD_VENTA stays in MODALIDAD_VENTA."""

    def test_blank_input_modalidad_venta_stays(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA

    def test_wrong_case_stays(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "presencial", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA

    def test_garbage_stays(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "xyz123", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA
