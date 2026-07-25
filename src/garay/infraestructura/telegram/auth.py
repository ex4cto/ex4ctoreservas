"""Authorization decorator for PTB handlers."""
from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from garay.dominio.puertos.repositorios import FreelancerRepository

logger = logging.getLogger(__name__)


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
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int | None:
        # Guard: effective_user can be None in channel posts
        user = update.effective_user
        if user is None:
            return ConversationHandler.END

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return ConversationHandler.END

        if repo.buscar_por_telegram_id(user.id) is None:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "No estás registrado como freelancer."
                )
            return ConversationHandler.END

        return await handler(update, context)

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

        repo: FreelancerRepository | None = context.bot_data.get("freelancer_repo")
        if repo is None:
            logger.error("freelancer_repo not found in bot_data — wiring error")
            return None

        freelancer = repo.buscar_por_telegram_id(user.id)
        if freelancer is None:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "No estás registrado como freelancer."
                )
            return None

        if not freelancer.es_admin:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Este comando es solo para administradores."
                )
            return None

        return await handler(update, context)

    return wrapper
