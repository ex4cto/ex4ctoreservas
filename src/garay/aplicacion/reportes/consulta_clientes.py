"""ConsultaClientesService — flattened cliente rows for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from garay.dominio.puertos.repositorios import ClienteRepository


@dataclass(frozen=True)
class FilaClienteConsulta:
    nombre: str
    tipo: str
    telefono: str | None
    email: str | None
    hotel: str | None
    numero_habitacion: str | None
    identificacion: str | None
    tipo_identificacion: str | None


class ConsultaClientesService:
    def __init__(self, clientes: ClienteRepository) -> None:
        self._clientes = clientes

    def ejecutar(self) -> list[FilaClienteConsulta]:
        return [
            FilaClienteConsulta(
                nombre=c.nombre,
                tipo=str(c.tipo),
                telefono=c.telefono,
                email=c.email,
                hotel=c.hotel,
                numero_habitacion=c.numero_habitacion,
                identificacion=c.identificacion,
                tipo_identificacion=c.tipo_identificacion,
            )
            for c in self._clientes.listar()
        ]
