"""Tests for RegenerarFacturaService and reconstruir_contexto (Slice C3, TDD)."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.factura.regenerar_factura import (
    RegenerarFacturaService,
    ResultadoRegenerarFactura,
    reconstruir_contexto,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cliente(
    *,
    nombre: str = "Ana Garcia",
    email: str | None = "ana@example.com",
    telefono: str | None = "+57300",
    hotel: str | None = "Hotel Sol",
    numero_habitacion: str | None = "101",
    identificacion: str | None = "123456",
    tipo_identificacion: str | None = "CC",
) -> MagicMock:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.nombre = nombre
    c.email = email
    c.telefono = telefono
    c.hotel = hotel
    c.numero_habitacion = numero_habitacion
    c.identificacion = identificacion
    c.tipo_identificacion = tipo_identificacion
    c.tipo = TipoCliente.EXTERNO
    return c


def _make_servicio(numero: int = 1, nombre: str = "Tour Isla") -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.numero = numero
    s.nombre = nombre
    return s


def _make_venta(
    *,
    cliente_id: uuid.UUID | None = None,
    valor: Decimal = Decimal("500000"),
    abono: Decimal | None = Decimal("100000"),
    adultos: int = 2,
    ninos: int = 1,
    fecha: datetime.date | None = None,
    servicio_ids: list[uuid.UUID] | None = None,
    fechas_por_servicio: dict[uuid.UUID, datetime.datetime] | None = None,
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.cliente_id = cliente_id or uuid.uuid4()
    v.valor_venta = Dinero(valor)
    v.abono = Dinero(abono) if abono is not None else None
    v.adultos = adultos
    v.ninos = ninos
    v.fecha = fecha or datetime.date(2026, 9, 20)
    _sid = uuid.uuid4()
    v.servicio_ids = servicio_ids if servicio_ids is not None else [_sid]
    v.fechas_por_servicio = fechas_por_servicio
    return v


def _make_factura(venta_id: uuid.UUID | None = None) -> Factura:
    return Factura(
        id=uuid.uuid4(),
        numero="GT-ORIGINAL",
        venta_id=venta_id or uuid.uuid4(),
        cliente_email="ana@example.com",
        monto_total=Dinero("300000"),
        fecha_emision=datetime.date(2026, 8, 1),
        html_contenido="<html>original</html>",
        estado_envio=EstadoEnvioFactura.ENVIADO,
    )


def _make_repos(
    *,
    venta: MagicMock | None = None,
    factura: Factura | None = None,
    cliente: MagicMock | None = None,
    servicio: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    facturas_repo = MagicMock()
    facturas_repo.buscar_por_venta_id.return_value = factura
    clientes_repo = MagicMock()
    clientes_repo.buscar_por_id.return_value = cliente
    servicios_repo = MagicMock()
    servicios_repo.buscar_por_id.return_value = servicio
    return ventas_repo, facturas_repo, clientes_repo, servicios_repo


def _make_service(
    *,
    ventas_repo: MagicMock,
    facturas_repo: MagicMock,
    clientes_repo: MagicMock,
    servicios_repo: MagicMock,
    html: str = "<html>regenerado</html>",
    email_raises: Exception | None = None,
) -> tuple[RegenerarFacturaService, MagicMock, MagicMock]:
    generador = MagicMock()
    generador.generar.return_value = html
    email = MagicMock()
    if email_raises is not None:
        email.enviar.side_effect = email_raises
    svc = RegenerarFacturaService(
        ventas=ventas_repo,
        clientes=clientes_repo,
        servicios=servicios_repo,
        facturas=facturas_repo,
        generador=generador,
        email=email,
    )
    return svc, generador, email


# ---------------------------------------------------------------------------
# ResultadoRegenerarFactura enum
# ---------------------------------------------------------------------------


class TestResultadoEnum:
    def test_enum_values_exist(self) -> None:
        assert ResultadoRegenerarFactura.SIN_VENTA
        assert ResultadoRegenerarFactura.SIN_FACTURA
        assert ResultadoRegenerarFactura.REENVIADA
        assert ResultadoRegenerarFactura.ERROR_ENVIO


# ---------------------------------------------------------------------------
# reconstruir_contexto
# ---------------------------------------------------------------------------


class TestReconstruirContexto:
    def test_cliente_fields_copied(self) -> None:
        cliente = _make_cliente()
        servicio = _make_servicio(numero=1, nombre="Tour Isla")
        venta = _make_venta(
            cliente_id=cliente.id,
            servicio_ids=[servicio.id],
            fechas_por_servicio=None,
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.cliente_nombre == "Ana Garcia"
        assert ctx.cliente_email == "ana@example.com"
        assert ctx.cliente_telefono == "+57300"
        assert ctx.cliente_hotel == "Hotel Sol"
        assert ctx.cliente_habitacion == "101"
        assert ctx.cliente_identificacion == "123456"
        assert ctx.cliente_tipo_identificacion == "CC"

    def test_sin_hotel_always_false(self) -> None:
        """sin_hotel must be set to False regardless of client data (accepted limitation)."""
        cliente = _make_cliente(hotel=None)
        servicio = _make_servicio()
        venta = _make_venta(servicio_ids=[servicio.id], fechas_por_servicio=None)
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.sin_hotel is False

    def test_valor_and_abono_carried(self) -> None:
        cliente = _make_cliente()
        servicio = _make_servicio()
        venta = _make_venta(
            valor=Decimal("600000"),
            abono=Decimal("150000"),
            servicio_ids=[servicio.id],
            fechas_por_servicio=None,
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.valor == Decimal("600000")
        assert ctx.abono == Decimal("150000")

    def test_adultos_ninos_carried(self) -> None:
        cliente = _make_cliente()
        servicio = _make_servicio()
        venta = _make_venta(adultos=3, ninos=2, servicio_ids=[servicio.id])
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.adultos == 3
        assert ctx.ninos == 2

    def test_destinos_from_servicio_lookup(self) -> None:
        """destinos_numeros and destinos_nombres are built from servicio lookups."""
        cliente = _make_cliente()
        sid = uuid.uuid4()
        servicio = _make_servicio(numero=5, nombre="Bahía Rumbera")
        venta = _make_venta(servicio_ids=[sid], fechas_por_servicio=None)
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.destinos_numeros == [5]
        assert ctx.destinos_nombres == ["Bahía Rumbera"]

    def test_missing_servicio_falls_back_to_placeholder(self) -> None:
        """When buscar_por_id returns None, use str(sid) as name and 0 as numero."""
        cliente = _make_cliente()
        sid = uuid.uuid4()
        venta = _make_venta(servicio_ids=[sid], fechas_por_servicio=None)
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = None  # simulates missing servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert len(ctx.destinos_numeros) == 1
        assert len(ctx.destinos_nombres) == 1
        assert ctx.destinos_nombres[0] == "?"

    def test_fechas_por_servicio_uuid_to_int(self) -> None:
        """venta.fechas_por_servicio {uuid: dt} must be remapped to {servicio.numero: dt}."""
        cliente = _make_cliente()
        sid = uuid.uuid4()
        dt = datetime.datetime(2026, 9, 20, 10, 30)
        servicio = _make_servicio(numero=3, nombre="City Tour")
        venta = _make_venta(
            servicio_ids=[sid],
            fechas_por_servicio={sid: dt},
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.fechas_por_servicio == {3: dt}

    def test_fechas_por_servicio_none_gives_empty_dict(self) -> None:
        """When venta.fechas_por_servicio is None, ctx.fechas_por_servicio must be {}."""
        cliente = _make_cliente()
        servicio = _make_servicio()
        venta = _make_venta(servicio_ids=[servicio.id], fechas_por_servicio=None)
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.fechas_por_servicio == {}

    def test_fecha_salida_from_venta_fecha_when_no_fechas_por_servicio(self) -> None:
        """When fechas_por_servicio is None, fecha_salida is midnight of venta.fecha."""
        cliente = _make_cliente()
        servicio = _make_servicio()
        fecha = datetime.date(2026, 9, 25)
        venta = _make_venta(
            fecha=fecha,
            servicio_ids=[servicio.id],
            fechas_por_servicio=None,
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.fecha_salida == datetime.datetime.combine(fecha, datetime.time.min)

    def test_fecha_salida_is_min_of_fechas_por_servicio(self) -> None:
        """When fechas_por_servicio is present, fecha_salida = min datetime value."""
        cliente = _make_cliente()
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()
        dt_early = datetime.datetime(2026, 9, 20, 8, 0)
        dt_late = datetime.datetime(2026, 9, 20, 19, 0)
        s1 = _make_servicio(numero=1, nombre="Tour A")
        s2 = _make_servicio(numero=2, nombre="Tour B")
        venta = _make_venta(
            servicio_ids=[sid1, sid2],
            fechas_por_servicio={sid1: dt_early, sid2: dt_late},
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.side_effect = lambda sid: s1 if sid == sid1 else s2

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)

        assert ctx.fecha_salida == dt_early

    def test_html_contains_new_date_after_reconstruction(self) -> None:
        """Integration: regenerated HTML must contain the new venta.fecha."""
        from garay.aplicacion.factura.servicio import GenerarFacturaService

        cliente = _make_cliente()
        sid = uuid.uuid4()
        nueva_fecha = datetime.date(2026, 10, 15)
        servicio = _make_servicio(numero=1, nombre="Tour Isla")
        venta = _make_venta(
            servicio_ids=[sid],
            fechas_por_servicio={sid: datetime.datetime(2026, 10, 15, 9, 0)},
            fecha=nueva_fecha,
        )
        servicios_repo = MagicMock()
        servicios_repo.buscar_por_id.return_value = servicio

        ctx = reconstruir_contexto(venta, cliente, servicios_repo)
        html = GenerarFacturaService().generar(ctx, venta.id)

        assert "15/10/2026" in html


# ---------------------------------------------------------------------------
# RegenerarFacturaService.ejecutar
# ---------------------------------------------------------------------------


class TestRegenerarFacturaService:
    def test_sin_venta_retorna_sin_venta(self) -> None:
        venta_id = uuid.uuid4()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(venta=None)
        svc, _, _ = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
        )

        resultado = svc.ejecutar(venta_id)

        assert resultado is ResultadoRegenerarFactura.SIN_VENTA
        facturas_repo.buscar_por_venta_id.assert_not_called()

    def test_sin_factura_retorna_sin_factura_y_no_envia(self) -> None:
        """When buscar_por_venta_id → None, return SIN_FACTURA, no email, no save."""
        venta = _make_venta()
        cliente = _make_cliente()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=None,
            cliente=cliente,
        )
        svc, _, email = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
        )

        resultado = svc.ejecutar(venta.id)

        assert resultado is ResultadoRegenerarFactura.SIN_FACTURA
        email.enviar.assert_not_called()
        facturas_repo.guardar.assert_not_called()

    def test_reenviada_on_success(self) -> None:
        """Happy path: factura regenerated, saved, email sent, returns REENVIADA."""
        venta_id = uuid.uuid4()
        venta = _make_venta()
        cliente = _make_cliente()
        factura = _make_factura(venta_id=venta_id)
        servicio = _make_servicio()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=factura,
            cliente=cliente,
            servicio=servicio,
        )
        svc, _, email = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
            html="<html>nuevo</html>",
        )

        resultado = svc.ejecutar(venta.id)

        assert resultado is ResultadoRegenerarFactura.REENVIADA
        email.enviar.assert_called_once()
        # Verify the html was updated on the factura (via guardar)
        assert facturas_repo.guardar.called
        last_factura: Factura = facturas_repo.guardar.call_args_list[-1].args[0]
        assert last_factura.estado_envio is EstadoEnvioFactura.ENVIADO
        assert last_factura.html_contenido == "<html>nuevo</html>"

    def test_reenviada_email_sent_to_factura_email(self) -> None:
        """Email is sent to factura.cliente_email."""
        venta = _make_venta()
        cliente = _make_cliente(email="otro@example.com")
        factura = _make_factura()
        # factura.cliente_email is "ana@example.com"
        servicio = _make_servicio()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=factura,
            cliente=cliente,
            servicio=servicio,
        )
        svc, _, email = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
        )

        svc.ejecutar(venta.id)

        dest = email.enviar.call_args.args[0]
        assert dest == "ana@example.com"

    def test_error_envio_on_email_exception(self) -> None:
        """When email.enviar raises, return ERROR_ENVIO and save estado ERROR."""
        venta = _make_venta()
        cliente = _make_cliente()
        factura = _make_factura()
        servicio = _make_servicio()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=factura,
            cliente=cliente,
            servicio=servicio,
        )
        svc, _, _ = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
            email_raises=RuntimeError("smtp down"),
        )

        resultado = svc.ejecutar(venta.id)

        assert resultado is ResultadoRegenerarFactura.ERROR_ENVIO
        last_factura: Factura = facturas_repo.guardar.call_args_list[-1].args[0]
        assert last_factura.estado_envio is EstadoEnvioFactura.ERROR

    def test_sin_cliente_retorna_sin_factura(self) -> None:
        """Defensive: if cliente lookup returns None (data inconsistency), return SIN_FACTURA."""
        venta = _make_venta()
        factura = _make_factura()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=factura,
            cliente=None,
        )
        svc, _, email = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
        )

        resultado = svc.ejecutar(venta.id)

        assert resultado is ResultadoRegenerarFactura.SIN_FACTURA
        email.enviar.assert_not_called()

    def test_factura_numero_and_id_preserved(self) -> None:
        """Keep factura.id, numero, fecha_emision — only html/montos/estado change."""
        original_id = uuid.uuid4()
        original_fecha = datetime.date(2026, 8, 1)
        factura = Factura(
            id=original_id,
            numero="GT-ORIGINAL",
            venta_id=uuid.uuid4(),
            cliente_email="ana@example.com",
            monto_total=Dinero("300000"),
            fecha_emision=original_fecha,
            html_contenido="<html>old</html>",
            estado_envio=EstadoEnvioFactura.ERROR,
        )
        venta = _make_venta(valor=Decimal("500000"))
        cliente = _make_cliente()
        servicio = _make_servicio()
        ventas_repo, facturas_repo, clientes_repo, servicios_repo = _make_repos(
            venta=venta,
            factura=factura,
            cliente=cliente,
            servicio=servicio,
        )
        svc, _, _ = _make_service(
            ventas_repo=ventas_repo,
            facturas_repo=facturas_repo,
            clientes_repo=clientes_repo,
            servicios_repo=servicios_repo,
        )

        svc.ejecutar(venta.id)

        last_factura: Factura = facturas_repo.guardar.call_args_list[-1].args[0]
        assert last_factura.id == original_id
        assert last_factura.numero == "GT-ORIGINAL"
        assert last_factura.fecha_emision == original_fecha
