"""Errores de dominio del modulo ventas."""

from __future__ import annotations

from garay.dominio.comun.dinero import MonedaIncompatible as MonedaIncompatible  # re-export
from garay.dominio.comun.errores import ErrorDeDominio


class GananciaNegativa(ErrorDeDominio):
    """El neto supera al valor de venta, lo que produciria una ganancia negativa."""


class ValorVentaInvalido(ErrorDeDominio):
    """El valor de venta debe ser mayor que cero."""


class CantidadInvalida(ErrorDeDominio):
    """La cantidad de pasajeros debe ser al menos 1."""


class AbonoSuperaValorVenta(ErrorDeDominio):
    """El abono no puede superar el valor de la venta."""


class DigitalConPuntoDeVenta(ErrorDeDominio):
    """Una venta DIGITAL no puede tener un punto de venta asociado."""


class VentaYaAnulada(ErrorDeDominio):
    """No se puede anular una venta que ya fue anulada."""


class MotivoRequerido(ErrorDeDominio):
    """Se requiere un motivo no vacío para anular una venta."""


class VentaNoEncontrada(ErrorDeDominio):
    """No se encontró la venta con el ID indicado."""


class LimiteEdicionesAlcanzado(ErrorDeDominio):
    """La venta alcanzó el máximo de ediciones permitidas y no puede editarse más."""


class MismoCanal(ErrorDeDominio):
    """El nuevo tipo_cliente es igual al tipo_cliente actual de la venta."""


class PuntoDeVentaRequerido(ErrorDeDominio):
    """El canal INTERNO requiere un punto_de_venta_id no nulo."""


class MismosParticipantes(ErrorDeDominio):
    """Se intenta cambiar los participantes por los mismos valores ya registrados."""


class NetoIgualOSuperaValorVenta(ErrorDeDominio):
    """El nuevo neto es igual o mayor al valor de venta (ganancia cero o negativa bloqueada)."""


class ValorVentaMenorQueAbono(ErrorDeDominio):
    """El nuevo valor de venta es menor que el abono ya registrado."""


class MismoNeto(ErrorDeDominio):
    """Idempotency guard: el nuevo neto es idéntico al neto actual."""


class MismoValorVenta(ErrorDeDominio):
    """Idempotency guard: el nuevo valor de venta es idéntico al valor actual."""


class MismoServicio(ErrorDeDominio):
    """Idempotency guard: los nuevos servicio_ids son idénticos a los actuales."""
