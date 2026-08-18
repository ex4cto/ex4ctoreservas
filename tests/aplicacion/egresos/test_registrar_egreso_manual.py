"""Tests for RegistrarEgresoManualService — RED phase."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from garay.aplicacion.egresos.registrar_egreso_manual import RegistrarEgresoManualService
from garay.dominio.comun.dinero import Dinero
from garay.dominio.conciliacion.tipos import TipoEgreso


def _make_service(categorias: list[str] | None = None) -> RegistrarEgresoManualService:
    egreso_repo = MagicMock()
    categoria_repo = MagicMock()
    categoria_repo.listar_activas.return_value = categorias or ["arriendo", "nomina", "otro"]
    return RegistrarEgresoManualService(egreso_repo=egreso_repo, categoria_repo=categoria_repo)


class TestRegistrarEgresoManual:
    def test_registrar_crea_egreso_con_campos_correctos(self) -> None:
        service = _make_service()
        egreso = service.registrar(
            monto=Decimal("500000"),
            descripcion="Pago de arriendo",
            categoria="arriendo",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
        )
        assert egreso.monto == Dinero("500000", "COP")
        assert egreso.descripcion == "Pago de arriendo"
        assert egreso.categoria == "arriendo"
        assert egreso.fecha == datetime.date(2026, 7, 1)
        assert egreso.tipo == TipoEgreso.MANUAL

    def test_registrar_llama_repo_guardar(self) -> None:
        egreso_repo = MagicMock()
        categoria_repo = MagicMock()
        categoria_repo.listar_activas.return_value = ["otro"]
        service = RegistrarEgresoManualService(
            egreso_repo=egreso_repo, categoria_repo=categoria_repo
        )
        egreso = service.registrar(
            monto=Decimal("10000"),
            descripcion="Gasto varios",
            categoria="otro",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
        )
        egreso_repo.guardar.assert_called_once_with(egreso)

    def test_registrar_categoria_invalida_lanza_error(self) -> None:
        service = _make_service(categorias=["arriendo", "nomina"])
        with pytest.raises(ValueError, match="Categoria no valida"):
            service.registrar(
                monto=Decimal("100000"),
                descripcion="Test",
                categoria="inexistente",
                fecha=datetime.date(2026, 7, 1),
                moneda="COP",
            )

    def test_listar_categorias_delega_al_repo(self) -> None:
        service = _make_service(categorias=["arriendo", "nomina", "otro"])
        cats = service.listar_categorias()
        assert cats == ["arriendo", "nomina", "otro"]

    def test_registrar_genera_uuid_unico(self) -> None:
        service = _make_service()
        e1 = service.registrar(
            monto=Decimal("100000"),
            descripcion="A",
            categoria="otro",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
        )
        e2 = service.registrar(
            monto=Decimal("100000"),
            descripcion="B",
            categoria="otro",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
        )
        assert e1.id != e2.id

    def test_registrar_asigna_fecha_recibido_no_none(self) -> None:
        service = _make_service()
        egreso = service.registrar(
            monto=Decimal("50000"),
            descripcion="Pago varios",
            categoria="otro",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
        )
        assert egreso.fecha_recibido is not None

    def test_registrar_con_gasto_recurrente_id_salta_validacion_categoria(self) -> None:
        """When gasto_recurrente_id is provided, skip active-category validation."""
        import uuid
        service = _make_service(categorias=["arriendo"])  # "nomina" not in list
        rec_id = uuid.uuid4()
        # Must NOT raise even though "nomina" is not an active category
        egreso = service.registrar(
            monto=Decimal("200000"),
            descripcion="Arriendo recurrente",
            categoria="nomina",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
            gasto_recurrente_id=rec_id,
        )
        assert egreso.gasto_recurrente_id == rec_id

    def test_registrar_con_gasto_recurrente_id_asigna_campo(self) -> None:
        """gasto_recurrente_id is persisted in the returned Egreso."""
        import uuid
        service = _make_service()
        rec_id = uuid.uuid4()
        egreso = service.registrar(
            monto=Decimal("100000"),
            descripcion="Servicios",
            categoria="otro",
            fecha=datetime.date(2026, 7, 1),
            moneda="COP",
            gasto_recurrente_id=rec_id,
        )
        assert egreso.gasto_recurrente_id == rec_id

    def test_registrar_sin_gasto_recurrente_id_valida_categoria(self) -> None:
        """Without gasto_recurrente_id, invalid category still raises."""
        service = _make_service(categorias=["arriendo"])
        with pytest.raises(ValueError, match="Categoria no valida"):
            service.registrar(
                monto=Decimal("100000"),
                descripcion="Test",
                categoria="inexistente",
                fecha=datetime.date(2026, 7, 1),
                moneda="COP",
            )
