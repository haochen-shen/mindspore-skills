#!/usr/bin/env python3
"""Collect a minimal operator-build context snapshot.

First-version placeholder: this script is intentionally small and only records
basic workspace facts for later expansion.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    cwd = Path(os.getcwd()).resolve()
    data = {
        "working_dir": str(cwd),
        "has_git": (cwd / ".git").exists(),
        "files": sorted(p.name for p in cwd.iterdir())[:50] if cwd.exists() else [],
    }
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
