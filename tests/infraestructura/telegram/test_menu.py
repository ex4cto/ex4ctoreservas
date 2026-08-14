"""Tests for menu.py — single source of truth for Telegram command menu."""

from __future__ import annotations

from telegram import BotCommand

from garay.infraestructura.telegram.menu import (
    CATALOGO_COMANDOS,
    GrupoComando,
    TierComando,
    comandos_bot,
    comandos_para_tier,
    render_menu,
    tier_de_usuario,
)


class TestCatalogo:
    """Verify catalog structure and completeness."""

    def test_catalogo_tiene_16_comandos(self) -> None:
        assert len(CATALOGO_COMANDOS) == 19

    def test_catalogo_cubre_todos_los_grupos(self) -> None:
        grupos = {c.grupo for c in CATALOGO_COMANDOS}
        assert grupos == {
            GrupoComando.VENTAS,
            GrupoComando.PAGOS,
            GrupoComando.REPORTES,
            GrupoComando.ADMINISTRACION,
            GrupoComando.TOURS,
        }

    def test_catalogo_tiene_grupo_tours(self) -> None:
        assert GrupoComando.TOURS in {c.grupo for c in CATALOGO_COMANDOS}

    def test_catalogo_tiene_editar_tour(self) -> None:
        comandos = [c.comando for c in CATALOGO_COMANDOS]
        assert "editar_tour" in comandos

    def test_catalogo_tiene_eliminar_tour(self) -> None:
        comandos = [c.comando for c in CATALOGO_COMANDOS]
        assert "eliminar_tour" in comandos

    def test_catalogo_tiene_nueva_venta(self) -> None:
        comandos = [c.comando for c in CATALOGO_COMANDOS]
        assert "nueva_venta" in comandos

    def test_catalogo_tiene_flujo_caja(self) -> None:
        comandos = [c.comando for c in CATALOGO_COMANDOS]
        assert "flujo_caja" in comandos

    def test_catalogo_tiene_editar_freelancer(self) -> None:
        comandos = [c.comando for c in CATALOGO_COMANDOS]
        assert "editar_freelancer" in comandos


class TestComandosParaTier:
    """Verify tier filtering behavior."""

    def test_freelancer_ve_solo_sus_comandos(self) -> None:
        result = comandos_para_tier(TierComando.FREELANCER)
        tiers = {c.tier for c in result}
        assert tiers == {TierComando.FREELANCER}

    def test_freelancer_ve_exactamente_4_comandos(self) -> None:
        # nueva_venta, mis_ventas, cancelar (VENTAS) + verificar_pago (PAGOS)
        result = comandos_para_tier(TierComando.FREELANCER)
        assert len(result) == 4

    def test_freelancer_no_ve_comandos_admin(self) -> None:
        result = comandos_para_tier(TierComando.FREELANCER)
        comandos = [c.comando for c in result]
        assert "editar_freelancer" not in comandos
        assert "nuevo_egreso" not in comandos
        assert "dashboard_ventas" not in comandos

    def test_freelancer_no_ve_generar_mes(self) -> None:
        """Regression: /generar_mes is admin-only and must never reach freelancers."""
        comandos = [c.comando for c in comandos_para_tier(TierComando.FREELANCER)]
        assert "generar_mes" not in comandos

    def test_admin_ve_generar_mes(self) -> None:
        comandos = [c.comando for c in comandos_para_tier(TierComando.ADMIN)]
        assert "generar_mes" in comandos

    def test_admin_ve_freelancer_y_admin(self) -> None:
        result = comandos_para_tier(TierComando.ADMIN)
        freelancer_cmds = [c for c in result if c.tier == TierComando.FREELANCER]
        admin_cmds = [c for c in result if c.tier == TierComando.ADMIN]
        assert len(freelancer_cmds) == 4
        assert len(admin_cmds) > 0

    def test_admin_no_ve_propietario(self) -> None:
        result = comandos_para_tier(TierComando.ADMIN)
        tiers = {c.tier for c in result}
        assert TierComando.PROPIETARIO not in tiers

    def test_admin_no_ve_flujo_caja(self) -> None:
        result = comandos_para_tier(TierComando.ADMIN)
        comandos = [c.comando for c in result]
        assert "flujo_caja" not in comandos
        assert "movimientos" not in comandos
        assert "tours" not in comandos

    def test_propietario_ve_todos_16(self) -> None:
        result = comandos_para_tier(TierComando.PROPIETARIO)
        assert len(result) == 19

    def test_freelancer_no_ve_editar_tour(self) -> None:
        """Regression: /editar_tour is admin-only and must never reach freelancers."""
        comandos = [c.comando for c in comandos_para_tier(TierComando.FREELANCER)]
        assert "editar_tour" not in comandos

    def test_freelancer_no_ve_eliminar_tour(self) -> None:
        """Regression: /eliminar_tour is admin-only and must never reach freelancers."""
        comandos = [c.comando for c in comandos_para_tier(TierComando.FREELANCER)]
        assert "eliminar_tour" not in comandos

    def test_admin_ve_editar_tour(self) -> None:
        comandos = [c.comando for c in comandos_para_tier(TierComando.ADMIN)]
        assert "editar_tour" in comandos

    def test_admin_ve_eliminar_tour(self) -> None:
        comandos = [c.comando for c in comandos_para_tier(TierComando.ADMIN)]
        assert "eliminar_tour" in comandos

    def test_propietario_ve_flujo_caja(self) -> None:
        result = comandos_para_tier(TierComando.PROPIETARIO)
        comandos = [c.comando for c in result]
        assert "flujo_caja" in comandos

    def test_orden_preservado_del_catalogo(self) -> None:
        """Filtered result must preserve catalog order (not reorder)."""
        result_full = comandos_para_tier(TierComando.PROPIETARIO)
        nombres = [c.comando for c in result_full]
        cat_nombres = [c.comando for c in CATALOGO_COMANDOS]
        assert nombres == cat_nombres


class TestComandosBot:
    """Verify BotCommand list output per tier."""

    def test_freelancer_retorna_4_botcommands(self) -> None:
        result = comandos_bot(TierComando.FREELANCER)
        assert len(result) == 4
        assert all(isinstance(c, BotCommand) for c in result)

    def test_admin_retorna_mas_que_freelancer(self) -> None:
        fl = comandos_bot(TierComando.FREELANCER)
        ad = comandos_bot(TierComando.ADMIN)
        assert len(ad) > len(fl)

    def test_propietario_retorna_16_botcommands(self) -> None:
        result = comandos_bot(TierComando.PROPIETARIO)
        assert len(result) == 19
        assert all(isinstance(c, BotCommand) for c in result)

    def test_botcommand_tiene_comando_y_descripcion(self) -> None:
        result = comandos_bot(TierComando.FREELANCER)
        for bc in result:
            assert bc.command
            assert bc.description


class TestRenderMenu:
    """Verify render_menu text output."""

    def test_freelancer_contiene_nueva_venta(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        assert "nueva_venta" in text

    def test_freelancer_no_contiene_flujo_caja(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        assert "flujo_caja" not in text

    def test_freelancer_no_contiene_editar_freelancer(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        assert "editar_freelancer" not in text

    def test_propietario_contiene_flujo_caja(self) -> None:
        text = render_menu(TierComando.PROPIETARIO)
        assert "flujo_caja" in text

    def test_propietario_contiene_editar_freelancer(self) -> None:
        text = render_menu(TierComando.PROPIETARIO)
        assert "editar_freelancer" in text

    def test_contiene_cabecera_bienvenida(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        assert "Garay Tours" in text

    def test_grupo_ventas_presente_para_todos(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        assert "Ventas" in text

    def test_grupo_administracion_ausente_para_freelancer(self) -> None:
        text = render_menu(TierComando.FREELANCER)
        # ADMINISTRACION group has only ADMIN tier commands
        assert "Administraci" not in text

    def test_grupo_administracion_presente_para_admin(self) -> None:
        text = render_menu(TierComando.ADMIN)
        assert "Administraci" in text

    def test_grupo_reportes_parcial_para_admin(self) -> None:
        # Admin can see dashboard_ventas but not flujo_caja/tours/movimientos
        text = render_menu(TierComando.ADMIN)
        assert "dashboard_ventas" in text
        assert "flujo_caja" not in text

    def test_no_tiene_sufijos_solo_admin(self) -> None:
        """Descriptions must NOT contain '(solo admin)' or '(solo propietario)'."""
        for tier in TierComando:
            text = render_menu(tier)
            assert "(solo admin)" not in text
            assert "(solo propietario)" not in text

    def test_sin_markdown_breakage_en_underscores(self) -> None:
        """Command names with underscores must not appear as raw Markdown _."""
        text = render_menu(TierComando.PROPIETARIO)
        # No bare underscore in a command name — must be escaped or use HTML
        # The simplest check: every underscore-containing command appears intact
        assert "nueva_venta" in text
        assert "editar_freelancer" in text
        assert "flujo_caja" in text


class TestTierDeUsuario:
    """Verify tier resolution from uid/flags/sets."""

    def test_dev_obtiene_propietario(self) -> None:
        result = tier_de_usuario(
            uid=99,
            es_admin=False,
            propietario_ids=set(),
            dev_ids={99},
        )
        assert result == TierComando.PROPIETARIO

    def test_propietario_uid_obtiene_propietario(self) -> None:
        result = tier_de_usuario(
            uid=10,
            es_admin=False,
            propietario_ids={10},
            dev_ids=set(),
        )
        assert result == TierComando.PROPIETARIO

    def test_admin_obtiene_admin(self) -> None:
        result = tier_de_usuario(
            uid=20,
            es_admin=True,
            propietario_ids=set(),
            dev_ids=set(),
        )
        assert result == TierComando.ADMIN

    def test_freelancer_regular_obtiene_freelancer(self) -> None:
        result = tier_de_usuario(
            uid=30,
            es_admin=False,
            propietario_ids=set(),
            dev_ids=set(),
        )
        assert result == TierComando.FREELANCER

    def test_uid_none_no_es_dev_ni_propietario(self) -> None:
        result = tier_de_usuario(
            uid=None,
            es_admin=False,
            propietario_ids={10},
            dev_ids={99},
        )
        assert result == TierComando.FREELANCER

    def test_propietario_que_es_admin_obtiene_propietario(self) -> None:
        """Propietario wins over admin even when es_admin=True."""
        result = tier_de_usuario(
            uid=5,
            es_admin=True,
            propietario_ids={5},
            dev_ids=set(),
        )
        assert result == TierComando.PROPIETARIO

    def test_dev_que_es_admin_obtiene_propietario(self) -> None:
        result = tier_de_usuario(
            uid=7,
            es_admin=True,
            propietario_ids=set(),
            dev_ids={7},
        )
        assert result == TierComando.PROPIETARIO
