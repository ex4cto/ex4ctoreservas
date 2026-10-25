"""Unit tests for post-sale freelancer DM dispatch in RegistrarVentaService.

Spec ref: "Happy path", "Vendedor equals cerrador", "Null participant",
          "DM Telegram failure", "Multi-Tour Sale DM Loop", "Freelancer Telegram ID Guard".
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.servicio import RegistrarVentaService
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.ventas.valor_objetos import Participantes

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FECHA = datetime.date(2026, 10, 17)
_SERVICIO_ID_1 = uuid.uuid4()
_SERVICIO_ID_2 = uuid.uuid4()
_VENDEDOR_ID = uuid.uuid4()
_CERRADOR_ID = uuid.uuid4()

def _make_servicio(
    sid: uuid.UUID,
    nombre: str = "Tour Test",
    info_tour: str | None = None,
    observaciones: str | None = None,
) -> Servicio:
    return Servicio(
        id=sid,
        numero=1,
        nombre=nombre,
        precio_neto_adulto=Decimal("100000"),
        info_tour=info_tour,
        observaciones=observaciones,
    )

def _make_freelancer(
    fid: uuid.UUID,
    telegram_user_id: int | None = 12345,
) -> Freelancer:
    return Freelancer(id=fid, nombre="Vendedor Test", telegram_user_id=telegram_user_id)

def _make_reglas() -> ReglasComision:
    return ReglasComision(
        id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        porcentaje_vendedor=Decimal("20"),
        porcentaje_cerrador=Decimal("10"),
        punto_de_venta_nombre=None,
        numero_personas=None,
    )

def _make_service(
    servicio_map: dict[uuid.UUID, Servicio | None] | None = None,
    freelancer_map: dict[uuid.UUID, Freelancer | None] | None = None,
) -> tuple[RegistrarVentaService, MagicMock]:
    """Build a RegistrarVentaService with mock repositories.

    Returns (service, notificador_mock).
    """
    ventas_repo = MagicMock()
    ventas_repo.guardar.return_value = None

    reglas_repo = MagicMock()
    reglas_repo.buscar_regla.return_value = _make_reglas()

    tiqueteras_repo = MagicMock()
    puntos_repo = MagicMock()
    puntos_repo.buscar_por_id.return_value = None

    from garay.dominio.comisiones.motor import MotorComisiones
    motor = MotorComisiones()

    notificador = MagicMock()
    notificador.notificar.return_value = None

    comisiones_repo = MagicMock()
    comisiones_repo.guardar.return_value = None

    socios_config = MagicMock()
    socios_config.listar.return_value = []

    freelancers_repo = MagicMock()

    def _freelancer_buscar(fid: uuid.UUID) -> Freelancer | None:
        if freelancer_map is None:
            return None
        return freelancer_map.get(fid)

    freelancers_repo.buscar_por_id.side_effect = _freelancer_buscar

    servicios_repo = MagicMock()

    def _servicio_buscar(sid: uuid.UUID) -> Servicio | None:
        if servicio_map is None:
            return None
        return servicio_map.get(sid)

    servicios_repo.buscar_por_id.side_effect = _servicio_buscar

    service = RegistrarVentaService(
        ventas=ventas_repo,
        reglas_repo=reglas_repo,
        tiqueteras=tiqueteras_repo,
        puntos_repo=puntos_repo,
        motor=motor,
        notificador=notificador,
        grupo_id="-1001234",
        comisiones_repo=comisiones_repo,
        socios_config=socios_config,
        freelancers=freelancers_repo,
        servicios=servicios_repo,
    )
    return service, notificador

def _make_cmd(
    servicio_ids: list[uuid.UUID],
    servicio_nombres: list[str],
    vendedor_id: uuid.UUID | None = _VENDEDOR_ID,
    cerrador_id: uuid.UUID | None = _CERRADOR_ID,
) -> RegistrarVentaComando:
    cliente_id = uuid.uuid4()
    return RegistrarVentaComando(
        valor_venta=Dinero("300000"),
        neto=Dinero("200000"),
        servicio_ids=servicio_ids,
        cliente_id=cliente_id,
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=_FECHA,
        participantes=Participantes(
            vendedor_id=vendedor_id,
            cerrador_id=cerrador_id,
            vendedor_nombre="Vendedor",
            cerrador_nombre="Cerrador",
        ),
        adultos=2,
        ninos=0,
        servicio_nombres=servicio_nombres,
    )

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_vendedor_equals_cerrador_single_dm_sent() -> None:
    """When vendedor_id == cerrador_id, only one DM is sent per tour."""
    fid = _VENDEDOR_ID
    freelancer = _make_freelancer(fid)
    servicio = _make_servicio(_SERVICIO_ID_1, info_tour="Info del tour")
    service, notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: servicio},
        freelancer_map={fid: freelancer},
    )
    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1],
        servicio_nombres=["Tour Test"],
        vendedor_id=fid,
        cerrador_id=fid,  # same person
    )
    service.ejecutar(cmd)

    # Count only the DM calls (not the group call)
    dm_calls = [
        c for c in notificador.notificar.call_args_list
        if c.args[1] == str(freelancer.telegram_user_id)
    ]
    assert len(dm_calls) == 1

def test_vendedor_id_none_no_crash() -> None:
    """vendedor_id=None should not crash and no DM attempted for null participant."""
    cerrador = _make_freelancer(_CERRADOR_ID)
    servicio = _make_servicio(_SERVICIO_ID_1, info_tour="Info")
    service, _notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: servicio},
        freelancer_map={_CERRADOR_ID: cerrador},
    )
    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1],
        servicio_nombres=["Tour Test"],
        vendedor_id=None,
        cerrador_id=_CERRADOR_ID,
    )
    result = service.ejecutar(cmd)
    assert result is not None  # no exception raised

def test_telegram_notifier_raises_sale_result_unaffected() -> None:
    """Telegram DM failure does not affect the returned sale result."""
    fid = _VENDEDOR_ID
    freelancer = _make_freelancer(fid)
    servicio = _make_servicio(_SERVICIO_ID_1, info_tour="Info del tour")
    service, notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: servicio},
        freelancer_map={fid: freelancer},
    )

    # Make DM notificaciones raise after the group message (first call)
    call_count = {"n": 0}

    def _side_effect(msg: str, chat_id: str) -> None:
        call_count["n"] += 1
        if call_count["n"] > 1:
            raise RuntimeError("Telegram error")
        return None

    notificador.notificar.side_effect = _side_effect

    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1],
        servicio_nombres=["Tour Test"],
        vendedor_id=fid,
        cerrador_id=fid,
    )
    result = service.ejecutar(cmd)
    assert result.venta_id is not None

def test_two_tours_one_with_content_one_dm_sent() -> None:
    """Two tours in the sale, only one with content -> exactly one freelancer DM."""
    fid = _VENDEDOR_ID
    freelancer = _make_freelancer(fid)
    s1 = _make_servicio(_SERVICIO_ID_1, nombre="Tour A", info_tour="Contenido")
    s2 = _make_servicio(_SERVICIO_ID_2, nombre="Tour B", info_tour=None, observaciones=None)
    service, notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: s1, _SERVICIO_ID_2: s2},
        freelancer_map={fid: freelancer},
    )
    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1, _SERVICIO_ID_2],
        servicio_nombres=["Tour A", "Tour B"],
        vendedor_id=fid,
        cerrador_id=fid,
    )
    service.ejecutar(cmd)

    dm_calls = [
        c for c in notificador.notificar.call_args_list
        if c.args[1] == str(freelancer.telegram_user_id)
    ]
    assert len(dm_calls) == 1

def test_two_tours_both_with_content_two_dms_sent() -> None:
    """Two tours both with content -> two separate DMs sent to the freelancer."""
    fid = _VENDEDOR_ID
    freelancer = _make_freelancer(fid)
    s1 = _make_servicio(_SERVICIO_ID_1, nombre="Tour A", info_tour="Info A")
    s2 = _make_servicio(_SERVICIO_ID_2, nombre="Tour B", observaciones="Obs B")
    service, notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: s1, _SERVICIO_ID_2: s2},
        freelancer_map={fid: freelancer},
    )
    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1, _SERVICIO_ID_2],
        servicio_nombres=["Tour A", "Tour B"],
        vendedor_id=fid,
        cerrador_id=fid,
    )
    service.ejecutar(cmd)

    dm_calls = [
        c for c in notificador.notificar.call_args_list
        if c.args[1] == str(freelancer.telegram_user_id)
    ]
    assert len(dm_calls) == 2

def test_freelancer_telegram_user_id_none_no_dm_attempted() -> None:
    """Freelancer with telegram_user_id=None -> no DM attempted."""
    fid = _VENDEDOR_ID
    freelancer = _make_freelancer(fid, telegram_user_id=None)
    servicio = _make_servicio(_SERVICIO_ID_1, info_tour="Info del tour")
    service, notificador = _make_service(
        servicio_map={_SERVICIO_ID_1: servicio},
        freelancer_map={fid: freelancer},
    )
    cmd = _make_cmd(
        servicio_ids=[_SERVICIO_ID_1],
        servicio_nombres=["Tour Test"],
        vendedor_id=fid,
        cerrador_id=fid,
    )
    service.ejecutar(cmd)

    # Only group message, no DM to None telegram_user_id
    assert notificador.notificar.call_count == 1  # just the group message
