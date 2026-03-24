#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collect_msprof.sh --stack <ms|pta> --script <train.py> --output-dir <dir>

Purpose:
  Scaffold a controlled profiling rerun by copying the training entry script to
  a sibling `*-perf.py` file, preparing stack-specific profiler instrumentation
  on the copy, and collecting profiling artifacts in the requested output
  directory.

Important:
  - The original training script is not modified.
  - The caller must specify `--stack ms` or `--stack pta`.
  - This scaffold is not yet a full injector; it prepares the copied script
    path and records metadata so the next implementation can add deterministic
    stack-specific edits.

Example:
  collect_msprof.sh --stack ms --script train.py --output-dir /tmp/msprof-run

Outputs:
  - output directory with profiler artifacts
  - copied perf entry script path metadata
  - collect_metadata.json
  - hotspot_summary.md (if a recognizable operator time table is found)
  - hotspot_summary.json (if a recognizable operator time table is found)

This is a helper scaffold for future controlled execution. It now centers on
copying the Python entry script and preserving the original CLI surface instead
of wrapping the original command in one universal external `msprof` launcher.
EOF
}

OUTPUT_DIR=""
STACK=""
SCRIPT_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stack)
      STACK="${2:-}"
      shift 2
      ;;
    --script)
      SCRIPT_PATH="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
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

if [[ -z "$STACK" ]]; then
  echo "--stack is required" >&2
  usage >&2
  exit 2
fi

if [[ "$STACK" != "ms" && "$STACK" != "pta" ]]; then
  echo "--stack must be either 'ms' or 'pta'" >&2
  exit 2
fi

if [[ -z "$SCRIPT_PATH" ]]; then
  echo "--script is required" >&2
  usage >&2
  exit 2
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
  echo "Training entry script does not exist: $SCRIPT_PATH" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"

SCRIPT_DIRNAME="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
SCRIPT_BASENAME="$(basename "$SCRIPT_PATH")"
SCRIPT_STEM="${SCRIPT_BASENAME%.py}"
PERF_SCRIPT_PATH="$SCRIPT_DIRNAME/${SCRIPT_STEM}-perf.py"

cp "$SCRIPT_PATH" "$PERF_SCRIPT_PATH"

cat > "$OUTPUT_DIR/collect_metadata.json" <<EOF
{
  "stack": "$STACK",
  "output_dir": "$OUTPUT_DIR",
  "source_script": "$SCRIPT_PATH",
  "perf_script": "$PERF_SCRIPT_PATH",
  "injector_status": "scaffold_only"
}
EOF

echo "Copied training entry script:"
echo "  $SCRIPT_PATH -> $PERF_SCRIPT_PATH"
echo "No profiler injection is implemented yet in this scaffold."
echo "Add the stack-specific profiler hooks to the copied script before running it."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMARY_SCRIPT="$SCRIPT_DIR/summarize_msprof_hotspots.py"
BRIEF_SCRIPT="$SCRIPT_DIR/build_hotspot_brief.py"

if [[ -f "$SUMMARY_SCRIPT" ]]; then
  echo "Attempting to summarize msprof hotspots from existing artifacts, if any..."
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
