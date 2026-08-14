"""PTB handler functions — thin adapter over FSMTiquetera."""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from telegram import (
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from garay.aplicacion.factura.generar_y_guardar import GenerarYGuardarFacturaService
from garay.aplicacion.tiquetera.comandos import RegistrarVentaComando
from garay.aplicacion.tiquetera.fsm import EstadoFSM, FSMTiquetera, SalidaFSM
from garay.config.settings import obtener_settings
from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comun.dinero import Dinero
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    FreelancerRepository,
    IngresoRepository,
    VentaRepository,
)
from garay.dominio.ventas.contexto import ContextoVenta
from garay.dominio.ventas.valor_objetos import Participantes
from garay.infraestructura.telegram.auth import dev_telegram_ids, requiere_rol
from garay.infraestructura.telegram.estados import ESTADO_PTB
from garay.infraestructura.telegram.menu import (
    TierComando,
    comandos_bot,
    render_menu,
    tier_de_usuario,
)
from garay.mensajes.catalogo import obtener_mensaje

_UTC = datetime.UTC

_TZ = ZoneInfo("America/Bogota")

logger = logging.getLogger(__name__)


def _teclado(opciones: list[str]) -> InlineKeyboardMarkup | None:
    if not opciones:
        return None
    botones = [[InlineKeyboardButton(op, callback_data=op)] for op in opciones]
    return InlineKeyboardMarkup(botones)


_ESTADOS_TOUR_PICKER: frozenset[EstadoFSM] = frozenset(
    {EstadoFSM.SERVICIO_EN_FAMILIA, EstadoFSM.DESTINO}
)


def _columnas_para_salida(salida: SalidaFSM) -> int:
    """Return the column count for a structured keyboard based on FSM state.

    Tour/service option lists (SERVICIO_EN_FAMILIA, DESTINO) render 1 button per
    row so that long tour names are fully visible. All other structured keyboards
    (e.g. freelancer pickers) keep the default 2-column layout.
    """
    if salida.nuevo_estado in _ESTADOS_TOUR_PICKER:
        return 1
    return 2


def _teclado_estructurado(
    opciones: list[tuple[str, str]],
    columnas: int = 2,
) -> InlineKeyboardMarkup | None:
    """Render (label, callback_data) pairs in a multi-column grid.

    callback_data is the encoded value (e.g. 'fam:3', 'srv:14'), never the label,
    so it always fits Telegram's 64-byte callback_data limit.
    """
    if not opciones:
        return None
    filas: list[list[InlineKeyboardButton]] = []
    for indice in range(0, len(opciones), columnas):
        grupo = opciones[indice : indice + columnas]
        filas.append(
            [InlineKeyboardButton(label, callback_data=data) for label, data in grupo]
        )
    return InlineKeyboardMarkup(filas)


def _get_contexto(context: ContextTypes.DEFAULT_TYPE) -> ContextoVenta:
    if context.user_data is None:
        return ContextoVenta()
    ctx = context.user_data.get("contexto")
    if not isinstance(ctx, ContextoVenta):
        return ContextoVenta()
    return ctx


def _get_fsm(context: ContextTypes.DEFAULT_TYPE) -> FSMTiquetera | None:
    fsm = context.bot_data.get("fsm")
    if not isinstance(fsm, FSMTiquetera):
        logger.error("fsm not found in bot_data — wiring error")
        return None
    return fsm


async def _enviar_salida(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    salida: SalidaFSM,
) -> int:
    context.user_data["contexto"] = salida.contexto  # type: ignore[index]
    if salida.opciones_estructuradas is not None:
        teclado = _teclado_estructurado(
            salida.opciones_estructuradas,
            columnas=_columnas_para_salida(salida),
        )
    else:
        teclado = _teclado(salida.opciones)
    if update.message:
        await update.message.reply_text(
            salida.mensaje,
            reply_markup=teclado,
            parse_mode="Markdown",
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            salida.mensaje,
            reply_markup=teclado,
            parse_mode="Markdown",
        )
    elif update.effective_message:
        await update.effective_message.reply_text(
            salida.mensaje,
            reply_markup=teclado,
            parse_mode="Markdown",
        )
    if salida.nuevo_estado in (EstadoFSM.TERMINADO, EstadoFSM.CANCELADO):
        return ConversationHandler.END
    return ESTADO_PTB[salida.nuevo_estado]


def _contexto_a_comando(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    ctx: ContextoVenta,
) -> RegistrarVentaComando | None:
    user = update.effective_user
    if user is None:
        logger.error("effective_user is None — cannot resolve freelancer")
        return None

    freelancer_repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if freelancer_repo is None:
        logger.error("freelancer_repo not found in bot_data")
        return None
    freelancer = freelancer_repo.buscar_por_telegram_id(user.id)
    if freelancer is None:
        logger.error("freelancer not found for telegram_id=%s", user.id)
        return None

    vendedor_nombre: str | None
    cerrador_nombre: str | None
    vendedor_id: uuid.UUID | None
    cerrador_id: uuid.UUID | None
    if ctx.rol_registrante == "ambos":
        vendedor_nombre = freelancer.nombre
        cerrador_nombre = freelancer.nombre
        vendedor_id = freelancer.id
        cerrador_id = freelancer.id
    elif ctx.rol_registrante == "vendedor":
        vendedor_nombre = freelancer.nombre
        cerrador_nombre = ctx.cerrador_nombre
        vendedor_id = freelancer.id
        cerrador_id = ctx.cerrador_id
    elif ctx.rol_registrante == "cerrador":
        cerrador_nombre = freelancer.nombre
        vendedor_nombre = ctx.vendedor_nombre
        cerrador_id = freelancer.id
        vendedor_id = ctx.vendedor_id
    else:
        logger.error("rol_registrante is invalid: %s", ctx.rol_registrante)
        return None

    if ctx.valor is None or ctx.neto is None or ctx.tipo_cliente is None:
        logger.error(
            "Missing required fields: valor=%s neto=%s tipo_cliente=%s",
            ctx.valor,
            ctx.neto,
            ctx.tipo_cliente,
        )
        return None
    if not ctx.destinos_numeros or ctx.fecha_salida is None:
        logger.error("Missing destinos or fecha_salida")
        return None
    # Guard: when more than one tour is selected every tour must have a per-tour date.
    # Checking len > 1 catches the edge case where fechas_por_servicio is empty but
    # multiple tours were selected — the old guard was skipped in that case.
    if len(ctx.destinos_numeros) > 1:
        missing = [n for n in ctx.destinos_numeros if n not in ctx.fechas_por_servicio]
        if missing:
            logger.error("Tours missing a date: %s", missing)
            return None
    if not ctx.cliente_nombre:
        logger.error("Missing cliente_nombre")
        return None

    servicio_repo = context.bot_data.get("servicio_repo")
    if servicio_repo is None:
        logger.error("servicio_repo not found in bot_data")
        return None
    servicio_map = {s.numero: s.id for s in servicio_repo.listar()}
    servicio_ids = [servicio_map[n] for n in ctx.destinos_numeros if n in servicio_map]
    if not servicio_ids:
        logger.error("No servicio_ids resolved from destinos_numeros=%s", ctx.destinos_numeros)
        return None

    # Translate per-tour dates from numero keys to servicio-id keys.
    fechas_id: dict[uuid.UUID, datetime.datetime] = {}
    if ctx.fechas_por_servicio:
        fechas_id = {
            servicio_map[n]: dt
            for n, dt in ctx.fechas_por_servicio.items()
            if n in servicio_map
        }
    # Translate per-tour horarios from numero keys to servicio-id keys (mirrors fechas_id).
    horarios_id: dict[uuid.UUID, str] = {}
    if ctx.horarios_por_servicio:
        horarios_id = {
            servicio_map[n]: h
            for n, h in ctx.horarios_por_servicio.items()
            if n in servicio_map
        }
    # Derive primary date: min across per-tour datetimes, or fall back to ctx.fecha_salida.
    if fechas_id:
        fecha_principal = min(dt.date() for dt in fechas_id.values())
    else:
        fecha_principal = ctx.fecha_salida.date()

    pdv_id: uuid.UUID | None = None
    if ctx.punto_de_venta_nombre:
        pdv_repo = context.bot_data.get("pdv_repo")
        if pdv_repo is not None:
            nombre_lower = ctx.punto_de_venta_nombre.lower()
            match = next(
                (p for p in pdv_repo.listar() if p.nombre.lower() == nombre_lower),
                None,
            )
            pdv_id = match.id if match else None

    cliente_repo = context.bot_data.get("cliente_repo")
    if cliente_repo is None:
        logger.error("cliente_repo not found in bot_data")
        return None
    nuevo_cliente = Cliente(
        id=uuid.uuid4(),
        nombre=ctx.cliente_nombre,
        tipo=ctx.tipo_cliente,
        telefono=ctx.cliente_telefono,
        hotel=ctx.cliente_hotel,
        numero_habitacion=ctx.cliente_habitacion,
        email=ctx.cliente_email,
        identificacion=ctx.cliente_identificacion,
        tipo_identificacion=ctx.cliente_tipo_identificacion,
    )
    cliente_repo.guardar(nuevo_cliente)

    participantes = Participantes(
        vendedor_nombre=vendedor_nombre,
        cerrador_nombre=cerrador_nombre,
        punto_de_venta_id=pdv_id,
        vendedor_id=vendedor_id,
        cerrador_id=cerrador_id,
    )

    return RegistrarVentaComando(
        valor_venta=Dinero(ctx.valor),
        neto=Dinero(ctx.neto),
        servicio_ids=servicio_ids,
        cliente_id=nuevo_cliente.id,
        tipo_cliente=ctx.tipo_cliente,
        fecha=fecha_principal,
        participantes=participantes,
        adultos=ctx.adultos if ctx.adultos is not None else 0,
        ninos=ctx.ninos if ctx.ninos is not None else 0,
        abono=Dinero(ctx.abono) if ctx.abono else None,
        numero_fisico=ctx.numero_fisico,
        cliente_nombre=ctx.cliente_nombre,
        cliente_telefono=ctx.cliente_telefono,
        servicio_nombres=ctx.destinos_nombres,
        hotel=ctx.cliente_hotel,
        habitacion=ctx.cliente_habitacion,
        canal_origen=ctx.canal_origen,
        fechas_por_servicio=fechas_id if fechas_id else None,
        horarios_por_servicio=horarios_id if horarios_id else None,
    )


async def _foto_en_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_message:
        await update.effective_message.reply_text(
            "Ya tenés una conversación activa. Usá /cancelar para reiniciarla con una foto nueva."
        )
    return ConversationHandler.END


async def _resolver_tier(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> TierComando:
    """Resolve the caller's permission tier from settings, dev ids, and the repo."""
    user = update.effective_user
    uid: int | None = user.id if user is not None else None

    # Resolve propietario ids from settings (comma-separated string).
    settings = obtener_settings()
    propietario_ids: set[int] = set()
    ids_str = settings.propietario_telegram_ids.strip()
    if ids_str:
        propietario_ids = {int(x.strip()) for x in ids_str.split(",") if x.strip()}

    # dev_ids come from auth helper (already tested and reused by guards).
    _dev_ids = dev_telegram_ids()

    # Determine es_admin by looking up the caller in the repo.
    es_admin = False
    repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    if repo is not None and uid is not None:
        freelancer = await asyncio.to_thread(repo.buscar_por_telegram_id, uid)
        if freelancer is not None:
            es_admin = freelancer.es_admin

    return tier_de_usuario(
        uid=uid,
        es_admin=es_admin,
        propietario_ids=propietario_ids,
        dev_ids=_dev_ids,
    )


async def _render_menu_para_usuario(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    """Resolve the caller's tier and return the rendered menu text."""
    tier = await _resolver_tier(update, context)
    return render_menu(tier)


async def _sincronizar_menu_desplegable(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    tier: TierComando,
) -> None:
    """Refresh THIS chat's Telegram command dropdown to match the caller's tier.

    The per-chat dropdown is otherwise only set at startup (bot._post_init), which
    silently fails for any user whose chat did not yet exist then. Re-setting it on
    every /start guarantees a user (dev, admin, freelancer) always sees an up-to-date
    command list without waiting for a bot restart.
    """
    user = update.effective_user
    uid: int | None = user.id if user is not None else None
    if uid is None:
        return
    try:
        await context.bot.set_my_commands(
            comandos_bot(tier),
            scope=BotCommandScopeChat(chat_id=uid),
        )
    except TelegramError as exc:
        # Never let a menu refresh failure break /start — log and continue.
        logger.warning("No se pudo refrescar el menú del chat %s: %s", uid, exc)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /start — refresh the caller's command dropdown and show the menu."""
    if update.message is None:
        return ConversationHandler.END
    tier = await _resolver_tier(update, context)
    await _sincronizar_menu_desplegable(update, context, tier)
    await update.message.reply_text(render_menu(tier), parse_mode="HTML")
    return ConversationHandler.END


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /help — same role-aware menu as /start."""
    if update.message is None:
        return ConversationHandler.END
    texto = await _render_menu_para_usuario(update, context)
    await update.message.reply_text(texto, parse_mode="HTML")
    return ConversationHandler.END


async def handle_iniciar_venta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the tiquetera FSM — entry point from button or /nueva_venta."""
    if update.callback_query is not None:
        await update.callback_query.answer()
    fsm = _get_fsm(context)
    if fsm is None:
        return ConversationHandler.END
    if context.user_data is not None:
        context.user_data["reservas_registradas"] = 0
    salida = fsm.iniciar()
    return await _enviar_salida(update, context, salida)


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle /cancelar — cancel from any state."""
    if context.user_data is not None:
        context.user_data["_cancelar_handled"] = True
    fsm = _get_fsm(context)
    if fsm is None:
        return ConversationHandler.END
    ctx = _get_contexto(context)
    salida = fsm.cancelar(ctx)
    return await _enviar_salida(update, context, salida)


async def cmd_cancelar_sin_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Standalone /cancelar handler — fires when no conversation is active."""
    if context.user_data is not None and context.user_data.pop("_cancelar_handled", False):
        return
    if update.effective_message is not None:
        await update.effective_message.reply_text(obtener_mensaje("cancelar_sin_operacion"))


def _fmt_cop(valor: Decimal) -> str:
    """Format a Decimal as Colombian pesos. E.g.: 260000 → '$260.000'"""
    return "$" + f"{int(valor):,}".replace(",", ".")


@requiere_rol
async def cmd_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle photo or image document — extract reservation data via AI."""
    if update.message is None:
        return ConversationHandler.END

    extractor = context.bot_data.get("extractor_reserva")
    if extractor is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("error_extraccion_no_disponible")
            )
        return ConversationHandler.END

    foto_bytes: bytes | None = None
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        foto_bytes = bytes(await file.download_as_bytearray())
    elif (
        update.message.document is not None
        and update.message.document.mime_type is not None
        and "image" in update.message.document.mime_type
    ):
        file = await update.message.document.get_file()
        foto_bytes = bytes(await file.download_as_bytearray())

    if not foto_bytes:
        return ConversationHandler.END

    try:
        ctx = await asyncio.wait_for(
            asyncio.to_thread(extractor.extraer_de_foto, foto_bytes),
            timeout=300.0,
        )
    except TimeoutError:
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("error_extraccion_timeout")
            )
        return ConversationHandler.END
    except Exception:
        logger.exception("Error al procesar foto con IA")
        if update.effective_message:
            await update.effective_message.reply_text(
                obtener_mensaje("error_extraccion_fallo")
            )
        return ConversationHandler.END

    fsm = _get_fsm(context)
    if fsm is None:
        return ConversationHandler.END

    # Build summary of extracted data
    lineas: list[str] = [obtener_mensaje("titulo_datos_extraidos_foto")]
    if ctx.cliente_nombre:
        lineas.append(
            obtener_mensaje("dato_extraido_nombre").format(valor=ctx.cliente_nombre)
        )
    if ctx.cliente_telefono:
        lineas.append(
            obtener_mensaje("dato_extraido_telefono").format(valor=ctx.cliente_telefono)
        )
    if ctx.fecha_salida:
        lineas.append(
            obtener_mensaje("dato_extraido_fecha").format(
                valor=ctx.fecha_salida.strftime("%d/%m/%Y")
            )
        )
    if ctx.destinos_nombres:
        lineas.append(
            obtener_mensaje("dato_extraido_destinos").format(
                valor=", ".join(ctx.destinos_nombres)
            )
        )
    if ctx.adultos is not None:
        lineas.append(
            obtener_mensaje("dato_extraido_adultos").format(valor=ctx.adultos)
        )
    if ctx.ninos is not None and ctx.ninos > 0:
        lineas.append(
            obtener_mensaje("dato_extraido_ninos").format(valor=ctx.ninos)
        )
    if ctx.valor is not None:
        lineas.append(
            obtener_mensaje("dato_extraido_valor").format(valor=_fmt_cop(ctx.valor))
        )
    if ctx.abono is not None:
        lineas.append(
            obtener_mensaje("dato_extraido_abono").format(valor=_fmt_cop(ctx.abono))
        )
    if ctx.numero_fisico is not None:
        lineas.append(
            obtener_mensaje("dato_extraido_ticket").format(valor=ctx.numero_fisico)
        )
    if ctx.cliente_hotel:
        lineas.append(
            obtener_mensaje("dato_extraido_hotel").format(valor=ctx.cliente_hotel)
        )
    if ctx.cliente_habitacion:
        lineas.append(
            obtener_mensaje("dato_extraido_habitacion").format(valor=ctx.cliente_habitacion)
        )
    if ctx.vendedor_nombre:
        lineas.append(
            obtener_mensaje("dato_extraido_vendedor").format(valor=ctx.vendedor_nombre)
        )
    lineas.append(obtener_mensaje("completar_datos_faltantes"))

    ctx.foto_modo = True  # jump to PARTICIPANTE_ROL after PUNTO_DE_VENTA

    # Start the FSM at MODALIDAD_VENTA with the pre-filled ctx
    # (photo entry skips METODO_INPUT — user already chose Foto implicitly)
    salida = SalidaFSM(
        mensaje="\n".join(lineas)
        + "\n\n"
        + obtener_mensaje("pregunta_modalidad_venta"),
        opciones=["Presencial", "Digital"],
        nuevo_estado=EstadoFSM.MODALIDAD_VENTA,
        contexto=ctx,
        listo=False,
    )
    return await _enviar_salida(update, context, salida)


def _make_handler(estado: EstadoFSM) -> Callable[..., Any]:
    """Factory: creates an async handler for a given FSM state."""

    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        if update.callback_query:
            try:
                await update.callback_query.answer()
            except Exception:
                logger.warning("callback_query.answer() failed — query may be too old")
        fsm = _get_fsm(context)
        if fsm is None:
            return ConversationHandler.END
        entrada: str = ""
        if update.callback_query:
            entrada = update.callback_query.data or ""
        elif update.message and update.message.text:
            entrada = update.message.text
        ctx = _get_contexto(context)
        salida = fsm.procesar_foto(estado, entrada, ctx)
        logger.info(
            "[FSM %s] entrada=%r listo=%s nuevo_estado=%s",
            estado.value,
            entrada[:30],
            salida.listo,
            salida.nuevo_estado,
        )
        registro_exitoso: bool = False
        if salida.listo:
            cmd = _contexto_a_comando(update, context, salida.contexto)
            if cmd is not None:
                servicio = context.bot_data.get("registrar_venta_service")
                if servicio is not None:
                    try:
                        resultado = await asyncio.to_thread(servicio.ejecutar, cmd)
                        desglose = resultado.desglose
                        ctx_final = salida.contexto

                        def _cop(v: object) -> str:
                            raw: Any = v.monto if hasattr(v, "monto") else (v or 0)
                            return "$" + f"{int(raw):,}".replace(",", ".")

                        if (
                            desglose.vendedor
                            and desglose.cerrador
                            and desglose.vendedor != desglose.cerrador
                        ):
                            comision_txt = (
                                f"Vendedor: {_cop(desglose.vendedor)} / "
                                f"Cerrador: {_cop(desglose.cerrador)}"
                            )
                        else:
                            comision_txt = _cop(desglose.vendedor + desglose.cerrador)
                        msg_ok = (
                            f"✅ <b>Venta registrada exitosamente</b>\n\n"
                            f"Cliente: {ctx_final.cliente_nombre or '—'}\n"
                            f"Valor: {_cop(ctx_final.valor)} | Abono: {_cop(ctx_final.abono)}\n"
                            f"Comisión: {comision_txt}\n\n"
                            f"Usá /mis_ventas para ver tu historial."
                        )
                        try:
                            if update.effective_chat:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=msg_ok,
                                    parse_mode="HTML",
                                )
                        except Exception:
                            logger.exception("Error al enviar mensaje de confirmación")
                        factura_service: GenerarYGuardarFacturaService | None = (
                            context.bot_data.get("factura_service")
                        )
                        if factura_service is not None:
                            try:
                                await asyncio.to_thread(
                                    factura_service.ejecutar, ctx_final, resultado
                                )
                            except Exception:
                                logger.exception("Error al generar/guardar la factura")
                        registro_exitoso = True
                    except Exception:
                        logger.exception("Error al registrar venta")
                        if update.effective_message:
                            await update.effective_message.reply_text(
                                "Ocurrió un error al registrar la venta. "
                                "Por favor intentá de nuevo con /start."
                            )
                        return ConversationHandler.END
                else:
                    logger.error("registrar_venta_service not found in bot_data")
        if registro_exitoso:
            context.user_data["reservas_registradas"] = (  # type: ignore[index]
                context.user_data.get("reservas_registradas", 0) + 1  # type: ignore[union-attr]
            )
            context.user_data["contexto"] = salida.contexto  # type: ignore[index]
            mensaje_otro = obtener_mensaje("pregunta_otro_tour").format(
                cliente=salida.contexto.cliente_nombre or "el cliente"
            )
            teclado_otro = _teclado(
                [
                    obtener_mensaje("boton_otro_tour"),
                    obtener_mensaje("boton_terminar"),
                ]
            )
            if update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=mensaje_otro,
                    reply_markup=teclado_otro,
                    parse_mode="Markdown",
                )
            return ESTADO_PTB[EstadoFSM.OTRO_TOUR]
        return await _enviar_salida(update, context, salida)

    handler.__name__ = f"handle_{estado.value}"
    handler.__qualname__ = f"handle_{estado.value}"
    return handler


# Pre-built handlers for each FSM state
handle_metodo_input = _make_handler(EstadoFSM.METODO_INPUT)
handle_esperando_foto = _make_handler(EstadoFSM.ESPERANDO_FOTO)
handle_modalidad_venta = _make_handler(EstadoFSM.MODALIDAD_VENTA)
handle_tipo_reserva = _make_handler(EstadoFSM.TIPO_RESERVA)
handle_punto_de_venta = _make_handler(EstadoFSM.PUNTO_DE_VENTA)
handle_familia = _make_handler(EstadoFSM.FAMILIA)
handle_servicio_en_familia = _make_handler(EstadoFSM.SERVICIO_EN_FAMILIA)
handle_destino = _make_handler(EstadoFSM.DESTINO)
handle_cliente_nombre = _make_handler(EstadoFSM.CLIENTE_NOMBRE)
handle_cliente_telefono = _make_handler(EstadoFSM.CLIENTE_TELEFONO)
handle_cliente_email = _make_handler(EstadoFSM.CLIENTE_EMAIL)
handle_cliente_tipo_id = _make_handler(EstadoFSM.CLIENTE_TIPO_ID)
handle_cliente_identificacion = _make_handler(EstadoFSM.CLIENTE_IDENTIFICACION)
handle_cliente_hotel = _make_handler(EstadoFSM.CLIENTE_HOTEL)
handle_cliente_habitacion = _make_handler(EstadoFSM.CLIENTE_HABITACION)
handle_fecha_salida = _make_handler(EstadoFSM.FECHA_SALIDA)
handle_pax_adultos = _make_handler(EstadoFSM.PAX_ADULTOS)
handle_pax_ninos = _make_handler(EstadoFSM.PAX_NINOS)
handle_monto_valor = _make_handler(EstadoFSM.MONTO_VALOR)
handle_monto_abono = _make_handler(EstadoFSM.MONTO_ABONO)
handle_monto_neto = _make_handler(EstadoFSM.MONTO_NETO)
handle_participante_rol = _make_handler(EstadoFSM.PARTICIPANTE_ROL)
handle_participante_otro = _make_handler(EstadoFSM.PARTICIPANTE_OTRO)
handle_canal_origen = _make_handler(EstadoFSM.CANAL_ORIGEN)
handle_confirmacion = _make_handler(EstadoFSM.CONFIRMACION)
handle_editar_selector = _make_handler(EstadoFSM.EDITAR_SELECTOR)
handle_editar_vendedor = _make_handler(EstadoFSM.EDITAR_VENDEDOR)
handle_editar_cerrador = _make_handler(EstadoFSM.EDITAR_CERRADOR)
handle_horario_salida = _make_handler(EstadoFSM.HORARIO_SALIDA)


async def handle_otro_tour(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the OTRO_TOUR state: offer another tour for the same client or end."""
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            logger.warning("callback_query.answer() failed — query may be too old")
    entrada: str = ""
    if update.callback_query:
        entrada = update.callback_query.data or ""
    elif update.message and update.message.text:
        entrada = update.message.text

    boton_otro = obtener_mensaje("boton_otro_tour")
    boton_terminar = obtener_mensaje("boton_terminar")

    if entrada == boton_otro:
        fsm = _get_fsm(context)
        if fsm is None:
            return ConversationHandler.END
        ctx = _get_contexto(context)
        salida = fsm.iniciar_otro_tour(ctx)
        return await _enviar_salida(update, context, salida)

    if entrada == boton_terminar:
        ctx = _get_contexto(context)
        n: int = context.user_data.get("reservas_registradas", 0)  # type: ignore[union-attr]
        cliente = ctx.cliente_nombre or "el cliente"
        resumen = obtener_mensaje("resumen_reservas").format(cantidad=n, cliente=cliente)
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(resumen)
            except Exception:
                if update.effective_message:
                    await update.effective_message.reply_text(resumen)
        elif update.effective_message:
            await update.effective_message.reply_text(resumen)
        context.user_data["reservas_registradas"] = 0  # type: ignore[index]
        return ConversationHandler.END

    # Unknown input: re-send the prompt, stay in OTRO_TOUR
    ctx = _get_contexto(context)
    prompt = SalidaFSM(
        nuevo_estado=EstadoFSM.OTRO_TOUR,
        mensaje=obtener_mensaje("pregunta_otro_tour").format(
            cliente=ctx.cliente_nombre or "el cliente"
        ),
        opciones=[boton_otro, boton_terminar],
        contexto=ctx,
    )
    return await _enviar_salida(update, context, prompt)


@requiere_rol
async def cmd_mis_ventas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    freelancer_repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
    venta_repo: VentaRepository | None = context.bot_data.get("venta_repo")
    comision_repo: ComisionRegistradaRepository | None = context.bot_data.get(
        "comision_registrada_repo"
    )

    if freelancer_repo is None or venta_repo is None or comision_repo is None:
        if update.effective_message:
            await update.effective_message.reply_text("Error interno. Contactá al administrador.")
        return

    freelancer = await asyncio.to_thread(freelancer_repo.buscar_por_telegram_id, user.id)
    if freelancer is None:
        return  # requiere_rol already validated

    hoy = date.today()
    desde = date(hoy.year, hoy.month, 1)
    hasta = hoy

    ventas = await asyncio.to_thread(
        venta_repo.listar_por_freelancer_y_periodo, freelancer.id, freelancer.nombre, desde, hasta
    )
    venta_ids = [v.id for v in ventas]
    comisiones = await asyncio.to_thread(comision_repo.listar_por_venta_ids, venta_ids)

    total_ventas = len(ventas)
    valor_total = sum((v.valor_venta.monto for v in ventas), start=Decimal("0"))
    comision_total = sum(
        (c.desglose.vendedor.monto + c.desglose.cerrador.monto for c in comisiones),
        start=Decimal("0"),
    )

    lineas = [
        f"*Mis ventas — {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}*",
        f"Total ventas: {total_ventas}",
        f"Valor total: ${valor_total:,.0f}",
        f"Mis comisiones: ${comision_total:,.0f}",
    ]

    if ventas:
        lineas.append("\n*Detalle:*")
        for v in ventas[-10:]:
            linea = f"• {v.fecha.strftime('%d/%m')} — ${v.valor_venta.monto:,.0f}"
            if v.fechas_por_servicio is not None and len(v.fechas_por_servicio) > 1:
                linea += " (varias fechas)"
            if v.canal_origen:
                linea += f" · 📲 {v.canal_origen}"
            lineas.append(linea)

    mensaje = "\n".join(lineas)
    if len(mensaje) > 4096:
        mensaje = mensaje[:4090] + "\n..."

    if update.effective_message:
        await update.effective_message.reply_text(mensaje, parse_mode="Markdown")


def _fmt_hace_minutos(fecha_recibido: datetime.datetime) -> str:
    """Return a human-readable 'hace N min' string relative to now (UTC)."""
    aware = (
        fecha_recibido.replace(tzinfo=_UTC)
        if fecha_recibido.tzinfo is None
        else fecha_recibido
    )
    delta = datetime.datetime.now(_UTC) - aware
    minutos = max(0, int(delta.total_seconds() // 60))
    return f"hace {minutos} min"


@requiere_rol
async def cmd_verificar_pago(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /verificar_pago — list unreconciled ingresos from the last 5 minutes."""
    ingreso_repo: IngresoRepository | None = context.bot_data.get("ingreso_repo")

    if ingreso_repo is None:
        if update.effective_message:
            await update.effective_message.reply_text("Error interno. Contactá al administrador.")
        return

    ingresos = await asyncio.to_thread(ingreso_repo.listar_recientes, 5)

    if not ingresos:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ Sin pagos en los últimos 5 minutos.\nPedile al cliente el comprobante."
            )
        return

    lineas = ["✅ *Pagos recibidos (últimos 5 min):*", ""]
    for ingreso in ingresos:
        monto_fmt = _fmt_cop(ingreso.monto.monto)
        remitente = ingreso.remitente or "Desconocido"
        tiempo = (
            _fmt_hace_minutos(ingreso.fecha_recibido)
            if ingreso.fecha_recibido is not None
            else "hora desconocida"
        )
        lineas.append(f"• {monto_fmt} — {remitente} ({ingreso.banco}) — {tiempo}")

    if update.effective_message:
        await update.effective_message.reply_text("\n".join(lineas), parse_mode="Markdown")


