#!/usr/bin/env python3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ArtifactPaths:
    output_dir: Path
    meta_dir: Path
    debug_dir: Path
    inputs_json: Path
    env_json: Path
    report_json: Path
    report_md: Path
    verdict_json: Path
    debug_state_json: Path

    @classmethod
    def for_output_dir(cls, output_dir: Path) -> "ArtifactPaths":
        meta_dir = output_dir / "meta"
        debug_dir = output_dir / "debug"
        return cls(
            output_dir=output_dir,
            meta_dir=meta_dir,
            debug_dir=debug_dir,
            inputs_json=meta_dir / "inputs.json",
            env_json=meta_dir / "env.json",
            report_json=output_dir / "report.json",
            report_md=output_dir / "report.md",
            verdict_json=meta_dir / "readiness-verdict.json",
            debug_state_json=debug_dir / "state.json",
        )


@dataclass
class PipelinePassState:
    selection: dict
    target: dict
    closure: dict
    task_smoke_checks: List[dict]
    checks: List[dict]
    normalized: dict


def default_fix_applied() -> dict:
    return {
        "execute": False,
        "results": [],
        "executed_actions": [],
        "failed_actions": [],
        "needs_revalidation": [],
    }


def default_plan() -> dict:
    return {
        "actions": [],
        "skipped": [],
    }


@dataclass
class ReadinessState:
    working_dir: Path
    output_dir: Path
    mode: str
    pipeline_passes: int = 0
    initial_pass: Optional[PipelinePassState] = None
    final_pass: Optional[PipelinePassState] = None
    remediation_plan: dict = field(default_factory=default_plan)
    fix_applied: dict = field(default_factory=default_fix_applied)

    def record_initial_pass(self, pipeline_pass: PipelinePassState) -> None:
        self.initial_pass = pipeline_pass
        self.final_pass = pipeline_pass
        self.pipeline_passes = 1

    def record_fix_applied(self, fix_applied: dict) -> None:
        self.fix_applied = fix_applied

    def record_plan(self, remediation_plan: dict) -> None:
        self.remediation_plan = remediation_plan

    def record_revalidated_pass(self, pipeline_pass: PipelinePassState) -> None:
        self.final_pass = pipeline_pass
        self.pipeline_passes = max(self.pipeline_passes, 2)

    @property
    def final_selection(self) -> dict:
        if self.final_pass:
            return self.final_pass.selection
        return {}

    def env_snapshot_payload(self) -> Dict[str, object]:
        initial_selection = self.initial_pass.selection if self.initial_pass else {}
        final_selection = self.final_pass.selection if self.final_pass else {}
        return {
            "mode": self.mode,
            "pipeline_passes": self.pipeline_passes,
            "initial_selection": initial_selection,
            "final_selection": final_selection,
            "fix_execute": bool(self.fix_applied.get("execute")),
            "executed_actions": self.fix_applied.get("executed_actions", []),
            "failed_actions": self.fix_applied.get("failed_actions", []),
            "needs_revalidation": self.fix_applied.get("needs_revalidation", []),
        }

    def debug_state_payload(self) -> Dict[str, object]:
        return {
            "working_dir": str(self.working_dir),
            "output_dir": str(self.output_dir),
            "mode": self.mode,
            "pipeline_passes": self.pipeline_passes,
            "initial_pass": asdict(self.initial_pass) if self.initial_pass else None,
            "final_pass": asdict(self.final_pass) if self.final_pass else None,
            "remediation_plan": self.remediation_plan,
            "fix_applied": self.fix_applied,
        }
