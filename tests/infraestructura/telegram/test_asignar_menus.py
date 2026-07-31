"""Unit tests for asignar_menus — the pure id→menu resolver (no PTB types)."""

from __future__ import annotations

from garay.infraestructura.telegram.bot import asignar_menus


def test_propietario_obtiene_menu_propietario() -> None:
    resultado = asignar_menus(propietario_ids={1}, dev_ids=set(), admin_ids=set())
    assert resultado == {1: "propietario"}


def test_dev_obtiene_menu_propietario() -> None:
    resultado = asignar_menus(propietario_ids=set(), dev_ids={2}, admin_ids=set())
    assert resultado == {2: "propietario"}


def test_admin_solo_obtiene_menu_admin() -> None:
    resultado = asignar_menus(propietario_ids=set(), dev_ids=set(), admin_ids={3})
    assert resultado == {3: "admin"}


def test_propietario_que_tambien_es_admin_obtiene_propietario() -> None:
    """Garay is both propietario AND es_admin → propietario wins over admin."""
    resultado = asignar_menus(propietario_ids={1}, dev_ids=set(), admin_ids={1})
    assert resultado == {1: "propietario"}


def test_dev_que_tambien_es_admin_obtiene_propietario() -> None:
    resultado = asignar_menus(propietario_ids=set(), dev_ids={2}, admin_ids={2})
    assert resultado == {2: "propietario"}


def test_conjuntos_vacios_devuelve_dict_vacio() -> None:
    assert asignar_menus(propietario_ids=set(), dev_ids=set(), admin_ids=set()) == {}


def test_mezcla_de_roles() -> None:
    resultado = asignar_menus(
        propietario_ids={1},
        dev_ids={2},
        admin_ids={1, 3, 4},
    )
    assert resultado == {1: "propietario", 2: "propietario", 3: "admin", 4: "admin"}
