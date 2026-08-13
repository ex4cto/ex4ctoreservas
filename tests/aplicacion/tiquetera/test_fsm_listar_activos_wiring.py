"""Integration test: verifies that main.py uses listar_activos() (not listar())
when building the FSM catalog. Inspects the production source as text so it
fails while main.py still uses listar() and passes after the switch.
"""

from __future__ import annotations

import ast
import pathlib

_MAIN_PY = (
    pathlib.Path(__file__).parents[3]
    / "src" / "garay" / "infraestructura" / "telegram" / "main.py"
)


def _catalog_build_calls_listar_activos() -> bool:
    """Parse main.py AST and verify the FSM catalog comprehension calls
    servicio_repo.listar_activos(), not servicio_repo.listar().

    Looks for an Attribute node with attr='listar_activos' on value.id containing
    'servicio_repo' inside the list comprehension that feeds the FSM.
    """
    source = _MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        # Find: `for s in servicio_repo.listar_activos()`  inside a list comp
        if not isinstance(node, ast.ListComp):
            continue
        for generator in node.generators:
            iter_node = generator.iter
            if (
                isinstance(iter_node, ast.Call)
                and isinstance(iter_node.func, ast.Attribute)
                and iter_node.func.attr == "listar_activos"
                and isinstance(iter_node.func.value, ast.Name)
                and "servicio_repo" in iter_node.func.value.id
            ):
                return True
    return False


def test_fsm_built_with_listar_activos() -> None:
    """main.py must use servicio_repo.listar_activos() for the FSM catalog build,
    not servicio_repo.listar()."""
    assert _catalog_build_calls_listar_activos(), (
        "main.py still calls servicio_repo.listar() for the FSM catalog. "
        "Switch it to servicio_repo.listar_activos() (task 3.2)."
    )
