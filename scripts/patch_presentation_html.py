#!/usr/bin/env python3
"""Patch reveal.js navigationMode after quarto render."""

from __future__ import annotations

import sys
from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "presentation" / "grpc-intro.html"


def main() -> int:
    if not HTML.exists():
        print(f"HTML no encontrado: {HTML}", file=sys.stderr)
        return 1

    text = HTML.read_text(encoding="utf-8")
    patched = text.replace("navigationMode: 'default'", "navigationMode: 'vertical'")
    if patched == text:
        print("Sin cambios (navigationMode ya configurado).")
    else:
        HTML.write_text(patched, encoding="utf-8")
        print("navigationMode -> vertical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
