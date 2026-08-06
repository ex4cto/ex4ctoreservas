from __future__ import annotations


class ErrorImportacion(Exception):
    """Base de errores de la importacion de ventas historicas."""


class DescripcionSinMapeo(ErrorImportacion):
    """La descripcion del Excel no tiene un servicio mapeado en el alias."""


class ImportacionConNombresNoResueltos(ErrorImportacion):
    """Uno o mas nombres de participante del Excel no resuelven a un unico freelancer.

    Aborta la importacion completa antes de persistir nada (all-or-nothing).
    Distingue nombres sin match (0) de nombres ambiguos (>=2) para que el
    operador sepa el remedio: corregir el nombre en la hoja/roster (0) o
    desambiguar a quien pertenece la venta (>=2).
    """

    def __init__(
        self,
        no_encontrados: list[tuple[int, str]],
        ambiguos: list[tuple[int, str]],
    ) -> None:
        self.no_encontrados = no_encontrados
        self.ambiguos = ambiguos
        super().__init__(self._mensaje())

    def _mensaje(self) -> str:
        partes: list[str] = []
        if self.no_encontrados:
            lineas = ", ".join(f"fila {i}: {n!r}" for i, n in self.no_encontrados)
            partes.append(
                f"Sin match en el roster ({len(self.no_encontrados)}): {lineas}"
            )
        if self.ambiguos:
            lineas = ", ".join(f"fila {i}: {n!r}" for i, n in self.ambiguos)
            partes.append(
                f"Ambiguos / mas de un match ({len(self.ambiguos)}): {lineas}"
            )
        return "Importacion abortada, nada fue persistido. " + " | ".join(partes)


class VentaCrespoSinParticipantes(ErrorImportacion):
    """One or more Crespo rows are missing the vendedor or cerrador name needed to
    determine the number of people in the sale (1 vs 2 personas for buscar_regla).

    Aborts the entire import before any persistence (all-or-nothing, consistent
    with ImportacionConNombresNoResueltos).  The error message names every
    offending row number so the operator knows exactly which rows to fix.
    """

    def __init__(self, filas: list[int]) -> None:
        self.filas = filas
        super().__init__(self._mensaje())

    def _mensaje(self) -> str:
        nums = ", ".join(str(i) for i in self.filas)
        return (
            "Importacion abortada, nada fue persistido. "
            f"Filas Crespo sin vendedor o cerrador (se requieren para determinar "
            f"1 o 2 personas): {nums}"
        )


class PuntoCrespoNoConfigurado(ErrorImportacion):
    """The batch contains Crespo rows but the 'Crespo' punto de venta was not found
    in the database.  This is a seeding/configuration error: without the Crespo punto
    the motor cannot compute the 20% capa, and the commission would be silently zeroed.

    Raised before any persistence so the operator can seed the punto and re-run.
    """

    def __init__(self) -> None:
        super().__init__(
            "Importacion abortada: el lote contiene filas Crespo pero el punto de venta "
            "'Crespo' no existe en la base de datos. "
            "Ejecute el seed (scripts/seed.py) y vuelva a importar."
        )
