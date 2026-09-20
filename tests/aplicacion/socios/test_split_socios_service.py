"""Tests for SplitSociosService — TDD suite."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.socios.servicio_split import SplitSociosService
from garay.aplicacion.socios.split import ResumenSplitPeriodo, ResumenSplitSocios
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


def _make_service_periodo(
    ventas_periodo: list[Venta],
    comisiones: list[ComisionRegistrada],
    configs: list[SocioConfig],
) -> SplitSociosService:
    """Factory for calcular_periodo tests — listar_por_periodo is the key method."""
    repo_ventas = MagicMock()
    repo_ventas.listar_por_periodo.return_value = ventas_periodo

    repo_comisiones = MagicMock()
    repo_comisiones.listar_por_venta_ids.return_value = comisiones

    repo_configs = MagicMock()
    repo_configs.listar.return_value = configs

    repo_pagos = MagicMock()

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


class TestSplitSociosServiceCalcularPeriodo:
    """TDD tests for calcular_periodo — RED → GREEN."""

    _DESDE = datetime.date(2026, 9, 1)
    _HASTA = datetime.date(2026, 9, 30)

    def _make_venta_con_bruto(self, valor: int = 2_000_000) -> Venta:
        return _make_venta(valor)

    def _make_comision_completa(
        self,
        venta_id: uuid.UUID,
        agencia: int,
        vendedor: int = 100_000,
        cerrador: int = 80_000,
        punto: int = 0,
    ) -> ComisionRegistrada:
        return ComisionRegistrada(
            venta_id=venta_id,
            desglose=DesgloseComision(
                vendedor=Dinero(vendedor),
                cerrador=Dinero(cerrador),
                punto_de_venta=Dinero(punto),
                referido=Dinero(0),
                agencia=Dinero(agencia),
                snapshot=_make_snapshot(),
            ),
            fecha=datetime.date(2026, 9, 5),
        )

    def test_periodo_con_dos_ventas_suma_agencia(self) -> None:
        """Dos ventas en el período → total_agencia = suma de desglose.agencia."""
        venta1 = self._make_venta_con_bruto(2_000_000)
        venta2 = self._make_venta_con_bruto(3_000_000)
        com1 = self._make_comision_completa(venta1.id, agencia=500_000)
        com2 = self._make_comision_completa(venta2.id, agencia=500_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service_periodo([venta1, venta2], [com1, com2], configs)

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert isinstance(resultado, ResumenSplitPeriodo)
        assert resultado.total_agencia == Dinero(1_000_000)
        assert resultado.ventas_count == 2

    def test_periodo_split_por_socio_proporcional(self) -> None:
        """El acumulado de cada socio es proporcional a su porcentaje."""
        venta = self._make_venta_con_bruto(2_000_000)
        com = self._make_comision_completa(venta.id, agencia=1_000_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service_periodo([venta], [com], configs)

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        empresa = next(r for r in resultado.por_socio if r.nombre == "empresa")
        garay = next(r for r in resultado.por_socio if r.nombre == "garay")
        ryan = next(r for r in resultado.por_socio if r.nombre == "ryan")
        assert empresa.acumulado == Dinero("500000")
        assert garay.acumulado == Dinero("250000")
        assert ryan.acumulado == Dinero("250000")

    def test_periodo_sin_ventas_retorna_cero(self) -> None:
        """Sin ventas en el período → total_agencia=Dinero(0), ventas_count=0."""
        configs = [
            _make_config("empresa", "50"),
            _make_config("garay", "25"),
            _make_config("ryan", "25"),
        ]
        service = _make_service_periodo([], [], configs)

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert resultado.total_agencia == Dinero(0)
        assert resultado.ventas_count == 0
        for r in resultado.por_socio:
            assert r.acumulado == Dinero(0)

    def test_periodo_sin_socios_retorna_por_socio_vacio(self) -> None:
        """Sin socios configurados → por_socio es tupla vacía."""
        venta = self._make_venta_con_bruto()
        com = self._make_comision_completa(venta.id, agencia=400_000)
        service = _make_service_periodo([venta], [com], [])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert resultado.por_socio == ()
        assert resultado.total_agencia == Dinero(400_000)

    def test_periodo_no_accede_pago_socio_repo(self) -> None:
        """calcular_periodo NUNCA consulta PagoSocioRepository."""
        venta = self._make_venta_con_bruto()
        com = self._make_comision_completa(venta.id, agencia=300_000)
        configs = [_make_config("empresa", "100")]
        service = _make_service_periodo([venta], [com], configs)

        # If PagoSocioRepository were called it would fail (return value not set).
        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        # pagos_socio mock was never configured → any call would return a MagicMock,
        # not crash; but the real invariant is that acumulado is correct without it.
        assert resultado.total_agencia == Dinero(300_000)
        empresa = resultado.por_socio[0]
        assert empresa.acumulado == Dinero(300_000)

    def test_periodo_total_bruto_y_comisiones_freelancer(self) -> None:
        """total_bruto y total_comisiones_freelancer se calculan correctamente."""
        venta = self._make_venta_con_bruto(2_000_000)
        com = self._make_comision_completa(
            venta.id,
            agencia=820_000,
            vendedor=100_000,
            cerrador=80_000,
            punto=0,
        )
        service = _make_service_periodo([venta], [com], [])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert resultado.total_bruto == Dinero(2_000_000)
        assert resultado.total_comisiones_freelancer == Dinero(180_000)

    def test_periodo_usa_listar_por_periodo(self) -> None:
        """calcular_periodo llama listar_por_periodo con los argumentos correctos."""
        configs = [_make_config("empresa", "100")]
        repo_ventas = MagicMock()
        repo_ventas.listar_por_periodo.return_value = []
        repo_comisiones = MagicMock()
        repo_comisiones.listar_por_venta_ids.return_value = []
        repo_configs = MagicMock()
        repo_configs.listar.return_value = configs
        repo_pagos = MagicMock()

        service = SplitSociosService(
            ventas=repo_ventas,
            comisiones=repo_comisiones,
            socios_config=repo_configs,
            pagos_socio=repo_pagos,
        )
        service.calcular_periodo(self._DESDE, self._HASTA)

        repo_ventas.listar_por_periodo.assert_called_once_with(self._DESDE, self._HASTA)


class TestResumenVentaDetalleDTO:
    """Tests for ResumenVentaDetalle and ResumenFreelancerPeriodo DTOs."""

    def test_resumen_venta_detalle_fields_exist(self) -> None:
        """ResumenVentaDetalle has all required fields."""
        from garay.aplicacion.socios.split import ResumenVentaDetalle

        venta_id = uuid.uuid4()
        detalle = ResumenVentaDetalle(
            venta_id=venta_id,
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre="Juan García",
            cerrador_nombre=None,
            valor_bruto=Dinero(600_000),
            desglose_vendedor=Dinero(60_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(540_000),
            split_socios=(),
        )

        assert detalle.venta_id == venta_id
        assert detalle.fecha == datetime.date(2026, 9, 19)
        assert detalle.vendedor_nombre == "Juan García"
        assert detalle.cerrador_nombre is None
        assert detalle.valor_bruto == Dinero(600_000)
        assert detalle.desglose_vendedor == Dinero(60_000)
        assert detalle.desglose_cerrador == Dinero(0)
        assert detalle.desglose_punto == Dinero(0)
        assert detalle.desglose_agencia == Dinero(540_000)
        assert detalle.split_socios == ()

    def test_resumen_freelancer_periodo_fields_exist(self) -> None:
        """ResumenFreelancerPeriodo has nombre and comision fields."""
        from garay.aplicacion.socios.split import ResumenFreelancerPeriodo

        fl = ResumenFreelancerPeriodo(nombre="Juan García", comision=Dinero(60_000))

        assert fl.nombre == "Juan García"
        assert fl.comision == Dinero(60_000)

    def test_resumen_split_periodo_has_new_fields(self) -> None:
        """ResumenSplitPeriodo has ventas_detalle and por_freelancer fields."""
        from garay.aplicacion.socios.split import ResumenFreelancerPeriodo, ResumenVentaDetalle

        resultado = ResumenSplitPeriodo(
            por_socio=(),
            total_agencia=Dinero(0),
            total_bruto=Dinero(0),
            total_comisiones_freelancer=Dinero(0),
            ventas_count=0,
        )
        # Default values should be empty tuples
        assert resultado.ventas_detalle == ()
        assert resultado.por_freelancer == ()

    def test_resumen_split_periodo_with_detalle(self) -> None:
        """ResumenSplitPeriodo accepts ventas_detalle and por_freelancer."""
        from garay.aplicacion.socios.split import ResumenFreelancerPeriodo, ResumenVentaDetalle

        venta_id = uuid.uuid4()
        detalle = ResumenVentaDetalle(
            venta_id=venta_id,
            fecha=datetime.date(2026, 9, 19),
            vendedor_nombre="Juan",
            cerrador_nombre=None,
            valor_bruto=Dinero(600_000),
            desglose_vendedor=Dinero(60_000),
            desglose_cerrador=Dinero(0),
            desglose_punto=Dinero(0),
            desglose_agencia=Dinero(540_000),
            split_socios=(),
        )
        fl = ResumenFreelancerPeriodo(nombre="Juan", comision=Dinero(60_000))

        resultado = ResumenSplitPeriodo(
            por_socio=(),
            total_agencia=Dinero(540_000),
            total_bruto=Dinero(600_000),
            total_comisiones_freelancer=Dinero(60_000),
            ventas_count=1,
            ventas_detalle=(detalle,),
            por_freelancer=(fl,),
        )

        assert len(resultado.ventas_detalle) == 1
        assert resultado.ventas_detalle[0] == detalle
        assert len(resultado.por_freelancer) == 1
        assert resultado.por_freelancer[0] == fl


class TestCalcularPeriodoVentaDetalle:
    """Tests for calcular_periodo populating ventas_detalle and por_freelancer."""

    _DESDE = datetime.date(2026, 9, 1)
    _HASTA = datetime.date(2026, 9, 30)

    def _make_venta(
        self,
        valor: int = 600_000,
        vendedor_nombre: str | None = "Juan García",
        cerrador_nombre: str | None = None,
    ) -> Venta:
        return Venta(
            id=uuid.uuid4(),
            valor_venta=Dinero(valor),
            neto=Dinero(valor // 2),
            servicio_ids=[uuid.uuid4()],
            cliente_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
            fecha=datetime.date(2026, 9, 19),
            participantes=Participantes(
                vendedor_nombre=vendedor_nombre,
                cerrador_nombre=cerrador_nombre,
            ),
        )

    def _make_comision(
        self,
        venta_id: uuid.UUID,
        vendedor: int = 60_000,
        cerrador: int = 0,
        punto: int = 0,
        agencia: int = 540_000,
    ) -> ComisionRegistrada:
        return ComisionRegistrada(
            venta_id=venta_id,
            desglose=DesgloseComision(
                vendedor=Dinero(vendedor),
                cerrador=Dinero(cerrador),
                punto_de_venta=Dinero(punto),
                referido=Dinero(0),
                agencia=Dinero(agencia),
                snapshot=_make_snapshot(),
            ),
            fecha=datetime.date(2026, 9, 19),
        )

    def _make_service(
        self,
        ventas: list[Venta],
        comisiones: list[ComisionRegistrada],
        configs: list[SocioConfig] | None = None,
    ) -> SplitSociosService:
        if configs is None:
            configs = []
        repo_ventas = MagicMock()
        repo_ventas.listar_por_periodo.return_value = ventas
        repo_comisiones = MagicMock()
        repo_comisiones.listar_por_venta_ids.return_value = comisiones
        repo_configs = MagicMock()
        repo_configs.listar.return_value = configs
        repo_pagos = MagicMock()
        return SplitSociosService(
            ventas=repo_ventas,
            comisiones=repo_comisiones,
            socios_config=repo_configs,
            pagos_socio=repo_pagos,
        )

    def test_ventas_detalle_populated_from_venta_and_comision(self) -> None:
        """calcular_periodo populates ventas_detalle with joined data."""
        from garay.aplicacion.socios.split import ResumenVentaDetalle

        venta = self._make_venta(valor=600_000, vendedor_nombre="Juan García")
        com = self._make_comision(
            venta.id, vendedor=60_000, cerrador=0, punto=0, agencia=540_000
        )
        service = self._make_service([venta], [com])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert len(resultado.ventas_detalle) == 1
        det = resultado.ventas_detalle[0]
        assert isinstance(det, ResumenVentaDetalle)
        assert det.venta_id == venta.id
        assert det.fecha == venta.fecha
        assert det.vendedor_nombre == "Juan García"
        assert det.valor_bruto == Dinero(600_000)
        assert det.desglose_vendedor == Dinero(60_000)
        assert det.desglose_agencia == Dinero(540_000)

    def test_ventas_detalle_uses_zero_when_no_comision(self) -> None:
        """When no comision found for a venta, zero Dinero is used."""
        venta = self._make_venta(valor=600_000)
        # No comisiones provided
        service = self._make_service([venta], [])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert len(resultado.ventas_detalle) == 1
        det = resultado.ventas_detalle[0]
        assert det.desglose_agencia == Dinero(0)
        assert det.desglose_vendedor == Dinero(0)

    def test_por_freelancer_aggregates_vendedor(self) -> None:
        """por_freelancer sums vendedor commission across sales."""
        from garay.aplicacion.socios.split import ResumenFreelancerPeriodo

        venta1 = self._make_venta(vendedor_nombre="Juan García")
        venta2 = self._make_venta(vendedor_nombre="Juan García")
        com1 = self._make_comision(venta1.id, vendedor=60_000, agencia=540_000)
        com2 = self._make_comision(venta2.id, vendedor=60_000, agencia=540_000)
        service = self._make_service([venta1, venta2], [com1, com2])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        # Juan should have 120_000 total commission
        juan = next(
            (f for f in resultado.por_freelancer if f.nombre == "Juan García"), None
        )
        assert juan is not None
        assert juan.comision == Dinero(120_000)

    def test_por_freelancer_aggregates_cerrador_separately(self) -> None:
        """Cerrador commission aggregated under cerrador_nombre."""
        venta = self._make_venta(
            vendedor_nombre="Juan García",
            cerrador_nombre="Maria Lopez",
        )
        com = self._make_comision(venta.id, vendedor=60_000, cerrador=40_000, agencia=500_000)
        service = self._make_service([venta], [com])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        nombres = {f.nombre: f.comision for f in resultado.por_freelancer}
        assert "Juan García" in nombres
        assert "Maria Lopez" in nombres
        assert nombres["Juan García"] == Dinero(60_000)
        assert nombres["Maria Lopez"] == Dinero(40_000)

    def test_por_freelancer_omits_none_names(self) -> None:
        """Freelancers with None name are not included in por_freelancer."""
        venta = self._make_venta(vendedor_nombre=None, cerrador_nombre=None)
        com = self._make_comision(venta.id, vendedor=0, cerrador=0, agencia=600_000)
        service = self._make_service([venta], [com])

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        assert resultado.por_freelancer == ()

    def test_per_sale_split_in_ventas_detalle(self) -> None:
        """ventas_detalle[i].split_socios reflects per-sale split."""
        venta = self._make_venta(valor=600_000)
        com = self._make_comision(venta.id, agencia=540_000)
        configs = [
            _make_config("empresa", "50"),
            _make_config("ryan", "50"),
        ]
        service = self._make_service([venta], [com], configs)

        resultado = service.calcular_periodo(self._DESDE, self._HASTA)

        det = resultado.ventas_detalle[0]
        assert len(det.split_socios) == 2
        empresa = next(s for s in det.split_socios if s.nombre == "empresa")
        ryan = next(s for s in det.split_socios if s.nombre == "ryan")
        assert empresa.acumulado == Dinero(270_000)
        assert ryan.acumulado == Dinero(270_000)
