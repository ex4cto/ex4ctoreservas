"""Tests for GenerarYGuardarFacturaService — persist-then-send flow, TDD RED phase."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.factura.generar_y_guardar import GenerarYGuardarFacturaService
from garay.aplicacion.tiquetera.comandos import ResultadoRegistrarVenta
from garay.dominio.comisiones.snapshot import SnapshotReglas
from garay.dominio.comisiones.valor_objetos import DesgloseComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.facturas.entidades import Factura
from garay.dominio.facturas.tipos import EstadoEnvioFactura
from garay.dominio.ventas.contexto import ContextoVenta

_CERO = Dinero(Decimal("0"), "COP")
_SNAPSHOT = SnapshotReglas(
    tipo_cliente=TipoCliente.EXTERNO,
    porcentaje_vendedor=Decimal("0"),
    porcentaje_cerrador=Decimal("0"),
    porcentaje_referido_maximo=Decimal("0"),
    porcentaje_capa_punto=Decimal("0"),
)


def _resultado(venta_id: uuid.UUID | None = None) -> ResultadoRegistrarVenta:
    return ResultadoRegistrarVenta(
        venta_id=venta_id or uuid.uuid4(),
        desglose=DesgloseComision(
            vendedor=_CERO,
            cerrador=_CERO,
            punto_de_venta=_CERO,
            referido=_CERO,
            agencia=_CERO,
            snapshot=_SNAPSHOT,
        ),
    )


def _ctx(
    *,
    email: str | None = "juan@example.com",
    valor: Decimal | None = Decimal("500000"),
) -> ContextoVenta:
    ctx = ContextoVenta()
    ctx.cliente_nombre = "Juan Perez"
    ctx.cliente_email = email
    ctx.valor = valor
    ctx.abono = Decimal("100000")
    return ctx


def _generador_mock(html: str = "<html>factura</html>") -> MagicMock:
    gen = MagicMock()
    gen.generar.return_value = html
    return gen


def test_happy_envia_y_persiste_enviado() -> None:
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
    )

    servicio.ejecutar(_ctx(), _resultado())

    notificador.enviar.assert_called_once()
    # Se persiste al menos dos veces: PENDIENTE primero, ENVIADO despues.
    assert facturas.guardar.call_count >= 2
    final = facturas.guardar.call_args_list[-1].args[0]
    assert isinstance(final, Factura)
    assert final.estado_envio is EstadoEnvioFactura.ENVIADO
    assert final.monto_total == Dinero("500000")
    assert final.abono == Dinero("100000")


def test_notificador_lanza_persiste_error() -> None:
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    notificador.enviar.side_effect = RuntimeError("smtp down")
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
    )

    # No debe re-lanzar (comportamiento lenient).
    servicio.ejecutar(_ctx(), _resultado())

    final = facturas.guardar.call_args_list[-1].args[0]
    assert final.estado_envio is EstadoEnvioFactura.ERROR


def test_notificador_none_persiste_sin_email() -> None:
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=None,
    )

    servicio.ejecutar(_ctx(), _resultado())

    final = facturas.guardar.call_args_list[-1].args[0]
    assert final.estado_envio is EstadoEnvioFactura.SIN_EMAIL


def test_idempotente_enviado_no_regenera_ni_reenvia() -> None:
    venta_id = uuid.uuid4()
    existente = Factura(
        id=uuid.uuid4(),
        numero="GT-EXISTENTE",
        venta_id=venta_id,
        cliente_email="juan@example.com",
        monto_total=Dinero("500000"),
        fecha_emision=datetime.date(2026, 7, 15),
        html_contenido="<html></html>",
        estado_envio=EstadoEnvioFactura.ENVIADO,
    )
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = existente
    generador = _generador_mock()
    notificador = MagicMock()
    servicio = GenerarYGuardarFacturaService(
        generador=generador,
        facturas=facturas,
        notificador=notificador,
    )

    servicio.ejecutar(_ctx(), _resultado(venta_id=venta_id))

    generador.generar.assert_not_called()
    notificador.enviar.assert_not_called()
    facturas.guardar.assert_not_called()


def test_reintento_error_reusa_documento_original_y_reenvia() -> None:
    venta_id = uuid.uuid4()
    id_existente = uuid.uuid4()
    existente = Factura(
        id=id_existente,
        numero="GT-EXISTENTE",
        venta_id=venta_id,
        cliente_email="juan@example.com",
        monto_total=Dinero("500000"),
        fecha_emision=datetime.date(2026, 7, 15),
        html_contenido="<html>original</html>",
        estado_envio=EstadoEnvioFactura.ERROR,
    )
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = existente
    notificador = MagicMock()
    generador = _generador_mock(html="<html>REGENERADO</html>")
    servicio = GenerarYGuardarFacturaService(
        generador=generador,
        facturas=facturas,
        notificador=notificador,
    )

    servicio.ejecutar(_ctx(), _resultado(venta_id=venta_id))

    # Un reintento reenvia el MISMO documento: no se regenera nada y la identidad
    # legal (numero, fecha, html) se preserva intacta.
    generador.generar.assert_not_called()
    notificador.enviar.assert_called_once()
    assert notificador.enviar.call_args.args[2] == "<html>original</html>"
    final = facturas.guardar.call_args_list[-1].args[0]
    assert final.id == id_existente
    assert final.numero == "GT-EXISTENTE"
    assert final.fecha_emision == datetime.date(2026, 7, 15)
    assert final.html_contenido == "<html>original</html>"
    assert final.estado_envio is EstadoEnvioFactura.ENVIADO


def test_sin_email_es_no_op() -> None:
    facturas = MagicMock()
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=MagicMock(),
    )

    servicio.ejecutar(_ctx(email=None), _resultado())

    facturas.buscar_por_venta_id.assert_not_called()
    facturas.guardar.assert_not_called()


def test_valor_none_es_no_op() -> None:
    facturas = MagicMock()
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=MagicMock(),
    )

    servicio.ejecutar(_ctx(valor=None), _resultado())

    facturas.buscar_por_venta_id.assert_not_called()
    facturas.guardar.assert_not_called()


# --- copia oculta (BCC) al cerrador -----------------------------------------


def _ctx_con_cerrador(cerrador_id: uuid.UUID, email: str = "juan@example.com") -> ContextoVenta:
    ctx = _ctx(email=email)
    ctx.cerrador_id = cerrador_id
    return ctx


def _freelancer(cid: uuid.UUID, email: str | None) -> object:
    from garay.dominio.freelancers.entidades import Freelancer

    return Freelancer(id=cid, nombre="Cerrador", email=email)


def test_bcc_al_cerrador_cuando_tiene_email() -> None:
    cid = uuid.uuid4()
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    freelancers = MagicMock()
    freelancers.buscar_por_id.return_value = _freelancer(cid, "cerrador@garay.com")
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
        freelancers=freelancers,
    )

    servicio.ejecutar(_ctx_con_cerrador(cid), _resultado())

    freelancers.buscar_por_id.assert_called_once_with(cid)
    assert notificador.enviar.call_args.kwargs["bcc"] == "cerrador@garay.com"


def test_sin_repo_freelancers_no_bcc() -> None:
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
    )

    servicio.ejecutar(_ctx_con_cerrador(uuid.uuid4()), _resultado())

    assert notificador.enviar.call_args.kwargs["bcc"] is None


def test_cerrador_sin_email_no_bcc() -> None:
    cid = uuid.uuid4()
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    freelancers = MagicMock()
    freelancers.buscar_por_id.return_value = _freelancer(cid, None)
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
        freelancers=freelancers,
    )

    servicio.ejecutar(_ctx_con_cerrador(cid), _resultado())

    assert notificador.enviar.call_args.kwargs["bcc"] is None


def test_cerrador_email_igual_cliente_no_bcc() -> None:
    cid = uuid.uuid4()
    facturas = MagicMock()
    facturas.buscar_por_venta_id.return_value = None
    notificador = MagicMock()
    freelancers = MagicMock()
    freelancers.buscar_por_id.return_value = _freelancer(cid, "juan@example.com")
    servicio = GenerarYGuardarFacturaService(
        generador=_generador_mock(),
        facturas=facturas,
        notificador=notificador,
        freelancers=freelancers,
    )

    servicio.ejecutar(_ctx_con_cerrador(cid, email="juan@example.com"), _resultado())

    assert notificador.enviar.call_args.kwargs["bcc"] is None
