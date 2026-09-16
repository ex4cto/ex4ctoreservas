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
from garay.dominio.socios.entidades import SocioConfig
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
    socios_config: MagicMock | None = None,
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
        socios_config=socios_config or MagicMock(),
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
    cliente_email: str | None = None,
    servicio_nombres: list[str] | None = None,
    hotel: str | None = None,
    habitacion: str | None = None,
    abono: Dinero | None = None,
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
        cliente_email=cliente_email,
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
        reglas_repo.buscar_regla.return_value = None

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

    def test_mensaje_contiene_agencia_garay_tours_despues_del_titulo(self) -> None:
        """Group notification must show 'Agencia Garay Tours' on the second line."""
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd())
        mensaje = notificador.notificar.call_args.args[0]
        lineas = mensaje.splitlines()
        assert any("Nueva venta registrada" in linea for linea in lineas), "title line missing"
        titulo_idx = next(i for i, linea in enumerate(lineas) if "Nueva venta registrada" in linea)
        assert titulo_idx + 1 < len(lineas), "no line after title"
        assert lineas[titulo_idx + 1] == "Agencia Garay Tours"

    def test_agencia_titulo_seguido_de_linea_en_blanco(self) -> None:
        """After 'Agencia Garay Tours' there must be a blank separator line."""
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(servicio_nombres=["Isla Barú"]))
        mensaje = notificador.notificar.call_args.args[0]
        lineas = mensaje.splitlines()
        agencia_idx = next(i for i, linea in enumerate(lineas) if linea == "Agencia Garay Tours")
        assert agencia_idx + 1 < len(lineas), "no line after agency title"
        assert lineas[agencia_idx + 1] == "", "expected blank separator after agency title"

    def test_mensaje_muestra_saldo_pendiente_no_neto(self) -> None:
        """Group message shows saldo pendiente (valor - abono), never the internal neto."""
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(abono=Dinero(400_000)))
        mensaje = notificador.notificar.call_args.args[0]
        # valor 1.000.000 - abono 400.000 = 600.000
        assert "Saldo pendiente: $600.000" in mensaje
        assert "Neto" not in mensaje

    def test_saldo_pendiente_sin_abono_es_el_valor_total(self) -> None:
        """With no abono, saldo pendiente equals the full sale value."""
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd())
        mensaje = notificador.notificar.call_args.args[0]
        assert "Saldo pendiente: $1.000.000" in mensaje

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

    def test_venta_se_registra_aunque_falle_la_notificacion(self) -> None:
        """Best-effort: si la notificación al grupo falla, la venta igual se registra
        (no se lanza excepción; el registro ya se commiteó antes de notificar)."""
        from garay.infraestructura.telegram.errores import NotificadorError

        service, notificador = self._capturar_mensaje()
        notificador.notificar.side_effect = NotificadorError("grupo caído")

        resultado = service.ejecutar(_cmd())  # NO debe lanzar

        assert resultado.venta_id is not None

    def test_mensaje_escapa_html_en_valores_dinamicos(self) -> None:
        """El mensaje va con parse_mode=HTML: los valores dinámicos deben ir
        escapados para que un '&'/'<'/'>' en cliente/destino/nombre no rompa el
        parser HTML de Telegram (causaría HTTP 400 y fallaría la venta)."""
        service, notificador = self._capturar_mensaje()
        service.ejecutar(
            _cmd(
                cliente_nombre="Juan & Ana",
                servicio_nombres=["Isla <Barú>"],
                vendedor_nombre="A & B",
            )
        )
        mensaje = notificador.notificar.call_args.args[0]
        assert "Juan &amp; Ana" in mensaje
        assert "Isla &lt;Barú&gt;" in mensaje
        assert "A &amp; B" in mensaje
        # Ningún valor especial provisto por el usuario se filtra sin escapar:
        assert "Juan & Ana" not in mensaje
        assert "Isla <Barú>" not in mensaje

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

    def test_mensaje_contiene_correo_si_presente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(cliente_email="juan@example.com"))
        mensaje = notificador.notificar.call_args.args[0]
        assert "juan@example.com" in mensaje

    def test_mensaje_omite_correo_si_ausente(self) -> None:
        service, notificador = self._capturar_mensaje()
        service.ejecutar(_cmd(cliente_email=None))
        mensaje = notificador.notificar.call_args.args[0]
        assert "Correo" not in mensaje

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


# ---------------------------------------------------------------------------
# WU-9: _derivar_numero_personas unit tests
# ---------------------------------------------------------------------------

class TestDerivarNumeroPersonas:
    """Unit tests for _derivar_numero_personas helper (design S2)."""

    def _fn(self, vendedor_id: uuid.UUID | None, cerrador_id: uuid.UUID | None) -> int | None:
        from garay.aplicacion.tiquetera.servicio import _derivar_numero_personas

        p = Participantes(vendedor_id=vendedor_id, cerrador_id=cerrador_id)
        return _derivar_numero_personas(p)

    def test_same_person_returns_1(self) -> None:
        """(A, A) → 1: same vendedor and cerrador."""
        uid = uuid.uuid4()
        assert self._fn(uid, uid) == 1

    def test_different_persons_returns_2(self) -> None:
        """(A, B) → 2: distinct vendedor and cerrador."""
        assert self._fn(uuid.uuid4(), uuid.uuid4()) == 2

    def test_both_none_returns_none(self) -> None:
        """(None, None) → None: no ids present, cannot determine count."""
        assert self._fn(None, None) is None

    def test_vendedor_none_cerrador_present_returns_none(self) -> None:
        """(None, B) → None: only cerrador present — cannot determine count (design S2)."""
        # Per design S2: returns None if EITHER id is None.
        assert self._fn(None, uuid.uuid4()) is None

    def test_vendedor_present_cerrador_none_returns_none(self) -> None:
        """(A, None) → None: only vendedor present, returns None."""
        assert self._fn(uuid.uuid4(), None) is None


# ---------------------------------------------------------------------------
# WU-9: service reorder + buscar_regla integration tests
# ---------------------------------------------------------------------------

def _cmd_with_participantes(
    *,
    vendedor_id: uuid.UUID | None = None,
    cerrador_id: uuid.UUID | None = None,
    punto_de_venta_id: uuid.UUID | None = None,
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
) -> RegistrarVentaComando:
    return RegistrarVentaComando(
        valor_venta=_VALOR_VENTA,
        neto=_NETO,
        servicio_ids=[_SERVICIO_ID],
        cliente_id=_CLIENTE_ID,
        tipo_cliente=tipo_cliente,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_nombre="Ana",
            cerrador_nombre="Ana",
            punto_de_venta_id=punto_de_venta_id,
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
        ),
        adultos=2,
        ninos=0,
        porcentaje_referido=Decimal("0"),
        servicio_nombres=[],
    )


class TestServiceUsasBuscarRegla:
    """WU-9: service must call buscar_regla (not buscar_por_tipo_cliente)."""

    def test_service_calls_buscar_regla_not_buscar_por_tipo_cliente(self) -> None:
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(reglas_repo=reglas_repo, motor=motor)
        cmd = _cmd()

        service.ejecutar(cmd)

        reglas_repo.buscar_regla.assert_called_once()
        reglas_repo.buscar_por_tipo_cliente.assert_not_called()

    def test_service_resolves_punto_before_buscar_regla(self) -> None:
        """punto must be resolved before buscar_regla is called (design S1 ordering)."""
        punto_id = uuid.uuid4()
        fake_punto = MagicMock()
        fake_punto.nombre = "OtroLugar"
        puntos_repo = MagicMock()
        puntos_repo.buscar_por_id.return_value = fake_punto
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        call_order: list[str] = []

        def track_punto(*args: object, **kwargs: object) -> object:
            call_order.append("punto")
            return fake_punto

        def track_regla(*args: object, **kwargs: object) -> object:
            call_order.append("regla")
            return MagicMock()

        puntos_repo.buscar_por_id.side_effect = track_punto
        reglas_repo.buscar_regla.side_effect = track_regla

        service = _build_service(
            puntos_repo=puntos_repo, reglas_repo=reglas_repo, motor=motor
        )
        cmd = _cmd_with_participantes(punto_de_venta_id=punto_id)
        service.ejecutar(cmd)

        assert call_order.index("punto") < call_order.index("regla")

    def test_service_fail_fast_when_crespo_rule_absent(self) -> None:
        """S3: if buscar_regla returns None, raise ReglasComisionNoEncontradas."""
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = None

        service = _build_service(reglas_repo=reglas_repo)
        cmd = _cmd()

        with pytest.raises(ReglasComisionNoEncontradas):
            service.ejecutar(cmd)

    def test_service_passes_correct_args_to_buscar_regla_non_crespo(self) -> None:
        """For non-Crespo sale: buscar_regla(tipo, None, None)."""
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()
        puntos_repo = MagicMock()
        puntos_repo.buscar_por_id.return_value = None

        service = _build_service(
            reglas_repo=reglas_repo, motor=motor, puntos_repo=puntos_repo
        )
        cmd = _cmd_with_participantes(tipo_cliente=TipoCliente.INTERNO)
        service.ejecutar(cmd)

        call = reglas_repo.buscar_regla.call_args
        assert call.args[0] == TipoCliente.INTERNO
        assert call.args[1] is None
        assert call.args[2] is None

    def test_service_passes_crespo_punto_and_numero_personas_to_buscar_regla(
        self,
    ) -> None:
        """For Crespo 1-person sale: buscar_regla(tipo, 'Crespo', 1)."""
        punto_id = uuid.uuid4()
        fake_punto = MagicMock()
        fake_punto.nombre = "Crespo"
        puntos_repo = MagicMock()
        puntos_repo.buscar_por_id.return_value = fake_punto
        reglas_repo = MagicMock()
        reglas_repo.buscar_regla.return_value = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        uid = uuid.uuid4()
        service = _build_service(
            puntos_repo=puntos_repo, reglas_repo=reglas_repo, motor=motor
        )
        cmd = _cmd_with_participantes(
            punto_de_venta_id=punto_id,
            vendedor_id=uid,
            cerrador_id=uid,  # same person → 1
            tipo_cliente=TipoCliente.EXTERNO,
        )
        service.ejecutar(cmd)

        call = reglas_repo.buscar_regla.call_args
        assert call.args[0] == TipoCliente.EXTERNO
        assert call.args[1] == "Crespo"
        assert call.args[2] == 1

    def test_non_crespo_punto_with_two_participants_uses_global_rule(self) -> None:
        """CRITICAL-1 (REQ-08b): a non-Crespo punto with both vendedor_id and
        cerrador_id set (distinct) must resolve the global EXTERNO rule and NOT
        raise ReglasComisionNoEncontradas.

        Before the Crespo gate fix, the service passed punto_nombre='Marie Real'
        and numero_personas=2 unconditionally, causing buscar_regla to attempt a
        point-specific step-1 lookup that found nothing and returned None — which
        then raised ReglasComisionNoEncontradas, breaking every non-Crespo sale
        at a named punto when both participant IDs were identified.
        """
        punto_id = uuid.uuid4()
        fake_punto = MagicMock()
        fake_punto.nombre = "Marie Real"  # non-Crespo punto
        puntos_repo = MagicMock()
        puntos_repo.buscar_por_id.return_value = fake_punto

        reglas_repo = MagicMock()
        # Simulate global EXTERNO rule being available
        reglas_repo.buscar_regla.return_value = MagicMock()
        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(
            puntos_repo=puntos_repo, reglas_repo=reglas_repo, motor=motor
        )
        # Both vendedor_id and cerrador_id set and distinct — 2 participants
        cmd = _cmd_with_participantes(
            punto_de_venta_id=punto_id,
            vendedor_id=uuid.uuid4(),
            cerrador_id=uuid.uuid4(),
            tipo_cliente=TipoCliente.EXTERNO,
        )

        # Must NOT raise — should succeed using the global EXTERNO rule
        service.ejecutar(cmd)

        # Service must call buscar_regla with (EXTERNO, None, None) — global lookup
        call = reglas_repo.buscar_regla.call_args
        assert call.args[0] == TipoCliente.EXTERNO
        assert call.args[1] is None  # no point-specific lookup for non-Crespo
        assert call.args[2] is None


# ---------------------------------------------------------------------------
# E3: private split DM to socios with telegram_id
# ---------------------------------------------------------------------------

_AGENCIA = Dinero(150_000)


def _make_socio(nombre: str, porcentaje: Decimal, telegram_id: int | None) -> SocioConfig:
    return SocioConfig(nombre=nombre, porcentaje=porcentaje, telegram_id=telegram_id)


def _build_service_con_socios(
    socios: list[SocioConfig],
    notificador: MagicMock,
) -> RegistrarVentaService:
    """Helper: service with a real-looking desglose.agencia = _AGENCIA."""
    motor = MagicMock()
    fake_desglose = MagicMock()
    fake_desglose.agencia = _AGENCIA
    motor.calcular.return_value = fake_desglose

    socios_config = MagicMock()
    socios_config.listar.return_value = socios

    return _build_service(motor=motor, notificador=notificador, socios_config=socios_config)


class TestMensajePrivadoSocios:
    """E3: send private split DM to each socio that has telegram_id configured."""

    def test_envia_dm_a_socio_con_telegram_id(self) -> None:
        """When a socio has telegram_id, notificador.notificar is called with that chat_id."""
        notificador = MagicMock()
        socios = [
            _make_socio("garay", Decimal("75"), 111111),
            _make_socio("ryan", Decimal("25"), 222222),
        ]
        service = _build_service_con_socios(socios, notificador)
        service.ejecutar(_cmd())

        # notificador called: 1x grupo + 2x socios
        assert notificador.notificar.call_count == 3
        chat_ids = [call.args[1] for call in notificador.notificar.call_args_list]
        assert "111111" in chat_ids
        assert "222222" in chat_ids

    def test_no_envia_dm_a_socio_sin_telegram_id(self) -> None:
        """A socio with telegram_id=None does not receive a DM."""
        notificador = MagicMock()
        socios = [
            _make_socio("empresa", Decimal("50"), None),  # no DM
            _make_socio("ryan", Decimal("50"), 333333),
        ]
        service = _build_service_con_socios(socios, notificador)
        service.ejecutar(_cmd())

        # 1x grupo + 1x ryan only
        assert notificador.notificar.call_count == 2
        chat_ids = [call.args[1] for call in notificador.notificar.call_args_list]
        assert "333333" in chat_ids
        assert _GRUPO_ID in chat_ids

    def test_fallo_dm_no_tumba_venta(self) -> None:
        """If the DM send fails, the sale is already registered — service returns OK."""
        from garay.infraestructura.telegram.errores import NotificadorError

        notificador = MagicMock()
        notificador.notificar.side_effect = NotificadorError("DM fallido")

        socios = [_make_socio("ryan", Decimal("100"), 999999)]
        service = _build_service_con_socios(socios, notificador)

        resultado = service.ejecutar(_cmd())  # must NOT raise

        assert resultado.venta_id is not None

    def test_sin_socios_configurados_no_envia_dm(self) -> None:
        """If socios_config.listar() returns [], no extra notificar calls are made."""
        notificador = MagicMock()
        socios_config = MagicMock()
        socios_config.listar.return_value = []

        motor = MagicMock()
        motor.calcular.return_value = MagicMock()

        service = _build_service(motor=motor, notificador=notificador, socios_config=socios_config)
        service.ejecutar(_cmd())

        # only the group notification
        assert notificador.notificar.call_count == 1
        assert notificador.notificar.call_args.args[1] == _GRUPO_ID

    def test_split_correcto_en_mensaje(self) -> None:
        """The DM amount reflects the socio's correct percentage of agencia."""
        notificador = MagicMock()
        # ryan gets 25% of 150.000 = 37.500
        socios = [
            _make_socio("garay", Decimal("75"), None),
            _make_socio("ryan", Decimal("25"), 444444),
        ]
        service = _build_service_con_socios(socios, notificador)
        service.ejecutar(_cmd(servicio_nombres=["Playa Blanca"]))

        ryan_calls = [
            c for c in notificador.notificar.call_args_list if c.args[1] == "444444"
        ]
        assert len(ryan_calls) == 1
        mensaje = ryan_calls[0].args[0]
        # 25% of 150.000 = 37.500
        assert "37.500" in mensaje
        # Must show the agencia total too
        assert "150.000" in mensaje

    def test_mensaje_privado_omite_destino_si_no_hay_servicios(self) -> None:
        """If servicio_nombres is empty, the 'Destino' line is omitted from the DM."""
        notificador = MagicMock()
        socios = [_make_socio("ryan", Decimal("100"), 555555)]
        service = _build_service_con_socios(socios, notificador)
        service.ejecutar(_cmd(servicio_nombres=[]))

        ryan_calls = [
            c for c in notificador.notificar.call_args_list if c.args[1] == "555555"
        ]
        assert len(ryan_calls) == 1
        assert "Destino" not in ryan_calls[0].args[0]

    def test_mensaje_privado_contiene_porcentaje_del_socio(self) -> None:
        """The DM message includes the socio's percentage."""
        notificador = MagicMock()
        socios = [_make_socio("ryan", Decimal("25"), 666666)]
        service = _build_service_con_socios(socios, notificador)
        service.ejecutar(_cmd())

        ryan_calls = [
            c for c in notificador.notificar.call_args_list if c.args[1] == "666666"
        ]
        assert len(ryan_calls) == 1
        assert "25" in ryan_calls[0].args[0]
