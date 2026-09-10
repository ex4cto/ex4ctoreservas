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
    """Parse main.py AST and verify it calls servicio_repo.listar_activos().

    Checks the call anywhere (the result may be bound to a variable that feeds
    both the FSM catalog and the permite_ninos map), not only inline in a
    comprehension. The invariant is: listar_activos(), never bare listar().
    """
    source = _MAIN_PY.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "listar_activos"
            and isinstance(node.func.value, ast.Name)
            and "servicio_repo" in node.func.value.id
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
