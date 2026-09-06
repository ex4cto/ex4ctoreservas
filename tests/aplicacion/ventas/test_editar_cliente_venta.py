"""Tests for EditarClienteVentaService — Strict TDD (Slice 2)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarClienteVentaComando
from garay.aplicacion.ventas.editar_cliente_venta import EditarClienteVentaService
from garay.dominio.clientes.entidades import CampoCliente, Cliente
from garay.dominio.clientes.errores import ClienteNoEncontrado
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MotivoRequerido,
    VentaNoEncontrada,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cliente(telefono: str | None = "300000") -> Cliente:
    return Cliente(
        id=uuid.uuid4(),
        nombre="Juan Perez",
        tipo=TipoCliente.EXTERNO,
        telefono=telefono,
    )


def _make_venta(cliente_id: uuid.UUID) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.cliente_id = cliente_id
    return venta


def _make_repos(
    venta: MagicMock | None = None,
    cliente: Cliente | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    clientes_repo = MagicMock()
    clientes_repo.buscar_por_id.return_value = cliente
    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = []
    return ventas_repo, clientes_repo, auditoria_repo


def _rec(accion: AccionAuditoria) -> MagicMock:
    r = MagicMock()
    r.accion = accion
    return r


def _make_cmd(
    venta_id: uuid.UUID,
    campo: CampoCliente = CampoCliente.TELEFONO,
    nuevo_valor: str = "3009998877",
    motivo: str = "Corrección de dato",
) -> EditarClienteVentaComando:
    return EditarClienteVentaComando(
        venta_id=venta_id,
        campo=campo,
        nuevo_valor=nuevo_valor,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEditarClienteVentaService:
    def test_success_muta_cliente_y_persiste(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        service.ejecutar(_make_cmd(venta.id, CampoCliente.TELEFONO, "3009998877"))

        assert cliente.telefono == "3009998877"
        auditoria_repo.guardar.assert_called_once()
        clientes_repo.guardar.assert_called_once_with(cliente)

    def test_audit_guardado_antes_que_cliente(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        parent = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.clientes.buscar_por_id.return_value = cliente
        parent.auditoria.listar_por_venta_id.return_value = []

        service = EditarClienteVentaService(
            ventas=parent.ventas, clientes=parent.clientes, auditoria=parent.auditoria
        )
        service.ejecutar(_make_cmd(venta.id))

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "clientes.guardar" in str(guardar_calls[1])

    def test_audit_guardar_raises_cliente_never_persisted(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        auditoria_repo.guardar.side_effect = RuntimeError("DB error")
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        with pytest.raises(RuntimeError):
            service.ejecutar(_make_cmd(venta.id))

        clientes_repo.guardar.assert_not_called()

    def test_datos_previos_captura_valor_anterior(self) -> None:
        cliente = _make_cliente(telefono="111")
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        service.ejecutar(_make_cmd(venta.id, CampoCliente.TELEFONO, "222"))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"telefono": "111"}

    def test_audit_record_campos_correctos(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        cmd = EditarClienteVentaComando(
            venta_id=venta.id,
            campo=CampoCliente.EMAIL,
            nuevo_valor="a@b.com",
            motivo="  motivo con espacios  ",
            realizada_por_telegram_id=99,
            realizada_por_nombre="Propietario",
        )
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_CLIENTE
        assert registro.motivo == "motivo con espacios"
        assert registro.realizada_por_telegram_id == 99
        assert registro.venta_id == venta.id
        assert registro.realizada_at.tzinfo is not None

    def test_motivo_vacio_raises_nada_guardado(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta.id, motivo="   "))

        auditoria_repo.guardar.assert_not_called()
        clientes_repo.guardar.assert_not_called()

    def test_venta_no_encontrada_raises(self) -> None:
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta=None)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd(uuid.uuid4()))

        clientes_repo.guardar.assert_not_called()

    def test_cliente_no_encontrado_raises(self) -> None:
        venta = _make_venta(uuid.uuid4())
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente=None)
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        with pytest.raises(ClienteNoEncontrado):
            service.ejecutar(_make_cmd(venta.id))

        auditoria_repo.guardar.assert_not_called()
        clientes_repo.guardar.assert_not_called()

    def test_limite_dos_ediciones_bloquea(self) -> None:
        cliente = _make_cliente()
        venta = _make_venta(cliente.id)
        ventas_repo, clientes_repo, auditoria_repo = _make_repos(venta, cliente)
        auditoria_repo.listar_por_venta_id.return_value = [
            _rec(AccionAuditoria.EDITAR_FECHA),
            _rec(AccionAuditoria.EDITAR_CLIENTE),
        ]
        service = EditarClienteVentaService(
            ventas=ventas_repo, clientes=clientes_repo, auditoria=auditoria_repo
        )

        with pytest.raises(LimiteEdicionesAlcanzado):
            service.ejecutar(_make_cmd(venta.id))

        auditoria_repo.guardar.assert_not_called()
        clientes_repo.guardar.assert_not_called()
