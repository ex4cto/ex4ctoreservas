"""HTML-to-text normalization for forwarded bank emails.

Gmail auto-forwards resend the bank's original message untouched. For some banks
(e.g. Nequi) that original is HTML-only, with an empty text/plain part, whereas a
manual Gmail forward re-composes a clean text/plain. Bank parsers expect plain
text, so when only HTML is available we derive text from it: drop style/script
blocks, strip tags, decode HTML entities, and collapse whitespace.
"""

from __future__ import annotations

import re
from html import unescape

_STYLE_SCRIPT = re.compile(r"(?is)<(style|script)\b[^>]*>.*?</\1>")
_ETIQUETAS = re.compile(r"<[^>]+>")


def html_a_texto(html: str) -> str:
    """Convert an HTML body into collapsed plain text.

    ``<style>``/``<script>`` blocks are removed with their content; remaining
    tags become a single space so adjacent words stay separated; HTML entities
    are decoded; and runs of whitespace collapse to single spaces.
    """
    sin_bloques = _STYLE_SCRIPT.sub(" ", html)
    sin_etiquetas = _ETIQUETAS.sub(" ", sin_bloques)
    return " ".join(unescape(sin_etiquetas).split())
