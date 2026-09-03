"""Contexto de dominio para la generación de propuestas comerciales.

Empieza mínimo (nombre + precios) y crece con los campos que defina el UX del
comando. Reemplaza el paso de strings sueltos: el servicio de aplicación recibe
este contexto tipado, no argumentos crudos.

Los precios usan el value object ``Dinero`` (Decimal, nunca float) conforme al
estándar de dinero del proyecto. Los valores por defecto son constantes con
nombre (no números mágicos); mover a config/entorno queda como mejora futura.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from garay.dominio.comun.dinero import Dinero


@dataclass(frozen=True)
class PreciosAudiovisual:
    """Precios de la propuesta audiovisual (planes + complementos)."""

    completo: Dinero
    medio: Dinero
    community: Dinero
    trafficker: Dinero


PRECIOS_AUDIOVISUAL_DEFAULT = PreciosAudiovisual(
    completo=Dinero(3_000_000),
    medio=Dinero(1_800_000),
    community=Dinero(500_000),
    trafficker=Dinero(600_000),
)


@dataclass(frozen=True)
class PropuestaContexto:
    """Datos variables de una propuesta para una empresa."""

    empresa_nombre: str
    precios: PreciosAudiovisual = field(default=PRECIOS_AUDIOVISUAL_DEFAULT)
