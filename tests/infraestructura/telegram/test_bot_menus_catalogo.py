"""Tests verifying that bot.py's BotCommand lists derive from the catalog.

These are approval + integration tests that protect the refactor from
diverging the menu lists away from the CATALOGO_COMANDOS source of truth.
"""

from __future__ import annotations

from garay.infraestructura.telegram.bot import (
    _COMANDOS_ADMIN,
    _COMANDOS_FREELANCER,
    _COMANDOS_PROPIETARIO,
    _MENUS,
)
from garay.infraestructura.telegram.menu import TierComando, comandos_bot


class TestBotMenusDesdesCatalogo:
    """After refactor, bot.py lists must equal catalog-derived BotCommand lists."""

    def test_freelancer_commands_equal_catalog(self) -> None:
        expected = comandos_bot(TierComando.FREELANCER)
        assert len(_COMANDOS_FREELANCER) == len(expected)
        for bc, ex in zip(_COMANDOS_FREELANCER, expected, strict=True):
            assert bc.command == ex.command, f"{bc.command!r} != {ex.command!r}"

    def test_admin_commands_equal_catalog(self) -> None:
        expected = comandos_bot(TierComando.ADMIN)
        assert len(_COMANDOS_ADMIN) == len(expected)
        for bc, ex in zip(_COMANDOS_ADMIN, expected, strict=True):
            assert bc.command == ex.command, f"{bc.command!r} != {ex.command!r}"

    def test_propietario_commands_equal_catalog(self) -> None:
        expected = comandos_bot(TierComando.PROPIETARIO)
        assert len(_COMANDOS_PROPIETARIO) == len(expected)
        for bc, ex in zip(_COMANDOS_PROPIETARIO, expected, strict=True):
            assert bc.command == ex.command, f"{bc.command!r} != {ex.command!r}"

    def test_freelancer_count_es_4(self) -> None:
        assert len(_COMANDOS_FREELANCER) == 4

    def test_admin_count_es_16(self) -> None:
        assert len(_COMANDOS_ADMIN) == 16

    def test_propietario_count_es_21(self) -> None:
        assert len(_COMANDOS_PROPIETARIO) == 21

    def test_menus_dict_tiene_propietario_y_admin(self) -> None:
        assert "propietario" in _MENUS
        assert "admin" in _MENUS

    def test_menus_propietario_igual_al_catalog(self) -> None:
        expected = comandos_bot(TierComando.PROPIETARIO)
        propietario_cmds = _MENUS["propietario"]
        assert len(propietario_cmds) == len(expected)
        for bc, ex in zip(propietario_cmds, expected, strict=True):
            assert bc.command == ex.command

    def test_menus_admin_igual_al_catalog(self) -> None:
        expected = comandos_bot(TierComando.ADMIN)
        admin_cmds = _MENUS["admin"]
        assert len(admin_cmds) == len(expected)
        for bc, ex in zip(admin_cmds, expected, strict=True):
            assert bc.command == ex.command
