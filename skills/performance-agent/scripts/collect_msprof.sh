#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collect_msprof.sh --output-dir <dir> -- <original run command ...>

Purpose:
  Rerun the same Ascend workload command under an msprof launcher and write
  profiling artifacts to the requested output directory.

Important:
  - This helper does NOT ask the caller to specify `ms` or `pta`.
  - The framework is inferred from the command being rerun; the same command is
    executed again under msprof collection.
  - The exact msprof launch syntax is intentionally delegated to
    `MSPROF_LAUNCHER`, because deployment environments often wrap msprof
    differently.

Required environment:
  MSPROF_LAUNCHER
    Shell snippet used as the msprof collection prefix.
    It must contain the literal token "__OUT_DIR__" which will be replaced with
    the requested output directory.

Example:
  export MSPROF_LAUNCHER='msprof --output=__OUT_DIR__'
  collect_msprof.sh --output-dir /tmp/msprof-run -- python train.py --config x.yaml

Outputs:
  - output directory with profiler artifacts
  - run_command.txt
  - collect_metadata.json
  - hotspot_summary.md (if a recognizable operator time table is found)
  - hotspot_summary.json (if a recognizable operator time table is found)

This is a helper scaffold for future controlled execution. It avoids hardcoding
framework-specific inputs and assumes the caller is rerunning the same command
that already ran successfully on Ascend.
EOF
}

OUTPUT_DIR=""
RUN_CMD=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      RUN_CMD=("$@")
      break
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
  echo "--output-dir is required" >&2
  usage >&2
  exit 2
fi

if [[ ${#RUN_CMD[@]} -eq 0 ]]; then
  echo "A run command is required after --" >&2
  usage >&2
  exit 2
fi

if [[ -z "${MSPROF_LAUNCHER:-}" ]]; then
  cat >&2 <<'EOF'
MSPROF_LAUNCHER is not set.

Set it to the msprof launch prefix used in your environment and include the
literal token "__OUT_DIR__" so this helper can inject the output directory.
EOF
  exit 2
fi

if [[ "$MSPROF_LAUNCHER" != *"__OUT_DIR__"* ]]; then
  echo 'MSPROF_LAUNCHER must contain the literal token "__OUT_DIR__"' >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"

CMD_STR=""
printf -v CMD_STR '%q ' "${RUN_CMD[@]}"
CMD_STR="${CMD_STR% }"

LAUNCHER="${MSPROF_LAUNCHER//__OUT_DIR__/$OUTPUT_DIR}"

printf '%s\n' "$CMD_STR" > "$OUTPUT_DIR/run_command.txt"

cat > "$OUTPUT_DIR/collect_metadata.json" <<EOF
{
  "output_dir": "$OUTPUT_DIR",
  "launcher": "$LAUNCHER",
  "command": "$CMD_STR"
}
EOF

echo "Running under msprof launcher:"
echo "  $LAUNCHER $CMD_STR"

# Intentionally use shell evaluation so the launcher can be a site-specific
# wrapper or msprof prefix. The workload command is already safely shell-quoted.
eval "$LAUNCHER $CMD_STR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMARY_SCRIPT="$SCRIPT_DIR/summarize_msprof_hotspots.py"
BRIEF_SCRIPT="$SCRIPT_DIR/build_hotspot_brief.py"

if [[ -f "$SUMMARY_SCRIPT" ]]; then
  echo "Attempting to summarize msprof hotspots..."
  if python "$SUMMARY_SCRIPT" \
    --input-dir "$OUTPUT_DIR" \
    --output-md "$OUTPUT_DIR/hotspot_summary.md" \
    --output-json "$OUTPUT_DIR/hotspot_summary.json"; then
    echo "Hotspot summary written to:"
    echo "  $OUTPUT_DIR/hotspot_summary.md"
    echo "  $OUTPUT_DIR/hotspot_summary.json"
    if [[ -f "$BRIEF_SCRIPT" ]]; then
      echo "Building hotspot brief..."
      if python "$BRIEF_SCRIPT" \
        --input-json "$OUTPUT_DIR/hotspot_summary.json" \
        --output-json "$OUTPUT_DIR/hotspot_brief.json" \
        --output-md "$OUTPUT_DIR/hotspot_brief.md"; then
        echo "Hotspot brief written to:"
        echo "  $OUTPUT_DIR/hotspot_brief.md"
        echo "  $OUTPUT_DIR/hotspot_brief.json"
      else
        echo "Hotspot brief generation failed." >&2
      fi
    fi
  else
    echo "Hotspot summary was not generated. No recognizable operator time table was found." >&2
  fi
else
  echo "Hotspot summary script not found: $SUMMARY_SCRIPT" >&2
fi
