"""Unit tests for RegistroAuditoria value object.

RED phase: these tests are written BEFORE the implementation.
They will fail until src/garay/dominio/auditoria/entidades.py is created.
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.auditoria.entidades import RegistroAuditoria


_NOW = datetime.datetime(2026, 10, 17, 12, 0, 0, tzinfo=datetime.UTC)
_ACTOR_ID = 5870211102
_ACTOR_NOMBRE = "Ryan"
_ENTIDAD_ID = uuid.uuid4()


def _registro_valido(**kwargs: object) -> RegistroAuditoria:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "entidad_tipo": "servicio",
        "entidad_id": _ENTIDAD_ID,
        "entidad_clave": None,
        "campo": "precio_neto_adulto",
        "valor_anterior": "50000",
        "valor_nuevo": "60000",
        "realizada_por_telegram_id": _ACTOR_ID,
        "realizada_por_nombre": _ACTOR_NOMBRE,
        "realizada_at": _NOW,
    }
    defaults.update(kwargs)
    return RegistroAuditoria(**defaults)  # type: ignore[arg-type]


class TestRegistroAuditoriaConstruction:
    def test_construye_con_campos_completos(self) -> None:
        r = _registro_valido()
        assert r.entidad_tipo == "servicio"
        assert r.campo == "precio_neto_adulto"
        assert r.valor_anterior == "50000"
        assert r.valor_nuevo == "60000"
        assert r.realizada_por_telegram_id == _ACTOR_ID
        assert r.realizada_por_nombre == _ACTOR_NOMBRE

    def test_construye_con_entidad_clave_y_sin_entidad_id(self) -> None:
        """socios_config uses entidad_clave, not entidad_id."""
        r = _registro_valido(entidad_id=None, entidad_clave="Ryan")
        assert r.entidad_id is None
        assert r.entidad_clave == "Ryan"

    def test_entidad_id_puede_ser_none_con_clave(self) -> None:
        r = _registro_valido(entidad_id=None, entidad_clave="socio-nombre")
        assert r.entidad_id is None

    def test_valor_anterior_puede_ser_none(self) -> None:
        r = _registro_valido(valor_anterior=None)
        assert r.valor_anterior is None

    def test_valor_nuevo_puede_ser_none(self) -> None:
        r = _registro_valido(valor_nuevo=None)
        assert r.valor_nuevo is None


class TestRegistroAuditoriaImmutability:
    def test_instancia_es_frozen(self) -> None:
        r = _registro_valido()
        with pytest.raises((AttributeError, TypeError)):
            r.campo = "otro_campo"  # type: ignore[misc]

    def test_frozen_instance_error_en_campo_id(self) -> None:
        from dataclasses import FrozenInstanceError

        r = _registro_valido()
        with pytest.raises(FrozenInstanceError):
            r.id = uuid.uuid4()  # type: ignore[misc]


class TestRegistroAuditoriaValidation:
    def test_rechaza_realizada_por_telegram_id_none(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            _registro_valido(realizada_por_telegram_id=None)

    def test_realizada_por_nombre_puede_ser_none(self) -> None:
        """Actor name is optional (bot-initiated edits may lack it)."""
        r = _registro_valido(realizada_por_nombre=None)
        assert r.realizada_por_nombre is None

    def test_id_es_uuid(self) -> None:
        r = _registro_valido()
        assert isinstance(r.id, uuid.UUID)

    def test_realizada_at_es_datetime(self) -> None:
        r = _registro_valido()
        assert isinstance(r.realizada_at, datetime.datetime)
