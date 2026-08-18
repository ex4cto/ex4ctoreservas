"""Single source of truth for the Telegram command catalog.

Groups, tiers, and descriptions are defined once here.
Both the Telegram menu (set_my_commands) and /start / /help replies derive
from CATALOGO_COMANDOS — they can never diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from telegram import BotCommand


class GrupoComando(StrEnum):
    """Display group for a command entry (value = header shown in the menu)."""

    VENTAS = "🎫 Ventas"
    PAGOS = "💵 Pagos y Egresos"
    REPORTES = "📊 Reportes"
    ADMINISTRACION = "👥 Administración"
    TOURS = "🗺️ Tours"


class TierComando(IntEnum):
    """Minimum permission tier required to use a command.

    Comparison: FREELANCER < ADMIN < PROPIETARIO.
    Dev users are treated as PROPIETARIO.
    """

    FREELANCER = 0
    ADMIN = 1
    PROPIETARIO = 2


@dataclass(frozen=True)
class ComandoMenu:
    """A single entry in the command catalog."""

    comando: str
    descripcion: str
    grupo: GrupoComando
    tier: TierComando


# ---------------------------------------------------------------------------
# The single source of truth.
# Edit HERE to change what appears in the Telegram menu AND in /start / /help.
# ---------------------------------------------------------------------------

_V = GrupoComando.VENTAS
_P = GrupoComando.PAGOS
_R = GrupoComando.REPORTES
_A = GrupoComando.ADMINISTRACION
_T = GrupoComando.TOURS
_FL = TierComando.FREELANCER
_AD = TierComando.ADMIN
_PR = TierComando.PROPIETARIO

CATALOGO_COMANDOS: list[ComandoMenu] = [
    # ── Ventas ──────────────────────────────────────────────────────────────
    ComandoMenu("nueva_venta", "Registrar una venta", _V, _FL),
    ComandoMenu("mis_ventas", "Mis ventas del período", _V, _FL),
    ComandoMenu("gestionar_ventas", "Gestionar ventas (anular, etc.)", _V, _AD),
    ComandoMenu("cancelar", "Cancelar operación actual", _V, _FL),
    # ── Pagos y Egresos ─────────────────────────────────────────────────────
    ComandoMenu("verificar_pago", "Pagos recibidos (últimos 5 min)", _P, _FL),
    ComandoMenu("conciliar", "Conciliar pagos con ventas", _P, _PR),
    ComandoMenu("pendientes", "Revisar conciliaciones pendientes", _P, _PR),
    ComandoMenu("nuevo_egreso", "Registrar un egreso manual", _P, _AD),
    ComandoMenu("gastos_fijos", "Ver y gestionar gastos fijos", _P, _AD),
    ComandoMenu("generar_mes", "Generar gastos fijos del mes actual", _P, _AD),
    # ── Reportes ────────────────────────────────────────────────────────────
    ComandoMenu("dashboard_ventas", "Dashboard de ventas", _R, _AD),
    ComandoMenu("flujo_caja", "Flujo de caja mensual", _R, _PR),
    ComandoMenu("tours", "Reporte de tours", _R, _PR),
    ComandoMenu("movimientos", "Movimientos recientes", _R, _AD),
    # ── Administración ──────────────────────────────────────────────────────
    ComandoMenu("listar_freelancers", "Ver freelancers registrados", _A, _AD),
    ComandoMenu("nuevo_freelancer", "Registrar un nuevo freelancer", _A, _AD),
    ComandoMenu("editar_freelancer", "Editar un freelancer", _A, _AD),
    ComandoMenu("eliminar_freelancer", "Desactivar un freelancer", _A, _AD),
    # ── Tours ────────────────────────────────────────────────────────────────
    ComandoMenu("nuevo_tour", "Crear un nuevo tour", _T, _AD),
    ComandoMenu("editar_tour", "Editar datos de un tour", _T, _AD),
    ComandoMenu("eliminar_tour", "Desactivar un tour", _T, _AD),
]


def comandos_para_tier(tier: TierComando) -> list[ComandoMenu]:
    """Return catalog entries whose ``tier <= tier``, preserving catalog order."""
    return [c for c in CATALOGO_COMANDOS if c.tier <= tier]


def comandos_bot(tier: TierComando) -> list[BotCommand]:
    """Map ``comandos_para_tier(tier)`` to ``BotCommand`` objects.

    Used for ``set_my_commands``.
    """
    return [BotCommand(c.comando, c.descripcion) for c in comandos_para_tier(tier)]


def render_menu(tier: TierComando) -> str:
    """Build the /start and /help text for a given tier.

    Format: welcome header, then one section per group that has ≥1 accessible
    command, followed by one line per command.  Uses HTML parse mode to avoid
    Markdown underscore breakage on command names.
    """
    accessible = comandos_para_tier(tier)

    lines: list[str] = ["👋 <b>Bienvenido a Garay Tours</b>"]

    # Iterate groups in declaration order (StrEnum preserves insertion order).
    for grupo in GrupoComando:
        group_cmds = [c for c in accessible if c.grupo == grupo]
        if not group_cmds:
            continue
        lines.append("")
        lines.append(f"<b>{grupo}</b>")
        for cmd in group_cmds:
            lines.append(f"/{cmd.comando} — {cmd.descripcion}")

    return "\n".join(lines)


def tier_de_usuario(
    uid: int | None,
    es_admin: bool,
    propietario_ids: set[int],
    dev_ids: set[int],
) -> TierComando:
    """Resolve the tier for a Telegram user.

    Priority: PROPIETARIO (dev or propietario_ids) > ADMIN (es_admin) > FREELANCER.
    A ``None`` uid is never in any id set, so it resolves to FREELANCER unless
    ``es_admin`` is True.
    """
    if uid is not None and (uid in propietario_ids or uid in dev_ids):
        return TierComando.PROPIETARIO
    if es_admin:
        return TierComando.ADMIN
    return TierComando.FREELANCER
