"""Tests for task 1.7: Venta.cambiar_referido(alias) + MismoReferido error."""

from __future__ import annotations

import datetime
import uuid

import pytest

from garay.dominio.ventas.entidades import Venta
from garay.dominio.ventas.errores import MismoReferido
from garay.dominio.ventas.valor_objetos import Participantes
from garay.dominio.comun.dinero import Dinero
from garay.dominio.comun.tipos import TipoCliente


def _venta(referido_alias: str | None = None) -> Venta:
    return Venta(
        id=uuid.uuid4(),
        valor_venta=Dinero(500_000),
        neto=Dinero(400_000),
        servicio_ids=[uuid.uuid4()],
        cliente_id=uuid.uuid4(),
        tipo_cliente=TipoCliente.EXTERNO,
        fecha=datetime.date(2026, 10, 1),
        participantes=Participantes(
            vendedor_nombre="Ana",
            referido_alias=referido_alias,
        ),
    )


class TestCambiarReferido:
    def test_cambiar_referido_actualiza_participantes(self) -> None:
        """Task 1.7: cambiar_referido sets referido_alias on participantes."""
        v = _venta(referido_alias=None)
        v.cambiar_referido("taxi")
        assert v.participantes.referido_alias == "taxi"

    def test_cambiar_referido_a_none_limpia_alias(self) -> None:
        """Task 1.7: cambiar_referido(None) clears the alias."""
        v = _venta(referido_alias="taxi")
        v.cambiar_referido(None)
        assert v.participantes.referido_alias is None

    def test_mismo_referido_lanza_error(self) -> None:
        """Task 1.7: idempotency guard raises MismoReferido."""
        v = _venta(referido_alias="taxi")
        with pytest.raises(MismoReferido):
            v.cambiar_referido("taxi")

    def test_mismo_referido_none_lanza_error(self) -> None:
        """Task 1.7: calling cambiar_referido(None) when already None raises MismoReferido."""
        v = _venta(referido_alias=None)
        with pytest.raises(MismoReferido):
            v.cambiar_referido(None)

    def test_cambiar_referido_preserva_otros_participantes(self) -> None:
        """Task 1.7: cambiar_referido only modifies referido_alias, nothing else."""
        v = _venta(referido_alias=None)
        v.cambiar_referido("nuevo")
        assert v.participantes.vendedor_nombre == "Ana"

    def test_mismoreferido_es_error_de_dominio(self) -> None:
        """Task 1.7: MismoReferido is an ErrorDeDominio subclass."""
        from garay.dominio.comun.errores import ErrorDeDominio
        assert issubclass(MismoReferido, ErrorDeDominio)
