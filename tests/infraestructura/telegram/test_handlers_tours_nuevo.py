"""Tests for /nuevo_tour conversation handler — PR 2 (Telegram surface).

Strict TDD: RED tests written first, then GREEN implementation.
All handler state-transition tests exercise the PTB router, NOT bare functions.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.ext import ConversationHandler

from garay.dominio.servicios.entidades import Servicio

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _servicio(
    nombre: str = "City Tour",
    categoria: str = "PLAYERO",
    activo: bool = True,
    neto_adulto: Decimal | None = None,
    neto_nino: Decimal | None = None,
    numero: int = 1,
) -> Servicio:
    return Servicio(
        id=uuid.uuid4(),
        numero=numero,
        nombre=nombre,
        categoria=categoria,
        activo=activo,
        precio_neto_adulto=neto_adulto,
        precio_neto_nino=neto_nino,
    )


def _make_update(text: str | None = None, callback_data: str | None = None) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock(id=42)
    update.effective_message = AsyncMock()
    if text is not None:
        update.effective_message.text = text
    else:
        update.effective_message.text = None
    if callback_data is not None:
        query = AsyncMock()
        query.data = callback_data
        query.answer = AsyncMock()
        update.callback_query = query
    else:
        update.callback_query = None
    return update


def _make_context(
    servicios: list[Servicio] | None = None,
    user_data: dict[str, object] | None = None,
    siguiente_numero: int = 1,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user_data = user_data if user_data is not None else {}
    repo = MagicMock()
    svcs = servicios or []
    repo.listar.return_value = svcs
    repo.listar_activos.return_value = [s for s in svcs if s.activo]
    repo.buscar_por_nombre.return_value = None
    repo.siguiente_numero.return_value = siguiente_numero
    fsm = MagicMock()
    ctx.bot_data = {"servicio_repo": repo, "fsm": fsm}
    return ctx


# ---------------------------------------------------------------------------
# Task 2.1 RED — State constants + FSM range test (no PTB needed, pure constants)
# ---------------------------------------------------------------------------


class TestNvtStateConstants:
    """NVT_* constants must be unique, in range 230-236, and correctly valued."""

    def test_nvt_familia_equals_230(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_FAMILIA

        assert NVT_FAMILIA == 230

    def test_nvt_nueva_familia_equals_231(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_NUEVA_FAMILIA

        assert NVT_NUEVA_FAMILIA == 231

    def test_nvt_nombre_equals_232(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_NOMBRE

        assert NVT_NOMBRE == 232

    def test_nvt_neto_adulto_equals_233(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_NETO_ADULTO

        assert NVT_NETO_ADULTO == 233

    def test_nvt_neto_nino_equals_234(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_NETO_NINO

        assert NVT_NETO_NINO == 234

    def test_nvt_confirma_equals_235(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_CONFIRMA

        assert NVT_CONFIRMA == 235

    def test_nvt_dup_confirma_equals_236(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_DUP_CONFIRMA

        assert NVT_DUP_CONFIRMA == 236

    def test_all_nvt_states_unique(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            NVT_DUP_CONFIRMA,
            NVT_FAMILIA,
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_NOMBRE,
            NVT_NUEVA_FAMILIA,
        )

        states = [
            NVT_FAMILIA,
            NVT_NUEVA_FAMILIA,
            NVT_NOMBRE,
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_CONFIRMA,
            NVT_DUP_CONFIRMA,
        ]
        assert len(states) == len(set(states)), "NVT_* states must all be unique"

    def test_all_nvt_states_in_range(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            NVT_DUP_CONFIRMA,
            NVT_FAMILIA,
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_NOMBRE,
            NVT_NUEVA_FAMILIA,
        )

        states = [
            NVT_FAMILIA,
            NVT_NUEVA_FAMILIA,
            NVT_NOMBRE,
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_CONFIRMA,
            NVT_DUP_CONFIRMA,
        ]
        for s in states:
            assert 230 <= s <= 236, f"State {s} is outside range 230-236"

    def test_no_collision_with_edf_elt_states(self) -> None:
        """NVT_* must not overlap EDF_* or ELT_* state ranges (220-228)."""
        from garay.infraestructura.telegram.handlers_tours import (
            EDF_CAMPO,
            EDF_CONFIRMA,
            EDF_FAMILIA,
            EDF_FICHA,
            EDF_NUEVA_FAMILIA,
            EDF_TOUR,
            ELT_CONFIRMA,
            ELT_FAMILIA,
            ELT_TOUR,
            NVT_CONFIRMA,
            NVT_DUP_CONFIRMA,
            NVT_FAMILIA,
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_NOMBRE,
            NVT_NUEVA_FAMILIA,
        )

        fase1_states = {
            EDF_FAMILIA, EDF_TOUR, EDF_FICHA, EDF_CAMPO, EDF_CONFIRMA, EDF_NUEVA_FAMILIA,
            ELT_FAMILIA, ELT_TOUR, ELT_CONFIRMA,
        }
        nvt_states = {
            NVT_FAMILIA, NVT_NUEVA_FAMILIA, NVT_NOMBRE,
            NVT_NETO_ADULTO, NVT_NETO_NINO, NVT_CONFIRMA, NVT_DUP_CONFIRMA,
        }
        overlap = fase1_states & nvt_states
        assert not overlap, f"State collision with Fase 1: {overlap}"


# ---------------------------------------------------------------------------
# Task 2.3 RED — Pure helper functions (unit tests, no async/PTB)
# ---------------------------------------------------------------------------


class TestNormalizarFamilia:
    """_normalizar_familia: trim + UPPERCASE + collapse internal spaces."""

    def test_trim_y_mayusculas(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _normalizar_familia

        assert _normalizar_familia("  playero  ") == "PLAYERO"

    def test_solo_mayusculas(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _normalizar_familia

        assert _normalizar_familia("nocturno") == "NOCTURNO"

    def test_colapsa_espacios_internos(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _normalizar_familia

        assert _normalizar_familia("city  tour") == "CITY TOUR"

    def test_ya_normalizado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _normalizar_familia

        assert _normalizar_familia("CULTURAL") == "CULTURAL"


class TestReusarFamilia:
    """_reusar_familia: return existing casing when match found, else normalized."""

    def test_retorna_casing_existente(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _reusar_familia

        servicios = [_servicio(categoria="Playero")]
        result = _reusar_familia("PLAYERO", servicios)
        assert result == "Playero"

    def test_sin_coincidencia_retorna_normalizada(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _reusar_familia

        result = _reusar_familia("NOCTURNO", [])
        assert result == "NOCTURNO"

    def test_coincidencia_case_insensitive(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _reusar_familia

        servicios = [_servicio(categoria="Cultural"), _servicio(categoria="Playero")]
        assert _reusar_familia("CULTURAL", servicios) == "Cultural"

    def test_primer_coincidencia_gana(self) -> None:
        """When multiple services share the same normalized family, first one wins."""
        from garay.infraestructura.telegram.handlers_tours import _reusar_familia

        servicios = [_servicio(categoria="Playero"), _servicio(categoria="PLAYERO")]
        result = _reusar_familia("PLAYERO", servicios)
        assert result == "Playero"  # first match


class TestLimpiarNvt:
    """_limpiar_nvt: removes all nvt_* keys from user_data."""

    def test_limpia_todas_las_claves_nvt(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _limpiar_nvt

        ctx = MagicMock()
        ctx.user_data = {
            "nvt_servicios": [],
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "City Tour",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
            "nvt_editando": False,
            "otro_campo": "keep",
        }
        _limpiar_nvt(ctx)
        for key in ("nvt_servicios", "nvt_familia", "nvt_nombre",
                    "nvt_neto_adulto", "nvt_neto_nino", "nvt_editando"):
            assert key not in ctx.user_data
        assert ctx.user_data.get("otro_campo") == "keep"

    def test_no_falla_con_user_data_none(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _limpiar_nvt

        ctx = MagicMock()
        ctx.user_data = None
        _limpiar_nvt(ctx)  # must not raise


class TestRenderFichaNuevo:
    """_render_ficha_nuevo: renders family, name, and '—' for None netos."""

    def test_incluye_familia_y_nombre(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _render_ficha_nuevo

        ud: dict[str, object] = {
            "nvt_familia": "CULTURAL",
            "nvt_nombre": "Tour Colonial",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        }
        result = _render_ficha_nuevo(ud)
        assert "CULTURAL" in result
        assert "Tour Colonial" in result

    def test_none_neto_muestra_guion(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _render_ficha_nuevo

        ud: dict[str, object] = {
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "Tour Playa",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        }
        result = _render_ficha_nuevo(ud)
        assert "—" in result

    def test_neto_decimal_se_muestra(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import _render_ficha_nuevo

        ud: dict[str, object] = {
            "nvt_familia": "CULTURAL",
            "nvt_nombre": "Tour Colonial",
            "nvt_neto_adulto": Decimal("120000"),
            "nvt_neto_nino": Decimal("80000"),
        }
        result = _render_ficha_nuevo(ud)
        assert "120000" in result
        assert "80000" in result


# ---------------------------------------------------------------------------
# Task 2.5 RED — Entry + family selection via PTB router
# ---------------------------------------------------------------------------


class TestCmdNuevoTour:
    """cmd_nuevo_tour: entry point displays family buttons, loads servicios into user_data."""

    @pytest.mark.asyncio
    async def test_muestra_botones_de_familia(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_FAMILIA,
            cmd_nuevo_tour,
        )

        s1 = _servicio("City Tour", "PLAYERO")
        s2 = _servicio("Islas", "CULTURAL")
        update = _make_update()
        ctx = _make_context(servicios=[s1, s2])

        result = await cmd_nuevo_tour.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert result == NVT_FAMILIA
        update.effective_message.reply_text.assert_called_once()
        # Keyboard must include a "Nueva familia" button
        call_kwargs = update.effective_message.reply_text.call_args[1]
        markup = call_kwargs.get("reply_markup")
        assert markup is not None
        all_labels = [btn.text for row in markup.inline_keyboard for btn in row]
        assert any("Nueva familia" in label for label in all_labels)

    @pytest.mark.asyncio
    async def test_carga_servicios_en_user_data(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import cmd_nuevo_tour

        s1 = _servicio("City Tour", "PLAYERO")
        update = _make_update()
        ctx = _make_context(servicios=[s1])

        await cmd_nuevo_tour.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        assert "nvt_servicios" in ctx.user_data
        assert ctx.user_data["nvt_servicios"] == [s1]

    @pytest.mark.asyncio
    async def test_usa_listar_activos_no_listar(self) -> None:
        """Entry point must call listar_activos() to build family buttons, not listar()."""
        from garay.infraestructura.telegram.handlers_tours import cmd_nuevo_tour

        s1 = _servicio("City Tour", "PLAYERO")
        update = _make_update()
        ctx = _make_context(servicios=[s1])

        await cmd_nuevo_tour.__wrapped__(update, ctx)  # type: ignore[attr-defined]

        ctx.bot_data["servicio_repo"].listar_activos.assert_called_once()
        ctx.bot_data["servicio_repo"].listar.assert_not_called()


class TestHandleNvtFamilia:
    """handle_nvt_familia: family button press stores familia and advances to NVT_NOMBRE."""

    @pytest.mark.asyncio
    async def test_seleccionar_familia_existente_avanza_a_nombre(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_familia,
        )

        update = _make_update(callback_data="nvt_familia:PLAYERO")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_familia(update, ctx)

        assert result == NVT_NOMBRE
        assert ctx.user_data.get("nvt_familia") == "PLAYERO"

    @pytest.mark.asyncio
    async def test_boton_nueva_familia_avanza_a_nvt_nueva_familia(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NUEVA_FAMILIA,
            handle_nvt_familia,
        )

        update = _make_update(callback_data="nvt_familia_nueva_libre")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_familia(update, ctx)

        assert result == NVT_NUEVA_FAMILIA

    @pytest.mark.asyncio
    async def test_edit_familia_desde_confirma_avanza_a_familia(self) -> None:
        """handle_nvt_edit for familia → NVT_FAMILIA (re-entry from confirmation)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_FAMILIA,
            handle_nvt_edit,
        )

        update = _make_update(callback_data="nvt_edit:familia")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_edit(update, ctx)

        assert result == NVT_FAMILIA
        assert ctx.user_data.get("nvt_editando") is True


# ---------------------------------------------------------------------------
# Task 2.7 RED — Nueva familia text input
# ---------------------------------------------------------------------------


class TestHandleNvtNuevaFamilia:
    """handle_nvt_nueva_familia: normalizes text, reuses existing family, advances to NVT_NOMBRE."""

    @pytest.mark.asyncio
    async def test_texto_vacio_rechazado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NUEVA_FAMILIA,
            handle_nvt_nueva_familia,
        )

        update = _make_update(text="   ")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nueva_familia(update, ctx)

        assert result == NVT_NUEVA_FAMILIA

    @pytest.mark.asyncio
    async def test_familia_nueva_normaliza_y_avanza(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_nueva_familia,
        )

        update = _make_update(text="  nocturno  ")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nueva_familia(update, ctx)

        assert result == NVT_NOMBRE
        assert ctx.user_data.get("nvt_familia") == "NOCTURNO"

    @pytest.mark.asyncio
    async def test_familia_existente_case_insensitive_reutiliza(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_nueva_familia,
        )

        s1 = _servicio("City Tour", "Playero")
        update = _make_update(text="playero")
        ctx = _make_context(servicios=[s1])
        ctx.user_data["nvt_servicios"] = [s1]

        result = await handle_nvt_nueva_familia(update, ctx)

        assert result == NVT_NOMBRE
        # Must reuse the existing casing "Playero", not "PLAYERO"
        assert ctx.user_data.get("nvt_familia") == "Playero"


# ---------------------------------------------------------------------------
# Task 2.9 RED — Nombre capture (NVT_NOMBRE state)
# ---------------------------------------------------------------------------


class TestHandleNvtNombre:
    """handle_nvt_nombre: validates name, checks duplicates, advances state accordingly."""

    @pytest.mark.asyncio
    async def test_nombre_vacio_rechazado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_nombre,
        )

        update = _make_update(text="   ")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_NOMBRE

    @pytest.mark.asyncio
    async def test_nombre_unico_avanza_a_neto_adulto(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_nombre,
        )

        update = _make_update(text="City Tour Mágico")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []
        ctx.bot_data["servicio_repo"].buscar_por_nombre.return_value = None

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_NETO_ADULTO
        assert ctx.user_data.get("nvt_nombre") == "City Tour Mágico"

    @pytest.mark.asyncio
    async def test_nombre_duplicado_avanza_a_dup_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_DUP_CONFIRMA,
            handle_nvt_nombre,
        )

        s_existing = _servicio("City Tour")
        update = _make_update(text="City Tour")
        # Pass servicios so listar() returns the existing tour (case-insensitive check)
        ctx = _make_context(servicios=[s_existing])
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_DUP_CONFIRMA

    @pytest.mark.asyncio
    async def test_re_edit_nombre_vuelve_a_confirma_tras_guardar(self) -> None:
        """When nvt_editando=True, after valid unique name → NVT_CONFIRMA (not NVT_NETO_ADULTO)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_nombre,
        )

        update = _make_update(text="Nuevo Nombre")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_neto_adulto"] = None
        ctx.user_data["nvt_neto_nino"] = None
        ctx.bot_data["servicio_repo"].buscar_por_nombre.return_value = None

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_CONFIRMA
        # Must clear nvt_editando flag
        assert not ctx.user_data.get("nvt_editando")


# ---------------------------------------------------------------------------
# Task 2.11 RED — Duplicate name confirmation (NVT_DUP_CONFIRMA state)
# ---------------------------------------------------------------------------


class TestHandleNvtDup:
    """handle_nvt_dup: usar → NVT_NETO_ADULTO; cambiar → NVT_NOMBRE."""

    @pytest.mark.asyncio
    async def test_usar_igual_avanza_a_neto_adulto(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_dup,
        )

        update = _make_update(callback_data="nvt_dup:usar")
        ctx = _make_context()
        ctx.user_data["nvt_nombre_pendiente"] = "City Tour"

        result = await handle_nvt_dup(update, ctx)

        assert result == NVT_NETO_ADULTO
        assert ctx.user_data.get("nvt_nombre") == "City Tour"

    @pytest.mark.asyncio
    async def test_cambiar_vuelve_a_nombre(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_dup,
        )

        update = _make_update(callback_data="nvt_dup:cambiar")
        ctx = _make_context()

        result = await handle_nvt_dup(update, ctx)

        assert result == NVT_NOMBRE

    @pytest.mark.asyncio
    async def test_re_edit_dup_usar_vuelve_a_confirma(self) -> None:
        """When nvt_editando=True, usar → NVT_CONFIRMA (not NVT_NETO_ADULTO)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_dup,
        )

        update = _make_update(callback_data="nvt_dup:usar")
        ctx = _make_context()
        ctx.user_data["nvt_nombre_pendiente"] = "City Tour"
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_neto_adulto"] = None
        ctx.user_data["nvt_neto_nino"] = None

        result = await handle_nvt_dup(update, ctx)

        assert result == NVT_CONFIRMA


# ---------------------------------------------------------------------------
# Task 2.13 RED — Neto adulto capture (NVT_NETO_ADULTO state)
# ---------------------------------------------------------------------------


class TestHandleNvtNetoAdulto:
    """handle_nvt_neto_adulto: empty→None skip; valid>0→Decimal; invalid/<=0→error."""

    @pytest.mark.asyncio
    async def test_texto_vacio_skip_almacena_none(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_NINO,
            handle_nvt_neto_adulto,
        )

        update = _make_update(text="")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_NETO_NINO
        assert ctx.user_data.get("nvt_neto_adulto") is None

    @pytest.mark.asyncio
    async def test_boton_saltar_almacena_none(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_NINO,
            handle_nvt_neto_adulto,
        )

        update = _make_update(callback_data="nvt_saltar_neto_adulto")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_NETO_NINO
        assert ctx.user_data.get("nvt_neto_adulto") is None

    @pytest.mark.asyncio
    async def test_valor_valido_almacena_decimal(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_NINO,
            handle_nvt_neto_adulto,
        )

        # Colombian format: dot is thousands separator → "120.000" = 120000
        update = _make_update(text="120.000")
        ctx = _make_context()

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_NETO_NINO
        assert ctx.user_data.get("nvt_neto_adulto") == Decimal("120000")

    @pytest.mark.asyncio
    async def test_cero_rechazado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_neto_adulto,
        )

        update = _make_update(text="0")
        ctx = _make_context()

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_NETO_ADULTO

    @pytest.mark.asyncio
    async def test_negativo_rechazado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_neto_adulto,
        )

        update = _make_update(text="-50")
        ctx = _make_context()

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_NETO_ADULTO

    @pytest.mark.asyncio
    async def test_re_edit_neto_adulto_vuelve_a_confirma(self) -> None:
        """When nvt_editando=True, valid value → NVT_CONFIRMA (not NVT_NETO_NINO)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_neto_adulto,
        )

        update = _make_update(text="80000")
        ctx = _make_context()
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "Tour"
        ctx.user_data["nvt_neto_nino"] = None

        result = await handle_nvt_neto_adulto(update, ctx)

        assert result == NVT_CONFIRMA
        assert not ctx.user_data.get("nvt_editando")


# ---------------------------------------------------------------------------
# Task 2.15 RED — Neto niño capture (NVT_NETO_NINO state)
# ---------------------------------------------------------------------------


class TestHandleNvtNetoNino:
    """handle_nvt_neto_nino: same logic as neto adulto but advances to NVT_CONFIRMA."""

    @pytest.mark.asyncio
    async def test_texto_vacio_skip_avanza_a_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_neto_nino,
        )

        update = _make_update(text="")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "Tour"
        ctx.user_data["nvt_neto_adulto"] = None

        result = await handle_nvt_neto_nino(update, ctx)

        assert result == NVT_CONFIRMA
        assert ctx.user_data.get("nvt_neto_nino") is None

    @pytest.mark.asyncio
    async def test_boton_saltar_avanza_a_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_neto_nino,
        )

        update = _make_update(callback_data="nvt_saltar_neto_nino")
        ctx = _make_context()
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "Tour"
        ctx.user_data["nvt_neto_adulto"] = None

        result = await handle_nvt_neto_nino(update, ctx)

        assert result == NVT_CONFIRMA
        assert ctx.user_data.get("nvt_neto_nino") is None

    @pytest.mark.asyncio
    async def test_valor_valido_almacena_decimal(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_neto_nino,
        )

        # Colombian format: dot is thousands separator → "80.000" = 80000
        update = _make_update(text="80.000")
        ctx = _make_context()
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "Tour"
        ctx.user_data["nvt_neto_adulto"] = None

        result = await handle_nvt_neto_nino(update, ctx)

        assert result == NVT_CONFIRMA
        assert ctx.user_data.get("nvt_neto_nino") == Decimal("80000")

    @pytest.mark.asyncio
    async def test_cero_rechazado(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_NINO,
            handle_nvt_neto_nino,
        )

        update = _make_update(text="0")
        ctx = _make_context()

        result = await handle_nvt_neto_nino(update, ctx)

        assert result == NVT_NETO_NINO

    @pytest.mark.asyncio
    async def test_re_edit_neto_nino_vuelve_a_confirma_sin_encadenar(self) -> None:
        """When nvt_editando=True, valid value → NVT_CONFIRMA (same as normal path for nino)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_neto_nino,
        )

        update = _make_update(text="60000")
        ctx = _make_context()
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "Tour"
        ctx.user_data["nvt_neto_adulto"] = None

        result = await handle_nvt_neto_nino(update, ctx)

        assert result == NVT_CONFIRMA
        assert not ctx.user_data.get("nvt_editando")


# ---------------------------------------------------------------------------
# Task 2.17 RED — Confirmation screen (NVT_CONFIRMA state)
# ---------------------------------------------------------------------------


class TestHandleNvtCancelar:
    """handle_nvt_cancelar: clears nvt_* keys and ends conversation."""

    @pytest.mark.asyncio
    async def test_cancelar_limpia_y_termina(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_cancelar

        update = _make_update(callback_data="nvt_cancelar")
        ctx = _make_context()
        ctx.user_data.update({
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "Tour",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        })

        result = await handle_nvt_cancelar(update, ctx)

        assert result == ConversationHandler.END
        for key in ("nvt_familia", "nvt_nombre", "nvt_neto_adulto", "nvt_neto_nino"):
            assert key not in ctx.user_data


class TestHandleNvtEdit:
    """handle_nvt_edit: sets nvt_editando=True, returns the target field's state."""

    @pytest.mark.asyncio
    async def test_editar_nombre_desde_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NOMBRE,
            handle_nvt_edit,
        )

        update = _make_update(callback_data="nvt_edit:nombre")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_edit(update, ctx)

        assert result == NVT_NOMBRE
        assert ctx.user_data.get("nvt_editando") is True

    @pytest.mark.asyncio
    async def test_editar_neto_adulto_desde_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_edit,
        )

        update = _make_update(callback_data="nvt_edit:neto_adulto")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_edit(update, ctx)

        assert result == NVT_NETO_ADULTO
        assert ctx.user_data.get("nvt_editando") is True

    @pytest.mark.asyncio
    async def test_editar_neto_nino_desde_confirma(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_NINO,
            handle_nvt_edit,
        )

        update = _make_update(callback_data="nvt_edit:neto_nino")
        ctx = _make_context()
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_edit(update, ctx)

        assert result == NVT_NETO_NINO
        assert ctx.user_data.get("nvt_editando") is True

    @pytest.mark.asyncio
    async def test_re_editar_nombre_no_borra_otros_campos(self) -> None:
        """Edit one field, verify others remain untouched in user_data."""
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_edit

        update = _make_update(callback_data="nvt_edit:nombre")
        ctx = _make_context()
        ctx.user_data.update({
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "Tour Original",
            "nvt_neto_adulto": Decimal("100000"),
            "nvt_neto_nino": None,
            "nvt_servicios": [],
        })

        await handle_nvt_edit(update, ctx)

        # Other fields must survive untouched
        assert ctx.user_data.get("nvt_familia") == "PLAYERO"
        assert ctx.user_data.get("nvt_neto_adulto") == Decimal("100000")
        assert ctx.user_data.get("nvt_neto_nino") is None


# ---------------------------------------------------------------------------
# Task 2.19 RED — Creation (handle_nvt_crear)
# ---------------------------------------------------------------------------


class TestHandleNvtCrear:
    """handle_nvt_crear: builds Servicio, calls guardar, refreshes FSM, replies ok."""

    @pytest.mark.asyncio
    async def test_crear_llama_guardar_y_refrescar_fsm(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(siguiente_numero=3)
        ctx.user_data.update({
            "nvt_familia": "CULTURAL",
            "nvt_nombre": "Tour Colonial",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        })

        result = await handle_nvt_crear(update, ctx)

        assert result == ConversationHandler.END
        ctx.bot_data["servicio_repo"].guardar.assert_called_once()
        ctx.bot_data["fsm"].refrescar_servicios.assert_called_once()

    @pytest.mark.asyncio
    async def test_crear_servicio_tiene_campos_correctos(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(siguiente_numero=5)
        # Decimals already parsed — stored directly in user_data
        ctx.user_data.update({
            "nvt_familia": "CULTURAL",
            "nvt_nombre": "Tour Colonial",
            "nvt_neto_adulto": Decimal("120000"),
            "nvt_neto_nino": Decimal("60000"),
        })

        await handle_nvt_crear(update, ctx)

        saved = ctx.bot_data["servicio_repo"].guardar.call_args[0][0]
        assert saved.numero == 5
        assert saved.nombre == "Tour Colonial"
        assert saved.categoria == "CULTURAL"
        assert saved.precio_neto_adulto == Decimal("120000")
        assert saved.precio_neto_nino == Decimal("60000")
        assert saved.activo is True
        assert saved.descripcion == ""

    @pytest.mark.asyncio
    async def test_crear_limpia_nvt_keys(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(siguiente_numero=1)
        ctx.user_data.update({
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "Tour Playa",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        })

        await handle_nvt_crear(update, ctx)

        for key in ("nvt_familia", "nvt_nombre", "nvt_neto_adulto", "nvt_neto_nino"):
            assert key not in ctx.user_data

    @pytest.mark.asyncio
    async def test_crear_responde_con_tour_creado_ok(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(siguiente_numero=1)
        ctx.user_data.update({
            "nvt_familia": "PLAYERO",
            "nvt_nombre": "Tour Playa",
            "nvt_neto_adulto": None,
            "nvt_neto_nino": None,
        })

        await handle_nvt_crear(update, ctx)

        update.effective_message.reply_text.assert_called()
        # At least one reply must contain the tour name
        texts = [str(c[0][0]) for c in update.effective_message.reply_text.call_args_list]
        assert any("Tour Playa" in t for t in texts)


# ---------------------------------------------------------------------------
# Fix W-1 RED — Case-insensitive duplicate name detection
# ---------------------------------------------------------------------------


class TestHandleNvtNombreCaseInsensitive:
    """handle_nvt_nombre must detect duplicates case-insensitively (owner decision)."""

    @pytest.mark.asyncio
    async def test_nombre_duplicado_case_insensitive_avisa(self) -> None:
        """'islas del rosario' with existing 'Islas del Rosario' → NVT_DUP_CONFIRMA."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_DUP_CONFIRMA,
            handle_nvt_nombre,
        )

        existing = _servicio(nombre="Islas del Rosario")
        update = _make_update(text="islas del rosario")
        ctx = _make_context(servicios=[existing])
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_DUP_CONFIRMA

    @pytest.mark.asyncio
    async def test_nombre_duplicado_exacto_sigue_avisando(self) -> None:
        """Exact match 'Islas del Rosario' still → NVT_DUP_CONFIRMA (regression guard)."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_DUP_CONFIRMA,
            handle_nvt_nombre,
        )

        existing = _servicio(nombre="Islas del Rosario")
        update = _make_update(text="Islas del Rosario")
        ctx = _make_context(servicios=[existing])
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_DUP_CONFIRMA

    @pytest.mark.asyncio
    async def test_nombre_nuevo_no_avisa(self) -> None:
        """A genuinely new name → NVT_NETO_ADULTO, no dup warning."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            handle_nvt_nombre,
        )

        existing = _servicio(nombre="Islas del Rosario")
        update = _make_update(text="Tour Nocturno")
        ctx = _make_context(servicios=[existing])
        ctx.user_data["nvt_servicios"] = []

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_NETO_ADULTO

    @pytest.mark.asyncio
    async def test_re_edit_nombre_case_insensitive_duplicado_avisa(self) -> None:
        """During re-edit, case-insensitive dup → NVT_DUP_CONFIRMA, nvt_editando preserved."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_DUP_CONFIRMA,
            handle_nvt_nombre,
        )

        existing = _servicio(nombre="City Tour")
        update = _make_update(text="CITY TOUR")
        ctx = _make_context(servicios=[existing])
        ctx.user_data["nvt_servicios"] = []
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_neto_adulto"] = None
        ctx.user_data["nvt_neto_nino"] = None

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_DUP_CONFIRMA
        # nvt_editando must still be set so the dup handler can return to NVT_CONFIRMA
        assert ctx.user_data.get("nvt_editando") is True


# ---------------------------------------------------------------------------
# Fix W-2 RED — Dead handler registration in NVT_FAMILIA must be removed
# ---------------------------------------------------------------------------


class TestNvtFamiliaDeadHandlerRemoved:
    """NVT_FAMILIA must not contain handle_nvt_edit; [Editar familia] fires from NVT_CONFIRMA."""

    def test_nvt_familia_sin_nvt_edit_handler(self) -> None:
        """NVT_FAMILIA state must not include handle_nvt_edit as a CallbackQueryHandler."""
        from telegram.ext import CallbackQueryHandler, ConversationHandler

        from garay.infraestructura.telegram import handlers_tours
        from garay.infraestructura.telegram.bot import crear_aplicacion

        app = crear_aplicacion("fake-token-for-test")
        group8 = app.handlers.get(8, [])
        nvt_conv: ConversationHandler | None = None  # type: ignore[type-arg]
        for h in group8:
            if isinstance(h, ConversationHandler) and handlers_tours.NVT_FAMILIA in h.states:
                nvt_conv = h
                break
        assert nvt_conv is not None, "nuevo_tour ConversationHandler not found in group=8"

        familia_handlers = nvt_conv.states.get(handlers_tours.NVT_FAMILIA, [])
        edit_cbs = [
            h for h in familia_handlers
            if isinstance(h, CallbackQueryHandler)
            and h.callback is handlers_tours.handle_nvt_edit
        ]
        assert len(edit_cbs) == 0, (
            f"NVT_FAMILIA must not register handle_nvt_edit; found {len(edit_cbs)} callback(s)"
        )

    def test_nvt_confirma_tiene_editar_familia(self) -> None:
        """NVT_CONFIRMA still fires handle_nvt_edit for 'nvt_edit:familia' (regression guard)."""
        from telegram.ext import CallbackQueryHandler, ConversationHandler

        from garay.infraestructura.telegram import handlers_tours
        from garay.infraestructura.telegram.bot import crear_aplicacion

        app = crear_aplicacion("fake-token-for-test")
        group8 = app.handlers.get(8, [])
        nvt_conv: ConversationHandler | None = None  # type: ignore[type-arg]
        for h in group8:
            if isinstance(h, ConversationHandler) and handlers_tours.NVT_FAMILIA in h.states:
                nvt_conv = h
                break
        assert nvt_conv is not None

        confirma_handlers = nvt_conv.states.get(handlers_tours.NVT_CONFIRMA, [])
        edit_cbs = [
            h for h in confirma_handlers
            if isinstance(h, CallbackQueryHandler)
            and h.callback is handlers_tours.handle_nvt_edit
        ]
        assert len(edit_cbs) == 1, (
            f"NVT_CONFIRMA must have exactly 1 handle_nvt_edit callback; found {len(edit_cbs)}"
        )


# ---------------------------------------------------------------------------
# Fix S-1 RED — Re-edit "Cambiar nombre" path with a second duplicate name
# ---------------------------------------------------------------------------


class TestReEditNombreSegundoDuplicado:
    """S-1: re-edit 'Cambiar nombre' with another dup → re-warn, nvt_editando preserved."""

    @pytest.mark.asyncio
    async def test_re_edit_cambiar_nombre_duplicado_vuelve_a_avisar(self) -> None:
        """nvt_editando=True, 'cambiar', types another dup → NVT_DUP_CONFIRMA, editando intact."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_DUP_CONFIRMA,
            handle_nvt_nombre,
        )

        existing_a = _servicio(nombre="City Tour")
        existing_b = _servicio(nombre="Tour Nocturno", numero=2)
        # Scenario: user was re-editing nombre, changed to "tour nocturno" (another dup)
        update = _make_update(text="tour nocturno")
        ctx = _make_context(servicios=[existing_a, existing_b])
        ctx.user_data["nvt_servicios"] = []
        ctx.user_data["nvt_editando"] = True
        ctx.user_data["nvt_familia"] = "PLAYERO"
        ctx.user_data["nvt_nombre"] = "City Tour"  # current name being replaced
        ctx.user_data["nvt_neto_adulto"] = Decimal("100000")
        ctx.user_data["nvt_neto_nino"] = None

        result = await handle_nvt_nombre(update, ctx)

        assert result == NVT_DUP_CONFIRMA
        # nvt_editando must remain so handle_nvt_dup "usar" can route back to NVT_CONFIRMA
        assert ctx.user_data.get("nvt_editando") is True
        # pending name stored correctly
        assert ctx.user_data.get("nvt_nombre_pendiente") == "tour nocturno"


# ---------------------------------------------------------------------------
# Task 2.21 RED — Menu visibility tests
# ---------------------------------------------------------------------------


class TestMenuNuevoTour:
    """nuevo_tour must appear for ADMIN tier and NOT for FREELANCER tier."""

    def test_nuevo_tour_visible_para_admin(self) -> None:
        from garay.infraestructura.telegram.menu import TierComando, comandos_para_tier

        comandos = comandos_para_tier(TierComando.ADMIN)
        nombres = [c.comando for c in comandos]
        assert "nuevo_tour" in nombres

    def test_nuevo_tour_no_visible_para_freelancer(self) -> None:
        from garay.infraestructura.telegram.menu import TierComando, comandos_para_tier

        comandos = comandos_para_tier(TierComando.FREELANCER)
        nombres = [c.comando for c in comandos]
        assert "nuevo_tour" not in nombres

    def test_nuevo_tour_esta_en_grupo_tours(self) -> None:
        from garay.infraestructura.telegram.menu import CATALOGO_COMANDOS, GrupoComando

        nvt = next((c for c in CATALOGO_COMANDOS if c.comando == "nuevo_tour"), None)
        assert nvt is not None, "nuevo_tour must be in CATALOGO_COMANDOS"
        assert nvt.grupo == GrupoComando.TOURS


# ---------------------------------------------------------------------------
# Task 2.22 RED — Routing correctness: unique handlers per state
# ---------------------------------------------------------------------------


class TestNvtStateRouting:
    """Assert structural correctness of the ConversationHandler routing table."""

    def test_each_text_state_has_exactly_one_message_handler(self) -> None:
        """No two MessageHandler(_TEXT) in the same NVT_* text state."""
        from telegram.ext import ConversationHandler, MessageHandler

        from garay.infraestructura.telegram.bot import crear_aplicacion

        # Build the app to get the registered handlers
        app = crear_aplicacion("fake-token-for-test")
        # Find nuevo_tour_conv_handler in group=8 handlers
        group8 = app.handlers.get(8, [])
        nvt_conv: ConversationHandler | None = None  # type: ignore[type-arg]
        for h in group8:
            # Identify nuevo_tour by checking NVT_FAMILIA (230) is in its states
            if isinstance(h, ConversationHandler) and 230 in h.states:
                nvt_conv = h
                break
        assert nvt_conv is not None, "nuevo_tour ConversationHandler not found in group=8"

        # Text states that must have exactly one MessageHandler
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_NETO_ADULTO,
            NVT_NETO_NINO,
            NVT_NOMBRE,
            NVT_NUEVA_FAMILIA,
        )

        for state_id in (NVT_NUEVA_FAMILIA, NVT_NOMBRE, NVT_NETO_ADULTO, NVT_NETO_NINO):
            handlers_in_state = nvt_conv.states.get(state_id, [])
            text_handlers = [
                h for h in handlers_in_state
                if isinstance(h, MessageHandler)
            ]
            assert len(text_handlers) == 1, (
                f"State {state_id} has {len(text_handlers)} MessageHandlers, expected exactly 1"
            )


# ---------------------------------------------------------------------------
# Task 7.1 RED -- NVT-HOR state constants + editor handlers
# ---------------------------------------------------------------------------


class TestNvtHorStateConstants:
    """NVT_HOR_* constants must be defined, unique, in range 240-241."""

    def test_nvt_hor_lista_equals_240(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_HOR_LISTA

        assert NVT_HOR_LISTA == 240

    def test_nvt_hor_agregar_equals_241(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import NVT_HOR_AGREGAR

        assert NVT_HOR_AGREGAR == 241

    def test_nvt_hor_constants_unique(self) -> None:
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_AGREGAR,
            NVT_HOR_LISTA,
        )

        assert NVT_HOR_LISTA != NVT_HOR_AGREGAR


class TestHandleNvtEditHorarios:
    """handle_nvt_edit with campo=horarios must open the NVT-HOR editor."""

    @pytest.mark.asyncio
    async def test_nvt_edit_horarios_opens_hor_lista(self) -> None:
        """Tapping horarios from the NVT ficha must return NVT_HOR_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_LISTA,
            handle_nvt_edit,
        )

        s1 = _servicio()
        update = _make_update(callback_data="nvt_edit:horarios")
        ctx = _make_context(
            servicios=[s1],
            user_data={"nvt_horarios": []},
        )

        result = await handle_nvt_edit(update, ctx)

        assert result == NVT_HOR_LISTA

    @pytest.mark.asyncio
    async def test_nvt_edit_horarios_sends_keyboard(self) -> None:
        """Opening the NVT horarios editor must send an InlineKeyboardMarkup."""
        from telegram import InlineKeyboardMarkup

        from garay.infraestructura.telegram.handlers_tours import handle_nvt_edit

        update = _make_update(callback_data="nvt_edit:horarios")
        ctx = _make_context(user_data={"nvt_horarios": ["07:00"]})

        await handle_nvt_edit(update, ctx)

        call_args = update.effective_message.reply_text.call_args_list
        keyboards = [
            c.kwargs.get("reply_markup") or (c.args[1] if len(c.args) > 1 else None)
            for c in call_args
        ]
        assert any(isinstance(k, InlineKeyboardMarkup) for k in keyboards)


class TestHandleNvtHorLista:
    """handle_nvt_hor_lista routes nvt_hor_agregar / nvt_hor_quitar / nvt_hor_listo."""

    @pytest.mark.asyncio
    async def test_nvt_hor_agregar_goes_to_agregar_state(self) -> None:
        """Tapping agregar returns NVT_HOR_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_AGREGAR,
            handle_nvt_hor_lista,
        )

        update = _make_update(callback_data="nvt_hor_agregar")
        ctx = _make_context(user_data={"nvt_horarios": []})

        result = await handle_nvt_hor_lista(update, ctx)

        assert result == NVT_HOR_AGREGAR

    @pytest.mark.asyncio
    async def test_nvt_hor_quitar_removes_from_user_data(self) -> None:
        """Tapping X removes horario from ud[nvt_horarios] and returns NVT_HOR_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_LISTA,
            handle_nvt_hor_lista,
        )

        update = _make_update(callback_data="nvt_hor_quitar:07:00")
        ctx = _make_context(user_data={"nvt_horarios": ["07:00", "19:00"]})

        result = await handle_nvt_hor_lista(update, ctx)

        assert result == NVT_HOR_LISTA
        assert "07:00" not in ctx.user_data["nvt_horarios"]
        assert "19:00" in ctx.user_data["nvt_horarios"]

    @pytest.mark.asyncio
    async def test_nvt_hor_listo_returns_nvt_confirma(self) -> None:
        """Tapping Listo returns NVT_CONFIRMA."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_CONFIRMA,
            handle_nvt_hor_lista,
        )

        update = _make_update(callback_data="nvt_hor_listo")
        ctx = _make_context(user_data={"nvt_horarios": ["07:00"]})

        result = await handle_nvt_hor_lista(update, ctx)

        assert result == NVT_CONFIRMA


class TestHandleNvtHorAgregarTexto:
    """handle_nvt_hor_agregar_texto validates and adds horario to user_data."""

    @pytest.mark.asyncio
    async def test_horario_valido_agrega_a_ud(self) -> None:
        """Valid horario text -> add to nvt_horarios, return NVT_HOR_LISTA."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_LISTA,
            handle_nvt_hor_agregar_texto,
        )

        update = _make_update(text="8am")
        ctx = _make_context(user_data={"nvt_horarios": []})

        result = await handle_nvt_hor_agregar_texto(update, ctx)

        assert result == NVT_HOR_LISTA
        assert "08:00" in ctx.user_data["nvt_horarios"]

    @pytest.mark.asyncio
    async def test_horario_invalido_queda_en_nvt_hor_agregar(self) -> None:
        """Invalid text -> error reply, stay in NVT_HOR_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_AGREGAR,
            handle_nvt_hor_agregar_texto,
        )

        update = _make_update(text="xyz")
        ctx = _make_context(user_data={"nvt_horarios": []})

        result = await handle_nvt_hor_agregar_texto(update, ctx)

        assert result == NVT_HOR_AGREGAR

    @pytest.mark.asyncio
    async def test_horario_duplicado_queda_en_nvt_hor_agregar(self) -> None:
        """Duplicate horario -> error reply, stay in NVT_HOR_AGREGAR."""
        from garay.infraestructura.telegram.handlers_tours import (
            NVT_HOR_AGREGAR,
            handle_nvt_hor_agregar_texto,
        )

        update = _make_update(text="7pm")  # canonical 19:00
        ctx = _make_context(user_data={"nvt_horarios": ["19:00"]})

        result = await handle_nvt_hor_agregar_texto(update, ctx)

        assert result == NVT_HOR_AGREGAR


class TestNvtCrearIncludesHorarios:
    """handle_nvt_crear must pass nvt_horarios to Servicio constructor."""

    @pytest.mark.asyncio
    async def test_nvt_crear_con_horarios_persiste(self) -> None:
        """Tour created with nvt_horarios=[08:00, 14:00] must have those horarios."""
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(
            user_data={
                "nvt_familia": "PLAYERO",
                "nvt_nombre": "City Tour",
                "nvt_neto_adulto": None,
                "nvt_neto_nino": None,
                "nvt_horarios": ["08:00", "14:00"],
            },
            siguiente_numero=5,
        )

        await handle_nvt_crear(update, ctx)

        repo = ctx.bot_data["servicio_repo"]
        repo.guardar.assert_called_once()
        saved = repo.guardar.call_args[0][0]
        assert saved.horarios == ["08:00", "14:00"], (
            f"Expected horarios=[08:00, 14:00] but got {saved.horarios!r}"
        )

    @pytest.mark.asyncio
    async def test_nvt_crear_sin_horarios_usa_lista_vacia(self) -> None:
        """Tour created without nvt_horarios must have empty horarios."""
        from garay.infraestructura.telegram.handlers_tours import handle_nvt_crear

        update = _make_update(callback_data="nvt_crear")
        ctx = _make_context(
            user_data={
                "nvt_familia": "MONTANAS",
                "nvt_nombre": "Treking",
                "nvt_neto_adulto": None,
                "nvt_neto_nino": None,
                # nvt_horarios absent
            },
            siguiente_numero=1,
        )

        await handle_nvt_crear(update, ctx)

        repo = ctx.bot_data["servicio_repo"]
        saved = repo.guardar.call_args[0][0]
        assert saved.horarios == []


# ---------------------------------------------------------------------------
# Task 7.3 RED -- NVT-HOR states wired in bot.py
# ---------------------------------------------------------------------------


class TestNvtHorStatesBotWiring:
    """Structural: NVT_HOR_LISTA and NVT_HOR_AGREGAR must be in nuevo_tour_conv_handler."""

    def _get_nvt_conv(self) -> object:
        from unittest.mock import MagicMock, patch

        from telegram.ext import ConversationHandler

        from garay.infraestructura.telegram.bot import crear_aplicacion

        with patch("garay.infraestructura.telegram.bot.obtener_settings") as ms:
            settings = MagicMock()
            settings.propietario_telegram_ids = ""
            settings.dev_telegram_ids = ""
            ms.return_value = settings
            app = crear_aplicacion("fake:token")

        for _group, handlers in app.handlers.items():
            for h in handlers:
                if isinstance(h, ConversationHandler) and 230 in h.states:
                    return h
        return None

    def test_nvt_hor_lista_registered(self) -> None:
        """NVT_HOR_LISTA (240) must appear in nuevo_tour_conv_handler states."""
        from garay.infraestructura.telegram.handlers_tours import NVT_HOR_LISTA

        nvt_conv = self._get_nvt_conv()
        assert nvt_conv is not None, "nuevo_tour_conv_handler not found"
        assert NVT_HOR_LISTA in nvt_conv.states, (  # type: ignore[union-attr]
            f"NVT_HOR_LISTA ({NVT_HOR_LISTA}) not in nuevo_tour_conv_handler states"
        )

    def test_nvt_hor_agregar_registered(self) -> None:
        """NVT_HOR_AGREGAR (241) must appear in nuevo_tour_conv_handler states."""
        from garay.infraestructura.telegram.handlers_tours import NVT_HOR_AGREGAR

        nvt_conv = self._get_nvt_conv()
        assert nvt_conv is not None, "nuevo_tour_conv_handler not found"
        assert NVT_HOR_AGREGAR in nvt_conv.states, (  # type: ignore[union-attr]
            f"NVT_HOR_AGREGAR ({NVT_HOR_AGREGAR}) not in nuevo_tour_conv_handler states"
        )

    def test_nvt_hor_agregar_has_single_message_handler(self) -> None:
        """NVT_HOR_AGREGAR must have exactly ONE MessageHandler (Fase 1 lesson)."""
        from telegram.ext import MessageHandler

        from garay.infraestructura.telegram.handlers_tours import NVT_HOR_AGREGAR

        nvt_conv = self._get_nvt_conv()
        assert nvt_conv is not None
        handlers_list = nvt_conv.states.get(NVT_HOR_AGREGAR, [])  # type: ignore[union-attr]
        text_handlers = [h for h in handlers_list if isinstance(h, MessageHandler)]
        assert len(text_handlers) == 1, (
            f"NVT_HOR_AGREGAR must have exactly 1 MessageHandler, got {len(text_handlers)}"
        )
