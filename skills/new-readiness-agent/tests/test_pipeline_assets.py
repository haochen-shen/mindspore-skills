import json
from pathlib import Path

from .helpers import check_by_id, current_field, run_pipeline, stdout_payload


def test_pipeline_surfaces_hf_asset_options_for_script_managed_dataset(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train_qwen3.py").write_text(
        "\n".join(
            [
                "from datasets import load_dataset",
                "from transformers import AutoModelForCausalLM, TrainingArguments",
                'TrainingArguments(output_dir="qwen3-finetuned")',
                'dataset = load_dataset("karthiksagarn/astro_horoscope", split="train")',
                'model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-0.6B")',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "huggingface-cache" / "datasets" / "karthiksagarn___astro_horoscope").mkdir(parents=True)

    summary = stdout_payload(
        run_pipeline(
            "--working-dir",
            str(workspace),
            "--output-dir",
            str(tmp_path / "out"),
            "--target",
            "training",
            "--framework-hint",
            "pta",
            "--launcher-hint",
            "python",
            "--selected-python",
            str(fake_selected_python),
            "--entry-script",
            "train_qwen3.py",
            "--confirm",
            "config_asset=inline_config",
            "--confirm",
            "model_asset=hf_hub:Qwen/Qwen3-0.6B",
            cwd=workspace,
        )
    )

    assert current_field(summary) == "dataset_asset"
    options = summary["current_confirmation"]["options"]
    source_types = {str(option.get("source_type")) for option in options if option.get("source_type")}
    assert "hf_cache" in source_types
    assert "hf_hub" in source_types
    assert "script_managed_remote" in source_types
    assert any((option.get("locator") or {}).get("repo_id") == "karthiksagarn/astro_horoscope" for option in options if isinstance(option.get("locator"), dict))


def test_pipeline_treats_hf_cache_dataset_as_satisfied_in_final_verdict(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train_qwen3.py").write_text(
        "\n".join(
            [
                "from datasets import load_dataset",
                "from transformers import AutoModelForCausalLM, TrainingArguments",
                'TrainingArguments(output_dir="qwen3-finetuned")',
                'dataset = load_dataset("karthiksagarn/astro_horoscope", split="train")',
                'model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-0.6B")',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "huggingface-cache" / "datasets" / "karthiksagarn___astro_horoscope").mkdir(parents=True)
    (workspace / "huggingface-cache" / "hub" / "models--Qwen--Qwen3-0.6B").mkdir(parents=True)
    cann_root = tmp_path / "cann"
    cann_root.mkdir()
    (cann_root / "version.cfg").write_text("version=8.5.0\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--framework-hint",
        "pta",
        "--launcher-hint",
        "python",
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "train_qwen3.py",
        "--model-hub-id",
        "Qwen/Qwen3-0.6B",
        "--dataset-hub-id",
        "karthiksagarn/astro_horoscope",
        "--cann-path",
        str(cann_root),
        "--confirm",
        "config_asset=inline_config",
        cwd=workspace,
    )

    verdict = json.loads((output_dir / "meta" / "readiness-verdict.json").read_text(encoding="utf-8"))
    dataset_check = check_by_id(verdict, "workspace-dataset-asset")
    model_check = check_by_id(verdict, "workspace-model-asset")

    assert verdict["status"] in {"WARN", "READY"}
    assert dataset_check["status"] == "ok"
    assert model_check["status"] == "ok"
    assert not any("dataset asset is required but unresolved" in item for item in verdict["missing_items"])


def test_pipeline_treats_inline_config_as_a_valid_asset(tmp_path: Path, fake_selected_python: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "train.py").write_text(
        "\n".join(
            [
                "from transformers import TrainingArguments",
                'TrainingArguments(output_dir="out")',
                "print('train')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace / "model").mkdir()
    (workspace / "dataset").mkdir()
    (workspace / "dataset" / "sample.txt").write_text("hello\n", encoding="utf-8")
    cann_root = tmp_path / "cann"
    cann_root.mkdir()
    (cann_root / "version.cfg").write_text("version=8.5.0\n", encoding="utf-8")
    output_dir = tmp_path / "out"

    run_pipeline(
        "--working-dir",
        str(workspace),
        "--output-dir",
        str(output_dir),
        "--target",
        "training",
        "--framework-hint",
        "pta",
        "--launcher-hint",
        "python",
        "--selected-python",
        str(fake_selected_python),
        "--entry-script",
        "train.py",
        "--model-path",
        "model",
        "--dataset-path",
        "dataset",
        "--cann-path",
        str(cann_root),
        "--confirm",
        "config_asset=inline_config",
        cwd=workspace,
    )

    verdict = json.loads((output_dir / "meta" / "readiness-verdict.json").read_text(encoding="utf-8"))
    config_check = check_by_id(verdict, "workspace-config-asset")
    assert config_check["status"] == "ok"
