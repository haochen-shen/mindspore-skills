#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from python_selection import resolve_selected_python


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the selected Python interpreter for readiness-agent")
    parser.add_argument("--working-dir", required=True, help="workspace root")
    parser.add_argument("--selected-python", help="explicit Python interpreter for the workspace")
    parser.add_argument("--selected-env-root", help="explicit environment root for the workspace")
    parser.add_argument("--output-json", required=True, help="path to write selected python JSON")
    args = parser.parse_args()

    root = Path(args.working_dir).resolve()
    result = resolve_selected_python(
        root=root,
        selected_python=args.selected_python,
        selected_env_root=args.selected_env_root,
    )
    output = Path(args.output_json)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "selection_status": result["selection_status"],
                "selection_source": result["selection_source"],
                "selected_python": result["selected_python"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
