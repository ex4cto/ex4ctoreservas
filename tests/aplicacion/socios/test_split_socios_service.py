"""Tests for SplitSociosService — TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.socios.servicio_split import SplitSociosService
from garay.aplicacion.socios.split import ResumenSplitSocios
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.socios.entidades import PagoSocio, SocioConfig
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


def _make_venta(valor: int = 1_000_000) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(valor),
        neto=Dinero(valor // 2),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 9, 1),
        participantes=Participantes(
            vendedor_nombre="Carlos",
            cerrador_nombre="Maria",
            vendedor_id=None,
            cerrador_id=None,
        ),
    )


def _make_comision(venta_id: uuid.UUID, agencia: int) -> ComisionRegistrada:
    return ComisionRegistrada(
        venta_id=venta_id,
        desglose=DesgloseComision(
            vendedor=Dinero("50000"),
            cerrador=Dinero("25000"),
            punto_de_venta=Dinero("10000"),
            referido=Dinero("5000"),
            agencia=Dinero(agencia),
            snapshot=_make_snapshot(),
        ),
        fecha=datetime.date(2026, 9, 1),
    )


def _make_pago(nombre_socio: str, monto: int) -> PagoSocio:
    return PagoSocio(
        id=uuid.uuid4(),
        nombre_socio=nombre_socio,
        monto=Dinero(monto),
        fecha=datetime.date(2026, 9, 10),
        tipo="parcial",
        nota=None,
        registrado_en=datetime.datetime(2026, 9, 10, 12, 0, 0),
    )


def _make_config(nombre: str, porcentaje: str) -> SocioConfig:
    return SocioConfig(
        nombre=nombre, porcentaje=Decimal(porcentaje), telegram_id=None
    )


def _make_service(
    ventas: list[Venta],
    comisiones: list[ComisionRegistrada],
    configs: list[SocioConfig],
    pagos: list[PagoSocio],
) -> SplitSociosService:
    repo_ventas = MagicMock()
    repo_ventas.listar.return_value = ventas

    repo_comisiones = MagicMock()
    repo_comisiones.listar_por_venta_ids.return_value = comisiones

    repo_configs = MagicMock()
    repo_configs.listar.return_value = configs

    repo_pagos = MagicMock()
    repo_pagos.listar.return_value = pagos

    return SplitSociosService(
        ventas=repo_ventas,
        comisiones=repo_comisiones,
        socios_config=repo_configs,
        pagos_socio=repo_pagos,
    )


class TestSplitSociosServiceCalcularAcumulado:
    def test_acumulado_correcto_con_ventas_y_comisiones(self) -> None:
        """Verifica que el acumulado por socio es correcto con ventas históricas."""
        venta = _make_venta()
        comision = _make_comision(venta.id, agencia=1_000_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service([venta], [comision], configs, [])

        resultado = service.calcular_acumulado()

        assert isinstance(resultado, ResumenSplitSocios)
        empresa = next(r for r in resultado.por_socio if r.nombre == "empresa")
        garay = next(r for r in resultado.por_socio if r.nombre == "garay")
        ryan = next(r for r in resultado.por_socio if r.nombre == "ryan")

        assert empresa.acumulado == Dinero("500000")
        assert garay.acumulado == Dinero("250000")
        assert ryan.acumulado == Dinero("250000")
        assert resultado.total_agencia == Dinero("1000000")

    def test_pendiente_correcto_con_pagos_parciales(self) -> None:
        """Pendiente = acumulado - pagado."""
        venta = _make_venta()
        comision = _make_comision(venta.id, agencia=2_000_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        pagos = [
            _make_pago("empresa", 200_000),
            _make_pago("garay", 100_000),
        ]
        service = _make_service([venta], [comision], configs, pagos)

        resultado = service.calcular_acumulado()

        empresa = next(r for r in resultado.por_socio if r.nombre == "empresa")
        garay = next(r for r in resultado.por_socio if r.nombre == "garay")
        ryan = next(r for r in resultado.por_socio if r.nombre == "ryan")

        # empresa: acumulado 1_000_000, pagado 200_000 → pendiente 800_000
        assert empresa.acumulado == Dinero("1000000")
        assert empresa.pagado == Dinero("200000")
        assert empresa.pendiente == Dinero("800000")

        # garay: acumulado 500_000, pagado 100_000 → pendiente 400_000
        assert garay.acumulado == Dinero("500000")
        assert garay.pagado == Dinero("100000")
        assert garay.pendiente == Dinero("400000")

        # ryan: acumulado 500_000, pagado 0 → pendiente 500_000
        assert ryan.acumulado == Dinero("500000")
        assert ryan.pagado == Dinero("0")
        assert ryan.pendiente == Dinero("500000")

    def test_sin_ventas_retorna_todo_en_cero(self) -> None:
        """Sin ventas, el resumen tiene todo en Dinero(0)."""
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service([], [], configs, [])

        resultado = service.calcular_acumulado()

        assert resultado.total_agencia == Dinero("0")
        for resumen in resultado.por_socio:
            assert resumen.acumulado == Dinero("0")
            assert resumen.pagado == Dinero("0")
            assert resumen.pendiente == Dinero("0")

    def test_sin_config_de_socios_retorna_splits_vacios(self) -> None:
        """Sin configuración de socios no lanza excepción — retorna splits vacíos."""
        venta = _make_venta()
        comision = _make_comision(venta.id, agencia=500_000)
        service = _make_service([venta], [comision], [], [])

        resultado = service.calcular_acumulado()

        assert isinstance(resultado, ResumenSplitSocios)
        assert len(resultado.por_socio) == 0
        assert resultado.total_agencia == Dinero("500000")

    def test_multiples_ventas_acumula_agencia(self) -> None:
        """Con múltiples ventas la agencia total es la suma de todas las comisiones."""
        venta1 = _make_venta()
        venta2 = _make_venta()
        comision1 = _make_comision(venta1.id, agencia=600_000)
        comision2 = _make_comision(venta2.id, agencia=400_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service([venta1, venta2], [comision1, comision2], configs, [])

        resultado = service.calcular_acumulado()

        assert resultado.total_agencia == Dinero("1000000")
        empresa = next(r for r in resultado.por_socio if r.nombre == "empresa")
        assert empresa.acumulado == Dinero("500000")

    def test_orden_por_socio_empresa_garay_ryan(self) -> None:
        """El orden de por_socio sigue el orden de socios_config.listar()."""
        venta = _make_venta()
        comision = _make_comision(venta.id, agencia=1_000_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service([venta], [comision], configs, [])

        resultado = service.calcular_acumulado()

        nombres = [r.nombre for r in resultado.por_socio]
        assert nombres == ["empresa", "garay", "ryan"]
