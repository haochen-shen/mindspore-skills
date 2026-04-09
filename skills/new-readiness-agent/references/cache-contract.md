# New-Readiness-Agent Cache Contract

Run-scoped artifacts live under:

- `runs/<run_id>/out/`

Workspace latest cache lives under:

- `runs/latest/new-readiness-agent/`

Downstream agents should prefer:

- `runs/latest/new-readiness-agent/workspace-readiness.lock.json`

If the user explicitly provides a run-scoped artifact path, downstream agents
may read:

- `runs/<run_id>/out/artifacts/workspace-readiness.lock.json`

`workspace-readiness.lock.json` must remain the stable downstream contract for:

- current phase and whether confirmation is still pending
- the current per-field confirmation step and remaining confirmation queue
- final selected target, launcher, framework, and runtime environment
- final selected assets for config, model, dataset, and checkpoint
- selected asset source types such as `local_path`, `hf_cache`, `hf_hub`,
  `script_managed_remote`, and `inline_config`
- selected asset locators such as paths, repo IDs, cache paths, and split names
- required packages
- missing items
- warnings
- confirmation metadata
- HF cache layout and remote-asset evidence summary when present
- evidence summary
- update timestamp
