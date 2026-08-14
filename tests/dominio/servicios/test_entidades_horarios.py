"""Tests for Servicio.horarios field — task 1.7 (RED).

Verifies that the Servicio entity accepts a horarios field,
defaults to [], and sorts the list on initialization.
"""

from __future__ import annotations

import uuid

from garay.dominio.servicios.entidades import Servicio


class TestServicioHorarios:
    def test_horarios_default_empty(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour")
        assert s.horarios == []

    def test_horarios_inicializado(self) -> None:
        s = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Tour",
            horarios=["19:00", "07:00", "09:00"],
        )
        assert s.horarios == ["07:00", "09:00", "19:00"]

    def test_horarios_ya_ordenados_no_cambia(self) -> None:
        s = Servicio(
            id=uuid.uuid4(),
            numero=1,
            nombre="Tour",
            horarios=["07:00", "09:00", "19:00"],
        )
        assert s.horarios == ["07:00", "09:00", "19:00"]

    def test_horarios_lista_unitaria(self) -> None:
        s = Servicio(id=uuid.uuid4(), numero=1, nombre="Tour", horarios=["12:00"])
        assert s.horarios == ["12:00"]

    def test_horarios_no_comparte_mutables(self) -> None:
        """Two Servicio instances have independent horarios lists."""
        s1 = Servicio(id=uuid.uuid4(), numero=1, nombre="A")
        s2 = Servicio(id=uuid.uuid4(), numero=2, nombre="B")
        s1.horarios.append("07:00")
        assert s2.horarios == []
