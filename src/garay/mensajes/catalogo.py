"""Catalogo centralizado de textos de usuario.

Todos los textos que ve el usuario viven aca, indexados por clave e idioma. Agregar un
idioma es agregar entradas: el codigo que consume mensajes no cambia (i18n-ready).
"""

from __future__ import annotations

from enum import StrEnum

from garay.dominio.comun.errores import ErrorDeConfiguracion


class Idioma(StrEnum):
    """Idiomas soportados por el catalogo de mensajes."""

    ES = "es"


_CATALOGO: dict[str, dict[Idioma, str]] = {
    "bienvenida": {Idioma.ES: "Bienvenido a Garay Tours."},
    "venta_registrada": {Idioma.ES: "Venta registrada correctamente."},
    "error_generico": {Idioma.ES: "Ocurrio un error. Intenta de nuevo."},
}


def obtener_mensaje(clave: str, idioma: Idioma = Idioma.ES) -> str:
    """Devuelve el texto para ``clave`` en ``idioma``.

    Lanza :class:`ErrorDeConfiguracion` si la combinacion no existe.
    """
    try:
        return _CATALOGO[clave][idioma]
    except KeyError as exc:
        raise ErrorDeConfiguracion(
            f"Mensaje no encontrado: clave={clave!r}, idioma={idioma.value!r}."
        ) from exc
