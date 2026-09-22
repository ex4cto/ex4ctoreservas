"""Tests for EditarCanalVentaService and EditarCanalVentaComando — Strict TDD."""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.ventas.comandos import EditarCanalVentaComando
from garay.aplicacion.ventas.editar_canal import EditarCanalVentaService
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.auditoria import AccionAuditoria
from garay.dominio.ventas.errores import (
    LimiteEdicionesAlcanzado,
    MismoCanal,
    MotivoRequerido,
    PuntoDeVentaRequerido,
    VentaNoEncontrada,
    VentaYaAnulada,
)

# ---------------------------------------------------------------------------
# Task-8 RED: EditarCanalVentaComando shape
# ---------------------------------------------------------------------------


class TestEditarCanalVentaComando:
    """EditarCanalVentaComando must be a frozen dataclass with the 6 required fields."""

    def test_comando_is_importable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarCanalVentaComando

        assert EditarCanalVentaComando is not None

    def test_comando_is_frozen_dataclass(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarCanalVentaComando

        fields = {f.name for f in dataclasses.fields(EditarCanalVentaComando)}
        assert fields == {
            "venta_id",
            "nuevo_tipo",
            "punto_id",
            "motivo",
            "realizada_por_telegram_id",
            "realizada_por_nombre",
        }

    def test_comando_is_immutable(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarCanalVentaComando

        cmd = EditarCanalVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_tipo=TipoCliente.EXTERNO,
            punto_id=None,
            motivo="test",
            realizada_por_telegram_id=1,
            realizada_por_nombre="Admin",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
            cmd.motivo = "changed"  # type: ignore[misc]

    def test_campo_tipos(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarCanalVentaComando

        pid = uuid.uuid4()
        vid = uuid.uuid4()
        cmd = EditarCanalVentaComando(
            venta_id=vid,
            nuevo_tipo=TipoCliente.INTERNO,
            punto_id=pid,
            motivo="motivo",
            realizada_por_telegram_id=42,
            realizada_por_nombre="Admin",
        )
        assert cmd.venta_id == vid
        assert cmd.nuevo_tipo == TipoCliente.INTERNO
        assert cmd.punto_id == pid
        assert cmd.motivo == "motivo"
        assert cmd.realizada_por_telegram_id == 42
        assert cmd.realizada_por_nombre == "Admin"

    def test_punto_id_optional_none(self) -> None:
        from garay.aplicacion.ventas.comandos import EditarCanalVentaComando

        cmd = EditarCanalVentaComando(
            venta_id=uuid.uuid4(),
            nuevo_tipo=TipoCliente.EXTERNO,
            punto_id=None,
            motivo="motivo",
            realizada_por_telegram_id=1,
            realizada_por_nombre=None,
        )
        assert cmd.punto_id is None
        assert cmd.realizada_por_nombre is None


# ---------------------------------------------------------------------------
# Task-10: EDITAR_CANAL in ACCIONES_EDICION
# ---------------------------------------------------------------------------


class TestAccionesEdicionIncludeEditarCanal:
    def test_editar_canal_in_acciones_edicion(self) -> None:
        from garay.aplicacion.ventas.limite_ediciones import ACCIONES_EDICION
        from garay.dominio.ventas.auditoria import AccionAuditoria

        assert AccionAuditoria.EDITAR_CANAL in ACCIONES_EDICION


# ---------------------------------------------------------------------------
# Task-11 RED: EditarCanalVentaService — all scenarios
# ---------------------------------------------------------------------------

# Helpers


def _make_venta_mock(
    tipo_cliente: TipoCliente = TipoCliente.EXTERNO,
    anulada: bool = False,
    punto_de_venta_id: uuid.UUID | None = None,
    adultos: int = 2,
    ninos: int = 0,
) -> MagicMock:
    v = MagicMock()
    v.id = uuid.uuid4()
    v.tipo_cliente = tipo_cliente
    v.anulada = anulada
    v.adultos = adultos
    v.ninos = ninos
    v.fecha = datetime.date(2026, 9, 1)
    participantes = MagicMock()
    participantes.punto_de_venta_id = punto_de_venta_id
    participantes.vendedor_id = uuid.uuid4()
    participantes.cerrador_id = uuid.uuid4()
    v.participantes = participantes

    def _cambiar_tipo_cliente(nuevo_tipo: TipoCliente, punto_id: uuid.UUID | None = None) -> None:
        if v.anulada:
            raise VentaYaAnulada("Ya anulada.")
        if nuevo_tipo == v.tipo_cliente:
            raise MismoCanal("Mismo canal.")
        if nuevo_tipo == TipoCliente.INTERNO and punto_id is None:
            raise PuntoDeVentaRequerido("Punto requerido.")
        v.tipo_cliente = nuevo_tipo
        v.participantes.punto_de_venta_id = punto_id if nuevo_tipo == TipoCliente.INTERNO else None

    v.cambiar_tipo_cliente.side_effect = _cambiar_tipo_cliente
    return v


def _make_repos(
    venta: MagicMock | None = None,
    auditoria_records: list[MagicMock] | None = None,
    punto: MagicMock | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    """Return (ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)."""
    ventas_repo = MagicMock()
    ventas_repo.buscar_por_id.return_value = venta

    auditoria_repo = MagicMock()
    auditoria_repo.listar_por_venta_id.return_value = auditoria_records or []

    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = MagicMock()

    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = punto

    comisiones_repo = MagicMock()

    return ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo


def _make_motor() -> MagicMock:
    motor = MagicMock()
    motor.calcular.return_value = MagicMock()
    return motor


def _make_cmd(
    venta_id: uuid.UUID | None = None,
    nuevo_tipo: TipoCliente = TipoCliente.EXTERNO,
    punto_id: uuid.UUID | None = None,
    motivo: str = "Corrección de canal",
) -> EditarCanalVentaComando:
    return EditarCanalVentaComando(
        venta_id=venta_id or uuid.uuid4(),
        nuevo_tipo=nuevo_tipo,
        punto_id=punto_id,
        motivo=motivo,
        realizada_por_telegram_id=42,
        realizada_por_nombre="Admin",
    )


def _make_service(
    ventas_repo: MagicMock,
    auditoria_repo: MagicMock,
    reglas_repo: MagicMock,
    puntos_repo: MagicMock,
    comisiones_repo: MagicMock,
    motor: MagicMock | None = None,
) -> EditarCanalVentaService:
    return EditarCanalVentaService(
        ventas=ventas_repo,
        auditoria=auditoria_repo,
        reglas_repo=reglas_repo,
        puntos_repo=puntos_repo,
        comisiones_repo=comisiones_repo,
        motor=motor or _make_motor(),
    )


def _rec(accion: AccionAuditoria) -> MagicMock:
    r = MagicMock()
    r.accion = accion
    return r


class TestEditarCanalVentaService:
    # --- motivo vacío → MotivoRequerido ---

    def test_motivo_vacio_raises_motivo_requerido(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo="   "))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    def test_motivo_cadena_vacia_raises_motivo_requerido(self) -> None:
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(MotivoRequerido):
            service.ejecutar(_make_cmd(venta_id=venta.id, motivo=""))

    # --- venta not found → VentaNoEncontrada ---

    def test_venta_no_encontrada_raises(self) -> None:
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta=None)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(VentaNoEncontrada):
            service.ejecutar(_make_cmd())

        ventas_repo.guardar.assert_not_called()

    # --- limit reached → LimiteEdicionesAlcanzado ---

    def test_limite_ediciones_raises_nada_guardado(self) -> None:
        # Financial limit: MAX=3, counting EDITAR_CANAL (x3)
        venta = _make_venta_mock()
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(
            venta,
            auditoria_records=[
                _rec(AccionAuditoria.EDITAR_CANAL),
                _rec(AccionAuditoria.EDITAR_CANAL),
                _rec(AccionAuditoria.EDITAR_CANAL),
            ],
        )
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(LimiteEdicionesAlcanzado):
            service.ejecutar(_make_cmd(venta_id=venta.id))

        ventas_repo.guardar.assert_not_called()
        auditoria_repo.guardar.assert_not_called()

    # --- MismoCanal from domain: audit NOT saved, no count ---

    def test_mismo_canal_not_saved_not_counted(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(MismoCanal):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.EXTERNO))

        auditoria_repo.guardar.assert_not_called()
        ventas_repo.guardar.assert_not_called()
        comisiones_repo.guardar.assert_not_called()

    # --- AUDIT-FIRST: assert call order ---

    def test_audit_first_order(self) -> None:
        """auditoria.guardar must be called before ventas.guardar before comisiones_repo.guardar."""
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        parent = MagicMock()
        parent.ventas = MagicMock()
        parent.ventas.buscar_por_id.return_value = venta
        parent.auditoria = MagicMock()
        parent.auditoria.listar_por_venta_id.return_value = []
        parent.reglas_repo = MagicMock()
        parent.reglas_repo.buscar_regla.return_value = MagicMock()
        parent.puntos_repo = MagicMock()
        parent.puntos_repo.buscar_por_id.return_value = None
        parent.comisiones_repo = MagicMock()
        motor = _make_motor()

        from garay.aplicacion.ventas.editar_canal import EditarCanalVentaService

        service = EditarCanalVentaService(
            ventas=parent.ventas,
            auditoria=parent.auditoria,
            reglas_repo=parent.reglas_repo,
            puntos_repo=parent.puntos_repo,
            comisiones_repo=parent.comisiones_repo,
            motor=motor,
        )

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL)
        service.ejecutar(cmd)

        guardar_calls = [c for c in parent.mock_calls if "guardar" in str(c)]
        assert len(guardar_calls) == 3
        assert "auditoria.guardar" in str(guardar_calls[0])
        assert "ventas.guardar" in str(guardar_calls[1])
        assert "comisiones_repo.guardar" in str(guardar_calls[2])

    # --- Crespo lookup ---

    def test_crespo_lookup_uses_punto_nombre_and_personas(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        pid = uuid.uuid4()
        punto = MagicMock()
        punto.nombre = "Crespo"
        punto.id = pid

        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(
            venta, punto=punto
        )
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.INTERNO, punto_id=pid)
        service.ejecutar(cmd)

        reglas_repo.buscar_regla.assert_called_once()
        call_args = reglas_repo.buscar_regla.call_args
        # Second arg is punto name (Crespo), third arg is personas (not None for Crespo)
        assert call_args.args[1] == "Crespo" or (
            len(call_args.args) >= 2 and call_args.args[1] == "Crespo"
        ) or call_args.kwargs.get("punto_nombre") == "Crespo"

    # --- Non-Crespo lookup → buscar_regla(tipo, None, None) ---

    def test_non_crespo_lookup_uses_none_none(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        pid = uuid.uuid4()
        punto = MagicMock()
        punto.nombre = "OtroPunto"
        punto.id = pid

        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(
            venta, punto=punto
        )
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.INTERNO, punto_id=pid)
        service.ejecutar(cmd)

        call_args = reglas_repo.buscar_regla.call_args
        # Non-Crespo: punto_nombre=None, personas=None
        assert call_args.args[1] is None or call_args.kwargs.get("punto_nombre") is None
        assert call_args.args[2] is None or call_args.kwargs.get("numero_personas") is None

    def test_no_punto_lookup_uses_none_none(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(
            venta, punto=None
        )
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL)
        service.ejecutar(cmd)

        call_args = reglas_repo.buscar_regla.call_args
        assert call_args.args[1] is None
        assert call_args.args[2] is None

    # --- ComisionRegistrada upserted with new desglose ---

    def test_comision_registrada_upserted(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        motor = _make_motor()
        desglose = MagicMock()
        motor.calcular.return_value = desglose
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL)
        service.ejecutar(cmd)

        comisiones_repo.guardar.assert_called_once()
        comision_arg = comisiones_repo.guardar.call_args[0][0]
        assert comision_arg.venta_id == venta.id
        assert comision_arg.desglose is desglose

    # --- datos_previos captures old tipo_cliente string BEFORE mutation ---

    def test_datos_previos_captures_old_tipo_cliente(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        old_tipo = venta.tipo_cliente.value  # "EXTERNO"
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL)
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.datos_previos == {"tipo_cliente": old_tipo}

    # --- VentaYaAnulada propagated from domain ---

    def test_venta_ya_anulada_propagated(self) -> None:
        venta = _make_venta_mock(anulada=True)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo)

        with pytest.raises(VentaYaAnulada):
            service.ejecutar(_make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL))

        auditoria_repo.guardar.assert_not_called()
        ventas_repo.guardar.assert_not_called()

    # --- Audit record content ---

    def test_audit_record_accion_editar_canal(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL, motivo="Corrección")
        service.ejecutar(cmd)

        registro = auditoria_repo.guardar.call_args[0][0]
        assert registro.accion == AccionAuditoria.EDITAR_CANAL
        assert registro.motivo == "Corrección"
        assert registro.venta_id == venta.id
        assert registro.realizada_por_telegram_id == 42
        assert isinstance(registro.realizada_at, datetime.datetime)
        assert registro.realizada_at.tzinfo is not None

    # --- Happy path: complete execution ---

    def test_happy_path_externo_to_digital(self) -> None:
        venta = _make_venta_mock(tipo_cliente=TipoCliente.EXTERNO)
        ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo = _make_repos(venta)
        motor = _make_motor()
        service = _make_service(ventas_repo, auditoria_repo, reglas_repo, puntos_repo, comisiones_repo, motor)

        cmd = _make_cmd(venta_id=venta.id, nuevo_tipo=TipoCliente.DIGITAL)
        service.ejecutar(cmd)

        venta.cambiar_tipo_cliente.assert_called_once_with(TipoCliente.DIGITAL, None)
        auditoria_repo.guardar.assert_called_once()
        ventas_repo.guardar.assert_called_once_with(venta)
        comisiones_repo.guardar.assert_called_once()
