"""Tests for EditarAbonoVentaService — Strict TDD."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarAbonoVentaComando
from garay.aplicacion.ventas.editar_abono import EditarAbonoVentaService
from garay.aplicacion.ventas.limite_ediciones import ACCIONES_FINANCIERAS
from garay.dominio.comun.dinero import Dinero
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    AbonoSuperaValorVenta,
    MismoAbono,
    MotivoRequerido,
    VentaNoEncontrada,
    VentaYaAnulada,
)


def _make_venta(
    abono: Dinero | None = None,
    valor_venta: Dinero | None = None,
    anulada: bool = False,
) -> MagicMock:
    venta = MagicMock()
    venta.id = uuid.uuid4()
    venta.abono = abono
    venta.valor_venta = valor_venta or Dinero(300_000)
    venta.anulada = anulada

    def _cambiar_abono(nuevo: Dinero | None) -> None:
        if venta.anulada:
            raise VentaYaAnulada("Ya anulada.")
        if nuevo == venta.abono:
            raise MismoAbono("Ya es ese abono.")
        if nuevo is not None and nuevo > venta.valor_venta:
            raise AbonoSuperaValorVenta("Supera el valor de venta.")
        venta.abono = nuevo

    venta.cambiar_abono.side_effect = _cambiar_abono
    return venta


def _make_repos(venta: MagicMock | None = None) -> tuple[MagicMock, MagicMock]:
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta
    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = []
    return ventas_repo, auditoria_repo


def _make_cmd(
    venta_id: uuid.UUID | None = None,
    nuevo_abono: Dinero | None = Dinero(50_000),
    motivo: str = "Abono recibido",
) -> EditarAbonoVentaComando:
    return EditarAbonoVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nuevo_abono=nuevo_abono,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


class TestEditarAbonoVentaService:
    def test_motivo_vacio_raises_motivo_requerido(self) -> None:
        venta = _make_venta()
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo="  "))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_venta_no_encontrada_raises(self) -> None:
        ventas_repo, auditoria_repo = _make_repos(venta=None)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_mismo_abono_raises(self) -> None:
        venta = _make_venta(abono=Dinero(50_000))
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(MismoAbono):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(50_000)))

    def test_venta_anulada_raises(self) -> None:
        venta = _make_venta(anulada=True)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        with pytest.raises(VentaYaAnulada):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_success_cambia_abono_y_persiste(self) -> None:
        venta = _make_venta(abono=None)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(80_000)))

        venta.cambiar_abono.assert_called_once_with(Dinero(80_000))
        auditoria_repo.guardar.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)

    def test_success_limpia_abono_none(self) -> None:
        venta = _make_venta(abono=Dinero(50_000))
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=None))

        venta.cambiar_abono.assert_called_once_with(None)
        auditoria_repo.guardar.assert_called_once()

    def test_audit_first(self) -> None:
        """AUDIT-FIRST: auditoria.guardar must precede ventas.guardar."""
        venta = _make_venta(abono=None)

        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()
        parent.auditoria.listar_por_venta_id.return_value = []

        service = EditarAbonoVentaService(ventas=parent.ventas, auditoria=parent.auditoria)
        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(50_000)))

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 2
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])

    def test_datos_previos_contiene_abono_anterior(self) -> None:
        venta = _make_venta(abono=Dinero(40_000))
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(80_000)))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"abono": 40_000}

    def test_datos_previos_abono_none_guardado_como_none(self) -> None:
        venta = _make_venta(abono=None)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(50_000)))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"abono": None}

    def test_audit_accion_editar_abono(self) -> None:
        venta = _make_venta(abono=None)
        ventas_repo, auditoria_repo = _make_repos(venta)
        service = EditarAbonoVentaService(ventas=ventas_repo, auditoria=auditoria_repo)

        service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_abono=Dinero(50_000)))

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_ABONO

    def test_editar_abono_no_esta_en_acciones_financieras(self) -> None:
        """EDITAR_ABONO must NOT be in ACCIONES_FINANCIERAS — it is informational."""
        assert AccionAuditoria.EDITAR_ABONO not in ACCIONES_FINANCIERAS
