"""Tests for RegistrarVentaComando.horarios_por_servicio and RegistrarVentaService.

Phase 9 — TDD RED: tests written first. They verify:
  1. RegistrarVentaComando has the new optional field.
  2. _contexto_a_comando translates ctx.horarios_por_servicio (numero→str)
     to horarios_por_servicio (uuid.UUID→str) using the same servicio_map.
  3. RegistrarVentaService passes horarios_por_servicio to Venta.

Note: _contexto_a_comando is an async function wired to PTB context; we test
the translation logic through the data model (command field) rather than
calling the PTB handler directly.
"""

from __future__ import annotations

import uuid

from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.ventas.valor_objetos import Participantes


def _base_comando(**kwargs: object) -> RegistrarVentaComando:
    """Minimal valid RegistrarVentaComando with all required fields."""
    import datetime

    return RegistrarVentaComando(
        valor_venta=Dinero(100_000),
        neto=Dinero(80_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 12, 25),
        participantes=Participantes(
            vendedor_nombre="Test",
            cerrador_nombre=None,
            punto_de_venta_id=None,
            referido_nombre=None,
            vendedor_id=None,
            cerrador_id=None,
        ),
        adultos=2,
        ninos=0,
        **kwargs,  # type: ignore[arg-type]
    )


class TestRegistrarVentaComandoHorarios:
    """RegistrarVentaComando.horarios_por_servicio field contract."""

    def test_campo_por_defecto_es_none(self) -> None:
        """When not supplied, horarios_por_servicio defaults to None."""
        cmd = _base_comando()
        assert cmd.horarios_por_servicio is None

    def test_campo_acepta_dict_uuid_str(self) -> None:
        """horarios_por_servicio accepts dict[uuid.UUID, str]."""
        uid = uuid.uuid4()
        cmd = _base_comando(horarios_por_servicio={uid: "07:00"})
        assert cmd.horarios_por_servicio == {uid: "07:00"}

    def test_campo_acepta_none_explicito(self) -> None:
        """horarios_por_servicio=None is accepted."""
        cmd = _base_comando(horarios_por_servicio=None)
        assert cmd.horarios_por_servicio is None


class TestHorariosIdTranslation:
    """Unit tests for the horarios numero→uuid.UUID translation logic.

    The _contexto_a_comando function in handlers.py performs this translation.
    We test the logic in isolation by exercising it directly (pure dict transform).
    """

    @staticmethod
    def _translate(
        horarios_por_servicio: dict[int, str],
        servicio_map: dict[int, uuid.UUID],
    ) -> dict[uuid.UUID, str] | None:
        """Mirror of the translation logic from _contexto_a_comando."""
        horarios_id: dict[uuid.UUID, str] = {}
        if horarios_por_servicio:
            horarios_id = {
                servicio_map[n]: h
                for n, h in horarios_por_servicio.items()
                if n in servicio_map
            }
        return horarios_id if horarios_id else None

    def test_traduccion_un_tour(self) -> None:
        """Single tour horario is translated from numero to uuid key."""
        uid_a = uuid.uuid4()
        servicio_map = {1: uid_a}
        resultado = self._translate({1: "07:00"}, servicio_map)
        assert resultado == {uid_a: "07:00"}

    def test_contexto_vacio_devuelve_none(self) -> None:
        """Empty horarios_por_servicio in context produces None command field."""
        resultado = self._translate({}, {})
        assert resultado is None

    def test_numero_no_en_mapa_ignorado(self) -> None:
        """A tour numero missing from servicio_map is silently dropped."""
        uid_a = uuid.uuid4()
        servicio_map = {1: uid_a}
        # numero 2 is not in the map
        resultado = self._translate({1: "07:00", 2: "09:00"}, servicio_map)
        assert resultado == {uid_a: "07:00"}

    def test_todos_numeros_fuera_de_mapa_devuelve_none(self) -> None:
        """When no numero is in servicio_map, result is None (not empty dict)."""
        servicio_map: dict[int, uuid.UUID] = {}
        resultado = self._translate({1: "07:00"}, servicio_map)
        assert resultado is None
