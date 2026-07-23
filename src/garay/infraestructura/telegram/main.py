"""Entry point for the Telegram bot.

Repository and service wiring will be completed in Etapa 5 (infrastructure adapters).
Until then, dependencies raise NotImplementedError as stubs.
"""
from __future__ import annotations

import logging

from garay.aplicacion.tiquetera.servicio import RegistrarVentaService  # noqa: F401
from garay.infraestructura.telegram.bot import crear_aplicacion  # noqa: F401


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # TODO (Etapa 5): load token from settings and wire real repositories
    raise NotImplementedError(
        "main() not yet wired — complete infrastructure adapters in Etapa 5."
    )

    # Skeleton for reference (unreachable until Etapa 5):
    # from garay.config.settings import get_settings
    # settings = get_settings()
    # servicio: RegistrarVentaService = ...  # wire real repos here
    # crear_aplicacion(settings.telegram_token, servicio).run_polling()


if __name__ == "__main__":
    main()
