"""Tests for ComisionRegistrada entity."""
from __future__ import annotations

import datetime
import uuid
from unittest.mock import MagicMock

from garay.dominio.comisiones.entidades import ComisionRegistrada


class TestComisionRegistradaIdentidad:
    def test_mismo_venta_id_son_iguales(self) -> None:
        venta_id = uuid.uuid4()
        c1 = ComisionRegistrada(
            venta_id=venta_id,
            desglose=MagicMock(),
            fecha=datetime.date(2026, 7, 1),
        )
        c2 = ComisionRegistrada(
            venta_id=venta_id,
            desglose=MagicMock(),
            fecha=datetime.date(2026, 7, 2),
        )
        assert c1 == c2

    def test_distinto_venta_id_son_distintas(self) -> None:
        c1 = ComisionRegistrada(
            venta_id=uuid.uuid4(),
            desglose=MagicMock(),
            fecha=datetime.date(2026, 7, 1),
        )
        c2 = ComisionRegistrada(
            venta_id=uuid.uuid4(),
            desglose=MagicMock(),
            fecha=datetime.date(2026, 7, 1),
        )
        assert c1 != c2

    def test_hash_consistente_con_venta_id(self) -> None:
        venta_id = uuid.uuid4()
        c = ComisionRegistrada(
            venta_id=venta_id,
            desglose=MagicMock(),
            fecha=datetime.date(2026, 7, 1),
        )
        assert hash(c) == hash(venta_id)
