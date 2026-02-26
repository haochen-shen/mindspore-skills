#!/usr/bin/env python3
"""
Post-tool-use hook - Logs tool outputs for each session.

All tool calls for a single session are logged to a JSON file
named by session_id.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_session_id():
    """Get session_id from environment or file."""
    session_file = Path.cwd() / ".claude" / ".session_id"
    if session_file.exists():
        with open(session_file, "r") as f:
            return f.read().strip()
    return "unknown"


def run_linting(file_path):
    """
    Automatically perform code optimization and static analysis based on
    local configuration files.
    """
    if not file_path.endswith(".py") or not os.path.exists(file_path):
        return None

    subprocess.run(["isort", file_path], capture_output=True)
    subprocess.run(["black", file_path], capture_output=True)

    result = subprocess.run(
        ["flake8", file_path],
        capture_output=True,
        text=True
    )

    if result.stdout.strip():
        return result.stdout.strip()

    return None


def main():
    try:
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Get session_id from hook input
        session_id = input_data.get("session_id", get_session_id())

        error_to_feedback = None

        if tool_name in ["Write", "Edit", "MultiEdit"]:
            file_path = tool_input.get("file_path")
            if file_path:
                error_to_feedback = run_linting(file_path)

        # Log to session file
        log_dir = Path.cwd() / "logs"
        session_log_path = log_dir / f"{session_id}.json"

        if session_log_path.exists():
            with open(session_log_path, "r") as f:
                session_data = json.load(f)
        else:
            # Initialize if doesn't exist
            session_data = {
                "session_id": session_id,
                "tool_calls": [],
            }

        # Add post-tool-use log entry
        log_entry = input_data.copy()
        log_entry["phase"] = "post_tool_use"

        session_data["tool_calls"].append(log_entry)

        with open(session_log_path, "w") as f:
            json.dump(session_data, f, indent=2)

        if error_to_feedback:
            msg = "\n[Quality Check Failed]\n"
            msg += error_to_feedback
            print(msg, file=sys.stderr)
            sys.exit(2)

        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
