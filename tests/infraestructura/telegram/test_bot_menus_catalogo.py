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

    def test_freelancer_count_es_5(self) -> None:
        # +1 lista_precios (FREELANCER) vs original 4
        assert len(_COMANDOS_FREELANCER) == 5

    def test_admin_count_es_18(self) -> None:
        # 19 - 1 removed (categorias_egreso — duplicate of egresos submenu) = 18
        assert len(_COMANDOS_ADMIN) == 18

    def test_propietario_count_es_22(self) -> None:
        # 23 - 1 removed (categorias_egreso) = 22
        assert len(_COMANDOS_PROPIETARIO) == 22

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


class TestListaPreciosCatalogEntry:
    """Spec: lista-precios-catalog-entry — /lista_precios must be in CATALOGO_COMANDOS."""

    def test_lista_precios_en_catalogo(self) -> None:
        """A ComandoMenu with nombre=='lista_precios' exists in CATALOGO_COMANDOS."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        nombres = [c.comando for c in CATALOGO_COMANDOS]
        assert "lista_precios" in nombres

    def test_lista_precios_tier_freelancer(self) -> None:
        """The lista_precios entry has tier FREELANCER."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS, TierComando

        entry = next((c for c in CATALOGO_COMANDOS if c.comando == "lista_precios"), None)
        assert entry is not None
        assert entry.tier == TierComando.FREELANCER

    def test_lista_precios_grupo_ventas(self) -> None:
        """The lista_precios entry belongs to the VENTAS group."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS, GrupoComando

        entry = next((c for c in CATALOGO_COMANDOS if c.comando == "lista_precios"), None)
        assert entry is not None
        assert entry.grupo == GrupoComando.VENTAS


class TestDeletedCommandsNotInCatalog:
    """Spec: catalog-entry-* (REMOVED) — deleted commands must not appear in catalog."""

    def test_deudas_no_en_catalogo(self) -> None:
        """deudas was never in CATALOGO_COMANDOS; verify it remains absent."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        assert all(c.comando != "deudas" for c in CATALOGO_COMANDOS)

    def test_flujo_caja_no_en_catalogo(self) -> None:
        """flujo_caja must not be in CATALOGO_COMANDOS after removal."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        assert all(c.comando != "flujo_caja" for c in CATALOGO_COMANDOS)

    def test_tours_reporte_no_en_catalogo(self) -> None:
        """tours (report) must not be in CATALOGO_COMANDOS after removal."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        assert all(c.comando != "tours" for c in CATALOGO_COMANDOS)

    def test_conciliar_no_en_catalogo(self) -> None:
        """conciliar must not be in CATALOGO_COMANDOS after removal."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        assert all(c.comando != "conciliar" for c in CATALOGO_COMANDOS)

    def test_pendientes_no_en_catalogo(self) -> None:
        """pendientes must not be in CATALOGO_COMANDOS after removal."""
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS

        assert all(c.comando != "pendientes" for c in CATALOGO_COMANDOS)
