"""Application service for freelancer payment liquidation."""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from garay.dominio.comun.dinero import Dinero
from garay.dominio.liquidaciones.entidades import PagoFreelancer, PagoReferido
from garay.dominio.puertos.repositorios import (
    ComisionRegistradaRepository,
    FreelancerRepository,
    PagoFreelancerRepository,
    PagoReferidoRepository,
    ServicioRepository,
    VentaRepository,
)

# ---------------------------------------------------------------------------
# DTOs for referido liquidation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferidoVentaDetalle:
    """Detail line for a single sale contributing to a referido's amount."""

    fecha: datetime.date
    referido: Dinero


@dataclass(frozen=True)
class ResultadoLiquidacionReferido:
    """Result of calculating what a referido alias is owed for a period."""

    referido_alias: str
    desde: datetime.date
    hasta: datetime.date
    total: Dinero
    desglose: list[ReferidoVentaDetalle]

# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComisionVentaDetalle:
    """Detail line for a single sale contributing to a freelancer's commission."""

    fecha: datetime.date
    servicio_nombre: str
    adultos: int
    ninos: int
    comision: Dinero


@dataclass(frozen=True)
class ResultadoCalculoLiquidacion:
    """Result of calculating what a freelancer is owed for a period."""

    freelancer_id: uuid.UUID
    freelancer_nombre: str
    freelancer_telegram_id: int | None
    desde: datetime.date
    hasta: datetime.date
    comisiones_total: Dinero
    desglose: list[ComisionVentaDetalle]
    solapados: list[PagoFreelancer]


@dataclass(frozen=True)
class RegistrarPagoFreelancerComando:
    """Command to register a payment to a freelancer."""

    freelancer_id: uuid.UUID
    monto: Dinero
    desde: datetime.date
    hasta: datetime.date
    registrado_por_telegram_id: int
    registrado_por_nombre: str | None


# ---------------------------------------------------------------------------
# Overlap helper
# ---------------------------------------------------------------------------


def _dias_solapados(
    desde1: date, hasta1: date, desde2: date, hasta2: date
) -> list[date]:
    """Return the list of dates that are in both [desde1, hasta1] and [desde2, hasta2]."""
    inicio = max(desde1, desde2)
    fin = min(hasta1, hasta2)
    if inicio > fin:
        return []
    result: list[date] = []
    current = inicio
    while current <= fin:
        result.append(current)
        current += timedelta(days=1)
    return result


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class LiquidarFreelancerService:
    """Calculates commissions owed to a freelancer and records payments."""

    def __init__(
        self,
        freelancer_repo: FreelancerRepository,
        ventas_repo: VentaRepository,
        comisiones_repo: ComisionRegistradaRepository,
        servicios_repo: ServicioRepository,
        pago_repo: PagoFreelancerRepository,
    ) -> None:
        self._freelancer_repo = freelancer_repo
        self._ventas_repo = ventas_repo
        self._comisiones_repo = comisiones_repo
        self._servicios_repo = servicios_repo
        self._pago_repo = pago_repo

    def calcular(
        self,
        freelancer_id: uuid.UUID,
        desde: date,
        hasta: date,
    ) -> ResultadoCalculoLiquidacion:
        """Calculate commissions for a freelancer over [desde, hasta].

        Steps:
        1. Load freelancer (raises ValueError if not found).
        2. Load all non-anulada ventas in period.
        3. Load registered commissions for those ventas.
        4. Build service id→name lookup.
        5. For each venta, check if the freelancer was vendedor or cerrador.
        6. Check for overlap with existing payments.
        """
        freelancer = self._freelancer_repo.buscar_por_id(freelancer_id)
        if freelancer is None:
            raise ValueError(f"Freelancer {freelancer_id} not found")

        ventas = self._ventas_repo.listar_por_periodo(desde, hasta)
        venta_ids = [v.id for v in ventas]

        comisiones_list = self._comisiones_repo.listar_por_venta_ids(venta_ids) if venta_ids else []
        comisiones_by_venta = {c.venta_id: c for c in comisiones_list}

        servicios = self._servicios_repo.listar_activos()
        servicio_nombres: dict[uuid.UUID, str] = {s.id: s.nombre for s in servicios}

        desglose: list[ComisionVentaDetalle] = []
        total = Dinero(0)

        for venta in ventas:
            if venta.anulada:
                continue

            comision = comisiones_by_venta.get(venta.id)
            if comision is None:
                continue

            nombre_vendedor = venta.participantes.vendedor_nombre
            nombre_cerrador = venta.participantes.cerrador_nombre

            es_vendedor = nombre_vendedor == freelancer.nombre
            es_cerrador = nombre_cerrador == freelancer.nombre

            if not es_vendedor and not es_cerrador:
                continue

            # Use the first service id for the name
            servicio_id = venta.servicio_ids[0] if venta.servicio_ids else None
            servicio_nombre = (
                servicio_nombres.get(servicio_id, "—") if servicio_id else "—"
            )

            # A freelancer can be both vendedor and cerrador on the same sale.
            # Add both contributions — matches how SplitSociosService aggregates.
            comision_monto = Dinero(0)
            if es_vendedor:
                comision_monto = comision_monto + comision.desglose.vendedor
            if es_cerrador:
                comision_monto = comision_monto + comision.desglose.cerrador

            desglose.append(
                ComisionVentaDetalle(
                    fecha=venta.fecha,
                    servicio_nombre=servicio_nombre,
                    adultos=venta.adultos,
                    ninos=venta.ninos,
                    comision=comision_monto,
                )
            )
            total = total + comision_monto

        solapados = self._pago_repo.buscar_solapados(freelancer_id, desde, hasta)

        return ResultadoCalculoLiquidacion(
            freelancer_id=freelancer_id,
            freelancer_nombre=freelancer.nombre,
            freelancer_telegram_id=freelancer.telegram_user_id,
            desde=desde,
            hasta=hasta,
            comisiones_total=total,
            desglose=desglose,
            solapados=solapados,
        )

    def registrar_pago(
        self, cmd: RegistrarPagoFreelancerComando
    ) -> PagoFreelancer:
        """Register a payment to a freelancer and persist it."""
        pago = PagoFreelancer(
            id=uuid.uuid4(),
            freelancer_id=cmd.freelancer_id,
            monto=cmd.monto,
            desde=cmd.desde,
            hasta=cmd.hasta,
            fecha_pago=datetime.datetime.now(tz=datetime.UTC),
            registrado_por_telegram_id=cmd.registrado_por_telegram_id,
            registrado_por_nombre=cmd.registrado_por_nombre,
        )
        self._pago_repo.guardar(pago)
        return pago


@dataclass(frozen=True)
class RegistrarPagoReferidoComando:
    """Command to register a payment to a referido alias for a given venta."""

    referido_alias: str
    venta_id: uuid.UUID
    monto: Dinero
    desde: date
    hasta: date
    registrado_por_telegram_id: int
    registrado_por_nombre: str | None


# ---------------------------------------------------------------------------
# Referido liquidation service
# ---------------------------------------------------------------------------


class LiquidarReferidoService:
    """Calculates the referido amount owed for a given alias over a period."""

    def __init__(
        self,
        ventas_repo: VentaRepository,
        comisiones_repo: ComisionRegistradaRepository,
        pago_referido_repo: PagoReferidoRepository | None = None,
    ) -> None:
        self._ventas_repo = ventas_repo
        self._comisiones_repo = comisiones_repo
        self._pago_referido_repo = pago_referido_repo

    def calcular(
        self,
        referido_alias: str,
        desde: date,
        hasta: date,
    ) -> ResultadoLiquidacionReferido:
        """Calculate total referido amount for alias over [desde, hasta].

        Steps:
        1. Load all non-anulada ventas in period.
        2. Load registered commissions for those ventas.
        3. For each venta where referido_alias matches, accumulate desglose.referido.
        """
        ventas = self._ventas_repo.listar_por_periodo(desde, hasta)
        venta_ids = [v.id for v in ventas]

        comisiones_list = (
            self._comisiones_repo.listar_por_venta_ids(venta_ids) if venta_ids else []
        )
        comisiones_by_venta = {c.venta_id: c for c in comisiones_list}

        desglose: list[ReferidoVentaDetalle] = []
        total = Dinero(0)

        for venta in ventas:
            if venta.anulada:
                continue
            if venta.participantes.referido_alias != referido_alias:
                continue

            comision = comisiones_by_venta.get(venta.id)
            if comision is None:
                continue

            monto_referido = comision.desglose.referido
            desglose.append(
                ReferidoVentaDetalle(
                    fecha=venta.fecha,
                    referido=monto_referido,
                )
            )
            total = total + monto_referido

        return ResultadoLiquidacionReferido(
            referido_alias=referido_alias,
            desde=desde,
            hasta=hasta,
            total=total,
            desglose=desglose,
        )

    def registrar_pago(self, cmd: RegistrarPagoReferidoComando) -> PagoReferido:
        """Register a payment to a referido alias and persist it.

        Raises ValueError if a pago for the same alias already exists in the period.
        """
        if self._pago_referido_repo is None:
            raise RuntimeError("pago_referido_repo is required for registrar_pago")

        solapados = self._pago_referido_repo.buscar_solapados(
            cmd.referido_alias, cmd.desde, cmd.hasta
        )
        if solapados:
            raise ValueError(
                f"Pago solapado: ya existe un pago para '{cmd.referido_alias}' "
                f"en el período {cmd.desde} - {cmd.hasta}"
            )

        pago = PagoReferido(
            id=uuid.uuid4(),
            venta_id=cmd.venta_id,
            referido_alias=cmd.referido_alias,
            monto=cmd.monto,
            fecha_pago=datetime.datetime.now(tz=datetime.UTC),
            registrado_por_telegram_id=cmd.registrado_por_telegram_id,
            registrado_por_nombre=cmd.registrado_por_nombre,
        )
        self._pago_referido_repo.guardar(pago)
        return pago
