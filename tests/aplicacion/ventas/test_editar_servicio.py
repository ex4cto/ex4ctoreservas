"""Tests for EditarServicioVentaService — strict TDD."""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarServicioVentaComando
from garay.aplicacion.ventas.editar_servicio import EditarServicioVentaService
from garay.aplicacion.ventas.errores import (
    ServicioMultipleNoSoportado,
    ServicioNoEncontrado,
    ServicioSinPrecio,
)
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import MismoServicio, MotivoRequerido, VentaNoEncontrada

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DEFAULT_NETO = Dinero(100)
_DEFAULT_VALOR_VENTA = Dinero(300)


def _make_venta_mock(
    servicio_ids: list[uuid.UUID] | None = None,
    neto: Dinero | None = None,
    valor_venta: Dinero | None = None,
    anulada: bool = False,
    punto_de_venta_id: uuid.UUID | None = None,
) -> MagicMock:
    if servicio_ids is None:
        servicio_ids = [uuid.uuid4()]
    effective_neto = neto if neto is not None else _DEFAULT_NETO
    effective_valor = valor_venta if valor_venta is not None else _DEFAULT_VALOR_VENTA
    v = MagicMock()
    v.id = uuid.uuid4()
    v.servicio_ids = servicio_ids
    v.neto = effective_neto
    v.valor_venta = effective_valor
    v.anulada = anulada
    v.adultos = 2
    v.ninos = 0
    v.tipo_cliente = TipoCliente.EXTERNO
    v.fecha = datetime.date(2026, 9, 1)
    v.horarios_por_servicio = None
    participantes = MagicMock()
    participantes.punto_de_venta_id = punto_de_venta_id
    v.participantes = participantes
    return v


def _make_servicio_mock(
    precio_adulto: Decimal | None = Decimal("50"),
    activo: bool = True,
) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.nombre = "Tour de prueba"
    s.activo = activo
    s.precio_neto_adulto = precio_adulto
    s.precio_neto_nino = None
    s.netos_por_horario = {}
    # Make neto_para_horario return precio_adulto (no horario-specific override)
    s.neto_para_horario.return_value = precio_adulto
    return s


def _make_repos(
    venta: MagicMock | None = None,
    nuevo_servicio: MagicMock | None = None,
    punto: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return (ventas, auditoria, servicios, reglas_repo, puntos_repo, comisiones_repo)."""
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta

    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = []

    servicios_repo = MagicMock()
    servicios_repo.buscar_por_id.return_value = nuevo_servicio

    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()

    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = punto

    comisiones_repo = MagicMock()

    return ventas_repo, auditoria_repo, servicios_repo, reglas_repo, puntos_repo, comisiones_repo


def _make_motor() -> MagicMock:
    motor = MagicMock()
    motor.calcular.return_value = MagicMock()
    return motor


def _make_cmd(
    venta_id: uuid.UUID | None = None,
    nuevo_servicio_id: uuid.UUID | None = None,
    motivo: str = "Corrección de tour",
    nuevo_valor_venta: Dinero | None = None,
) -> EditarServicioVentaComando:
    return EditarServicioVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nuevo_servicio_id=nuevo_servicio_id or uuid.uuid4(),
        nuevo_valor_venta=nuevo_valor_venta,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


def _make_service(
    ventas: MagicMock,
    auditoria: MagicMock,
    servicios: MagicMock,
    reglas_repo: MagicMock,
    puntos_repo: MagicMock,
    comisiones_repo: MagicMock,
    motor: MagicMock | None = None,
) -> EditarServicioVentaService:
    return EditarServicioVentaService(
        ventas=ventas,
        auditoria=auditoria,
        servicios=servicios,
        reglas_repo=reglas_repo,
        puntos_repo=puntos_repo,
        comisiones_repo=comisiones_repo,
        motor=motor or _make_motor(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEditarServicioVentaService:
    def test_editar_servicio_motivo_vacio_lanza_error(self) -> None:
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos()
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(motivo="   "))
        ventas.guardar.assert_not_called()
        auditoria.guardar.assert_not_called()

    def test_editar_servicio_venta_no_encontrada_lanza_error(self) -> None:
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(venta=None)
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())
        ventas.guardar.assert_not_called()

    def test_editar_servicio_multi_tour_no_soportado(self) -> None:
        venta = _make_venta_mock(servicio_ids=[uuid.uuid4(), uuid.uuid4()])
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(venta=venta)
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(ServicioMultipleNoSoportado):
            service.ejecutar(_make_cmd(venta_id=venta.id))
        ventas.guardar.assert_not_called()

    def test_editar_servicio_servicio_no_encontrado(self) -> None:
        venta = _make_venta_mock()
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=None
        )
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(ServicioNoEncontrado):
            service.ejecutar(_make_cmd(venta_id=venta.id))
        ventas.guardar.assert_not_called()

    def test_editar_servicio_tour_sin_precio_lanza_error(self) -> None:
        venta = _make_venta_mock()
        nuevo_servicio = _make_servicio_mock(precio_adulto=None)
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=nuevo_servicio
        )
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(ServicioSinPrecio):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_servicio_id=nuevo_servicio.id))
        ventas.guardar.assert_not_called()

    def test_editar_servicio_mismo_tour_lanza_error(self) -> None:
        """When cambiar_servicio raises MismoServicio, the service propagates it."""
        sid = uuid.uuid4()
        venta = _make_venta_mock(servicio_ids=[sid])
        nuevo_servicio = _make_servicio_mock()
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=nuevo_servicio
        )
        # Simulate domain raising MismoServicio
        venta.cambiar_servicio.side_effect = MismoServicio("Mismo servicio.")
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        with pytest.raises(MismoServicio):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_servicio_id=sid))
        auditoria.guardar.assert_not_called()
        ventas.guardar.assert_not_called()

    def test_editar_servicio_exito_guarda_auditoria_venta_comisiones(self) -> None:
        venta = _make_venta_mock()
        nuevo_servicio = _make_servicio_mock()
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=nuevo_servicio
        )
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_servicio_id=nuevo_servicio.id))
        auditoria.guardar.assert_called_once()
        ventas.guardar.assert_called_once_with(venta)
        comisiones.guardar.assert_called_once()

    def test_editar_servicio_exito_con_nuevo_valor_venta(self) -> None:
        """When nuevo_valor_venta is provided in command, it is forwarded to cambiar_servicio."""
        venta = _make_venta_mock(valor_venta=Dinero(300), neto=Dinero(100))
        nuevo_servicio = _make_servicio_mock()
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=nuevo_servicio
        )
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        nuevo_valor = Dinero(250)
        service.ejecutar(
            _make_cmd(
                venta_id=venta.id,
                nuevo_servicio_id=nuevo_servicio.id,
                nuevo_valor_venta=nuevo_valor,
            )
        )
        # cambiar_servicio must be called with nuevo_valor_venta
        call_args = venta.cambiar_servicio.call_args
        positional_match = call_args[0][2] == nuevo_valor
        kw_match = call_args.kwargs.get("nuevo_valor_venta") == nuevo_valor
        assert positional_match or kw_match

    def test_editar_servicio_audit_first_orden_de_persistencia(self) -> None:
        """auditoria.guardar must be called BEFORE ventas.guardar and comisiones.guardar."""
        venta = _make_venta_mock()
        nuevo_servicio = _make_servicio_mock()
        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()
        parent.auditoria.listar_por_venta_id.return_value = []
        parent.servicios = MagicMock()
        parent.servicios.buscar_por_id.return_value = nuevo_servicio
        parent.reglas_repo = MagicMock()
        parent.reglas_repo.buscar_regla.return_value = MagicMock()
        parent.puntos_repo = MagicMock()
        parent.puntos_repo.buscar_por_id.return_value = None
        parent.comisiones_repo = MagicMock()
        motor = _make_motor()

        service = EditarServicioVentaService(
            ventas=parent.ventas,
            auditoria=parent.auditoria,
            servicios=parent.servicios,
            reglas_repo=parent.reglas_repo,
            puntos_repo=parent.puntos_repo,
            comisiones_repo=parent.comisiones_repo,
            motor=motor,
        )

        cmd = _make_cmd(venta_id=venta.id, nuevo_servicio_id=nuevo_servicio.id)
        service.ejecutar(cmd)

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 3
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])
        assert "comisiones_repo.guardar" in str(guardar_calls[2])

    def test_editar_servicio_audit_record_accion_editar_servicio(self) -> None:
        venta = _make_venta_mock()
        nuevo_servicio = _make_servicio_mock()
        ventas, auditoria, servicios, reglas, puntos, comisiones = _make_repos(
            venta=venta, nuevo_servicio=nuevo_servicio
        )
        service = _make_service(ventas, auditoria, servicios, reglas, puntos, comisiones)
        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_servicio_id=nuevo_servicio.id))
        registro = auditoria.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_SERVICIO
        assert registro.venta_id == venta.id
        assert isinstance(registro.realizada_at, datetime.datetime)
        assert registro.realizada_at.tzinfo is not None
