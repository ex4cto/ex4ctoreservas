"""Telegram handler for the /lista_precios command.

TEXT-ONLY command — no image generation.
Lists active tours with precio_sugerido_adulto set, grouped by categoria,
ordered by numero ASC within each group.
All user-facing strings come from garay.mensajes.catalogo.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from garay.aplicacion.comun.formato import fmt_cop
from garay.dominio.puertos.repositorios import ServicioRepository
from garay.dominio.servicios.entidades import Servicio
from garay.infraestructura.telegram.auth import requiere_rol
from garay.mensajes.catalogo import obtener_mensaje


@requiere_rol
async def cmd_lista_precios(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Reply with a formatted text list of active tours and their public prices.

    Reads servicio_repo from context.bot_data.
    Filters: activo=True AND precio_sugerido_adulto IS NOT NULL.
    Groups by categoria, ordered by numero ASC within each group.
    Formats prices with fmt_cop().
    No FSM, no ConversationHandler, no admin guard.
    """
    repo: ServicioRepository = context.bot_data["servicio_repo"]
    todos: list[Servicio] = repo.listar_activos()

    elegibles = [
        s
        for s in todos
        if s.activo
        and s.precio_neto_adulto is not None
        and s.precio_sugerido_adulto is not None
    ]

    if not elegibles:
        text = obtener_mensaje("lista_precios.vacio")
        assert update.effective_message is not None
        await update.effective_message.reply_text(text)
        return

    # Group by categoria, preserve insertion order (Python 3.7+)
    grupos: dict[str, list[Servicio]] = {}
    for s in sorted(elegibles, key=lambda x: (x.categoria, x.numero)):
        grupos.setdefault(s.categoria, []).append(s)

    titulo = obtener_mensaje("lista_precios.titulo")

    # Build per-category blocks: each block is a list of lines.
    bloques: list[list[str]] = []
    for categoria, servicios in grupos.items():
        bloque: list[str] = [
            obtener_mensaje("lista_precios.categoria_encabezado").format(
                categoria=categoria
            )
        ]
        for s in servicios:
            precio_str = fmt_cop(s.precio_sugerido_adulto)
            linea = obtener_mensaje("lista_precios.linea_tour").format(
                nombre=s.nombre, precio=precio_str
            )
            if s.permite_ninos and s.precio_neto_nino is None:
                linea += obtener_mensaje("lista_precios.nota_nino_adulto")
            bloque.append(linea)
        bloques.append(bloque)

    # Pack blocks into pages ≤ 4096 chars (Telegram limit).
    _LIMIT = 4000  # leave headroom for the title line
    paginas: list[str] = []
    pagina_lines: list[str] = [titulo]

    for bloque in bloques:
        candidato = "\n".join(pagina_lines + bloque)
        if len(candidato) > _LIMIT and len(pagina_lines) > 1:
            # Flush current page and start a new one with this block.
            paginas.append("\n".join(pagina_lines))
            pagina_lines = bloque[:]
        else:
            pagina_lines.extend(bloque)

    if pagina_lines:
        paginas.append("\n".join(pagina_lines))

    assert update.effective_message is not None
    for pagina in paginas:
        await update.effective_message.reply_text(pagina, parse_mode="HTML")
