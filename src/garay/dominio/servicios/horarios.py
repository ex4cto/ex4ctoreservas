"""Pure domain helpers for tour schedule time management.

All functions are stateless and side-effect-free. They operate on canonical
"HH:MM" 24-hour strings and enforce the invariants: valid time, no duplicates,
chronological order.
"""

from __future__ import annotations

import re

from garay.dominio.servicios.errores import HorarioDuplicado, HorarioInvalido

# Regex that splits "HH:MM" canonical strings for display conversion.
_CANONICAL_RE = re.compile(r"^(\d{2}):(\d{2})$")


def normalizar_horario(texto: str) -> str:
    """Parse free-text time input and return canonical "HH:MM" (24h, zero-padded).

    Accepted formats:
      - 24-hour with colon: "19:00", "07:30", "0:00", "23:59"
      - 12-hour with am/pm (no space or with space): "7pm", "7:30am", "7 PM"
      - Hour-only (0-23) without meridian: "9", "07"

    Rejected:
      - Multi-digit inputs without colon separator: "730", "1930"
      - Invalid hours or minutes
      - Empty strings
      - Unrecognizable patterns

    Raises:
        HorarioInvalido: when the input cannot be interpreted as a valid time.
    """
    if not texto or not texto.strip():
        raise HorarioInvalido(f"Empty time input: {texto!r}")

    # Normalize: strip outer whitespace, collapse inner spaces, lowercase.
    t = texto.strip().lower()
    # Remove spaces around colon so "7 : 30" becomes "7:30".
    t = re.sub(r"\s*:\s*", ":", t)
    # Remove remaining spaces (handles "7 pm" → "7pm").
    t = t.replace(" ", "")

    # Detect and strip am/pm suffix.
    meridian: str | None = None
    for suffix, value in (("a.m.", "am"), ("p.m.", "pm"), ("am", "am"), ("pm", "pm")):
        if t.endswith(suffix):
            meridian = value
            t = t[: -len(suffix)]
            break

    # Now t is the numeric part only (e.g. "7", "7:30", "19:00").
    if not t:
        raise HorarioInvalido(f"No numeric component in: {texto!r}")

    # Parse hours and minutes.
    if ":" in t:
        parts = t.split(":")
        if len(parts) != 2:
            raise HorarioInvalido(f"Multiple colons in: {texto!r}")
        h_str, m_str = parts
    else:
        # Only accept 1 or 2 digit hour-only inputs (no colon, no ambiguity).
        if len(t) > 2:
            raise HorarioInvalido(
                f"Multi-digit input without colon separator is ambiguous: {texto!r}. "
                "Use HH:MM format (e.g. '7:30' not '730')."
            )
        h_str = t
        m_str = "0"

    try:
        h = int(h_str)
        m = int(m_str)
    except ValueError:
        raise HorarioInvalido(f"Non-numeric time component in: {texto!r}") from None

    if m < 0 or m > 59:
        raise HorarioInvalido(f"Minutes out of range [0-59]: {m} in {texto!r}")

    if meridian is not None:
        # 12-hour mode: hour must be 1-12.
        if h < 1 or h > 12:
            raise HorarioInvalido(
                f"Hour {h} out of range [1-12] for AM/PM format in: {texto!r}"
            )
        h = (h if h == 12 else h + 12) if meridian == "pm" else (0 if h == 12 else h)
    else:
        # 24-hour mode: hour must be 0-23.
        if h < 0 or h > 23:
            raise HorarioInvalido(f"Hour {h} out of range [0-23] in: {texto!r}")

    return f"{h:02d}:{m:02d}"


def formato_display(canonico: str) -> str:
    """Convert a canonical "HH:MM" (24h) string to AM/PM display format.

    Examples:
        "19:00" -> "7:00 PM"
        "07:30" -> "7:30 AM"
        "12:00" -> "12:00 PM"
        "00:00" -> "12:00 AM"

    The input is assumed to already be a valid canonical string. No validation
    is performed on the input.
    """
    m = _CANONICAL_RE.match(canonico)
    if not m:
        raise HorarioInvalido(f"Not a canonical HH:MM string: {canonico!r}")
    h = int(m.group(1))
    mins = int(m.group(2))

    if h == 0:
        display_h = 12
        suffix = "AM"
    elif h < 12:
        display_h = h
        suffix = "AM"
    elif h == 12:
        display_h = 12
        suffix = "PM"
    else:
        display_h = h - 12
        suffix = "PM"

    return f"{display_h}:{mins:02d} {suffix}"


def agregar_horario(actual: list[str], texto: str) -> list[str]:
    """Normalize texto and add it to the schedule list if it is not a duplicate.

    Returns a NEW sorted list (input is never mutated).

    Raises:
        HorarioInvalido: if texto cannot be parsed as a valid time.
        HorarioDuplicado: if the canonical value already exists in actual.
    """
    canonico = normalizar_horario(texto)
    if canonico in actual:
        raise HorarioDuplicado(
            f"Schedule {canonico!r} ({texto!r}) already exists in the list."
        )
    return sorted([*actual, canonico])


def quitar_horario(actual: list[str], canonico: str) -> list[str]:
    """Return a new list with the given canonical value removed.

    Idempotent: if the value is not present, the original list is returned as-is.
    The input list is never mutated.
    """
    return [h for h in actual if h != canonico]


def render_horarios(pares: list[tuple[str, str]]) -> str | None:
    """Render ordered (tour_name, canonical_hhmm) pairs for user-facing display.

    Rules:
    - Pairs whose horario is empty or None are filtered out.
    - If no pairs survive filtering → None (caller omits the row/line).
    - Single survivor → formato_display(horario) only — no tour name.
    - Multiple survivors → "Name HH:MM AP, Name HH:MM AP" (compact per-tour).

    Never emits a raw canonical 24h string in output.
    """
    survivors = [(name, h) for name, h in pares if h]
    if not survivors:
        return None
    if len(survivors) == 1:
        return formato_display(survivors[0][1])
    return ", ".join(f"{name} {formato_display(h)}" for name, h in survivors)
