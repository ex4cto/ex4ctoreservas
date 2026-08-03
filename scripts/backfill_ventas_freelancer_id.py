"""One-off backfill: assign vendedor_id/cerrador_id to historical ventas.

Historical ventas (registered before Slice B) carry only a name string in
`vendedor_nombre`/`cerrador_nombre` and NULL ids. This script resolves those
names to a stable freelancer id using a curated alias map confirmed by Garay,
so reports stop showing the same person twice (e.g. "Mairele" vs "Mairelis").

Dry-run by default (prints what WOULD change, writes nothing). Pass --apply to
persist. Names not in the alias map (e.g. "Ruth", "Hebert" — externals / the
Crespo restaurant owner, not freelancers) are left NULL by design.
"""

from __future__ import annotations

import argparse
import os
import uuid

from sqlalchemy import create_engine, text

# Curated alias map (confirmed by Garay 2026-08-03): normalized historical
# participant name -> target freelancer `nombre`. Anything NOT listed here
# resolves to None and is left NULL (external / non-freelancer).
ALIAS: dict[str, str] = {
    "eduardo": "Eduardo",
    "david": "David",
    "tania": "Tania",
    "yolimar": "Yolimar",
    "ryan": "Ryan",
    "garay": "Garay",
    "kike": "Kike",  # merges the KiKe/Kike/kike case variants
    "mairele": "Mairelis",
    "maximar": "Maximo",
    "saida": "Zaida",  # S <-> Z spelling
}


def resolver_id(
    nombre: str | None, ids_por_nombre: dict[str, uuid.UUID]
) -> uuid.UUID | None:
    """Resolve a historical participant name to a freelancer id via the alias map.

    Case-insensitive + trimmed. Returns None for blank names, names not in the
    alias map, or when the aliased target has no matching freelancer.
    """
    if not nombre or not nombre.strip():
        return None
    target = ALIAS.get(nombre.strip().lower())
    if target is None:
        return None
    return ids_por_nombre.get(target.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="persist changes (default: dry-run)"
    )
    args = parser.parse_args()

    engine = create_engine(os.environ["GARAY_DATABASE_URL"], future=True)
    with engine.begin() as conn:
        ids_por_nombre: dict[str, uuid.UUID] = {}
        for r in conn.execute(text("SELECT id, nombre FROM freelancers")):
            ids_por_nombre[r.nombre.strip().lower()] = r.id

        rows = conn.execute(
            text(
                "SELECT id, vendedor_nombre, cerrador_nombre, vendedor_id, cerrador_id "
                "FROM ventas "
                "WHERE vendedor_id IS NULL OR cerrador_id IS NULL"
            )
        ).fetchall()

        resumen_target: dict[str, str] = {}
        resumen_n: dict[str, int] = {}
        sin_resolver: dict[str, int] = {}
        updates: list[tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None]] = []
        set_vend = set_cerr = 0

        for v in rows:
            new_vend = v.vendedor_id
            new_cerr = v.cerrador_id
            for slot, nombre, current in (
                ("vend", v.vendedor_nombre, v.vendedor_id),
                ("cerr", v.cerrador_nombre, v.cerrador_id),
            ):
                if current is not None or not nombre:
                    continue
                fid = resolver_id(nombre, ids_por_nombre)
                key = nombre.strip()
                if fid is None:
                    sin_resolver[key] = sin_resolver.get(key, 0) + 1
                    continue
                resumen_target[key] = ALIAS[nombre.strip().lower()]
                resumen_n[key] = resumen_n.get(key, 0) + 1
                if slot == "vend":
                    new_vend = fid
                    set_vend += 1
                else:
                    new_cerr = fid
                    set_cerr += 1
            if new_vend != v.vendedor_id or new_cerr != v.cerrador_id:
                updates.append((v.id, new_vend, new_cerr))

        print(f"Ventas con al menos un id NULL: {len(rows)}")
        print(f"\n=== SE ASIGNARIAN IDs ({set_vend} vendedor + {set_cerr} cerrador) ===")
        for name in sorted(resumen_n):
            print(f"  {name!r} -> {resumen_target[name]}: {resumen_n[name]} slot(s)")
        print("\n=== QUEDAN NULL (externos / sin mapeo) ===")
        for name in sorted(sin_resolver):
            print(f"  {name!r}: {sin_resolver[name]} slot(s)")
        print(f"\nFilas de venta a actualizar: {len(updates)}")

        if not args.apply:
            print("\n[DRY-RUN] No se escribio nada. Corre con --apply para persistir.")
            return

        for vid, nv, nc in updates:
            conn.execute(
                text("UPDATE ventas SET vendedor_id = :nv, cerrador_id = :nc WHERE id = :vid"),
                {"nv": nv, "nc": nc, "vid": vid},
            )
        print(f"\n[APPLY] {len(updates)} ventas actualizadas.")


if __name__ == "__main__":
    main()
