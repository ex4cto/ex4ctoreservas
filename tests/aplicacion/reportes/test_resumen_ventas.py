"""Tests for ResumenVentasService — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.reportes.resumen_ventas import ResumenVentasService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _make_snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("10"),
        porcentaje_cerrador=Decimal("5"),
        porcentaje_referido_maximo=Decimal("3"),
        porcentaje_capa_punto=Decimal("2"),
    )


def _make_venta(
    *,
    valor: int = 500_000,
    neto: int = 300_000,
    vendedor: str | None = "Carlos",
    cerrador: str | None = "Maria",
    fecha: datetime.date = datetime.date(2026, 7, 10),
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(neto),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=fecha,
        participantes=Participantes(
            vendedor_nombre=vendedor,
            cerrador_nombre=cerrador,
        ),
    )


def _make_comision(
    venta_id: uuid.UUID,
    *,
    vendedor: int = 50_000,
    cerrador: int = 25_000,
    agencia: int = 200_000,
) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(vendedor),
            cerrador=Dinero(cerrador),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(agencia),
            snapshot=_make_snapshot(),
        ),
        fecha=datetime.date(2026, 7, 10),
    )


def _make_service(
    ventas: list[Venta],
    comisiones: list[ComisionRegistrada],
) -> ResumenVentasService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas

    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones

    return ResumenVentasService(ventas=ventas_repo, comisiones=comisiones_repo)


class TestResumenVentasServiceSinVentas:
    def test_sin_ventas_devuelve_ceros(self) -> None:
        service = _make_service(ventas=[], comisiones=[])
        resumen = service.ejecutar(mes=7, año=2026)

        assert resumen.total_ventas == 0
        assert resumen.total_valor == Dinero(0)
        assert resumen.ganancia_agencia == Dinero(0)
        assert resumen.por_vendedor == ()
        assert resumen.mes == 7
        assert resumen.año == 2026


class TestResumenVentasServiceUnVendedor:
    def test_un_vendedor_una_venta(self) -> None:
        venta = _make_venta(valor=500_000, neto=300_000, vendedor="Carlos", cerrador="Carlos")
        comision = _make_comision(venta.id, vendedor=50_000, cerrador=25_000, agencia=200_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        assert resumen.total_ventas == 1
        assert resumen.total_valor == Dinero(500_000)
        assert resumen.ganancia_agencia == Dinero(200_000)

    def test_un_vendedor_distintos_roles_en_misma_venta(self) -> None:
        """Mismo freelancer como vendedor Y cerrador — suma ambas comisiones."""
        venta = _make_venta(vendedor="Juan", cerrador="Juan")
        comision = _make_comision(venta.id, vendedor=50_000, cerrador=25_000, agencia=100_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        # Juan aparece una vez con la suma de vendedor + cerrador
        assert len(resumen.por_vendedor) == 1
        juan = resumen.por_vendedor[0]
        assert juan.nombre == "Juan"
        assert juan.comision == Dinero(75_000)  # 50000 + 25000


class TestResumenVentasServiceVendedorNulo:
    def test_vendedor_none_queda_como_sin_asignar(self) -> None:
        venta = _make_venta(vendedor=None, cerrador="Maria")
        comision = _make_comision(venta.id, vendedor=0, cerrador=25_000, agencia=100_000)
        service = _make_service(ventas=[venta], comisiones=[comision])

        resumen = service.ejecutar(mes=7, año=2026)

        nombres = {v.nombre for v in resumen.por_vendedor}
        assert "Sin asignar" in nombres
