"""Tests de la entidad Freelancer."""

from __future__ import annotations

import uuid

import pytest

from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.freelancers.errores import NombreFreelancerVacio


class TestFreelancer:
    def test_creacion_valida(self) -> None:
        f = Freelancer(id=uuid.uuid4(), nombre="Carlos")
        assert f.nombre == "Carlos"

    def test_activo_por_defecto(self) -> None:
        f = Freelancer(id=uuid.uuid4(), nombre="Carlos")
        assert f.activo is True

    def test_nombre_vacio_levanta_error(self) -> None:
        with pytest.raises(NombreFreelancerVacio):
            Freelancer(id=uuid.uuid4(), nombre="")

    def test_identidad_por_id(self) -> None:
        uid = uuid.uuid4()
        f1 = Freelancer(id=uid, nombre="Carlos")
        f2 = Freelancer(id=uid, nombre="Otro")
        assert f1 == f2
        assert hash(f1) == hash(f2)

    def test_telegram_user_id_opcional(self) -> None:
        f = Freelancer(id=uuid.uuid4(), nombre="Carlos")
        assert f.telegram_user_id is None

    def test_telegram_user_id_asignable(self) -> None:
        f = Freelancer(id=uuid.uuid4(), nombre="Carlos", telegram_user_id=123456789)
        assert f.telegram_user_id == 123456789
