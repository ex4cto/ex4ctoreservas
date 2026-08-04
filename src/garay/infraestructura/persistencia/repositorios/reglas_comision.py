from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from garay.dominio.comisiones.reglas import ReglasComision
from garay.dominio.comun.tipos import TipoCliente
from garay.dominio.puertos.repositorios import ReglasComisionRepository
from garay.infraestructura.persistencia.modelos import ReglasComisionModel


def to_orm(r: ReglasComision) -> ReglasComisionModel:
    return ReglasComisionModel(
        id=r.id,
        tipo_cliente=str(r.tipo_cliente),
        porcentaje_vendedor=r.porcentaje_vendedor,
        porcentaje_cerrador=r.porcentaje_cerrador,
        porcentaje_referido_maximo=r.porcentaje_referido_maximo,
        punto_de_venta_nombre=r.punto_de_venta_nombre,
        numero_personas=r.numero_personas,
    )


def to_domain(m: ReglasComisionModel) -> ReglasComision:
    return ReglasComision(
        id=m.id,
        tipo_cliente=TipoCliente(m.tipo_cliente),
        porcentaje_vendedor=m.porcentaje_vendedor,
        porcentaje_cerrador=m.porcentaje_cerrador,
        porcentaje_referido_maximo=m.porcentaje_referido_maximo,
        punto_de_venta_nombre=m.punto_de_venta_nombre,
        numero_personas=m.numero_personas,
    )


class SQLAReglasComisionRepository(ReglasComisionRepository):
    def __init__(self, sf: sessionmaker[Session]) -> None:
        self._sf = sf

    def guardar(self, reglas: ReglasComision) -> None:
        with self._sf.begin() as session:
            session.merge(to_orm(reglas))

    def buscar_regla(
        self,
        tipo: TipoCliente,
        punto_nombre: str | None,
        numero_personas: int | None,
    ) -> ReglasComision | None:
        """Two-step point-specific + global-fallback rule selector (design B3).

        C3 guard: exactly one of (punto_nombre, numero_personas) non-None is
        an invalid caller combination — raises ValueError.
        """
        # C3: both must be None together, or both must be non-None together.
        if (punto_nombre is None) != (numero_personas is None):
            raise ValueError(
                "buscar_regla: punto_nombre and numero_personas must both be "
                "None (global lookup) or both be non-None (point-specific lookup). "
                f"Got punto_nombre={punto_nombre!r}, numero_personas={numero_personas!r}."
            )

        with self._sf.begin() as session:
            # Step 1: point-specific match (ignores tipo_cliente per design B2).
            if punto_nombre is not None and numero_personas is not None:
                row = session.execute(
                    select(ReglasComisionModel).where(
                        ReglasComisionModel.punto_de_venta_nombre == punto_nombre,
                        ReglasComisionModel.numero_personas == numero_personas,
                    )
                ).scalar_one_or_none()
                if row is not None:
                    return to_domain(row)
                # Step 1 missed — no point-specific row found; return None
                # (do NOT fall through to global: a Crespo sale with no matching
                # row should fail loudly at the service layer, not silently apply
                # the wrong global rule — design S3).
                return None

            # Step 2: global fallback — IS NULL guards are mandatory (design B3).
            row = session.execute(
                select(ReglasComisionModel).where(
                    ReglasComisionModel.tipo_cliente == str(tipo),
                    ReglasComisionModel.punto_de_venta_nombre.is_(None),
                    ReglasComisionModel.numero_personas.is_(None),
                )
            ).scalar_one_or_none()
            return to_domain(row) if row is not None else None

    def buscar_por_tipo_cliente(self, tipo: TipoCliente) -> ReglasComision | None:
        # Filters IS NULL on punto_de_venta_nombre and numero_personas so that
        # point-specific rows (e.g. Crespo) never appear in this result set.
        # Without these guards, scalar_one_or_none() raises MultipleResultsFound
        # whenever two rows share the same tipo_cliente (design B1).
        with self._sf.begin() as session:
            row = session.execute(
                select(ReglasComisionModel).where(
                    ReglasComisionModel.tipo_cliente == str(tipo),
                    ReglasComisionModel.punto_de_venta_nombre.is_(None),
                    ReglasComisionModel.numero_personas.is_(None),
                )
            ).scalar_one_or_none()
            return to_domain(row) if row else None
