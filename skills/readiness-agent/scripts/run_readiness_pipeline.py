#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from build_readiness_report import (
    write_readiness_report,
)
from collect_readiness_checks import probe_readiness
from discover_execution_target import normalize_target_hint, resolve_target_state
from execute_env_fix import repair_readiness
from python_selection import derive_env_root_from_python
from readiness_state import ArtifactPaths, PipelinePassState, ReadinessState


VALUE_FLAGS = {
    "--working-dir",
    "--output-dir",
    "--target",
    "--framework-hint",
    "--cann-path",
    "--mode",
    "--entry-script",
    "--selected-python",
    "--selected-env-root",
    "--config-path",
    "--model-path",
    "--model-hub-id",
    "--dataset-path",
    "--dataset-hub-id",
    "--dataset-split",
    "--checkpoint-path",
    "--task-smoke-cmd",
    "--fix-scope",
    "--python-version",
    "--path-profile",
    "--timeout-seconds",
}
BOOL_FLAGS = {
    "--check",
    "--fix",
    "--auto",
    "--allow-network",
    "--verbose",
}
HELP_FLAGS = {"-h", "--help"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_optional_path(value: Optional[str], root: Path) -> Optional[Path]:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def sanitize_cli_args(raw_args: List[str]) -> Tuple[List[str], List[dict]]:
    sanitized: List[str] = []
    ignored: List[dict] = []
    index = 0

    while index < len(raw_args):
        token = raw_args[index]
        if token in HELP_FLAGS:
            sanitized.append(token)
            index += 1
            continue

        if token.startswith("--"):
            flag, has_inline_value, inline_value = token.partition("=")

            if flag in BOOL_FLAGS:
                sanitized.append(flag)
                if has_inline_value:
                    ignored.append(
                        {
                            "token": token,
                            "reason": "bool_flag_inline_value_ignored",
                        }
                    )
                index += 1
                continue

            if flag in VALUE_FLAGS:
                if has_inline_value:
                    if inline_value:
                        sanitized.extend([flag, inline_value])
                    else:
                        ignored.append({"token": token, "reason": "missing_value"})
                    index += 1
                    continue

                if index + 1 < len(raw_args) and not raw_args[index + 1].startswith("-"):
                    sanitized.extend([flag, raw_args[index + 1]])
                    index += 2
                    continue

                ignored.append({"token": token, "reason": "missing_value"})
                index += 1
                continue

            ignored.append({"token": token, "reason": "unknown_flag"})
            if not has_inline_value and index + 1 < len(raw_args) and not raw_args[index + 1].startswith("-"):
                ignored.append({"token": raw_args[index + 1], "reason": "unknown_flag_value"})
                index += 2
                continue

            index += 1
            continue

        if token.startswith("-"):
            ignored.append({"token": token, "reason": "unknown_short_flag"})
            if index + 1 < len(raw_args) and not raw_args[index + 1].startswith("-"):
                ignored.append({"token": raw_args[index + 1], "reason": "unknown_short_flag_value"})
                index += 2
                continue

            index += 1
            continue

        ignored.append({"token": token, "reason": "unsupported_positional_argument"})
        index += 1

    return sanitized, ignored


def write_inputs_snapshot(
    args: argparse.Namespace,
    working_dir: Path,
    output_dir: Path,
    path: Path,
    raw_cli_args: List[str],
    ignored_cli_args: List[dict],
) -> None:
    payload = {
        "working_dir": str(working_dir),
        "output_dir": str(output_dir),
        "target": args.target,
        "framework_hint": args.framework_hint,
        "cann_path": args.cann_path,
        "mode": args.mode,
        "verbose": bool(getattr(args, "verbose", False)),
        "entry_script": args.entry_script,
        "selected_python": args.selected_python,
        "selected_env_root": args.selected_env_root,
        "config_path": args.config_path,
        "model_path": args.model_path,
        "model_hub_id": args.model_hub_id,
        "dataset_path": args.dataset_path,
        "dataset_hub_id": args.dataset_hub_id,
        "dataset_split": args.dataset_split,
        "checkpoint_path": args.checkpoint_path,
        "task_smoke_cmd": args.task_smoke_cmd,
        "allow_network": args.allow_network,
        "fix_scope": args.fix_scope,
        "python_version": args.python_version,
        "timeout_seconds": args.timeout_seconds,
        "path_profile": args.path_profile,
        "raw_cli_args": raw_cli_args,
        "ignored_cli_args": ignored_cli_args,
    }
    write_json(path, payload)


def resolve_env_root_for_fix(
    working_dir: Path,
    selected_python: Optional[str],
    selected_env_root: Optional[str],
    selection: dict,
) -> Path:
    explicit_env_root = resolve_optional_path(selected_env_root, working_dir)
    if explicit_env_root:
        return explicit_env_root

    explicit_python = resolve_optional_path(selected_python, working_dir)
    if explicit_python:
        derived = derive_env_root_from_python(explicit_python)
        if derived:
            return derived.resolve()

    current_env_root = selection.get("selected_env_root")
    if current_env_root:
        return Path(str(current_env_root)).resolve()

    return (working_dir / ".venv").resolve()


def run_pipeline_pass(
    args: argparse.Namespace,
    working_dir: Path,
    selected_python: Optional[str],
    selected_env_root: Optional[str],
) -> PipelinePassState:
    target_state = resolve_target_state(
        root=working_dir,
        target_hint=normalize_target_hint(args.target),
        framework_hint=args.framework_hint,
        cann_path_hint=Path(args.cann_path) if args.cann_path else None,
        entry_script_hint=Path(args.entry_script) if args.entry_script else None,
        config_path_hint=Path(args.config_path) if args.config_path else None,
        model_path_hint=Path(args.model_path) if args.model_path else None,
        model_hub_id_hint=args.model_hub_id,
        dataset_path_hint=Path(args.dataset_path) if args.dataset_path else None,
        dataset_hub_id_hint=args.dataset_hub_id,
        dataset_split_hint=args.dataset_split,
        checkpoint_path_hint=Path(args.checkpoint_path) if args.checkpoint_path else None,
        task_smoke_cmd_hint=args.task_smoke_cmd,
        selected_python_hint=selected_python,
        selected_env_root_hint=selected_env_root,
    )
    selection = target_state["selection"]
    target = target_state["target"]
    probe_result = probe_readiness(target, working_dir, args.timeout_seconds)

    return PipelinePassState(
        selection=selection,
        target=target,
        closure=probe_result["closure"],
        task_smoke_checks=probe_result["task_smoke_checks"],
        checks=probe_result["checks"],
        normalized=probe_result["normalized"],
    )


def run_fix_plan_and_execution(
    args: argparse.Namespace,
    working_dir: Path,
    pipeline_state: PipelinePassState,
) -> Tuple[dict, dict]:
    selection = pipeline_state.selection
    selected_python = args.selected_python or selection.get("selected_python")
    selected_env_root = args.selected_env_root
    fallback_env_root = selection.get("selected_env_root")
    return repair_readiness(
        blockers=pipeline_state.normalized.get("blockers_detailed", []),
        closure=pipeline_state.closure,
        allow_network=args.allow_network,
        fix_scope=args.fix_scope,
        working_dir=working_dir,
        mode=args.mode,
        selected_python=selected_python,
        selected_env_root=selected_env_root,
        fallback_env_root=fallback_env_root,
        python_version=args.python_version,
        path_profile=args.path_profile,
    )


def debug_artifacts_enabled(args: argparse.Namespace) -> bool:
    env_value = (os.environ.get("READINESS_DEBUG_ARTIFACTS") or "").strip().lower()
    return bool(getattr(args, "verbose", False) or env_value in {"1", "true", "yes", "on"})


def normalize_mode_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> str:
    alias_modes = [
        mode
        for mode, enabled in (
            ("check", getattr(args, "check", False)),
            ("fix", getattr(args, "fix", False)),
            ("auto", getattr(args, "auto", False)),
        )
        if enabled
    ]
    if len(alias_modes) > 1:
        parser.error("use at most one of --check, --fix, or --auto")

    alias_mode = alias_modes[0] if alias_modes else None
    explicit_mode = args.mode
    if alias_mode and explicit_mode and explicit_mode != alias_mode:
        parser.error("--mode conflicts with the requested alias flag")

    if alias_mode:
        return alias_mode
    if explicit_mode:
        return explicit_mode
    return "check"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full readiness-agent helper pipeline with optional env re-entry",
        allow_abbrev=False,
    )
    parser.add_argument("--working-dir", help="workspace root (defaults to the current shell path)")
    parser.add_argument("--output-dir", help="output directory for readiness artifacts (defaults to <working_dir>/readiness-output)")
    parser.add_argument("--target", default="auto", help="training, inference, or auto")
    parser.add_argument("--framework-hint", help="explicit framework preference such as mindspore or pta")
    parser.add_argument("--cann-path", help="explicit CANN root or set_env.sh path")
    parser.add_argument("--mode", choices=("check", "fix", "auto"), help="check, fix, or auto")
    parser.add_argument("--check", action="store_true", help="alias for --mode check")
    parser.add_argument("--fix", action="store_true", help="alias for --mode fix")
    parser.add_argument("--auto", action="store_true", help="alias for --mode auto")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="accepted for caller compatibility; also enables a single aggregated debug snapshot",
    )
    parser.add_argument("--entry-script", help="explicit entry script path")
    parser.add_argument("--selected-python", help="explicit Python interpreter for the workspace")
    parser.add_argument("--selected-env-root", help="explicit environment root for the workspace")
    parser.add_argument("--config-path", help="explicit config path")
    parser.add_argument("--model-path", help="explicit model path")
    parser.add_argument("--model-hub-id", help="explicit Hugging Face model repo ID")
    parser.add_argument("--dataset-path", help="explicit dataset path")
    parser.add_argument("--dataset-hub-id", help="explicit Hugging Face dataset repo ID")
    parser.add_argument("--dataset-split", help="explicit dataset split for remote dataset download")
    parser.add_argument("--checkpoint-path", help="explicit checkpoint path")
    parser.add_argument("--task-smoke-cmd", help="explicit minimal task smoke command")
    parser.add_argument("--allow-network", action="store_true", help="allow network-dependent remediation planning")
    parser.add_argument("--fix-scope", default="safe-user-space", help="active fix scope")
    parser.add_argument("--python-version", help="Python version hint for environment creation")
    parser.add_argument("--path-profile", help="shell profile path for PATH repair")
    parser.add_argument("--timeout-seconds", type=int, default=10, help="timeout for explicit task smoke execution")
    raw_cli_args = sys.argv[1:]
    sanitized_cli_args, ignored_cli_args = sanitize_cli_args(raw_cli_args)
    args = parser.parse_args(sanitized_cli_args)
    args.mode = normalize_mode_args(parser, args)

    working_dir = Path(args.working_dir).resolve() if args.working_dir else Path.cwd().resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (working_dir / "readiness-output").resolve()
    paths = ArtifactPaths.for_output_dir(output_dir)
    paths.meta_dir.mkdir(parents=True, exist_ok=True)
    state = ReadinessState(working_dir=working_dir, output_dir=output_dir, mode=args.mode)
    write_inputs_snapshot(
        args,
        working_dir,
        output_dir,
        paths.inputs_json,
        raw_cli_args,
        ignored_cli_args,
    )

    initial_state = run_pipeline_pass(
        args,
        working_dir,
        args.selected_python,
        args.selected_env_root,
    )
    state.record_initial_pass(initial_state)
    remediation_plan, fix_applied = run_fix_plan_and_execution(args, working_dir, initial_state)
    state.record_plan(remediation_plan)
    state.record_fix_applied(fix_applied)

    final_state = initial_state
    if fix_applied.get("executed_actions"):
        rerun_selected_env_root = args.selected_env_root or str(
            resolve_env_root_for_fix(
                working_dir,
                args.selected_python,
                args.selected_env_root,
                initial_state.selection,
            )
        )
        final_state = run_pipeline_pass(
            args,
            working_dir,
            args.selected_python,
            rerun_selected_env_root,
        )
        state.record_revalidated_pass(final_state)

    write_json(
        paths.env_json,
        {
            **state.env_snapshot_payload(),
            "control_python": sys.executable,
        },
    )
    write_readiness_report(
        target=final_state.target,
        normalized=final_state.normalized,
        evidence_level="auto",
        fix_applied=fix_applied,
        checks=final_state.checks,
        dependency_closure=final_state.closure,
        output_json=paths.report_json,
        output_md=paths.report_md,
        output_verdict_json=paths.verdict_json,
    )
    if debug_artifacts_enabled(args):
        write_json(paths.debug_state_json, state.debug_state_payload())

    verdict = load_json(paths.verdict_json)
    print(
        json.dumps(
            {
                "status": verdict.get("status"),
                "target": verdict.get("target"),
                "selected_python": final_state.selection.get("selected_python"),
                "pipeline_passes": state.pipeline_passes or 1,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
