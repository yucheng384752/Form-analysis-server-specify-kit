"""Backward-compatible shim.

This script was archived to keep the backend root tidy.
New location: scripts/manual/check_p123_relation.py
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    target = Path(__file__).resolve().parent / "scripts" / "manual" / "check_p123_relation.py"
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
