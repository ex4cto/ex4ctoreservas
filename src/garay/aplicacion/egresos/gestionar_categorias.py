"""Application service: manage egreso categories (list, create, toggle, edit)."""

from __future__ import annotations

from garay.dominio.conciliacion.categorias import (
    es_categoria_duplicada,
    es_categoria_protegida,
    sugerir_categoria_parecida,
)
from garay.dominio.conciliacion.entidades import CategoriaEgreso
from garay.dominio.conciliacion.errores import (
    CategoriaEgresoDuplicada,
    CategoriaEgresoProtegida,
)
from garay.dominio.puertos.repositorios import CategoriaEgresoRepository


def _normalizar_nombre(nombre: str) -> str:
    """Trim y colapso de espacios. Preserva mayusculas/acentos tal como se escribio."""
    return " ".join(nombre.split())


class GestionarCategoriasService:
    def __init__(self, categoria_repo: CategoriaEgresoRepository) -> None:
        self._repo = categoria_repo

    def listar_todas(self) -> list[CategoriaEgreso]:
        return self._repo.listar_todas()

    def sugerir_parecida(self, nombre: str) -> str | None:
        existentes = [c.nombre for c in self._repo.listar_todas()]
        return sugerir_categoria_parecida(nombre, existentes)

    def crear(self, nombre: str, descripcion: str = "") -> CategoriaEgreso:
        limpio = _normalizar_nombre(nombre)
        if not limpio:
            raise ValueError("El nombre de la categoria no puede estar vacio.")
        todas = self._repo.listar_todas()
        if es_categoria_duplicada(limpio, [c.nombre for c in todas]):
            raise CategoriaEgresoDuplicada(f"La categoria {limpio!r} ya existe.")
        orden = max((c.orden for c in todas), default=0) + 1
        categoria = CategoriaEgreso(
            nombre=limpio, descripcion=descripcion, activo=True, orden=orden
        )
        self._repo.guardar(categoria)
        return categoria

    def desactivar(self, nombre: str) -> None:
        if es_categoria_protegida(nombre):
            raise CategoriaEgresoProtegida(
                f"La categoria {nombre!r} esta protegida y no puede desactivarse."
            )
        self._reemplazar(nombre, activo=False)

    def activar(self, nombre: str) -> None:
        self._reemplazar(nombre, activo=True)

    def editar_descripcion(self, nombre: str, descripcion: str) -> None:
        self._reemplazar(nombre, descripcion=descripcion)

    def _reemplazar(
        self,
        nombre: str,
        *,
        activo: bool | None = None,
        descripcion: str | None = None,
    ) -> None:
        """Vuelve a guardar una categoria existente cambiando solo lo indicado."""
        actual = next(
            (c for c in self._repo.listar_todas() if c.nombre == nombre), None
        )
        if actual is None:
            raise ValueError(f"La categoria {nombre!r} no existe.")
        self._repo.guardar(
            CategoriaEgreso(
                nombre=actual.nombre,
                descripcion=descripcion if descripcion is not None else actual.descripcion,
                activo=activo if activo is not None else actual.activo,
                orden=actual.orden,
            )
        )
