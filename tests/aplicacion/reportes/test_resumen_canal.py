"""TDD RED — WU-5: por_canal breakdown in ResumenVentas."""

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


def _snapshot() -> SnapshotReglas:
    return SnapshotReglas(
        tipo_cliente=TipoCliente.DIGITAL,
        porcentaje_vendedor=Decimal("10"),
        porcentaje_cerrador=Decimal("5"),
        porcentaje_referido_maximo=Decimal("3"),
        porcentaje_capa_punto=Decimal("2"),
    )


def _make_venta(
    tipo: TipoCliente = TipoCliente.DIGITAL,
    canal: str | None = "WhatsApp",
    valor: int = 500_000,
) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(valor - 100_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=tipo,
        fecha=datetime.date(2026, 7, 10),
        participantes=Participantes(vendedor_nombre="Ana", cerrador_nombre="Ana"),
        canal_origen=canal,
    )


def _make_comision(venta_id: uuid.UUID, agencia: int = 200_000) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero(50_000),
            cerrador=Dinero(25_000),
            punto_de_venta=Dinero(0),
            referido=Dinero(0),
            agencia=Dinero(agencia),
            snapshot=_snapshot(),
        ),
        fecha=datetime.date(2026, 7, 10),
    )


def _make_service(
    ventas: list[Venta], comisiones: list[ComisionRegistrada]
) -> ResumenVentasService:
    ventas_repo = MagicMock()
    ventas_repo.listar_por_periodo.return_value = ventas
    comisiones_repo = MagicMock()
    comisiones_repo.listar_por_venta_ids.return_value = comisiones
    return ResumenVentasService(ventas=ventas_repo, comisiones=comisiones_repo)


class TestResumenCanalOrigen:
    def test_resumen_ventas_tiene_campo_por_canal(self) -> None:
        from garay.aplicacion.reportes.resumen_ventas import ResumenVentas

        resumen = ResumenVentas(
            mes=7,
            año=2026,
            total_ventas=0,
            total_valor=Dinero(0),
            ganancia_agencia=Dinero(0),
            por_vendedor=(),
        )
        assert hasattr(resumen, "por_canal")
        assert resumen.por_canal == ()

    def test_resumen_canal_acumula_ventas_digital(self) -> None:
        v1 = _make_venta(tipo=TipoCliente.DIGITAL, canal="WhatsApp", valor=500_000)
        v2 = _make_venta(tipo=TipoCliente.DIGITAL, canal="WhatsApp", valor=300_000)
        v3 = _make_venta(tipo=TipoCliente.DIGITAL, canal="Instagram", valor=400_000)
        comisiones = [_make_comision(v.id) for v in [v1, v2, v3]]
        service = _make_service([v1, v2, v3], comisiones)
        resumen = service.ejecutar(mes=7, año=2026)
        canales = {c.canal: c for c in resumen.por_canal}
        assert "WhatsApp" in canales
        assert "Instagram" in canales
        assert canales["WhatsApp"].cantidad == 2
        assert canales["Instagram"].cantidad == 1
        assert canales["WhatsApp"].valor_total == Dinero(800_000)

    def test_resumen_canal_omite_interno(self) -> None:
        v1 = _make_venta(tipo=TipoCliente.DIGITAL, canal="TikTok", valor=500_000)
        v2 = _make_venta(tipo=TipoCliente.INTERNO, canal=None, valor=300_000)
        comisiones = [_make_comision(v.id) for v in [v1, v2]]
        service = _make_service([v1, v2], comisiones)
        resumen = service.ejecutar(mes=7, año=2026)
        canales = {c.canal for c in resumen.por_canal}
        assert "TikTok" in canales
        assert len(resumen.por_canal) == 1

    def test_resumen_canal_sin_ventas_no_rompe(self) -> None:
        service = _make_service([], [])
        resumen = service.ejecutar(mes=7, año=2026)
        assert resumen.por_canal == ()

    def test_resumen_canal_venta_digital_sin_canal_no_rompe(self) -> None:
        v1 = _make_venta(tipo=TipoCliente.DIGITAL, canal=None, valor=500_000)
        comisiones = [_make_comision(v1.id)]
        service = _make_service([v1], comisiones)
        resumen = service.ejecutar(mes=7, año=2026)
        assert isinstance(resumen.por_canal, tuple)
