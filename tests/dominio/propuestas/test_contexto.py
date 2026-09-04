"""Tests for PropuestaContexto — domain value object for proposals."""

from __future__ import annotations

from garay.dominio.comun.dinero import Dinero
from garay.dominio.propuestas.contexto import (
    PRECIOS_AUDIOVISUAL_DEFAULT,
    PreciosAudiovisual,
    PropuestaContexto,
)


def test_guarda_nombre_empresa() -> None:
    ctx = PropuestaContexto(empresa_nombre="Acme S.A.S.")
    assert ctx.empresa_nombre == "Acme S.A.S."


def test_precios_por_defecto() -> None:
    ctx = PropuestaContexto(empresa_nombre="X")
    assert ctx.precios == PRECIOS_AUDIOVISUAL_DEFAULT
    assert ctx.precios.completo == Dinero(3_000_000)
    assert ctx.precios.medio == Dinero(1_800_000)
    assert ctx.precios.community == Dinero(500_000)
    assert ctx.precios.trafficker == Dinero(600_000)


def test_defaults_software() -> None:
    from garay.dominio.propuestas.contexto import (
        EJEMPLOS_SERVICIOS_DEFAULT,
        PRECIOS_SOFTWARE_DEFAULT,
    )

    ctx = PropuestaContexto(empresa_nombre="X")
    assert ctx.precios_software == PRECIOS_SOFTWARE_DEFAULT
    assert ctx.precios_software.desarrollo == Dinero(24_000_000)
    assert ctx.precios_software.anual == Dinero(5_000_000)
    assert ctx.ejemplos_servicios == EJEMPLOS_SERVICIOS_DEFAULT


def test_precios_personalizados() -> None:
    precios = PreciosAudiovisual(
        completo=Dinero(4_000_000),
        medio=Dinero(2_000_000),
        community=Dinero(700_000),
        trafficker=Dinero(800_000),
    )
    ctx = PropuestaContexto(empresa_nombre="X", precios=precios)
    assert ctx.precios.completo == Dinero(4_000_000)


def test_igualdad_por_valor() -> None:
    assert PropuestaContexto(empresa_nombre="X") == PropuestaContexto(empresa_nombre="X")


def test_es_inmutable() -> None:
    ctx = PropuestaContexto(empresa_nombre="X")
    try:
        ctx.empresa_nombre = "Y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("PropuestaContexto debería ser inmutable (frozen)")
