"""Authorization decorator for PTB handlers."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.config.settings import obtener_settings
from garay.dominio.puertos.repositorios import FreelancerRepository
from garay.mensajes.catalogo import obtener_mensaje

logger = logging.getLogger(__name__)


def dev_telegram_ids() -> set[int]:
    """Return the set of Telegram user IDs configured as developers.

    Parses ``GARAY_DEV_TELEGRAM_IDS`` (comma-separated integers) from settings.
    Returns an empty set when the setting is blank or unset.
    """
    ids_str = obtener_settings().dev_telegram_ids.strip()
    if not ids_str:
        return set()
    return {int(x.strip()) for x in ids_str.split(",") if x.strip()}


def _es_dev(telegram_user_id: int) -> bool:
    return telegram_user_id in dev_telegram_ids()


def requiere_rol(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Decorator that guards a PTB handler to registered freelancers only.

    Reads ``freelancer_repo`` from ``context.bot_data`` (injected at wiring
    time) and denies access when the calling Telegram user is not found.

    Returns ``ConversationHandler.END`` on any access-denial path so the
    conversation never opens for unauthorized users.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        # Guard: effective_user can be None in channel posts
        user = update.effective_user
        if user is None:
            return ConversationHandler.END

        if _es_dev(user.id):
            return await handler(update, context)

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return ConversationHandler.END

        if repo.buscar_por_telegram_id(user.id) is None:
            if update.effective_message:
                await update.effective_message.reply_text("No estás registrado como freelancer.")
            return ConversationHandler.END

        return await handler(update, context)

    return wrapper


def requiere_dev_conv(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Guard for ConversationHandler entry points — developers ONLY.

    Unlike the other guards, dev is not a bypass here but the sole allowed role.
    Returns ``ConversationHandler.END`` on any deny so the conversation never
    opens for non-developers.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        user = update.effective_user
        if user is None:
            return ConversationHandler.END

        if _es_dev(user.id):
            return await handler(update, context)

        if update.effective_message:
            await update.effective_message.reply_text(
                "Este comando es solo para desarrolladores."
            )
        return ConversationHandler.END

    return wrapper


def requiere_admin(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Guard para CommandHandlers standalone — solo admins.

    Returns ``None`` on deny (not ``ConversationHandler.END``) because
    these are standalone CommandHandlers, not ConversationHandler entry points.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        user = update.effective_user
        if user is None:
            return None

        if _es_dev(user.id):
            return await handler(update, context)

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return None

        freelancer = repo.buscar_por_telegram_id(user.id)
        if freelancer is None:
            if update.effective_message:
                await update.effective_message.reply_text("No estás registrado como freelancer.")
            return None

        if not freelancer.es_admin:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Este comando es solo para administradores."
                )
            return None

        return await handler(update, context)

    return wrapper


def requiere_admin_conv(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Guard for ConversationHandler entry points — admins only.

    Returns ``ConversationHandler.END`` on deny (not ``None``) so the
    conversation is never opened for unauthorized users.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        user = update.effective_user
        if user is None:
            return ConversationHandler.END

        if _es_dev(user.id):
            return await handler(update, context)

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return ConversationHandler.END

        freelancer = repo.buscar_por_telegram_id(user.id)
        if freelancer is None:
            if update.effective_message:
                await update.effective_message.reply_text("No estás registrado como freelancer.")
            return ConversationHandler.END

        if not freelancer.es_admin:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Este comando es solo para administradores."
                )
            return ConversationHandler.END

        return await handler(update, context)

    return wrapper


def requiere_admin_o_propietario_conv(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Guard for ConversationHandler entry points — admins OR propietario.

    Allows access when the user is:
    - A dev (bypass), OR
    - Listed in ``propietario_telegram_ids`` settings, OR
    - A registered freelancer with ``es_admin=True``.

    Returns ``ConversationHandler.END`` on deny so the conversation never
    opens for unauthorized users.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        user = update.effective_user
        if user is None:
            return ConversationHandler.END

        if _es_dev(user.id):
            return await handler(update, context)

        settings = obtener_settings()
        ids_str = settings.propietario_telegram_ids.strip()
        if ids_str:
            ids_permitidos = {int(x.strip()) for x in ids_str.split(",") if x.strip()}
            if user.id in ids_permitidos:
                return await handler(update, context)

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return ConversationHandler.END

        freelancer = repo.buscar_por_telegram_id(user.id)
        if freelancer is not None and freelancer.es_admin:
            return await handler(update, context)

        if update.effective_message:
            await update.effective_message.reply_text(
                "Este comando es solo para administradores o el propietario."
            )
        return ConversationHandler.END

    return wrapper


def requiere_admin_o_propietario(
    handler: Callable[..., Coroutine[Any, Any, int | None]],
) -> Callable[..., Coroutine[Any, Any, int | None]]:
    """Guard for standalone CommandHandlers — admins OR the agency owner.

    Allows access when the user is a dev (bypass), listed in
    ``propietario_telegram_ids``, or a registered freelancer with ``es_admin=True``.
    Returns ``None`` on deny (not ``ConversationHandler.END``) because these are
    standalone CommandHandlers, not ConversationHandler entry points.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
        user = update.effective_user
        if user is None:
            return None

        if _es_dev(user.id):
            return await handler(update, context)

        settings = obtener_settings()
        ids_str = settings.propietario_telegram_ids.strip()
        if ids_str:
            ids_permitidos = {int(x.strip()) for x in ids_str.split(",") if x.strip()}
            if user.id in ids_permitidos:
                return await handler(update, context)

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return None

        freelancer = repo.buscar_por_telegram_id(user.id)
        if freelancer is not None and freelancer.es_admin:
            return await handler(update, context)

        if update.effective_message:
            await update.effective_message.reply_text(
                "Este comando es solo para administradores o el propietario."
            )
        return None

    return wrapper


def requiere_propietario(
    handler: Callable[..., Coroutine[Any, Any, Any]],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """Guard for standalone CommandHandlers reserved for the agency owner.

    Reads ``propietario_telegram_ids`` from settings (comma-separated integers).
    An empty list is a fail-safe: access is denied to everyone.
    Returns ``None`` on deny (not ``ConversationHandler.END``) because
    these are standalone CommandHandlers, not ConversationHandler entry points.
    """

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user = update.effective_user
        if user is None:
            return None

        if _es_dev(user.id):
            return await handler(update, context)

        settings = obtener_settings()
        ids_str = settings.propietario_telegram_ids.strip()
        if not ids_str:
            if update.effective_message:
                await update.effective_message.reply_text(
                    obtener_mensaje("conciliacion.sin_acceso")
                )
            return None

        ids_permitidos = {int(x.strip()) for x in ids_str.split(",") if x.strip()}
        if user.id not in ids_permitidos:
            if update.effective_message:
                await update.effective_message.reply_text(
                    obtener_mensaje("conciliacion.sin_acceso")
                )
            return None

        return await handler(update, context)

    return wrapper
