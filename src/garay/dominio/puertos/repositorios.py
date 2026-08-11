from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date

from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.conciliacion.entidades import (
    CategoriaEgreso,
    Conciliacion,
    CorreoNoParseado,
    Egreso,
    GastoRecurrente,
    Ingreso,
)
from garay.dominio.facturas.entidades import Factura
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.tiquetera.entidades import Tiquetera
from garay.dominio.ventas.auditoria import AuditoriaVenta
from garay.dominio.ventas.entidades import Venta


class VentaRepository(ABC):
    @abstractmethod
    def guardar(self, venta: Venta) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Venta | None: ...

    @abstractmethod
    def listar(self) -> list[Venta]: ...

    @abstractmethod
    def listar_por_freelancer_y_periodo(
        self,
        freelancer_id: uuid.UUID,
        nombre: str,
        desde: date,
        hasta: date,
    ) -> list[Venta]: ...

    @abstractmethod
    def listar_por_periodo(self, desde: date, hasta: date) -> list[Venta]: ...


class IngresoRepository(ABC):
    @abstractmethod
    def guardar(self, ingreso: Ingreso) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Ingreso | None: ...

    @abstractmethod
    def listar_sin_clasificar(self) -> list[Ingreso]: ...

    @abstractmethod
    def existe_referencia(self, referencia: str) -> bool: ...

    @abstractmethod
    def listar_recientes(self, minutos: int) -> list[Ingreso]:
        """Return ingresos with fecha_recibido within the last *minutos* minutes."""
        ...

    @abstractmethod
    def listar_por_periodo(self, desde: date, hasta: date) -> list[Ingreso]: ...


class EgresoRepository(ABC):
    @abstractmethod
    def guardar(self, egreso: Egreso) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Egreso | None: ...

    @abstractmethod
    def existe_referencia(self, referencia: str) -> bool: ...

    @abstractmethod
    def listar_recientes(self, minutos: int) -> list[Egreso]:
        """Return egresos with fecha_recibido within the last *minutos* minutes."""
        ...

    @abstractmethod
    def listar_por_periodo(self, desde: date, hasta: date) -> list[Egreso]: ...


class CategoriaEgresoRepository(ABC):
    @abstractmethod
    def listar_activas(self) -> list[str]: ...

    @abstractmethod
    def guardar(self, categoria: CategoriaEgreso) -> None: ...


class GastoRecurrenteRepository(ABC):
    @abstractmethod
    def guardar(self, gasto: GastoRecurrente) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> GastoRecurrente | None: ...

    @abstractmethod
    def listar_activos(self) -> list[GastoRecurrente]: ...

    @abstractmethod
    def desactivar(self, id: uuid.UUID) -> None: ...


class TiqueteraRepository(ABC):
    @abstractmethod
    def guardar(self, tiquetera: Tiquetera) -> None: ...

    @abstractmethod
    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> Tiquetera | None: ...


class ConciliacionRepository(ABC):
    @abstractmethod
    def guardar(self, conciliacion: Conciliacion) -> None: ...

    @abstractmethod
    def buscar_por_ingreso_id(self, ingreso_id: uuid.UUID) -> Conciliacion | None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Conciliacion | None: ...

    @abstractmethod
    def listar_pendientes(self) -> list[Conciliacion]:
        """Conciliaciones con estado PENDIENTE o SIN_MATCH — requieren revision humana."""
        ...

    @abstractmethod
    def listar_ingreso_ids_procesados(self) -> list[uuid.UUID]:
        """IDs de ingresos que ya tienen al menos una conciliacion registrada."""
        ...

    @abstractmethod
    def listar_por_periodo(self, desde: date, hasta: date) -> list[Conciliacion]:
        """Filtra por fecha del ingreso relacionado (JOIN ingresos)."""
        ...


class FreelancerRepository(ABC):
    @abstractmethod
    def guardar(self, freelancer: Freelancer) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Freelancer | None: ...

    @abstractmethod
    def listar_activos(self) -> list[Freelancer]: ...

    @abstractmethod
    def buscar_por_telegram_id(self, telegram_user_id: int) -> Freelancer | None: ...

    @abstractmethod
    def listar_todos(self) -> list[Freelancer]: ...

    @abstractmethod
    def buscar_por_cedula(self, cedula: str) -> Freelancer | None: ...

    @abstractmethod
    def listar_por_nombre(self, nombre: str) -> list[Freelancer]: ...

    @abstractmethod
    def buscar_por_telegram_id_cualquier_estado(
        self, telegram_user_id: int
    ) -> Freelancer | None: ...


class ClienteRepository(ABC):
    @abstractmethod
    def guardar(self, cliente: Cliente) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Cliente | None: ...

    @abstractmethod
    def buscar_por_nombre(self, nombre: str) -> Cliente | None: ...

    @abstractmethod
    def listar(self) -> list[Cliente]: ...


class FacturaRepository(ABC):
    @abstractmethod
    def guardar(self, factura: Factura) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Factura | None: ...

    @abstractmethod
    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> Factura | None: ...

    @abstractmethod
    def listar_por_periodo(self, desde: date, hasta: date) -> list[Factura]: ...


class ServicioRepository(ABC):
    @abstractmethod
    def guardar(self, servicio: Servicio) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Servicio | None: ...

    @abstractmethod
    def buscar_por_nombre(self, nombre: str) -> Servicio | None: ...

    @abstractmethod
    def listar(self) -> list[Servicio]: ...


class PuntoDeVentaRepository(ABC):
    @abstractmethod
    def guardar(self, punto: PuntoDeVenta) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> PuntoDeVenta | None: ...

    @abstractmethod
    def buscar_por_nombre(self, nombre: str) -> PuntoDeVenta | None: ...

    @abstractmethod
    def listar(self) -> list[PuntoDeVenta]: ...


class ReglasComisionRepository(ABC):
    @abstractmethod
    def buscar_por_tipo_cliente(self, tipo: TipoCliente) -> ReglasComision | None: ...

    @abstractmethod
    def buscar_regla(
        self,
        tipo: TipoCliente,
        punto_nombre: str | None,
        numero_personas: int | None,
    ) -> ReglasComision | None:
        """Two-step rule selector.

        Step 1 (point-specific): if punto_nombre and numero_personas are BOTH
        non-None, search for a row matching (punto_de_venta_nombre, numero_personas),
        ignoring tipo_cliente.  Returns it if found.

        Step 2 (global fallback): search for
        (tipo_cliente==tipo, punto_de_venta_nombre IS NULL, numero_personas IS NULL).

        C3 precondition: exactly one of (punto_nombre, numero_personas) being
        non-None is an invalid combination and MUST raise ValueError.
        """
        ...

    @abstractmethod
    def guardar(self, reglas: ReglasComision) -> None: ...


class ComisionRegistradaRepository(ABC):
    @abstractmethod
    def guardar(self, comision: ComisionRegistrada) -> None: ...

    @abstractmethod
    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> ComisionRegistrada | None: ...

    @abstractmethod
    def listar_por_venta_ids(self, ids: list[uuid.UUID]) -> list[ComisionRegistrada]: ...


class AuditoriaVentaRepository(ABC):
    @abstractmethod
    def guardar(self, registro: AuditoriaVenta) -> None: ...

    @abstractmethod
    def listar_por_venta_id(self, venta_id: uuid.UUID) -> list[AuditoriaVenta]: ...


class CorreoNoParseadoRepository(ABC):
    @abstractmethod
    def guardar(self, correo: CorreoNoParseado) -> None: ...

    @abstractmethod
    def existe_referencia(self, referencia: str) -> bool: ...

    @abstractmethod
    def listar_pendientes(self, max_intentos: int) -> list[CorreoNoParseado]:
        """Return rows where procesado is False AND intentos < max_intentos."""
        ...

    @abstractmethod
    def marcar_procesado(self, id: uuid.UUID) -> None: ...

    @abstractmethod
    def registrar_intento_fallido(self, id: uuid.UUID, error: str) -> None:
        """Increment intentos and set error_ultimo."""
        ...
