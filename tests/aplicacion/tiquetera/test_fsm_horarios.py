"""Tests for FSM catalog 6-tuple extension and HORARIO_SALIDA state — Phase 4, WU-1 + WU-2.

Follows strict TDD: RED tests are written first, then GREEN implementation.
PR A scope: catalog plumbing only.
PR B scope: HORARIO_SALIDA state + skip path + regression + prune symmetry.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera
from garay.dominio.ventas.contexto import ContextoVenta
from tests.aplicacion.tiquetera.conftest import catalogo_fsm

# ---------------------------------------------------------------------------
# Phase 2.1 RED — _build_catalog must populate self._horarios (new dict)
# ---------------------------------------------------------------------------


class TestHorariosDict:
    """self._horarios is a dict[int, list[str]] populated from the 6th tuple element."""

    def test_horarios_dict_populated(self) -> None:
        """FSM built with non-empty horarios stores them in _horarios keyed by numero."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == ["07:00", "09:00"]

    def test_horarios_empty_default(self) -> None:
        """FSM built with empty horarios stores [] for that tour."""
        servicios = catalogo_fsm()
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == []

    def test_horarios_multiple_tours(self) -> None:
        """When catalog has multiple tours, _horarios has an entry for each."""
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": []},
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == ["07:00"]
        assert fsm._horarios[2] == []

    def test_servicios_internal_layout_unchanged(self) -> None:
        """Internal _servicios keeps 3-tuple layout; adding _horarios must not change it."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["08:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        # _servicios[1] must be exactly (nombre, neto_a, neto_n) — the 3-tuple
        nombre, neto_a, neto_n = fsm._servicios[1]
        assert nombre == "Tour"
        assert neto_a == Decimal("50")
        assert neto_n == Decimal("25")


class TestRefrescarServicios6Tuples:
    """refrescar_servicios must accept 6-tuples and update _horarios."""

    def test_refrescar_servicios_accepts_6_tuples(self) -> None:
        """After refrescar_servicios with 6-tuples, _horarios is updated."""
        servicios = catalogo_fsm()
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert fsm._horarios[1] == []

        nuevos = catalogo_fsm({"numero": 1, "horarios": ["10:00", "14:00"]})
        fsm.refrescar_servicios(nuevos)
        assert fsm._horarios[1] == ["10:00", "14:00"]

    def test_refrescar_servicios_clears_old_horarios(self) -> None:
        """After refresh, tours no longer present are removed from _horarios."""
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": ["09:00"]},
        )
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        assert 2 in fsm._horarios

        nuevos = catalogo_fsm({"numero": 1, "horarios": ["08:00"]})
        fsm.refrescar_servicios(nuevos)
        assert fsm._horarios[1] == ["08:00"]
        assert 2 not in fsm._horarios


# ---------------------------------------------------------------------------
# Phase 4.1 RED — HORARIO_SALIDA state: skip path + happy path + edge cases
# ---------------------------------------------------------------------------


def _ctx_con_destino(numero: int = 1) -> ContextoVenta:
    """Return a ContextoVenta with one destino and no date yet."""
    ctx = ContextoVenta()
    ctx.destinos_numeros = [numero]
    ctx.destinos_nombres = ["Tour"]
    return ctx


def _ctx_con_fecha(numero: int = 1) -> ContextoVenta:
    """Return a ContextoVenta with one destino and its date already set."""
    ctx = _ctx_con_destino(numero)
    ctx.fechas_por_servicio = {numero: datetime.datetime(2026, 12, 25, 0, 0)}
    ctx.fecha_salida = datetime.datetime(2026, 12, 25, 0, 0)
    return ctx


class TestHorarioSalidaSkipPath:
    """Tour SIN horarios → FECHA_SALIDA must advance directly to PAX_ADULTOS.

    This is the regression requirement: path is byte-identical to today.
    Spec: Domain 1 / Scenario 'Single tour with no configured times'.
    """

    def test_sin_horarios_va_directo_a_pax_adultos(self) -> None:
        """Single tour with empty horarios advances from FECHA_SALIDA to PAX_ADULTOS."""
        fsm = FSMTiquetera(servicios=catalogo_fsm(), puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_sin_horarios_no_crea_entrada_en_horarios_por_servicio(self) -> None:
        """When tour has no horarios, horarios_por_servicio must remain empty."""
        fsm = FSMTiquetera(servicios=catalogo_fsm(), puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.contexto.horarios_por_servicio == {}

    def test_sin_horarios_modo_edicion_va_a_confirmacion(self) -> None:
        """In edit mode, tour without horarios returns to CONFIRMACION."""
        fsm = FSMTiquetera(servicios=catalogo_fsm(), puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


class TestHorarioSalidaConHorarios:
    """Tour CON horarios → FECHA_SALIDA must transition to HORARIO_SALIDA with buttons.

    Spec: Domain 1 / Scenario 'Tour with configured times prompts selection'.
    """

    def test_con_horarios_va_a_horario_salida(self) -> None:
        """Single tour with non-empty horarios advances from FECHA_SALIDA to HORARIO_SALIDA."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.nuevo_estado == EstadoFSM.HORARIO_SALIDA

    def test_con_horarios_muestra_opciones_estructuradas(self) -> None:
        """opciones_estructuradas must have one entry per configured horario."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.opciones_estructuradas is not None
        assert len(salida.opciones_estructuradas) == 2

    def test_con_horarios_labels_en_formato_ampm(self) -> None:
        """Button labels must be formato_display(h) — AM/PM format."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.opciones_estructuradas is not None
        labels = [label for label, _ in salida.opciones_estructuradas]
        assert labels == ["7:00 AM", "9:00 AM"]

    def test_con_horarios_callback_data_canonica(self) -> None:
        """Callback data must be 'hor:{HH:MM}'."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_destino()
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)

        assert salida.opciones_estructuradas is not None
        callbacks = [cb for _, cb in salida.opciones_estructuradas]
        assert callbacks == ["hor:07:00", "hor:09:00"]


class TestHandleHorarioSalida:
    """_handle_horario_salida: valid selection advances, invalid re-renders.

    Spec: Domain 1 / Scenarios 'Selecting a time advances to PAX_ADULTOS'
    and 'Invalid callback rejected'.
    """

    def test_seleccion_valida_avanza_a_pax_adultos(self) -> None:
        """A valid 'hor:{HH:MM}' callback moves the FSM to PAX_ADULTOS."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        # Set up context: date already assigned, no horario yet
        ctx = _ctx_con_fecha()
        salida = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:07:00", ctx)

        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_seleccion_valida_guarda_horario_en_contexto(self) -> None:
        """After selection, horarios_por_servicio[numero] == selected time."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00", "09:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        salida = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:07:00", ctx)

        assert salida.contexto.horarios_por_servicio[1] == "07:00"

    def test_horario_invalido_no_configurado_rerender(self) -> None:
        """An 'hor:' callback with a time not in the list stays in HORARIO_SALIDA."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        salida = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:25:99", ctx)

        assert salida.nuevo_estado == EstadoFSM.HORARIO_SALIDA

    def test_entrada_sin_prefijo_hor_rerender(self) -> None:
        """Free text or any non-hor: input re-renders HORARIO_SALIDA."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        salida = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "07:00", ctx)

        assert salida.nuevo_estado == EstadoFSM.HORARIO_SALIDA

    def test_seleccion_valida_modo_edicion_va_a_confirmacion(self) -> None:
        """In edit mode, a valid horario selection returns to CONFIRMACION."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        ctx.modo_edicion = True
        salida = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:07:00", ctx)

        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


class TestSiguienteTourSinHorarioHelper:
    """_siguiente_tour_sin_horario skips tours without configured horarios.

    This helper only returns a tour when it: has a date AND lacks a horario
    AND has horarios configured in the catalog.
    """

    def test_tour_sin_horarios_catalogo_ignorado(self) -> None:
        """Tour with empty horarios catalog is never returned by the helper."""
        fsm = FSMTiquetera(servicios=catalogo_fsm(), puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        # Tour 1 has no horarios configured — _siguiente_tour_sin_horario returns None
        resultado = fsm._siguiente_tour_sin_horario(ctx)
        assert resultado is None

    def test_tour_con_horarios_sin_eleccion_retornado(self) -> None:
        """Tour with configured horarios and a date but no selection is returned."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        resultado = fsm._siguiente_tour_sin_horario(ctx)
        assert resultado == 1

    def test_tour_con_horarios_ya_elegido_ignorado(self) -> None:
        """Tour with configured horarios that already has a selection is skipped."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])
        ctx = _ctx_con_fecha()
        ctx.horarios_por_servicio = {1: "07:00"}
        resultado = fsm._siguiente_tour_sin_horario(ctx)
        assert resultado is None


# ---------------------------------------------------------------------------
# WARNING-1 — Multi-tour horarios: drain loop with multi_tour_habilitado=True
# ---------------------------------------------------------------------------


def _ctx_dos_destinos() -> ContextoVenta:
    """Return a ContextoVenta with two destinos and no dates yet."""
    ctx = ContextoVenta()
    ctx.destinos_numeros = [1, 2]
    ctx.destinos_nombres = ["Tour A", "Tour B"]
    return ctx


class TestMultiTourHorarios:
    """Multi-tour horario drain: both pending horarios collected in sequence.

    Spec: Domain 1 — multi-tour scenarios with multi_tour_habilitado=True.
    The FSM is exercised through real procesar() calls, not internal helpers.
    """

    def test_dos_tours_con_horarios_drenan_ambos(self) -> None:
        """When two tours both have horarios, FECHA_SALIDA drains them one by one.

        Flow:
          FECHA_SALIDA → tour 1 date set, tour 2 still pending → FECHA_SALIDA
          FECHA_SALIDA → tour 2 date set, all dated → HORARIO_SALIDA (tour 1)
          HORARIO_SALIDA hor:07:00 → horario[1] stored, tour 2 pending → HORARIO_SALIDA
          HORARIO_SALIDA hor:08:00 → horario[2] stored, none pending → PAX_ADULTOS
        Result: horarios_por_servicio == {1: "07:00", 2: "08:00"}
        """
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00", "09:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": ["08:00"]},
        )
        fsm = FSMTiquetera(
            servicios=servicios,
            puntos_venta=["PDV"],
            multi_tour_habilitado=True,
        )
        ctx0 = _ctx_dos_destinos()

        # Step 1: date for tour 1
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx0)
        assert s1.nuevo_estado == EstadoFSM.FECHA_SALIDA  # tour 2 still needs date

        # Step 2: date for tour 2 — now all dated; drain starts with tour 1
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "26/12/2026", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.HORARIO_SALIDA

        # Step 3: select horario for tour 1
        s3 = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:07:00", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.HORARIO_SALIDA  # tour 2 still needs horario

        # Step 4: select horario for tour 2
        s4 = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:08:00", s3.contexto)
        assert s4.nuevo_estado == EstadoFSM.PAX_ADULTOS

        # Both horarios collected — one entry per tour
        assert s4.contexto.horarios_por_servicio[1] == "07:00"
        assert s4.contexto.horarios_por_servicio[2] == "08:00"

    def test_tour_con_horarios_y_tour_sin_horarios_solo_uno_pide(self) -> None:
        """When one tour has horarios and the other does not, only the first prompts.

        Flow:
          FECHA_SALIDA → tour 1 date set, tour 2 still pending → FECHA_SALIDA
          FECHA_SALIDA → tour 2 date set, all dated → HORARIO_SALIDA (only tour 1)
          HORARIO_SALIDA hor:07:00 → horario[1] stored, tour 2 skipped (no horarios) → PAX_ADULTOS
        Result: horarios_por_servicio == {1: "07:00"} (tour 2 absent)
        """
        servicios = catalogo_fsm(
            {"numero": 1, "horarios": ["07:00", "09:00"]},
            {"numero": 2, "nombre": "Tour B", "horarios": []},
        )
        fsm = FSMTiquetera(
            servicios=servicios,
            puntos_venta=["PDV"],
            multi_tour_habilitado=True,
        )
        ctx0 = _ctx_dos_destinos()

        # Step 1: date for tour 1
        s1 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx0)
        assert s1.nuevo_estado == EstadoFSM.FECHA_SALIDA  # tour 2 still needs date

        # Step 2: date for tour 2 — tour 1 has horarios, tour 2 does not → HORARIO_SALIDA for tour 1
        s2 = fsm.procesar(EstadoFSM.FECHA_SALIDA, "26/12/2026", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.HORARIO_SALIDA

        # Step 3: select horario for tour 1; tour 2 has no horarios so it is skipped
        s3 = fsm.procesar(EstadoFSM.HORARIO_SALIDA, "hor:07:00", s2.contexto)
        assert s3.nuevo_estado == EstadoFSM.PAX_ADULTOS

        # Only tour 1 has an entry; tour 2 is absent
        assert s3.contexto.horarios_por_servicio == {1: "07:00"}
        assert 2 not in s3.contexto.horarios_por_servicio


# ---------------------------------------------------------------------------
# WARNING-2 — iniciar_otro_tour clears horarios_por_servicio
# ---------------------------------------------------------------------------


class TestIniciarOtroTourLimpiaHorarios:
    """iniciar_otro_tour must clear horarios_por_servicio regardless of prior content.

    Spec: Domain 2 — scenario 'iniciar_otro_tour resets per-tour fields'.
    """

    def test_iniciar_otro_tour_limpia_horarios_por_servicio(self) -> None:
        """After iniciar_otro_tour, horarios_por_servicio must be empty ({})."""
        servicios = catalogo_fsm({"numero": 1, "horarios": ["07:00"]})
        fsm = FSMTiquetera(servicios=servicios, puntos_venta=["PDV"])

        ctx = ContextoVenta()
        ctx.horarios_por_servicio = {1: "07:00"}

        salida = fsm.iniciar_otro_tour(ctx)

        assert salida.contexto.horarios_por_servicio == {}
