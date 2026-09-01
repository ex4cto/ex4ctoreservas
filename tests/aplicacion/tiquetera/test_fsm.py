"""Tests for the pure FSM — Telegram-free, import-only garay.aplicacion.tiquetera.fsm."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from garay.aplicacion.tiquetera.fsm import (
    EstadoFSM,
    FSMTiquetera,
    _es_sin_hotel,
    _formatear_monto,
    _parsear_monto,
)
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta

SERVICIOS_TEST: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
    (1, "Tour Playa Blanca", Decimal("100000"), Decimal("50000"), "BARÚ", []),
    (2, "Tour Isla", Decimal("150000"), None, "ISLAS", []),
    (3, "City Tour", None, None, "ISLAS", []),
]
PUNTOS_TEST: list[str] = ["Marie Real", "Mama Waldi"]

# ── Freelancer roster used across picker tests ────────────────────────────────
F1_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
F2_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
F3_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

FREELANCERS_TEST: list[tuple[uuid.UUID, str, bool]] = [
    (F1_ID, "Ana", True),
    (F2_ID, "Luis", True),
    (F3_ID, "Carlos", False),  # inactive
]


@pytest.fixture()
def fsm() -> FSMTiquetera:
    return FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)


@pytest.fixture()
def fsm_multi() -> FSMTiquetera:
    """FSM with multi_tour_habilitado=True — preserves legacy accumulator behavior."""
    return FSMTiquetera(
        servicios=SERVICIOS_TEST,
        puntos_venta=PUNTOS_TEST,
        multi_tour_habilitado=True,
    )


@pytest.fixture()
def fsm_con_roster() -> FSMTiquetera:
    return FSMTiquetera(
        servicios=SERVICIOS_TEST,
        puntos_venta=PUNTOS_TEST,
        freelancers=FREELANCERS_TEST,
    )


@pytest.fixture()
def ctx() -> ContextoVenta:
    return ContextoVenta()


class TestIniciar:
    def test_iniciar_devuelve_estado_metodo_input(self, fsm: FSMTiquetera) -> None:
        salida = fsm.iniciar()
        assert salida.nuevo_estado == EstadoFSM.METODO_INPUT
        assert "Manual" in salida.opciones
        assert "Foto" in salida.opciones


class TestTipoReserva:
    def test_tipo_reserva_interno_avanza_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # After reorder: TIPO_RESERVA comes after PUNTO_DE_VENTA, so it goes to FAMILIA
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_tipo_reserva_externo_avanza_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # After reorder: TIPO_RESERVA comes after PUNTO_DE_VENTA, so it goes to FAMILIA
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA


class TestPickerFamilia:
    """Two-level button picker: pick familia, then tour in that familia."""

    def test_tipo_reserva_avanza_a_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # After Slice 3: TIPO_RESERVA (non-Crespo) routes to FAMILIA
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_canal_origen_avanza_a_familia(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CANAL_ORIGEN, "Instagram", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_familia_muestra_familias_como_opciones_estructuradas(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida.opciones_estructuradas is not None
        labels = [label for label, _ in salida.opciones_estructuradas]
        assert "BARÚ" in labels
        assert "ISLAS" in labels
        # callback_data must be encoded, not the raw label
        datas = [data for _, data in salida.opciones_estructuradas]
        assert all(d.startswith("fam:") for d in datas)

    def test_familia_no_muestra_categorias_vacias(self, fsm: FSMTiquetera) -> None:
        # Every categoria in SERVICIOS_TEST has at least one service, so 2 familias only
        # After Slice 3: reach FAMILIA via TIPO_RESERVA (punto already set before)
        fsm_local = FSMTiquetera(servicios=SERVICIOS_TEST, puntos_venta=PUNTOS_TEST)
        salida = fsm_local.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
        assert salida.opciones_estructuradas is not None
        assert len(salida.opciones_estructuradas) == 2  # BARÚ, ISLAS

    def test_familia_seleccionada_va_a_servicio_en_familia(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FAMILIA, "fam:0", ctx)
        assert salida.nuevo_estado == EstadoFSM.SERVICIO_EN_FAMILIA

    def test_familia_seleccionada_recuerda_familia_en_ctx(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FAMILIA, "fam:0", ctx)
        assert salida.contexto.familia_seleccionada is not None

    def test_familia_invalida_repite(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FAMILIA, "fam:999", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_familia_entrada_basura_repite(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FAMILIA, "no-es-fam", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA


class TestPickerServicioEnFamilia:
    def _familia_ctx(self, fsm: FSMTiquetera, indice_familia: int) -> ContextoVenta:
        salida = fsm.procesar(EstadoFSM.FAMILIA, f"fam:{indice_familia}", ContextoVenta())
        return salida.contexto

    def test_servicio_en_familia_muestra_tours_de_esa_familia(
        self, fsm: FSMTiquetera
    ) -> None:
        # Pick the ISLAS family (services 2, 3)
        salida = fsm.procesar(EstadoFSM.FAMILIA, f"fam:{_indice_de(fsm, 'ISLAS')}", ContextoVenta())
        assert salida.opciones_estructuradas is not None
        datas = [data for _, data in salida.opciones_estructuradas]
        assert "srv:2" in datas
        assert "srv:3" in datas
        assert "srv:1" not in datas  # service 1 is in a different family

    def test_servicio_seleccionado_agrega_numero_y_va_a_cliente_nombre(
        self, fsm: FSMTiquetera
    ) -> None:
        # Default (multi_tour_habilitado=False): one-tour mode → goes to CLIENTE_NOMBRE.
        ctx = self._familia_ctx(fsm, _indice_de(fsm, "BARÚ"))
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert 1 in salida.contexto.destinos_numeros

    def test_servicio_seleccionado_agrega_numero_y_va_a_destino_multi_tour(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        # Multi-tour mode (flag True): picking a tour still shows the accumulator.
        ctx = self._familia_ctx(fsm_multi, _indice_de(fsm_multi, "BARÚ"))
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.DESTINO
        assert 1 in salida.contexto.destinos_numeros

    def test_servicio_seleccionado_dedupe(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1], familia_seleccionada="BARÚ")
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.contexto.destinos_numeros == [1]

    def test_servicio_invalido_repite(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(familia_seleccionada="BARÚ")
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:9999", ctx)
        assert salida.nuevo_estado == EstadoFSM.SERVICIO_EN_FAMILIA


class TestAcumuladorDestino:
    """DESTINO repurposed as accumulator: add another tour or confirm."""

    def test_otro_tour_vuelve_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "+ Otro tour", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_confirmar_avanza_a_cliente_nombre(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_confirmar_en_modo_edicion_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1], adultos=2, ninos=0, modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # Neto recomputed from catalog: service 1 = 100000 * 2 = 200000
        assert salida.contexto.neto == Decimal("200000")

    def test_acumulador_muestra_nombres_seleccionados(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm_multi.procesar(EstadoFSM.DESTINO, "+ Otro tour", ctx)
        _ = salida
        # After selecting a second tour, the accumulator lists both by name
        ctx2 = ContextoVenta(destinos_numeros=[1, 2], familia_seleccionada="ISLAS")
        salida2 = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:2", ctx2)
        assert "Tour Playa Blanca" in salida2.mensaje
        assert "Tour Isla" in salida2.mensaje

    def test_acumulador_ofrece_otro_tour_y_confirmar(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(familia_seleccionada="BARÚ")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        labels = _labels(salida)
        assert any("Otro tour" in lbl for lbl in labels)
        assert any("Confirmar" in lbl for lbl in labels)


class TestAcumuladorGuardVacio:
    """FIX 1: confirming with an empty selection must never advance the sale."""

    def test_confirmar_sin_destinos_no_avanza_a_cliente_nombre(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[])
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado not in (EstadoFSM.CLIENTE_NOMBRE, EstadoFSM.CONFIRMACION)

    def test_confirmar_sin_destinos_vuelve_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[])
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_confirmar_sin_destinos_en_edicion_no_avanza_a_confirmacion(
        self, fsm: FSMTiquetera
    ) -> None:
        ctx = ContextoVenta(destinos_numeros=[], modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA


class TestServicioEnFamiliaFallback:
    """FIX 2: stale state (familia_seleccionada=None) routes back to FAMILIA."""

    def test_servicio_sin_familia_vuelve_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(familia_seleccionada=None)
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA
        assert salida.opciones_estructuradas is not None
        assert all(d.startswith("fam:") for _, d in salida.opciones_estructuradas)


class TestAcumuladorDeseleccion:
    """FIX 3: each selected tour renders a removable 'del:{numero}' button."""

    def test_acumulador_muestra_boton_borrar_por_tour(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2], familia_seleccionada="ISLAS")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:2", ctx)
        assert salida.opciones_estructuradas is not None
        datas = [d for _, d in salida.opciones_estructuradas]
        assert "del:1" in datas
        assert "del:2" in datas

    def test_del_remueve_solo_ese_tour(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2])
        salida = fsm.procesar(EstadoFSM.DESTINO, "del:1", ctx)
        assert salida.contexto.destinos_numeros == [2]
        assert salida.nuevo_estado == EstadoFSM.DESTINO

    def test_del_ultimo_tour_vuelve_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar(EstadoFSM.DESTINO, "del:1", ctx)
        assert salida.contexto.destinos_numeros == []
        assert salida.nuevo_estado == EstadoFSM.FAMILIA

    def test_del_boton_usa_label_con_nombre(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1], familia_seleccionada="BARÚ")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.opciones_estructuradas is not None
        labels = {d: label for label, d in salida.opciones_estructuradas}
        assert "Tour Playa Blanca" in labels["del:1"]

    def test_del_callback_data_bajo_limite(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2], familia_seleccionada="ISLAS")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:2", ctx)
        assert salida.opciones_estructuradas is not None
        for _, data in salida.opciones_estructuradas:
            assert len(data.encode("utf-8")) <= 64


def _indice_de(fsm: FSMTiquetera, categoria: str) -> int:
    # After Slice 3: reach FAMILIA via TIPO_RESERVA (punto set before, TIPO_RESERVA → FAMILIA)
    salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
    assert salida.opciones_estructuradas is not None
    for indice, (label, _) in enumerate(salida.opciones_estructuradas):
        if label == categoria:
            return indice
    raise AssertionError(f"categoria {categoria!r} not found")


def _labels(salida: object) -> list[str]:
    from garay.aplicacion.tiquetera.fsm import SalidaFSM

    assert isinstance(salida, SalidaFSM)
    if salida.opciones_estructuradas is not None:
        return [label for label, _ in salida.opciones_estructuradas]
    return list(salida.opciones)


class TestFechaSalida:
    def test_fecha_invalida_devuelve_error_mismo_estado(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "no-es-fecha", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_fecha_valida_avanza_a_pax_adultos(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS


class TestPax:
    def test_adultos_invalido_devuelve_error(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_pax_ninos_avanza_a_monto_valor(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        """After WU-3: PAX_NINOS transitions directly to MONTO_VALOR (no NUMERO_TICKET)."""
        salida = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR


class TestMonto:
    def test_monto_neto_estado_acepta_valor_valido(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """MONTO_NETO fallback state still works when neto_adulto is None."""
        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "50000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_monto_neto_supera_valor_devuelve_error(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        ctx_con_valor = ContextoVenta(valor=Decimal("100000"))
        salida = fsm.procesar(EstadoFSM.MONTO_NETO, "200000", ctx_con_valor)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO


class TestHotelSkip:
    """WU-5: hotel skip — 'no'/'sin hotel'/etc. jumps to FECHA_SALIDA."""

    def test_hotel_no_salta_fecha_salida(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.sin_hotel is True

    def test_hotel_variantes_sin_hotel(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        for variante in ("No", "no hotel", "sin hotel", "no hay"):
            salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, variante, ctx)
            assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA, f"Failed for: {variante!r}"

    def test_hotel_con_nombre_avanza_a_habitacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Grand Hyatt", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        assert salida.contexto.sin_hotel is False

    def test_habitacion_entry_normal(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "301", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA


class TestFechaFormatos:
    """WU-5: two-digit year format support."""

    def test_fecha_dd_mm_yy_valida(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/26", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS
        assert salida.contexto.fecha_salida is not None
        assert salida.contexto.fecha_salida.year == 2026
        assert salida.contexto.fecha_salida.month == 12
        assert salida.contexto.fecha_salida.day == 25

    def test_fecha_dd_mm_yyyy_sigue_funcionando(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12/2026", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS
        assert salida.contexto.fecha_salida is not None
        assert salida.contexto.fecha_salida.year == 2026


class TestOpcionesAcumulador:
    """The DESTINO accumulator always offers 'Otro tour' and 'Confirmar' (multi-tour mode)."""

    def test_acumulador_tiene_confirmar_y_otro_tour(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1], familia_seleccionada="BARÚ")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        labels = _labels(salida)
        assert any("Confirmar" in lbl for lbl in labels)
        assert any("Otro tour" in lbl for lbl in labels)


class TestNetoAutoCalculo:
    """WU-5: automatic neto calculation from service catalog."""

    def test_neto_auto_calcula_un_servicio(self, fsm: FSMTiquetera) -> None:
        # Service 1: neto_adulto=100000, neto_nino=50000; 2 adultos, 1 nino
        ctx = ContextoVenta(destinos_numeros=[1], adultos=2, ninos=1)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("250000")  # 100000*2 + 50000*1

    def test_neto_auto_calcula_multi_servicio(self, fsm: FSMTiquetera) -> None:
        # Services 1+2: (100000+150000)*2 adultos = 500000
        ctx = ContextoVenta(destinos_numeros=[1, 2], adultos=2, ninos=0)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("500000")

    def test_neto_sin_precio_pide_manual(self, fsm: FSMTiquetera) -> None:
        # Service 3 has neto_adulto=None → fallback to MONTO_NETO
        ctx = ContextoVenta(destinos_numeros=[3], adultos=2, ninos=0)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_NETO

    def test_neto_nino_none_usa_adulto_como_proxy(self, fsm: FSMTiquetera) -> None:
        # Service 2: neto_adulto=150000, neto_nino=None; 1 adult + 1 child
        # Business rule: neto_nino=None → use neto_adulto as proxy
        ctx = ContextoVenta(destinos_numeros=[2], adultos=1, ninos=1)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert salida.contexto.neto == Decimal("300000")  # 150000*1 + 150000*1 (proxy)

    def test_abono_mayor_que_neto_pero_menor_que_valor_avanza(
        self, fsm: FSMTiquetera
    ) -> None:
        # Bug 2b fix: guard is now against valor, not neto.
        # valor=None → abono guard skips; neto=100000 is set; advances to PARTICIPANTE_ROL.
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0)
        # neto calculado = 100000; abono = 200000; valor = None → guard does not fire
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "200000", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_neto_supera_valor_venta_vuelve_a_monto_valor(self, fsm: FSMTiquetera) -> None:
        # neto auto-calculated (100000) > valor_venta (50000) → MONTO_VALOR with error
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0, valor=Decimal("50000"))
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.MONTO_VALOR
        assert "$50.000" in salida.mensaje or "$100.000" in salida.mensaje


class TestResumen:
    """WU-5: summary shows tour names, not numbers; no Ticket N°; sin hotel sentinel."""

    def test_resumen_muestra_nombre_tour_no_numero(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            destinos_numeros=[1],
            rol_registrante="ambos",
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Tour Playa Blanca" in salida.mensaje
        assert "Destinos: 1" not in salida.mensaje

    def test_resumen_sin_ticket_fisico(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(rol_registrante="ambos")
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "Ticket N°" not in salida.mensaje


class TestConfirmacionEditar:
    """Fix 3: Editar from CONFIRMACION now goes to EDITAR_SELECTOR, not TIPO_RESERVA."""

    def test_confirmacion_editar_va_a_editar_selector(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR
        assert len(salida.opciones) > 0

    def test_confirmacion_confirmar_con_ctx_vacio_bloquea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With an empty context, confirmation must stay blocked at CONFIRMACION."""
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_confirmacion_cancelar_cancela(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "❌ Cancelar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CANCELADO


class TestMetodoInput:
    """WU-6: METODO_INPUT is the first state returned by iniciar()."""

    def test_metodo_input_manual_avanza_a_modalidad_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Manual", ctx)
        assert salida.nuevo_estado == EstadoFSM.MODALIDAD_VENTA

    def test_metodo_input_foto_avanza_a_esperando_foto(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Foto", ctx)
        assert salida.nuevo_estado == EstadoFSM.ESPERANDO_FOTO

    def test_esperando_foto_rechaza_texto(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.ESPERANDO_FOTO, "hola", ctx)
        assert salida.nuevo_estado == EstadoFSM.ESPERANDO_FOTO

    def test_metodo_input_invalido_repite(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.METODO_INPUT, "Audio", ctx)
        assert salida.nuevo_estado == EstadoFSM.METODO_INPUT

    def test_metodo_input_muestra_opciones_manual_foto(self, fsm: FSMTiquetera) -> None:
        salida = fsm.iniciar()
        assert "Manual" in salida.opciones
        assert "Foto" in salida.opciones


class TestParticipante:
    def test_rol_ambos_salta_a_confirmacion(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.rol_registrante == "ambos"

    def test_rol_solo_vendedor_pide_cerrador(
        self, fsm_con_roster: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # Requires active freelancers in roster; otherwise guard returns PARTICIPANTE_ROL error.
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO

    def test_rol_solo_cerrador_pide_vendedor(
        self, fsm_con_roster: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # Requires active freelancers in roster; otherwise guard returns PARTICIPANTE_ROL error.
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo cerrador", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO

    def test_participante_otro_como_vendedor_completa(
        self, fsm_con_roster: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # Migrated: feeds fl:{uuid}, asserts id + snapshot nombre on context
        ctx_prep = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F2_ID}", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.cerrador_nombre == "Luis"
        assert s.contexto.cerrador_id == F2_ID

    def test_participante_otro_como_cerrador_completa(
        self, fsm_con_roster: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        # Migrated: feeds fl:{uuid}, asserts id + snapshot nombre on context
        ctx_prep = ContextoVenta(rol_registrante="cerrador")
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F2_ID}", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.vendedor_nombre == "Luis"
        assert s.contexto.vendedor_id == F2_ID


class TestConfirmacion:
    def test_confirmacion_confirmar_con_ctx_vacio_bloquea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With an empty context, confirmation must stay blocked at CONFIRMACION."""
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


class TestCancelar:
    def test_cancelar_desde_cualquier_estado(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.cancelar(ctx)
        assert salida.nuevo_estado == EstadoFSM.CANCELADO


class TestDestinoDesdeIA:
    """Tests for IA-seeded destinos_nombres pre-population and UI hints."""

    def test_contexto_venta_tiene_campo_destinos_nombres(self) -> None:
        """5.1 — ContextoVenta must have destinos_nombres field defaulting to []."""
        ctx = ContextoVenta()
        assert ctx.destinos_nombres == []

    def test_destinos_nombres_se_puede_inicializar(self) -> None:
        """5.1 — destinos_nombres can be set on construction."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        assert ctx.destinos_nombres == ["Tour Playa Blanca"]

    def test_prepoblacion_exacta(self, fsm: FSMTiquetera) -> None:
        """5.3B — nombre exacto matchea y pre-popula destinos_numeros."""
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_prepoblacion_case_insensitive(self, fsm: FSMTiquetera) -> None:
        """5.3B — match es case-insensitive."""
        ctx = ContextoVenta(destinos_nombres=["tour playa blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros

    def test_encabezado_ia_detectado_prepobla_numero_con_match(self, fsm: FSMTiquetera) -> None:
        """When an IA name matches a service, its numero is pre-populated before the picker.

        After Slice 3: PUNTO_DE_VENTA (non-Crespo) → TIPO_RESERVA (punto already set);
        the pre-populated numero is carried in the context regardless.
        """
        ctx = ContextoVenta(destinos_nombres=["Tour Playa Blanca"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert 1 in salida.contexto.destinos_numeros
        # After Slice 3 non-Crespo goes to TIPO_RESERVA, not FAMILIA directly
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_sin_match_no_prepobla_numeros(self, fsm: FSMTiquetera) -> None:
        """When no IA name matches, no numbers are pre-populated; picker still shown."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.destinos_numeros == []
        # After Slice 3 non-Crespo goes to TIPO_RESERVA, not FAMILIA directly
        assert salida.nuevo_estado == EstadoFSM.TIPO_RESERVA

    def test_nombres_sin_match_no_agregan_numeros(self, fsm: FSMTiquetera) -> None:
        """5.3B — nombres sin match no agregan números al contexto."""
        ctx = ContextoVenta(destinos_nombres=["Destino Inventado"])
        salida = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert salida.contexto.destinos_numeros == []


class TestFlujoCompleto:
    def test_flujo_completo_feliz(self, fsm: FSMTiquetera) -> None:
        """Drive FSM through all states with valid inputs — must reach TERMINADO.

        After WU-3: PAX_NINOS → MONTO_VALOR (no NUMERO_TICKET).
        After WU-5: MONTO_ABONO auto-calculates neto when possible → PARTICIPANTE_ROL.
        After Slice 3: METODO_INPUT → MODALIDAD_VENTA → PUNTO_DE_VENTA → TIPO_RESERVA → FAMILIA.
        For this test, service 3 has neto_adulto=None → fallback to MONTO_NETO.
        """
        ctx = ContextoVenta()

        # MODALIDAD_VENTA → Presencial → PUNTO_DE_VENTA
        s = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        assert s.nuevo_estado == EstadoFSM.PUNTO_DE_VENTA
        ctx = s.contexto

        # PUNTO_DE_VENTA (non-Crespo) → TIPO_RESERVA
        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s.nuevo_estado == EstadoFSM.TIPO_RESERVA
        ctx = s.contexto

        # TIPO_RESERVA → FAMILIA (punto already set)
        s = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert s.nuevo_estado == EstadoFSM.FAMILIA
        ctx = s.contexto

        # FAMILIA → pick the family that holds service 3 (ISLAS)
        indice_islas = _indice_de(fsm, "ISLAS")
        s = fsm.procesar(EstadoFSM.FAMILIA, f"fam:{indice_islas}", ctx)
        assert s.nuevo_estado == EstadoFSM.SERVICIO_EN_FAMILIA
        ctx = s.contexto

        # SERVICIO_EN_FAMILIA → pick service 3 (no neto) → CLIENTE_NOMBRE (one-tour mode)
        s = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:3", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert 3 in s.contexto.destinos_numeros
        ctx = s.contexto

        # CLIENTE_NOMBRE
        s = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Juan Perez", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO
        ctx = s.contexto

        # CLIENTE_TELEFONO
        s = fsm.procesar(EstadoFSM.CLIENTE_TELEFONO, "3001234567", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_EMAIL
        ctx = s.contexto

        # CLIENTE_EMAIL → FACTURA_IDIOMA
        s = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "juan@example.com", ctx)
        assert s.nuevo_estado == EstadoFSM.FACTURA_IDIOMA
        ctx = s.contexto

        # FACTURA_IDIOMA → CLIENTE_TIPO_ID
        s = fsm.procesar(EstadoFSM.FACTURA_IDIOMA, "Español", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_TIPO_ID
        assert s.contexto.factura_idioma == "es"
        ctx = s.contexto

        # CLIENTE_TIPO_ID
        s = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "CC", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_IDENTIFICACION
        ctx = s.contexto

        # CLIENTE_IDENTIFICACION
        s = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_HOTEL
        ctx = s.contexto

        # CLIENTE_HOTEL
        s = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Caribe", ctx)
        assert s.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        ctx = s.contexto

        # CLIENTE_HABITACION
        s = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "301", ctx)
        assert s.nuevo_estado == EstadoFSM.FECHA_SALIDA
        ctx = s.contexto

        # FECHA_SALIDA
        s = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert s.nuevo_estado == EstadoFSM.PAX_ADULTOS
        ctx = s.contexto

        # PAX_ADULTOS
        s = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
        assert s.nuevo_estado == EstadoFSM.PAX_NINOS
        ctx = s.contexto

        # PAX_NINOS → MONTO_VALOR directly (NUMERO_TICKET removed in WU-3)
        s = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_VALOR
        ctx = s.contexto

        # MONTO_VALOR
        s = fsm.procesar(EstadoFSM.MONTO_VALOR, "500.000", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_ABONO
        ctx = s.contexto

        # MONTO_ABONO → MONTO_NETO (service 3 has no neto_adulto — fallback)
        s = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert s.nuevo_estado == EstadoFSM.MONTO_NETO
        ctx = s.contexto

        # MONTO_NETO
        s = fsm.procesar(EstadoFSM.MONTO_NETO, "450000", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        ctx = s.contexto

        # PARTICIPANTE_ROL — Ambos (skip PARTICIPANTE_OTRO)
        s = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        ctx = s.contexto

        # CONFIRMACION
        s = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert s.nuevo_estado == EstadoFSM.TERMINADO
        assert s.listo is True


class TestProcesarFoto:
    """Tests for procesar_foto() — photo AI pre-filled auto-advance logic."""

    def test_procesar_foto_sin_ctx_se_comporta_igual_que_procesar(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """Empty ctx: procesar_foto behaves identical to procesar."""
        salida_proc = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        salida_foto = fsm.procesar_foto(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        assert salida_proc.nuevo_estado == salida_foto.nuevo_estado

    def test_procesar_foto_auto_avanza_cliente_nombre_prefilled(self, fsm: FSMTiquetera) -> None:
        """ctx with cliente_nombre set: after DESTINO confirm reaches CLIENTE_TELEFONO."""
        ctx = ContextoVenta(destinos_numeros=[1], cliente_nombre="Juan")
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        # DESTINO confirm → CLIENTE_NOMBRE → auto-advance to CLIENTE_TELEFONO
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO
        assert salida.contexto.cliente_nombre == "Juan"

    def test_procesar_foto_no_avanza_sin_valor(self, fsm: FSMTiquetera) -> None:
        """ctx without cliente_nombre: stays at CLIENTE_NOMBRE."""
        ctx = ContextoVenta(destinos_numeros=[1])
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE

    def test_procesar_foto_pax_adultos_cero_no_avanza(self, fsm: FSMTiquetera) -> None:
        """adultos=0 should NOT auto-advance PAX_ADULTOS (business rule: min 1)."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300",
            cliente_hotel="Hotel",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=0,
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # Should advance through FECHA_SALIDA (pre-filled) but stop at PAX_ADULTOS (adultos=0)
        assert salida.nuevo_estado == EstadoFSM.PAX_ADULTOS

    def test_procesar_foto_pax_adultos_uno_avanza(self, fsm: FSMTiquetera) -> None:
        """adultos=1 should auto-advance PAX_ADULTOS."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300",
            cliente_hotel="Hotel",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=1,
            ninos=None,
        )
        salida = fsm.procesar_foto(EstadoFSM.CLIENTE_HABITACION, "101", ctx)
        # CLIENTE_HABITACION→FECHA_SALIDA (pre-filled)→PAX_ADULTOS (pre-filled, 1)
        # →PAX_NINOS (ninos=None, stops)
        assert salida.nuevo_estado == EstadoFSM.PAX_NINOS


# ─── Fix 1: destino mensaje sin instruccion cuando hay seleccion ─────────────


class TestDestinoMensaje:
    """Accumulator message lists the selected tours by name (multi-tour mode)."""

    def test_acumulador_lista_nombres_seleccionados(self, fsm_multi: FSMTiquetera) -> None:
        ctx = ContextoVenta(familia_seleccionada="BARÚ")
        salida = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert "Tour Playa Blanca" in salida.mensaje


# ─── Fix 2: hotel skip detection flexible ────────────────────────────────────


class TestEsSinHotel:
    """Fix 2: _es_sin_hotel covers flexible natural-language inputs."""

    def test_exacto_no(self) -> None:
        assert _es_sin_hotel("no") is True

    def test_exacto_ninguno(self) -> None:
        assert _es_sin_hotel("ninguno") is True

    def test_frase_corta_no_estoy(self) -> None:
        assert _es_sin_hotel("no estoy en ningún hotel") is True

    def test_frase_no_tengo(self) -> None:
        assert _es_sin_hotel("no tengo hotel") is True

    def test_hotel_nombre_real_no_confunde(self) -> None:
        # A real hotel name that starts with "Hotel No" should NOT match
        assert _es_sin_hotel("Hotel Novotel Centro") is False

    def test_nombre_largo_con_no_no_confunde(self) -> None:
        # Long sentence with "no" in it that is clearly a hotel name should not match
        assert _es_sin_hotel("Estamos en el Novotel cerca del centro comercial gran hotel") is False

    def test_typo_nignuno(self) -> None:
        assert _es_sin_hotel("nignuno") is True

    def test_typo_nignuna(self) -> None:
        assert _es_sin_hotel("nignuna") is True

    def test_typo_sin_htel(self) -> None:
        assert _es_sin_hotel("sin htel") is True

    def test_hotel_real_no_confunde_con_fuzzy(self) -> None:
        # Short real hotel names must not false-positive
        assert _es_sin_hotel("sol") is False
        assert _es_sin_hotel("ibis") is False


class TestHotelSkipFlexible:
    """Fix 2: FSM accepts flexible no-hotel phrases."""

    def test_hotel_frase_completa_sin_hotel(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no estoy en ningún hotel", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA
        assert salida.contexto.sin_hotel is True

    def test_hotel_frase_no_tengo(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "no tengo hotel", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_hotel_ninguna(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "ninguna", ctx)
        assert salida.nuevo_estado == EstadoFSM.FECHA_SALIDA

    def test_hotel_nombre_real_no_se_confunde(self, fsm: FSMTiquetera, ctx: ContextoVenta) -> None:
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Novotel Centro", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION


# ─── Fix 3: EDITAR_SELECTOR ──────────────────────────────────────────────────


class TestEditarSelector:
    """Fix 3: field-by-field edit mode from CONFIRMACION."""

    def test_editar_selector_aparece_desde_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✏️ Editar", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR
        assert len(salida.opciones) > 0
        assert "Nombre cliente" in salida.opciones

    def test_editar_selector_campo_invalido_repite(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "CampoQueNoExiste", ctx)
        assert salida.nuevo_estado == EstadoFSM.EDITAR_SELECTOR

    def test_editar_selector_cliente_va_a_cliente_nombre(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Nombre cliente", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert salida.contexto.modo_edicion is True

    def test_editar_cliente_nombre_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        # modo_edicion=True → after editing a field, return to CONFIRMACION
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Nuevo Nombre", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_nombre == "Nuevo Nombre"

    def test_editar_hotel_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Grand Hyatt", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_modo_edicion_se_resetea_tras_editar(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Otro", ctx)
        assert salida.contexto.modo_edicion is False

    def test_editar_tipo_reserva_externo_con_punto_vuelve_a_confirmacion(
        self, fsm: FSMTiquetera
    ) -> None:
        # When switching to EXTERNO and punto_de_venta is already set → go to CONFIRMACION
        ctx = ContextoVenta(modo_edicion=True)
        ctx.punto_de_venta_nombre = "Marie Real"
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_tipo_reserva_externo_va_a_confirmacion(
        self, fsm: FSMTiquetera
    ) -> None:
        # After Slice 3: TIPO_RESERVA in edit mode always returns to CONFIRMACION.
        # Punto is already known (set at PUNTO_DE_VENTA before TIPO_RESERVA).
        # The old "sin punto → PUNTO_DE_VENTA" smart routing was removed;
        # Modalidad/punto changes now go through MODALIDAD_VENTA edit.
        ctx = ContextoVenta(modo_edicion=True)
        ctx.punto_de_venta_nombre = None
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_fecha_salida_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # "25/12" without a year uses the current year — verify the parsed date is stored.
        assert salida.contexto.fecha_salida == datetime.datetime(
            datetime.datetime.now().year, 12, 25
        )

    def test_editar_monto_abono_vuelve_a_confirmacion_cuando_neto_conocido(
        self, fsm: FSMTiquetera
    ) -> None:
        # When neto can be auto-calculated and modo_edicion=True, go to CONFIRMACION
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0, modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_participante_rol_ambos_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION


# ─── Fix 4: formateo de montos ───────────────────────────────────────────────


class TestFormatearMonto:
    """Fix 4: _formatear_monto uses dot as thousands separator."""

    def test_formatear_monto_entero_grande(self) -> None:
        assert _formatear_monto(Decimal("200000")) == "$200.000"

    def test_formatear_monto_none(self) -> None:
        assert _formatear_monto(None) == "—"

    def test_formatear_monto_pequeño(self) -> None:
        assert _formatear_monto(Decimal("500")) == "$500"

    def test_formatear_monto_millon(self) -> None:
        assert _formatear_monto(Decimal("1000000")) == "$1.000.000"


class TestResumenMontos:
    """Fix 4: summary uses _formatear_monto for valor/abono/neto."""

    def test_resumen_muestra_montos_formateados(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(
            destinos_numeros=[1],
            rol_registrante="ambos",
            valor=Decimal("200000"),
            abono=Decimal("50000"),
            neto=Decimal("100000"),
        )
        salida = fsm.procesar(EstadoFSM.PARTICIPANTE_ROL, "Ambos", ctx)
        assert "200.000" in salida.mensaje
        assert "50.000" in salida.mensaje
        assert "100.000" in salida.mensaje


class TestParsearMonto:
    """_parsear_monto must scale plain numbers < 1000 by x1000 (Colombian miles notation)."""

    def test_plain_hundreds_scaled(self) -> None:
        assert _parsear_monto("500") == Decimal("500000")

    def test_plain_two_digits_scaled(self) -> None:
        assert _parsear_monto("50") == Decimal("50000")

    def test_dot_thousands_not_scaled(self) -> None:
        assert _parsear_monto("500.000") == Decimal("500000")

    def test_large_number_not_scaled(self) -> None:
        assert _parsear_monto("1800000") == Decimal("1800000")

    def test_dot_thousands_large_not_scaled(self) -> None:
        assert _parsear_monto("1.800.000") == Decimal("1800000")


# ─── foto_modo: jump to CONFIRMACION after PUNTO_DE_VENTA ────────────────────


class TestFotoModo:
    """foto_modo=True causes _handle_punto_de_venta to skip DESTINO and go to PARTICIPANTE_ROL."""

    def test_estados_foto_avanzar_no_incluye_monto_valor_ni_monto_abono(self) -> None:
        """MONTO_VALOR and MONTO_ABONO must NOT be in _ESTADOS_FOTO_AVANZAR.

        _handle_monto_abono can loop back to itself (abono > neto path) or to
        MONTO_VALOR (neto > valor path). Including them in the frozenset would
        create an infinite loop in procesar_foto.
        """
        from garay.aplicacion.tiquetera.fsm import _ESTADOS_FOTO_AVANZAR

        assert EstadoFSM.MONTO_VALOR not in _ESTADOS_FOTO_AVANZAR
        assert EstadoFSM.MONTO_ABONO not in _ESTADOS_FOTO_AVANZAR

    def test_foto_modo_salta_a_participante_rol_despues_de_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """With foto_modo=True non-Crespo, _handle_punto_de_venta goes to TIPO_RESERVA.
        After TIPO_RESERVA answers, the handler jumps to PARTICIPANTE_ROL."""
        ctx.foto_modo = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        assert s1.contexto.foto_modo is True  # kept for TIPO_RESERVA handler
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_foto_modo_false_after_punto_de_venta(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """foto_modo is preserved at TIPO_RESERVA then consumed when TIPO_RESERVA answers."""
        ctx.foto_modo = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.contexto.foto_modo is True  # NOT consumed yet
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        assert s2.contexto.foto_modo is False  # consumed at TIPO_RESERVA

    def test_foto_modo_computa_neto_cuando_datos_disponibles(
        self, fsm: FSMTiquetera
    ) -> None:
        """When foto_modo=True, neto is auto-computed at TIPO_RESERVA, not PUNTO_DE_VENTA."""
        ctx = ContextoVenta(
            foto_modo=True,
            abono=Decimal("50000"),
            adultos=2,
            ninos=0,
            destinos_numeros=[1],  # Tour Playa Blanca: neto_adulto=100000
        )
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert s2.contexto.neto == Decimal("200000")  # 100000 * 2 adultos

    def test_handle_destino_recomputa_neto_en_modo_edicion(
        self, fsm: FSMTiquetera
    ) -> None:
        """One-tour edit mode: picking a service in SERVICIO_EN_FAMILIA recomputes neto
        and returns to CONFIRMACION directly (skips DESTINO accumulator)."""
        ctx = ContextoVenta(
            modo_edicion=True,
            abono=Decimal("50000"),
            adultos=2,
            ninos=0,
            familia_seleccionada="BARÚ",
        )
        # In one-tour mode with modo_edicion=True, SERVICIO_EN_FAMILIA returns CONFIRMACION.
        salida = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.neto == Decimal("200000")  # 100000 * 2 adultos

    def test_zero_stays_zero(self) -> None:
        assert _parsear_monto("0") == Decimal("0")

    def test_invalid_returns_none(self) -> None:
        assert _parsear_monto("abc") is None


# ─── Change 1: procesar_foto respects modo_edicion ───────────────────────────


class TestProcesarFotoModoEdicion:
    """Change 1: procesar_foto must NOT auto-advance when modo_edicion=True."""

    def test_procesar_foto_no_avanza_cuando_modo_edicion(self, fsm: FSMTiquetera) -> None:
        """With modo_edicion=True, procesar_foto stops at the target state even when
        the next state also has a pre-filled value (telefono pre-filled)."""
        # Full context — all ESTADOS_FOTO_AVANZAR values are set
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono="300111222",
            cliente_hotel="Grand",
            cliente_habitacion="101",
            fecha_salida=datetime.datetime(2026, 12, 25, 10, 0),
            adultos=2,
            ninos=0,
            modo_edicion=True,
        )
        # Simulate: user selected "Nombre cliente" in EDITAR_SELECTOR → CLIENTE_NOMBRE
        # Now user types the new name — procesar_foto is called with EDITAR_SELECTOR
        salida = fsm.procesar_foto(EstadoFSM.EDITAR_SELECTOR, "Nombre cliente", ctx)
        # _handle_editar_selector sets modo_edicion=True and returns CLIENTE_NOMBRE.
        # Without the fix, procesar_foto would auto-advance through pre-filled states.
        # With the fix it must stop at CLIENTE_NOMBRE.
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_NOMBRE
        assert salida.contexto.modo_edicion is True

    def test_procesar_foto_avanza_normalmente_sin_modo_edicion(self, fsm: FSMTiquetera) -> None:
        """Regression: without modo_edicion auto-advance still works for photo flow."""
        ctx = ContextoVenta(
            destinos_numeros=[1],
            cliente_nombre="Juan",
            cliente_telefono=None,
        )
        salida = fsm.procesar_foto(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        # CLIENTE_NOMBRE has value, so it auto-advances to CLIENTE_TELEFONO (no value → stops)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_TELEFONO


# ─── Change 2: Adultos/Niños edit covers both fields ─────────────────────────


class TestEditarAdultosNinos:
    """Change 2: editing 'Adultos/Niños' must prompt for niños after adultos."""

    def test_editar_adultos_ninos_pide_ninos_tras_adultos(self, fsm: FSMTiquetera) -> None:
        """When modo_edicion=True, _handle_pax_adultos must go to PAX_NINOS, not CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True, adultos=1, ninos=2)
        salida = fsm.procesar(EstadoFSM.PAX_ADULTOS, "3", ctx)
        assert salida.nuevo_estado == EstadoFSM.PAX_NINOS
        assert salida.contexto.adultos == 3
        # modo_edicion must still be True so PAX_NINOS knows to return to CONFIRMACION
        assert salida.contexto.modo_edicion is True

    def test_editar_adultos_ninos_completo_va_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        """After adultos → niños, _handle_pax_ninos clears modo_edicion and goes to CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True, adultos=1, ninos=2)
        # Step 1: edit adultos
        salida1 = fsm.procesar(EstadoFSM.PAX_ADULTOS, "3", ctx)
        assert salida1.nuevo_estado == EstadoFSM.PAX_NINOS
        # Step 2: edit niños
        salida2 = fsm.procesar(EstadoFSM.PAX_NINOS, "1", salida1.contexto)
        assert salida2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida2.contexto.adultos == 3
        assert salida2.contexto.ninos == 1
        assert salida2.contexto.modo_edicion is False


# ─── Change 3: Habitación en _CAMPOS_EDITABLES ───────────────────────────────


class TestHabitacionEditable:
    """Change 3: 'Habitación' must appear in _CAMPOS_EDITABLES."""

    def test_habitacion_aparece_en_campos_editables(self, fsm: FSMTiquetera) -> None:
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        target_states = {estado for _, estado in _CAMPOS_EDITABLES}
        assert EstadoFSM.CLIENTE_HABITACION in target_states

    def test_editar_habitacion_vuelve_a_confirmacion(self, fsm: FSMTiquetera) -> None:
        """With modo_edicion=True, CLIENTE_HABITACION returns to CONFIRMACION."""
        ctx = ContextoVenta(modo_edicion=True)
        salida = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "202", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.cliente_habitacion == "202"

    def test_editar_selector_habitacion_navega_correctamente(self, fsm: FSMTiquetera) -> None:
        """Selecting 'Habitación' from EDITAR_SELECTOR navigates to CLIENTE_HABITACION."""
        ctx = ContextoVenta()
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Habitación", ctx)
        assert salida.nuevo_estado == EstadoFSM.CLIENTE_HABITACION
        assert salida.contexto.modo_edicion is True


# ─── WU-2 Phase 4: FSM Picker Core ───────────────────────────────────────────


class TestFSMFreelancerRoster:
    """Phase 4 — FSM accepts a freelancer roster and exposes picker helpers."""

    def test_fsm_acepta_parametro_freelancers(self) -> None:
        """FSMTiquetera must accept a `freelancers` keyword param without raising."""
        fsm = FSMTiquetera(
            servicios=SERVICIOS_TEST,
            puntos_venta=PUNTOS_TEST,
            freelancers=FREELANCERS_TEST,
        )
        assert fsm is not None

    def test_opciones_freelancers_solo_activos(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """_opciones_freelancers(solo_activos=True) returns only active entries."""
        opts = fsm_con_roster._opciones_freelancers(solo_activos=True)
        labels = [label for label, _ in opts]
        datas = [data for _, data in opts]
        # Active: Ana (F1_ID) and Luis (F2_ID)
        assert len(opts) == 2
        assert "Ana" in labels
        assert "Luis" in labels
        assert f"fl:{F1_ID}" in datas
        assert f"fl:{F2_ID}" in datas

    def test_opciones_freelancers_todos_incluye_inactivo(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """_opciones_freelancers(solo_activos=False) returns all 3, inactive marked."""
        opts = fsm_con_roster._opciones_freelancers(solo_activos=False)
        assert len(opts) == 3
        labels = [label for label, _ in opts]
        datas = [data for _, data in opts]
        assert "Ana" in labels
        assert "Luis" in labels
        # Inactive Carlos must be labelled with [inactivo]
        assert any("[inactivo]" in label for label in labels)
        assert f"fl:{F3_ID}" in datas


# ─── WU-2 Phase 5: PARTICIPANTE_OTRO Picker ──────────────────────────────────


class TestParticipanteOtroPicker:
    """Phase 5 — PARTICIPANTE_OTRO emits picker + parses fl:{uuid}."""

    def test_participante_otro_emite_opciones_estructuradas(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Solo vendedor → PARTICIPANTE_OTRO must have opciones_estructuradas with active fl."""
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ContextoVenta())
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None
        # Only active freelancers (Ana + Luis = 2)
        assert len(s.opciones_estructuradas) == 2

    def test_participante_otro_emite_opciones_para_solo_cerrador(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Solo cerrador → PARTICIPANTE_OTRO must also emit opciones_estructuradas."""
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo cerrador", ContextoVenta())
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None

    def test_participante_otro_fl_uuid_como_vendedor_sets_cerrador(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Feeding fl:{F2_ID} as vendedor sets cerrador_id + cerrador_nombre."""
        ctx_prep = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F2_ID}", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.cerrador_id == F2_ID
        assert s.contexto.cerrador_nombre == "Luis"

    def test_participante_otro_fl_uuid_como_cerrador_sets_vendedor(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Feeding fl:{F1_ID} as cerrador sets vendedor_id + vendedor_nombre."""
        ctx_prep = ContextoVenta(rol_registrante="cerrador")
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F1_ID}", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        assert s.contexto.vendedor_id == F1_ID
        assert s.contexto.vendedor_nombre == "Ana"

    def test_participante_otro_prefijo_invalido_reprompts(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Free-text without fl: prefix must re-emit picker (PARTICIPANTE_OTRO)."""
        ctx_prep = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, "free-text", ctx_prep)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        # Must include opciones_estructuradas on re-prompt
        assert s.opciones_estructuradas is not None

    def test_participante_otro_uuid_desconocido_reprompts(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """A valid fl: prefix with unknown uuid must re-emit picker."""
        unknown_id = uuid.uuid4()
        ctx_prep = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(
            EstadoFSM.PARTICIPANTE_OTRO, f"fl:{unknown_id}", ctx_prep
        )
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None


# ─── WU-2 Phase 6: Edit Pickers ──────────────────────────────────────────────


class TestEditarParticipantesPicker:
    """Phase 6 — EDITAR_VENDEDOR / EDITAR_CERRADOR become fl: pickers."""

    def test_editar_vendedor_emite_picker_todos(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Selecting 'Vendedor/Cerrador' in EDITAR_SELECTOR emits EDITAR_VENDEDOR."""
        ctx = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_SELECTOR, "Vendedor/Cerrador", ctx)
        assert s.nuevo_estado == EstadoFSM.EDITAR_VENDEDOR
        assert s.opciones_estructuradas is not None
        # Includes inactive (3 total)
        assert len(s.opciones_estructuradas) == 3

    def test_editar_vendedor_fl_uuid_sets_id_and_nombre(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Feeding fl:{F3_ID} to EDITAR_VENDEDOR sets vendedor_id + vendedor_nombre."""
        ctx = ContextoVenta(rol_registrante="vendedor")
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F3_ID}", ctx)
        assert s.contexto.vendedor_id == F3_ID
        assert s.contexto.vendedor_nombre == "Carlos"
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_cerrador_fl_uuid_sets_id_and_nombre(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Feeding fl:{F2_ID} to EDITAR_CERRADOR sets cerrador_id + cerrador_nombre."""
        ctx = ContextoVenta(rol_registrante="cerrador")
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_CERRADOR, f"fl:{F2_ID}", ctx)
        assert s.contexto.cerrador_id == F2_ID
        assert s.contexto.cerrador_nombre == "Luis"
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION

    def test_editar_vendedor_ambos_chains_to_editar_cerrador_picker(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """With rol=ambos, EDITAR_VENDEDOR chains to EDITAR_CERRADOR with opciones_estructuradas."""
        ctx = ContextoVenta(rol_registrante="ambos")
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F1_ID}", ctx)
        assert s.nuevo_estado == EstadoFSM.EDITAR_CERRADOR
        assert s.opciones_estructuradas is not None

    def test_editar_cerrador_emite_picker_todos(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """EDITAR_SELECTOR → 'Vendedor/Cerrador' with rol=cerrador goes to EDITAR_VENDEDOR."""
        ctx = ContextoVenta(rol_registrante="cerrador")
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_SELECTOR, "Vendedor/Cerrador", ctx)
        assert s.nuevo_estado == EstadoFSM.EDITAR_VENDEDOR
        assert s.opciones_estructuradas is not None
        assert len(s.opciones_estructuradas) == 3


# ─── Change 4: EDITAR_VENDEDOR / EDITAR_CERRADOR states ─────────────────────


class TestEditarParticipantes:
    """Change 4: new FSM states for editing participant names directly."""

    def test_editar_participantes_mapea_a_editar_vendedor(self, fsm: FSMTiquetera) -> None:
        """'Participantes' in EDITAR_SELECTOR must go to EDITAR_VENDEDOR (not PARTICIPANTE_ROL)."""
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        campos_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        assert campos_map.get("Vendedor/Cerrador") == EstadoFSM.EDITAR_VENDEDOR

    def test_editar_participantes_ambos_pide_vendedor_luego_cerrador(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """rol='ambos': EDITAR_VENDEDOR → EDITAR_CERRADOR → CONFIRMACION.

        Migrated: feeds fl:{uuid} picker values and asserts both id + nombre.
        """
        ctx = ContextoVenta(rol_registrante="ambos", modo_edicion=True)
        # Step 1: pick vendor via fl: callback
        salida1 = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F1_ID}", ctx)
        assert salida1.nuevo_estado == EstadoFSM.EDITAR_CERRADOR
        assert salida1.contexto.vendedor_nombre == "Ana"
        assert salida1.contexto.vendedor_id == F1_ID
        # Step 2: pick closer via fl: callback
        salida2 = fsm_con_roster.procesar(
            EstadoFSM.EDITAR_CERRADOR, f"fl:{F2_ID}", salida1.contexto
        )
        assert salida2.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida2.contexto.cerrador_nombre == "Luis"
        assert salida2.contexto.cerrador_id == F2_ID
        assert salida2.contexto.modo_edicion is False

    def test_editar_participantes_solo_vendedor_va_directo_a_confirmacion(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """rol='vendedor': EDITAR_VENDEDOR → CONFIRMACION (no cerrador step).

        Migrated: feeds fl:{uuid} and asserts id + nombre.
        """
        ctx = ContextoVenta(rol_registrante="vendedor", modo_edicion=True)
        salida = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F3_ID}", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.vendedor_nombre == "Carlos"
        assert salida.contexto.vendedor_id == F3_ID
        assert salida.contexto.modo_edicion is False

    def test_editar_participantes_cerrador_guarda_en_vendedor_nombre(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """rol='cerrador': EDITAR_VENDEDOR stores into vendedor_nombre → CONFIRMACION.

        Migrated: feeds fl:{uuid} and asserts id + nombre.
        """
        ctx = ContextoVenta(rol_registrante="cerrador", modo_edicion=True)
        salida = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F1_ID}", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert salida.contexto.vendedor_nombre == "Ana"
        assert salida.contexto.vendedor_id == F1_ID
        assert salida.contexto.modo_edicion is False

    def test_habitacion_en_campos_editables_no_es_participante_rol(
        self, fsm: FSMTiquetera
    ) -> None:
        """After change 4, 'Participantes' maps to EDITAR_VENDEDOR, NOT PARTICIPANTE_ROL."""
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        campos_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        assert campos_map.get("Vendedor/Cerrador") != EstadoFSM.PARTICIPANTE_ROL

    def test_editar_vendedor_estado_existe_en_enum(self) -> None:
        """EstadoFSM.EDITAR_VENDEDOR and EDITAR_CERRADOR must exist."""
        assert EstadoFSM.EDITAR_VENDEDOR.value == "editar_vendedor"
        assert EstadoFSM.EDITAR_CERRADOR.value == "editar_cerrador"

    def test_negative_returns_none(self) -> None:
        assert _parsear_monto("-500") is None


# ─── foto_modo: salta a PARTICIPANTE_ROL (no CONFIRMACION) ──────────────────


class TestFotoModoSaltaParticipanteRol:
    """Cambio 3: foto_modo=True non-Crespo routes through TIPO_RESERVA then PARTICIPANTE_ROL.
    Crespo jumps directly to PARTICIPANTE_ROL with tipo=EXTERNO (no TIPO_RESERVA needed)."""

    def test_foto_modo_salta_a_participante_rol_no_confirmacion(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """Con foto_modo=True non-Crespo, PUNTO_DE_VENTA va a TIPO_RESERVA (no CONFIRMACION)."""
        ctx.foto_modo = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_foto_modo_opciones_participante_rol(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """La salida de TIPO_RESERVA en foto_modo tiene las opciones de rol."""
        ctx.foto_modo = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        assert "Ambos" in s2.opciones

    def test_foto_modo_false_se_resetea(
        self, fsm: FSMTiquetera, ctx: ContextoVenta
    ) -> None:
        """foto_modo se resetea a False al salir de TIPO_RESERVA en foto mode."""
        ctx.foto_modo = True
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.contexto.foto_modo is True  # preserved at TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s1.contexto)
        assert s2.contexto.foto_modo is False


# ─── Validación en _handle_confirmacion ──────────────────────────────────────


@pytest.fixture()
def ctx_completo() -> ContextoVenta:
    """A ContextoVenta with all required fields filled (tipo INTERNO)."""
    return ContextoVenta(
        cliente_nombre="Ana García",
        cliente_telefono="3001234567",
        cliente_email="ana@example.com",
        cliente_identificacion="1234567890",
        cliente_tipo_identificacion="CC",
        cliente_hotel="Hotel Test",
        cliente_habitacion="101",
        fecha_salida=datetime.datetime(2026, 8, 1, 8, 0),
        adultos=2,
        ninos=1,
        destinos_numeros=[1],
        valor=Decimal("260000"),
        abono=Decimal("130000"),
        tipo_cliente=TipoCliente.INTERNO,
        punto_de_venta_nombre="Hotel Test",
        rol_registrante="ambos",
        neto=Decimal("180000"),
    )


class TestValidarDatosConfirmacion:
    def test_ctx_completo_no_tiene_faltantes(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        """Un contexto con todos los campos rellenos no bloquea confirmacion."""
        assert fsm._validar_datos_confirmacion(ctx_completo) == []

    def test_falta_cliente_nombre(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = None
        assert "Nombre del cliente" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_falta_telefono(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_telefono = None
        assert "Teléfono" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_hotel_habitacion_obligatorios_solo_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = TipoCliente.EXTERNO
        ctx_completo.cliente_hotel = None
        ctx_completo.cliente_habitacion = None
        faltantes = fsm._validar_datos_confirmacion(ctx_completo)
        assert "Hotel" not in faltantes
        assert "Habitación" not in faltantes

    def test_hotel_obligatorio_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = TipoCliente.INTERNO
        ctx_completo.cliente_hotel = None
        assert "Hotel" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_habitacion_obligatoria_para_interno(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.tipo_cliente = TipoCliente.INTERNO
        ctx_completo.cliente_habitacion = None
        assert "Habitación" in fsm._validar_datos_confirmacion(ctx_completo)

    def test_ninos_cero_es_valido(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.ninos = 0
        assert "Niños" not in " ".join(fsm._validar_datos_confirmacion(ctx_completo))

    def test_ninos_none_falla(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.ninos = None
        faltantes = fsm._validar_datos_confirmacion(ctx_completo)
        assert any("iños" in f for f in faltantes)

    def test_abono_cero_es_valido(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.abono = Decimal("0")
        assert "Abono" not in fsm._validar_datos_confirmacion(ctx_completo)

    def test_confirmacion_bloqueada_si_faltan_datos(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = None
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx_completo)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        assert "Nombre del cliente" in salida.mensaje

    def test_confirmacion_procede_si_datos_completos(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        salida = fsm.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx_completo)
        assert salida.nuevo_estado == EstadoFSM.TERMINADO


class TestEditarMensajesConValorActual:
    """_handle_editar_selector shows current ctx value in the prompt."""

    def test_editar_nombre_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_nombre = "Juan Pérez"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Nombre cliente", ctx_completo)
        assert "Juan Pérez" in salida.mensaje

    def test_editar_telefono_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_telefono = "3001234567"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Teléfono", ctx_completo)
        assert "3001234567" in salida.mensaje

    def test_editar_hotel_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_hotel = "Hotel Caribe"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Hotel", ctx_completo)
        assert "Hotel Caribe" in salida.mensaje

    def test_editar_hotel_sin_hotel_muestra_sin_hotel(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.sin_hotel = True
        ctx_completo.cliente_hotel = None
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Hotel", ctx_completo)
        assert "Sin hotel" in salida.mensaje

    def test_editar_habitacion_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.cliente_habitacion = "304"
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Habitación", ctx_completo)
        assert "304" in salida.mensaje

    def test_editar_fecha_muestra_valor_actual(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        import datetime
        ctx_completo.fecha_salida = datetime.datetime(2026, 7, 25, 9, 0)
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Fecha de salida", ctx_completo)
        assert "25/07/2026" in salida.mensaje

    def test_editar_adultos_muestra_ambos_valores(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        ctx_completo.adultos = 3
        ctx_completo.ninos = 1
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Adultos/Niños", ctx_completo)
        assert "3" in salida.mensaje
        assert "1" in salida.mensaje

    def test_editar_valor_muestra_monto_formateado(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        from decimal import Decimal
        ctx_completo.valor = Decimal("260000")
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Valor de venta", ctx_completo)
        assert "$260.000" in salida.mensaje

    def test_editar_abono_muestra_monto_formateado(
        self, fsm: FSMTiquetera, ctx_completo: ContextoVenta
    ) -> None:
        from decimal import Decimal
        ctx_completo.abono = Decimal("130000")
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Abono", ctx_completo)
        assert "$130.000" in salida.mensaje


class TestNetoRecalculoEnEdicion:
    """Neto must recalculate from catalog whenever destino or pax changes in edit mode."""

    def test_editar_destino_recalcula_neto_aunque_ya_estaba_seteado(
        self, fsm: FSMTiquetera
    ) -> None:
        # neto stale from a previous calculation; after confirming destino edit it must update
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            ninos=0,
            neto=Decimal("999999"),
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # Service 1: 100000 x 2 adultos = 200000
        assert salida.contexto.neto == Decimal("200000")

    def test_editar_pax_recalcula_neto_aunque_ya_estaba_seteado(
        self, fsm: FSMTiquetera
    ) -> None:
        # adultos went from 1 → 2; neto should update from 100000 to 200000
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            neto=Decimal("100000"),
            modo_edicion=True,
        )
        salida = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        assert salida.nuevo_estado == EstadoFSM.CONFIRMACION
        # Service 1: 100000 x 2 adultos = 200000
        assert salida.contexto.neto == Decimal("200000")

    def test_foto_modo_recalcula_neto_desde_catalogo(self, fsm: FSMTiquetera) -> None:
        # IA extracted a wrong neto; catalog must override it when TIPO_RESERVA is answered
        ctx = ContextoVenta(
            destinos_numeros=[1],
            adultos=2,
            ninos=0,
            abono=Decimal("0"),
            neto=Decimal("999999"),
            foto_modo=True,
        )
        s1 = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "EXTERNO", s1.contexto)
        # Service 1: 100000 x 2 adultos = 200000
        assert s2.contexto.neto == Decimal("200000")


# ─── Destination picker: edit flow, photo mode, callback_data limits ─────────


class TestEditarDestinosPicker:
    """Editing 'Destinos' routes to the family picker and resets the selection."""

    def test_editar_destinos_va_a_familia(self, fsm: FSMTiquetera) -> None:
        from garay.aplicacion.tiquetera.fsm import _CAMPOS_EDITABLES

        campos_map = {label: estado for label, estado in _CAMPOS_EDITABLES}
        assert campos_map.get("Destinos") == EstadoFSM.FAMILIA

    def test_editar_selector_destinos_navega_a_familia(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2])
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Destinos", ctx)
        assert salida.nuevo_estado == EstadoFSM.FAMILIA
        assert salida.contexto.modo_edicion is True

    def test_editar_destinos_resetea_seleccion(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(destinos_numeros=[1, 2])
        salida = fsm.procesar(EstadoFSM.EDITAR_SELECTOR, "Destinos", ctx)
        assert salida.contexto.destinos_numeros == []

    def test_modo_edicion_persiste_por_el_picker_hasta_confirmar(
        self, fsm_multi: FSMTiquetera
    ) -> None:
        # Multi-tour mode: edit Destinos → accumulator → confirm → CONFIRMACION.
        ctx = ContextoVenta(destinos_numeros=[1], adultos=1, ninos=0)
        s1 = fsm_multi.procesar(EstadoFSM.EDITAR_SELECTOR, "Destinos", ctx)
        assert s1.contexto.modo_edicion is True
        # Pick a family
        indice = _indice_de(fsm_multi, "BARÚ")
        s2 = fsm_multi.procesar(EstadoFSM.FAMILIA, f"fam:{indice}", s1.contexto)
        assert s2.contexto.modo_edicion is True
        # Pick a service → DESTINO accumulator (multi-tour mode)
        s3 = fsm_multi.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:1", s2.contexto)
        assert s3.contexto.modo_edicion is True
        # Confirm → back to CONFIRMACION
        s4 = fsm_multi.procesar(EstadoFSM.DESTINO, "✅ Confirmar", s3.contexto)
        assert s4.nuevo_estado == EstadoFSM.CONFIRMACION


class TestPickerModoFotoRegresion:
    """Photo mode must never enter the family/service picker."""

    def test_foto_modo_no_incluye_picker_en_estados_foto_avanzar(self) -> None:
        from garay.aplicacion.tiquetera.fsm import _ESTADOS_FOTO_AVANZAR

        assert EstadoFSM.FAMILIA not in _ESTADOS_FOTO_AVANZAR
        assert EstadoFSM.SERVICIO_EN_FAMILIA not in _ESTADOS_FOTO_AVANZAR

    def test_foto_modo_salta_picker_completo(self, fsm: FSMTiquetera) -> None:
        """With foto_modo, non-Crespo PUNTO_DE_VENTA routes through TIPO_RESERVA then
        PARTICIPANTE_ROL, skipping the family/service picker entirely."""
        ctx = ContextoVenta(foto_modo=True, destinos_numeros=[1], adultos=1, ninos=0)
        s1 = fsm.procesar_foto(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        # TIPO_RESERVA is NOT in _ESTADOS_FOTO_AVANZAR, so procesar_foto stops here
        assert s1.nuevo_estado == EstadoFSM.TIPO_RESERVA
        s2 = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", s1.contexto)
        assert s2.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL

    def test_foto_modo_canal_origen_salta_picker(self, fsm: FSMTiquetera) -> None:
        ctx = ContextoVenta(foto_modo=True, destinos_numeros=[1], adultos=1, ninos=0)
        salida = fsm.procesar_foto(EstadoFSM.CANAL_ORIGEN, "Instagram", ctx)
        assert salida.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL


class TestCallbackDataLimite:
    """Every generated tour callback_data must fit Telegram's 64-byte limit."""

    def test_callback_data_de_familias_bajo_limite(self, fsm: FSMTiquetera) -> None:
        # After Slice 3: reach FAMILIA via TIPO_RESERVA
        salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
        assert salida.opciones_estructuradas is not None
        for _, data in salida.opciones_estructuradas:
            assert len(data.encode("utf-8")) <= 64

    def test_callback_data_de_servicios_bajo_limite_catalogo_real(self) -> None:
        import json
        from pathlib import Path

        seed_path = Path(__file__).parents[3] / "servicios_seed.json"
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        servicios: list[tuple[int, str, Decimal | None, Decimal | None, str, list[str]]] = [
            (s["numero"], s["nombre"], None, None, s["categoria"], []) for s in raw
        ]
        puntos = ["Marie Real"]
        fsm_real = FSMTiquetera(servicios=servicios, puntos_venta=puntos)
        # After Slice 3: reach FAMILIA via TIPO_RESERVA
        salida_fam = fsm_real.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
        assert salida_fam.opciones_estructuradas is not None
        # Walk every family and assert every service button callback_data ≤ 64 bytes
        for indice in range(len(salida_fam.opciones_estructuradas)):
            salida_srv = fsm_real.procesar(EstadoFSM.FAMILIA, f"fam:{indice}", ContextoVenta())
            assert salida_srv.opciones_estructuradas is not None
            for _, data in salida_srv.opciones_estructuradas:
                assert len(data.encode("utf-8")) <= 64, f"overflow: {data!r}"

    def test_callback_data_de_freelancers_bajo_limite(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Every fl:{uuid} callback_data from _opciones_freelancers fits within 64 bytes."""
        for solo_activos in (True, False):
            opts = fsm_con_roster._opciones_freelancers(solo_activos=solo_activos)
            for _label, data in opts:
                assert len(data.encode("utf-8")) <= 64, (
                    f"overflow (solo_activos={solo_activos}): {data!r}"
                )


# ─── Fix 2: Empty-roster guard ───────────────────────────────────────────────


class TestEmptyRosterGuard:
    """PARTICIPANTE_ROL must not enter a button-less dead-end when no active freelancers."""

    def test_solo_vendedor_empty_roster_returns_error_not_dead_end(self) -> None:
        """FSM with freelancers=[] picking 'Solo vendedor' must return error, not PARTICIPANTE_OTRO.
        """
        fsm_vacio = FSMTiquetera(
            servicios=SERVICIOS_TEST,
            puntos_venta=PUNTOS_TEST,
            freelancers=[],
        )
        s = fsm_vacio.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ContextoVenta())
        # Must NOT advance to PARTICIPANTE_OTRO with zero buttons
        assert s.nuevo_estado != EstadoFSM.PARTICIPANTE_OTRO or (
            s.opciones_estructuradas is not None and len(s.opciones_estructuradas) > 0
        ), "Dead-end: PARTICIPANTE_OTRO with no opciones_estructuradas"
        # Must show the error message (key check handled by assertions below)
        # The real assertion: FSM must return error message or stay at PARTICIPANTE_ROL
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert "freelancer" in s.mensaje.lower() or "registr" in s.mensaje.lower()

    def test_solo_cerrador_empty_roster_returns_error_not_dead_end(self) -> None:
        """FSM with freelancers=[] picking 'Solo cerrador' must return error, not PARTICIPANTE_OTRO.
        """
        fsm_vacio = FSMTiquetera(
            servicios=SERVICIOS_TEST,
            puntos_venta=PUNTOS_TEST,
            freelancers=[],
        )
        s = fsm_vacio.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo cerrador", ContextoVenta())
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        assert "freelancer" in s.mensaje.lower() or "registr" in s.mensaje.lower()

    def test_solo_vendedor_with_roster_still_enters_participante_otro(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Sanity: non-empty roster still reaches PARTICIPANTE_OTRO."""
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ContextoVenta())
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None
        assert len(s.opciones_estructuradas) > 0


# ─── Fix 3: End-to-end flujo completo for solo vendedor / solo cerrador ───────


def _indice_familia_de(fsm: FSMTiquetera, categoria: str) -> int:
    """Return the index of a family by category name (substring match)."""
    # After Slice 3: reach FAMILIA via TIPO_RESERVA (punto already set before TIPO_RESERVA)
    salida = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ContextoVenta())
    assert salida.opciones_estructuradas is not None
    for i, (label, _) in enumerate(salida.opciones_estructuradas):
        if categoria in label:
            return i
    raise ValueError(f"Category {categoria!r} not found in family picker")


class TestFlujoCompletoSoloParticipante:
    """Fix 3 — full flow for 'Solo vendedor' and 'Solo cerrador' roles."""

    def _drive_to_participante_rol(
        self, fsm: FSMTiquetera
    ) -> ContextoVenta:
        """Drive the FSM from start through MONTO_NETO, returning context at PARTICIPANTE_ROL."""
        ctx = ContextoVenta()

        s = fsm.procesar(EstadoFSM.MODALIDAD_VENTA, "Presencial", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.PUNTO_DE_VENTA, "Marie Real", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.TIPO_RESERVA, "INTERNO", ctx)
        ctx = s.contexto

        indice_islas = _indice_familia_de(fsm, "ISLAS")
        s = fsm.procesar(EstadoFSM.FAMILIA, f"fam:{indice_islas}", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.SERVICIO_EN_FAMILIA, "srv:3", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.DESTINO, "✅ Confirmar", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_NOMBRE, "Juan Perez", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_TELEFONO, "3001234567", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_EMAIL, "juan@example.com", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_TIPO_ID, "CC", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_IDENTIFICACION, "1234567890", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_HOTEL, "Hotel Caribe", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.CLIENTE_HABITACION, "301", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.FECHA_SALIDA, "25/12", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.PAX_ADULTOS, "2", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.PAX_NINOS, "0", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.MONTO_VALOR, "500.000", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.MONTO_ABONO, "0", ctx)
        ctx = s.contexto

        s = fsm.procesar(EstadoFSM.MONTO_NETO, "450000", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_ROL
        return s.contexto

    def test_flujo_completo_solo_vendedor(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Full flow with 'Solo vendedor': pick F2_ID as counterpart → TERMINADO."""
        ctx = self._drive_to_participante_rol(fsm_con_roster)

        # Pick "Solo vendedor" → PARTICIPANTE_OTRO with picker
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo vendedor", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None
        ctx = s.contexto
        assert ctx.rol_registrante == "vendedor"

        # Pick the counterpart (cerrador) via fl: callback
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F2_ID}", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        ctx = s.contexto
        assert ctx.cerrador_id == F2_ID
        assert ctx.cerrador_nombre == "Luis"

        # Confirm → TERMINADO
        s = fsm_con_roster.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert s.nuevo_estado == EstadoFSM.TERMINADO
        assert s.listo is True

    def test_flujo_completo_solo_cerrador(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """Full flow with 'Solo cerrador': pick F1_ID as counterpart → TERMINADO."""
        ctx = self._drive_to_participante_rol(fsm_con_roster)

        # Pick "Solo cerrador" → PARTICIPANTE_OTRO with picker
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_ROL, "Solo cerrador", ctx)
        assert s.nuevo_estado == EstadoFSM.PARTICIPANTE_OTRO
        assert s.opciones_estructuradas is not None
        ctx = s.contexto
        assert ctx.rol_registrante == "cerrador"

        # Pick the counterpart (vendedor) via fl: callback
        s = fsm_con_roster.procesar(EstadoFSM.PARTICIPANTE_OTRO, f"fl:{F1_ID}", ctx)
        assert s.nuevo_estado == EstadoFSM.CONFIRMACION
        ctx = s.contexto
        assert ctx.vendedor_id == F1_ID
        assert ctx.vendedor_nombre == "Ana"

        # Confirm → TERMINADO
        s = fsm_con_roster.procesar(EstadoFSM.CONFIRMACION, "✅ Confirmar", ctx)
        assert s.nuevo_estado == EstadoFSM.TERMINADO
        assert s.listo is True


# ─── Fix 4: Edit guard symmetry in _handle_editar_vendedor ───────────────────


class TestEditarVendedorGuard:
    """Fix 4 — _handle_editar_vendedor must guard against None/unknown rol_registrante."""

    def test_editar_vendedor_rol_none_returns_error(
        self, fsm_con_roster: FSMTiquetera
    ) -> None:
        """ctx with rol_registrante=None must return error, not silently mutate + advance."""
        ctx = ContextoVenta(rol_registrante=None)
        s = fsm_con_roster.procesar(EstadoFSM.EDITAR_VENDEDOR, f"fl:{F1_ID}", ctx)
        # Must NOT advance to CONFIRMACION or EDITAR_CERRADOR silently
        assert s.nuevo_estado not in (EstadoFSM.CONFIRMACION, EstadoFSM.EDITAR_CERRADOR), (
            f"Expected error state, got {s.nuevo_estado}"
        )
        # The context must NOT have been silently mutated with the vendedor_id
        # (or if it was, it must at least return an error state)
        assert s.nuevo_estado == EstadoFSM.EDITAR_VENDEDOR
