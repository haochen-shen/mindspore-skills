#!/usr/bin/env python
"""
Pre-tool-use hook - Logs tool inputs for each session.

All tool calls for a single session are logged to a JSON file
named by session_id.
"""

import json
import re
import sys
from pathlib import Path


# Get the current session_id from environment or file
def get_session_id():
    """Get session_id from environment or file."""
    # Check for session ID file
    session_file = Path.cwd() / ".claude" / ".session_id"
    if session_file.exists():
        with open(session_file, "r") as f:
            return f.read().strip()
    return "unknown"


# The session_id is passed in the hook input data
def log_session_start(session_id):
    """Initialize session log file when first tool call is made."""
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    session_log_path = log_dir / f"{session_id}.json"

    if not session_log_path.exists():
        session_data = {
            "session_id": session_id,
            "tool_calls": [],
        }
        with open(session_log_path, "w") as f:
            json.dump(session_data, f, indent=2)


# Security functions
def is_dangerous_rm_command(command):
    """
    Comprehensive detection of dangerous rm commands.
    Matches various forms of rm -rf and similar destructive patterns.
    """
    normalized = " ".join(command.lower().split())

    patterns = [
        r"\brm\s+.*-[a-z]*r[a-z]*f",
        r"\brm\s+.*-[a-z]*f[a-z]*r",
        r"\brm\s+--recursive\s+--force",
        r"\brm\s+--force\s+--recursive",
        r"\brm\s+-r\s+.*-f",
        r"\brm\s+-f\s+.*-r",
    ]

    for pattern in patterns:
        if re.search(pattern, normalized):
            return True

    dangerous_paths = [
        r"/",
        r"/\*",
        r"~",
        r"~/",
        r"\$HOME",
        r"\.\.",
        r"\*",
        r"\.",
        r"\.\s*$",
    ]

    if re.search(r"\brm\s+.*-[a-z]*r", normalized):
        for path in dangerous_paths:
            if re.search(path, normalized):
                return True

    return False


def is_env_file_access(tool_name, tool_input):
    """Check if any tool is accessing .env files with sensitive data."""
    if tool_name in ["Read", "Edit", "MultiEdit", "Write", "Bash"]:
        if tool_name in ["Read", "Edit", "MultiEdit", "Write"]:
            file_path = tool_input.get("file_path", "")
            if ".env" in file_path and not file_path.endswith(".env.sample"):
                return True
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            env_patterns = [
                r"\b\.env\b(?!\.sample)",
                r"cat\s+.*\.env\b(?!\.sample)",
                r"echo\s+.*>\s*\.env\b(?!\.sample)",
                r"touch\s+.*\.env\b(?!\.sample)",
                r"cp\s+.*\.env\b(?!\.sample)",
                r"mv\s+.*\.env\b(?!\.sample)",
            ]
            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True
    return False


def main():
    try:
        input_data = json.load(sys.stdin)
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})

        # Get session_id from hook input
        session_id = input_data.get("session_id", get_session_id())

        # Initialize session log if needed
        log_session_start(session_id)

        # Security checks
        if is_env_file_access(tool_name, tool_input):
            print(
                "BLOCKED: Access to .env files containing "
                "sensitive data is prohibited",
                file=sys.stderr,
            )
            sys.exit(2)

        if tool_name == "Bash":
            command = tool_input.get("command", "")
            if is_dangerous_rm_command(command):
                print(
                    "BLOCKED: Dangerous rm command detected and prevented",
                    file=sys.stderr,
                )
                sys.exit(2)

        # Log tool call to session file
        log_dir = Path.cwd() / "logs"
        session_log_path = log_dir / f"{session_id}.json"

        with open(session_log_path, "r") as f:
            session_data = json.load(f)

        # Add pre-tool-use log entry
        log_entry = input_data.copy()
        log_entry["phase"] = "pre_tool_use"

        session_data["tool_calls"].append(log_entry)

        with open(session_log_path, "w") as f:
            json.dump(session_data, f, indent=2)

        sys.exit(0)

    except (json.JSONDecodeError, Exception):
        sys.exit(0)


if __name__ == "__main__":
    main()
