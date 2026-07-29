from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date

from garay.dominio.clientes.entidades import Cliente
from garay.dominio.comisiones.entidades import ComisionRegistrada
from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.conciliacion.entidades import Conciliacion, Egreso, Ingreso
from garay.dominio.freelancers.entidades import Freelancer
from garay.dominio.puntos_venta.entidades import PuntoDeVenta
from garay.dominio.servicios.entidades import Servicio
from garay.dominio.tiquetera.entidades import Tiquetera
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
        self, nombre: str, desde: date, hasta: date
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


class EgresoRepository(ABC):
    @abstractmethod
    def guardar(self, egreso: Egreso) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Egreso | None: ...

    @abstractmethod
    def existe_referencia(self, referencia: str) -> bool: ...


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


class FreelancerRepository(ABC):
    @abstractmethod
    def guardar(self, freelancer: Freelancer) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Freelancer | None: ...

    @abstractmethod
    def listar_activos(self) -> list[Freelancer]: ...

    @abstractmethod
    def buscar_por_telegram_id(self, telegram_user_id: int) -> Freelancer | None: ...


class ClienteRepository(ABC):
    @abstractmethod
    def guardar(self, cliente: Cliente) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Cliente | None: ...


class ServicioRepository(ABC):
    @abstractmethod
    def guardar(self, servicio: Servicio) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> Servicio | None: ...

    @abstractmethod
    def listar(self) -> list[Servicio]: ...


class PuntoDeVentaRepository(ABC):
    @abstractmethod
    def guardar(self, punto: PuntoDeVenta) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: uuid.UUID) -> PuntoDeVenta | None: ...

    @abstractmethod
    def listar(self) -> list[PuntoDeVenta]: ...


class ReglasComisionRepository(ABC):
    @abstractmethod
    def buscar_por_tipo_cliente(self, tipo: TipoCliente) -> ReglasComision | None: ...

    @abstractmethod
    def guardar(self, reglas: ReglasComision) -> None: ...


class ComisionRegistradaRepository(ABC):
    @abstractmethod
    def guardar(self, comision: ComisionRegistrada) -> None: ...

    @abstractmethod
    def buscar_por_venta_id(self, venta_id: uuid.UUID) -> ComisionRegistrada | None: ...

    @abstractmethod
    def listar_por_venta_ids(self, ids: list[uuid.UUID]) -> list[ComisionRegistrada]: ...
