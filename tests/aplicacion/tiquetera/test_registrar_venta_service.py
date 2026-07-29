"""Tests for RegistrarVentaService — TDD suite."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando, ResultadoRegistrarVenta
from garay.aplicacion.tiquetera.errores import ReglasComisionNoEncontradas
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes

_GRUPO_ID = "grupo-test-123"

_VALOR_VENTA = Dinero(1_000_000)
_NETO = Dinero(900_000)
_SERVICIO_ID = uuid.uuid4()
_CLIENTE_ID = uuid.uuid4()
_FECHA = datetime.date(2026, 7, 1)


def _build_service(
    *,
    ventas: MagicMock | None = None,
    reglas_repo: MagicMock | None = None,
    tiqueteras: MagicMock | None = None,
    puntos_repo: MagicMock | None = None,
    motor: MagicMock | None = None,
    notificador: MagicMock | None = None,
    comisiones_repo: MagicMock | None = None,
) -> RegistrarVentaService:
    return RegistrarVentaService(
        ventas=ventas or MagicMock(),
        reglas_repo=reglas_repo or MagicMock(),
        tiqueteras=tiqueteras or MagicMock(),
        puntos_repo=puntos_repo or MagicMock(),
        motor=motor or MagicMock(),
        notificador=notificador or MagicMock(),
        grupo_id=_GRUPO_ID,
        comisiones_repo=comisiones_repo or MagicMock(),
    )


def _cmd(
    *,
    foto_referencia: str | None = None,
    porcentaje_referido: Decimal = Decimal("0"),
    punto_de_venta_id: uuid.UUID | None = None,
    vendedor_nombre: str | None = "Ana",
    cerrador_nombre: str | None = "Luis",
    cliente_nombre: str | None = None,
    cliente_telefono: str | None = None,
    servicio_nombres: list[str] | None = None,
    hotel: str | None = None,
    habitacion: str | None = None,
    abono: "Dinero | None" = None,
    adultos: int = 2,
    ninos: int = 0,
) -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=_VALOR_VENTA,
        neto=_NETO,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre=vendedor_nombre,
            cerrador_nombre=cerrador_nombre,
            punto_de_venta_id=punto_de_venta_id,
        ),
        adultos=adultos,
        ninos=ninos,
        foto_referencia=foto_referencia,
        porcentaje_referido=porcentaje_referido,
        abono=abono,
        cliente_nombre=cliente_nombre,
        cliente_telefono=cliente_telefono,
        servicio_nombres=servicio_nombres if servicio_nombres is not None else [],
        hotel=hotel,
        habitacion=habitacion,
    )


class TestRegistrarVentaInternaSinPuntoSinReferido:
    def test_registrar_venta_interna_sin_punto_sin_referido(self) -> None:
        ventas = MagicMock()
        reglas_repo = MagicMock()
        motor = MagicMock()
        notificador = MagicMock()
        fake_desglose = MagicMock()
        motor.calcular.return_value = fake_desglose

        service = _build_service(
            ventas=ventas,
            reglas_repo=reglas_repo,
            motor=motor,
            notificador=notificador,
        )
        cmd = _cmd()

        resultado = service.ejecutar(cmd)

        # repo.guardar was called once
        ventas.guardar.assert_called_once()
        # motor.calcular was called once with the fetched rules and no punto
        motor.calcular.assert_called_once()
        # notificador.notificar was called once
        notificador.notificar.assert_called_once()
        # resultado carries correct venta_id and desglose
        assert isinstance(resultado, ResultadoRegistrarVenta)
        assert resultado.desglose is fake_desglose
        assert isinstance(resultado.venta_id, uuid.UUID)


class TestRegistrarVentaConPuntoDeVenta:
    def test_registrar_venta_con_punto_de_venta(self) -> None:
        punto_id = uuid.uuid4()
        fake_punto = MagicMock()
        puntos_repo = MagicMock()
        puntos_repo.buscar_por_id.return_value = fake_punto
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(puntos_repo=puntos_repo, motor=motor)
        cmd = _cmd(punto_de_venta_id=punto_id)

        service.ejecutar(cmd)

        puntos_repo.buscar_por_id.assert_called_once_with(punto_id)
        # motor received the resolved punto object
        call_args = motor.calcular.call_args
        _, kwargs = call_args
        # punto may be positional or keyword — check both
        passed_punto = kwargs.get("punto") or call_args.args[2]
        assert passed_punto is fake_punto


class TestRegistrarVentaCreaRequeteraConFoto:
    def test_registrar_venta_crea_tiquetera_si_hay_foto(self) -> None:
        tiqueteras = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(tiqueteras=tiqueteras, motor=motor)
        cmd = _cmd(foto_referencia="ruta/foto.jpg")

        resultado = service.ejecutar(cmd)

        tiqueteras.guardar.assert_called_once()
        saved_tiquetera = tiqueteras.guardar.call_args.args[0]
        assert saved_tiquetera.venta_id == resultado.venta_id
        assert saved_tiquetera.foto_referencia == "ruta/foto.jpg"
        assert saved_tiquetera.procesada is False


class TestRegistrarVentaSinFotoNoCreaTiquetera:
    def test_registrar_venta_sin_foto_no_crea_tiquetera(self) -> None:
        tiqueteras = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(tiqueteras=tiqueteras, motor=motor)
        cmd = _cmd(foto_referencia=None)

        service.ejecutar(cmd)

        tiqueteras.guardar.assert_not_called()


class TestRegistrarVentaRaisesSimReglas:
    def test_registrar_venta_raises_si_no_hay_reglas(self) -> None:
        reglas_repo = MagicMock()
        reglas_repo.buscar_por_tipo_cliente.return_value = None

        service = _build_service(reglas_repo=reglas_repo)
        cmd = _cmd()

        with pytest.raises(ReglasComisionNoEncontradas):
            service.ejecutar(cmd)


class TestMensajeNotificacion:
    """WU-7: notification message format — no UUID, item-by-item."""

    def _capturar_mensaje(self) -> tuple[RegistrarVentaService, MagicMock]:
        notificador = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()
        service = _build_service(motor=motor, notificador=notificador)
        return service, notificador

    def test_mensaje_notificacion_sin_uuid(self) -> None:
        import re

        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(vendedor_nombre="Ana", cerrador_nombre="Luis"))
        mensaje = notificador.notificar.call_args.args[0]
        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        )
        assert not uuid_pattern.search(mensaje), f"UUID found in message: {mensaje!r}"

    def test_mensaje_notificacion_formato_item_por_item(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(vendedor_nombre="Ana", cerrador_nombre="Luis"))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Vendedor" in mensaje
        assert "Cerrador" in mensaje
        assert "Valor:" in mensaje

    def test_mensaje_contiene_cliente_nombre(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(cliente_nombre="María García"))
        mensaje = notificador.notificar.call_args.args[0]
        assert "María García" in mensaje

    def test_mensaje_contiene_destino(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(servicio_nombres=["Playa Blanca"]))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Playa Blanca" in mensaje

    def test_mensaje_contiene_telefono_si_presente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(cliente_telefono="3001234567"))
        mensaje = notificador.notificar.call_args.args[0]
        assert "3001234567" in mensaje

    def test_mensaje_omite_telefono_si_ausente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(cliente_telefono=None))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Teléfono" not in mensaje

    def test_mensaje_contiene_abono_si_presente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(abono=Dinero(200_000)))
        mensaje = notificador.notificar.call_args.args[0]
        assert "$200.000" in mensaje

    def test_mensaje_contiene_pax(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(adultos=2, ninos=0))
        mensaje = notificador.notificar.call_args.args[0]
        assert "2" in mensaje

    def test_mensaje_usa_html_no_markdown(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd())
        mensaje = notificador.notificar.call_args.args[0]
        assert "<b>" in mensaje
        assert "*" not in mensaje

    def test_mensaje_contiene_hotel_si_presente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(hotel="Dann Carlton"))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Dann Carlton" in mensaje

    def test_mensaje_omite_hotel_si_ausente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(hotel=None))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Hotel" not in mensaje


class TestRegistrarVentaPersistsComision:
    def test_comision_guardada_con_venta_id_correcto(self) -> None:
        comisiones_repo = MagicMock()
        motor = MagicMock()
        fake_desglose = MagicMock()
        motor.calcular.return_value = fake_desglose

        service = _build_service(motor=motor, comisiones_repo=comisiones_repo)
        cmd = _cmd()

        resultado = service.ejecutar(cmd)

        comisiones_repo.guardar.assert_called_once()
        saved = comisiones_repo.guardar.call_args.args[0]
        assert isinstance(saved, ComisionRegistrada)
        assert saved.venta_id == resultado.venta_id
