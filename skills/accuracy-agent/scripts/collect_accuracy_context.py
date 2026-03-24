#!/usr/bin/env python3
"""Collect a minimal accuracy-context snapshot for later diagnosis."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    cwd = Path(os.getcwd()).resolve()
    data = {
        "working_dir": str(cwd),
        "candidate_metric_files": sorted(
            str(p)
            for p in list(cwd.glob("**/*.json")) + list(cwd.glob("**/*.log"))
            if p.is_file()
        )[:50],
    }
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
