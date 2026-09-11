"""One-off backfill: set display = nombre_completo for all freelancers.

Before this change, `display` was derived via `derivar_display()` (e.g.
"Bryan Castro" -> "Bryan C."). The new rule is display = nombre_completo
verbatim. This script aligns existing rows with that rule.

Dry-run by default (prints what WOULD change, writes nothing). Pass --apply to
persist.
"""

from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="persist changes (default: dry-run)"
    )
    args = parser.parse_args()

    engine = create_engine(os.environ["GARAY_DATABASE_URL"], future=True)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, nombre_completo, display "
                "FROM freelancers "
                "WHERE nombre_completo IS NOT NULL"
            )
        ).fetchall()

        to_update = [r for r in rows if r.display != r.nombre_completo]

        print(f"Freelancers con nombre_completo: {len(rows)}")
        print(f"Freelancers donde display != nombre_completo: {len(to_update)}")

        for r in to_update:
            print(f"  id={r.id!s:.36}  display={r.display!r} -> {r.nombre_completo!r}")

        if not args.apply:
            print("\n[DRY-RUN] No se escribio nada. Corre con --apply para persistir.")
            return

        conn.execute(
            text(
                "UPDATE freelancers "
                "SET display = nombre_completo "
                "WHERE nombre_completo IS NOT NULL"
            )
        )
        print(f"\n[APPLY] {len(to_update)} fila(s) actualizada(s).")


if __name__ == "__main__":
    main()
