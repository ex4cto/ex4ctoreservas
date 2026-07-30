"""TDD RED — WU-1: CanalOrigen enum and canal_origen field."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import pytest

from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import CanalOrigen, TipoCliente
from garay.dominio.ventas.contexto import ContextoVenta
from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.valor_objetos import Participantes


def _venta_base(**kwargs: object) -> Venta:
    defaults: dict[str, Any] = dict(
        id=uuid.uuid4(),
        valor_venta=Dinero(1_000_000),
        neto=Dinero(900_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 7, 1),
        participantes=Participantes(),
    )
    defaults.update(kwargs)
    return Venta(**defaults)


class TestCanalOrigenEnum:
    def test_canal_origen_tiene_6_valores(self) -> None:
        assert len(CanalOrigen) == 6

    def test_canal_origen_values_son_etiquetas_legibles(self) -> None:
        assert CanalOrigen.WHATSAPP.value == "WhatsApp"
        assert CanalOrigen.INSTAGRAM.value == "Instagram"
        assert CanalOrigen.TIKTOK.value == "TikTok"
        assert CanalOrigen.FACEBOOK.value == "Facebook"
        assert CanalOrigen.GOOGLE.value == "Google"
        assert CanalOrigen.PAGINA_WEB.value == "Página web"

    def test_canal_origen_lookup_por_value_valido(self) -> None:
        assert CanalOrigen("WhatsApp") == CanalOrigen.WHATSAPP
        assert CanalOrigen("Página web") == CanalOrigen.PAGINA_WEB

    def test_canal_origen_lookup_por_nombre_miembro_lanza_error(self) -> None:
        with pytest.raises(ValueError):
            CanalOrigen("WHATSAPP")

    def test_canal_origen_valor_invalido_lanza_error(self) -> None:
        with pytest.raises(ValueError):
            CanalOrigen("TELEGRAM")


class TestContextoVentaCanalOrigen:
    def test_contexto_venta_canal_origen_default_none(self) -> None:
        ctx = ContextoVenta()
        assert ctx.canal_origen is None

    def test_contexto_venta_canal_origen_asignable(self) -> None:
        ctx = ContextoVenta()
        ctx.canal_origen = "WhatsApp"
        assert ctx.canal_origen == "WhatsApp"


class TestVentaCanalOrigen:
    def test_venta_canal_origen_default_none(self) -> None:
        v = _venta_base()
        assert v.canal_origen is None

    def test_venta_digital_con_canal_es_valida(self) -> None:
        v = _venta_base(tipo_cliente=TipoCliente.DIGITAL, canal_origen="Instagram")
        assert v.canal_origen == "Instagram"

    def test_venta_interno_sin_canal_es_valida(self) -> None:
        v = _venta_base(tipo_cliente=TipoCliente.INTERNO, canal_origen=None)
        assert v.canal_origen is None
