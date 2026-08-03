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
