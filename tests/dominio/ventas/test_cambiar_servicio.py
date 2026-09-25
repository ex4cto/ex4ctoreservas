"""Tests for Venta.cambiar_servicio() and calcular_neto_tour() — strict TDD."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest

from garay.aplicacion.ventas.editar_servicio import calcular_neto_tour
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import (
    MismoServicio,
    NetoIgualOSuperaValorVenta,
    ValorVentaMenorQueAbono,
    VentaYaAnulada,
)
from garay.dominio.ventas.valor_objetos import Participantes

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _venta(
    valor_venta: Dinero | None = None,
    neto: Dinero | None = None,
    abono: Dinero | None = None,
    servicio_ids: list[uuid.UUID] | None = None,
    fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None = None,
    horarios_por_servicio: dict[uuid.UUID, str] | None = None,
) -> Venta:
    sid = uuid.uuid4() if servicio_ids is None else servicio_ids[0]
    ids = servicio_ids if servicio_ids is not None else [sid]
    return Venta(
        id=uuid.uuid4(),
        valor_venta=valor_venta or Dinero(300),
        neto=neto or Dinero(100),
        servicio_ids=ids,
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2024, 6, 1),
        participantes=Participantes(),
        abono=abono,
        fechas_por_servicio=fechas_por_servicio,
        horarios_por_servicio=horarios_por_servicio,
    )


def _servicio(
    precio_adulto: Decimal | None = Decimal("50"),
    precio_nino: Decimal | None = None,
    netos_por_horario: dict[str, Decimal] | None = None,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=1,
        nombre="Tour de prueba",
        precio_neto_adulto=precio_adulto,
        precio_neto_nino=precio_nino,
        netos_por_horario=netos_por_horario or {},
    )


# ---------------------------------------------------------------------------
# Venta.cambiar_servicio — happy paths
# ---------------------------------------------------------------------------


class TestCambiarServicio:
    def test_cambiar_servicio_actualiza_servicio_neto_y_valor(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        nuevo_id = uuid.uuid4()
        venta.cambiar_servicio([nuevo_id], Dinero(80), Dinero(250))
        assert venta.servicio_ids == [nuevo_id]
        assert venta.neto == Dinero(80)
        assert venta.valor_venta == Dinero(250)

    def test_cambiar_servicio_solo_neto_sin_cambio_valor_venta(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        nuevo_id = uuid.uuid4()
        venta.cambiar_servicio([nuevo_id], Dinero(80), None)
        assert venta.valor_venta == Dinero(300)
        assert venta.neto == Dinero(80)

    # ---------------------------------------------------------------------------
    # Error cases
    # ---------------------------------------------------------------------------

    def test_cambiar_servicio_venta_anulada_lanza_error(self) -> None:
        venta = _venta()
        venta.anular()
        with pytest.raises(VentaYaAnulada):
            venta.cambiar_servicio([uuid.uuid4()], Dinero(80))

    def test_cambiar_servicio_mismo_servicio_lanza_mismoservicio(self) -> None:
        sid = uuid.uuid4()
        venta = _venta(servicio_ids=[sid])
        with pytest.raises(MismoServicio):
            venta.cambiar_servicio([sid], Dinero(80))

    def test_cambiar_servicio_neto_igual_valor_venta_lanza_error(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100))
        with pytest.raises(NetoIgualOSuperaValorVenta):
            venta.cambiar_servicio([uuid.uuid4()], Dinero(300))

    def test_cambiar_servicio_valor_venta_invalido_lanza_error(self) -> None:
        """nuevo_valor_venta=0 with neto=1 fires NetoIgualOSuperaValorVenta first.

        Domain order: anulada -> mismo_servicio -> moneda -> neto>=vv -> vv<=0 -> abono.
        ValorVentaInvalido is unreachable via the public API because Dinero>=0 means
        neto(>=0) >= vv(0) is always True, triggering the prior guard first.
        The test documents the observable boundary.
        """
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(1))
        # neto(1) >= vv(0) -> NetoIgualOSuperaValorVenta, not ValorVentaInvalido
        with pytest.raises(NetoIgualOSuperaValorVenta):
            venta.cambiar_servicio([uuid.uuid4()], Dinero(1), Dinero(0))

    def test_cambiar_servicio_valor_venta_menor_abono_lanza_error(self) -> None:
        venta = _venta(valor_venta=Dinero(300), neto=Dinero(100), abono=Dinero(200))
        with pytest.raises(ValorVentaMenorQueAbono):
            venta.cambiar_servicio([uuid.uuid4()], Dinero(80), Dinero(150))

    # ---------------------------------------------------------------------------
    # Remap fechas_por_servicio
    # ---------------------------------------------------------------------------

    def test_cambiar_servicio_remap_fechas_por_servicio_single_entry(self) -> None:
        viejo_id = uuid.uuid4()
        nuevo_id = uuid.uuid4()
        ts = datetime.datetime(2024, 6, 1, 9, 0, tzinfo=datetime.UTC)
        venta = _venta(
            servicio_ids=[viejo_id],
            fechas_por_servicio={viejo_id: ts},
        )
        venta.cambiar_servicio([nuevo_id], Dinero(80))
        assert venta.fechas_por_servicio == {nuevo_id: ts}

    def test_cambiar_servicio_remap_horarios_por_servicio_single_entry(self) -> None:
        viejo_id = uuid.uuid4()
        nuevo_id = uuid.uuid4()
        venta = _venta(
            servicio_ids=[viejo_id],
            horarios_por_servicio={viejo_id: "09:00"},
        )
        venta.cambiar_servicio([nuevo_id], Dinero(80))
        assert venta.horarios_por_servicio == {nuevo_id: "09:00"}

    def test_cambiar_servicio_no_remap_si_multiples_entries(self) -> None:
        """With multiple entries in fechas_por_servicio, the dict is not remapped."""
        viejo_id = uuid.uuid4()
        otro_id = uuid.uuid4()
        nuevo_id = uuid.uuid4()
        ts = datetime.datetime(2024, 6, 1, 9, 0, tzinfo=datetime.UTC)
        fechas = {viejo_id: ts, otro_id: ts}
        venta = _venta(
            servicio_ids=[viejo_id],
            fechas_por_servicio=dict(fechas),
        )
        venta.cambiar_servicio([nuevo_id], Dinero(80))
        # Should NOT be remapped — the original dict shape is preserved
        assert nuevo_id not in venta.fechas_por_servicio  # type: ignore[operator]
        assert viejo_id in venta.fechas_por_servicio  # type: ignore[operator]


# ---------------------------------------------------------------------------
# calcular_neto_tour
# ---------------------------------------------------------------------------


class TestCalcularNetoTour:
    def test_calcular_neto_tour_sin_precio_retorna_none(self) -> None:
        servicio = _servicio(precio_adulto=None)
        result = calcular_neto_tour(servicio, adultos=2, ninos=0, horario=None)
        assert result is None

    def test_calcular_neto_tour_adultos_sin_ninos(self) -> None:
        servicio = _servicio(precio_adulto=Decimal("50"))
        result = calcular_neto_tour(servicio, adultos=3, ninos=0, horario=None)
        assert result == Dinero(150)

    def test_calcular_neto_tour_adultos_y_ninos(self) -> None:
        servicio = _servicio(precio_adulto=Decimal("50"), precio_nino=Decimal("25"))
        result = calcular_neto_tour(servicio, adultos=2, ninos=2, horario=None)
        assert result == Dinero(150)

    def test_calcular_neto_tour_usa_horario_especifico(self) -> None:
        servicio = _servicio(
            precio_adulto=Decimal("50"),
            netos_por_horario={"14:00": Decimal("45")},
        )
        result = calcular_neto_tour(servicio, adultos=2, ninos=0, horario="14:00")
        assert result == Dinero(90)

    def test_calcular_neto_tour_precio_nino_none_trata_como_cero(self) -> None:
        servicio = _servicio(precio_adulto=Decimal("50"), precio_nino=None)
        result = calcular_neto_tour(servicio, adultos=2, ninos=3, horario=None)
        # ninos contribute 0 when precio_nino is None
        assert result == Dinero(100)
