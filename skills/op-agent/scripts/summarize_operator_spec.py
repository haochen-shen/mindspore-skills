#!/usr/bin/env python3
"""Print a minimal normalized operator spec from CLI inputs."""

from __future__ import annotations

import json
import sys


def main(argv: list[str]) -> None:
    spec = {
        "operator_name": argv[1] if len(argv) > 1 else "",
        "framework": argv[2] if len(argv) > 2 else "",
        "backend": argv[3] if len(argv) > 3 else "",
    }
    print(json.dumps(spec, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv)
