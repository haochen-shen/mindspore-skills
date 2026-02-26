---
name: hf-diffusers-migrate
description: Migrate Hugging Face diffusers models to mindone.diffusers. Uses auto_convert.py for automated conversion.
---

# HF Diffusers Migration

Migrate Hugging Face diffusers models (PyTorch) to mindone.diffusers (MindSpore) using automated code conversion.

## When to Use

- Porting Stable Diffusion, SDXL, SD3, Flux, ControlNet, or other diffusion models
- Converting diffusers pipelines to MindSpore framework
- Migrating attention operations for Ascend NPU/GPU backends

## Supported Models

Check [SUPPORT_LIST.md](https://github.com/mindspore-lab/mindone/blob/master/mindone/diffusers/SUPPORT_LIST.md) for current status (240+ pipelines):
- Base: SD 1.x, SD 2.x, SDXL, SD3, Flux, Flux2
- Video: AnimateDiff, SVD, CogVideoX, Mochi
- Conditioning: ControlNet, LoRA, IP-Adapter, T2I-Adapter
- Text-to-Image: PixArt, Sana, Lumina, AuraFlow

## Workflow

```
1. Analyze HF source → 2. Run auto_convert.py → 3. Manual fixes → 4. Validate
```

## Step 1: Analyze HF Source

Before running conversion, identify dependencies and files to migrate.

**Check support status:**
1. [SUPPORT_LIST.md](https://github.com/mindspore-lab/mindone/blob/master/mindone/diffusers/SUPPORT_LIST.md) - is model already supported?
2. Note HF diffusers version - API compatibility may vary

**List mindone utility dependencies required:**
```
mindone.diffusers.models.layers_compat
  - scaled_dot_product_attention
  - conv_transpose2d
  - interpolate

mindone.diffusers.utils
  - randn_tensor  (from diffusers.utils.torch_utils)

mindone.diffusers.schedulers.scheduling_utils

mindone.diffusers.utils.outputs
  - TextEncoderOutput
  - BaseModelOutput
```

**Check if HF utilities need migration:**
- `diffusers.utils.torch_utils.randn_tensor` → `mindone.diffusers.utils.mindspore_utils.randn_tensor`
- `diffusers.utils.import_utils` imports
- Pillow `PIL_INTERPOLATION` constants

**List HF files to migrate (by category):**
- Models: `models/unet_2d_condition.py`, `models/vae.py`, `models/transformer_2d.py`
- Pipelines: `pipelines/stable_diffusion/*.py`, `pipelines/flux/*.py`
- Schedulers: `schedulers/*.py`
- Configs: `configs/*.json`, `configuration_*.py`

**IMPORTANT: DO NOT migrate tests**
- Test files exist on the remote server and should NOT be migrated
- After migration, sync to remote and run tests using the sync-mindone skill

<MUST> MUST: show the table for utilities or files to migrate. </MUST>

## Step 2: Run auto_convert.py (Automated Conversion)

**USE THIS FIRST** - The `auto_convert.py` tool handles most conversions automatically.

```bash
# Convert folder - ALL Python files
python auto_convert.py --src_root /path/to/hf/diffusers --dst_root /path/to/mindone/diffusers

# Convert SPECIFIC files only (recommended for selective migration)
python auto_convert.py --src_root /path/to/hf/diffusers --dst_root /path/to/mindone/diffusers \
    --files "models/controlnet.py" "pipelines/qwenimage/*.py"

# Convert single file in place
python auto_convert.py --src_file /path/to/file.py --inplace
```

**IMPORTANT:** Use `--files` to specify exact file patterns to avoid modifying unrelated files.
The `--files` parameter accepts glob patterns relative to `src_root`.

### Auto-converted:
| Category | Examples |
|----------|----------|
| Imports | `torch` → `mindspore.mint`, `torch.nn` → `mindspore.nn` |
| Classes | `nn.Module` → `nn.Cell`, `forward()` → `construct()` |
| Tensor operations | 200+ functions (`torch.cat` → `mint.cat`, etc.) |
| Diffusers imports | `diffusers.utils.randn_tensor` → `mindone.diffusers.utils.mindspore_utils.randn_tensor` |
| Module mapping | `torch_utils` → `mindspore_utils` |
| Cleanup | All device-related: `.to(device)`, `.to("cuda")`, `.to("cpu")`, `.cuda()`, `.cpu()`, `torch.cuda.is_available()`, `device=` params, `device = torch.device(...)`. Also: XLA code, `USE_PEFT_BACKEND`, `replace_example_docstring`, `is_torch_xla_available` |

### What needs manual fixes (logged by converter):
- Unmapped interfaces listed in output
- Dynamic module loading with `importlib`
- Custom attention → use `layers_compat.scaled_dot_product_attention()`
- Parameter keyword differences: `dim=` → `axis=`

## Step 3: Fix Unmapped Interfaces

Check the converter output log and fix reported issues manually.

**Common manual fixes:**
```python
# Tensor method
tensor.numpy() → tensor.asnumpy()

# Device context (set once, not per tensor)
ms.set_context(device_target="Ascend")  # or "GPU"

# new_zeros (requires tuple wrap)
tensor.new_zeros(shape) → ms.new_zeros((shape))

# Tokenizer (NP not PT)
return_tensors="pt" → return_tensors="np"
ms.tensor(txt_tokens.input_ids)  # wrap ALL tokenizer outputs
# IMPORTANT: Use grep to find ALL txt_tokens.* accesses and wrap each one

# retrieve_latents (use vae.diag_gauss_dist directly)
def retrieve_latents(vae, encoder_output: ms.Tensor, ...):
    vae.diag_gauss_dist.sample(encoder_output, ...)  # instead of hasattr

# vae.encode() returns tuple - requires [0] index
retrieve_latents(self.vae, self.vae.encode(image), ...)  # WRONG
retrieve_latents(self.vae, self.vae.encode(image)[0], ...)  # CORRECT
# In mindone, vae.encode() returns a tuple, so we need [0] to extract the tensor
# Check all instances of retrieve_latents() calls with vae.encode() and add [0]
```

**CRITICAL: See `Post-Conversion Manual Fixes` in [03-migration-guide.md](references/03-migration-guide.md) to complete the manual fixes.**

**Model/Pipeline Registration:**
After migration with manual fixes, register the model/pipeline to `__init__.py`:

```bash
# LEVEL 1: Top-level (both models and pipelines)
mindone/diffusers/__init__.py              # Top-level exports (models + pipelines)

# LEVEL 2: These contain the actual exports
mindone/diffusers/models/__init__.py       # Model exports
mindone/diffusers/pipelines/__init__.py    # Pipeline exports

# LEVEL 3: Category-level (optional, for pipelines in subdirectories)
mindone/diffusers/pipelines/[category]/__init__.py  # Category pipeline exports
```

**CRITICAL: Register at ALL levels for proper exports**

For each migrated class (Model or Pipeline):

1. ** models/__init__.py** (for models):
   - Add to `_import_structure` under appropriate category
   - Add to TYPE_CHECKING import section

2. **pipelines/[category]/__init__.py** (for pipelines with category):
   - Add to `_import_structure` dictionary
   - Add to TYPE_CHECKING import section

3. **pipelines/__init__.py** (for pipelines):
   - Add to `_import_structure["category"]` list
   - Add to TYPE_CHECKING import section

4. **diffusers/__init__.py** (BOTH models and pipelines):
   - Add to `_import_structure["models"]` or `_import_structure["pipelines"]` list
   - Add to TYPE_CHECKING import section

**Example - Model Registration:**

```python
# models/__init__.py
_import_structure = {
    "controlnets.controlnet_qwenimage": ["QwenImageControlNetModel", "QwenImageMultiControlNetModel"],
    ...
}

if TYPE_CHECKING:
    from .controlnets.controlnet_qwenimage import QwenImageControlNetModel, QwenImageMultiControlNetModel
```

```python
# diffusers/__init__.py
_import_structure = {
    "models": [
        ...,
        "QwenImageControlNetModel",
        "QwenImageMultiControlNetModel",
        ...
    ],
    ...
}

if TYPE_CHECKING:
    from .models import QwenImageControlNetModel, QwenImageMultiControlNetModel
```

**Example - Pipeline Registration:**

```python
# pipelines/qwenimage/__init__.py
_import_structure = {
    "pipeline_qwenimage_controlnet": ["QwenImageControlNetPipeline"],
    ...
}

if TYPE_CHECKING:
    from .pipeline_qwenimage_controlnet import QwenImageControlNetPipeline
```

```python
# pipelines/__init__.py
_import_structure = {
    "qwenimage": [
        ...,
        "QwenImageControlNetPipeline",
        ...
    ],
    ...
}

if TYPE_CHECKING:
    from .qwenimage import QwenImageControlNetPipeline
```

```python
# diffusers/__init__.py
_import_structure = {
    "pipelines": [
        ...,
        "QwenImageControlNetPipeline",
        ...
    ],
    ...
}

if TYPE_CHECKING:
    from .pipelines import QwenImageControlNetPipeline
```

**Registration Checklist:**

```
For each model class:
  [ ] models/__init__.py - Add to _import_structure and TYPE_CHECKING
  [ ] diffusers/__init__.py - Add to _import_structure["models"] and TYPE_CHECKING

For each pipeline class:
  [ ] pipelines/[category]/__init__.py - Add to _import_structure and TYPE_CHECKING
  [ ] pipelines/__init__.py - Add to _import_structure["category"] and TYPE_CHECKING
  [ ] diffusers/__init__.py - Add to _import_structure["pipelines"] and TYPE_CHECKING
```

<MUST> MUST: do manual edits after running auto_convert script. </MUST>

## Step 4: Validate

```python
import numpy as np

# Compare outputs between HF and MindOne
hf_np = hf_output.numpy() if hasattr(hf_output, 'numpy') else hf_output
ms_np = ms_output.asnumpy()
assert np.allclose(hf_np, ms_np, rtol=1e-3, atol=1e-3)
```

## Key API Mappings

| PyTorch | MindSpore |
|---------|-----------|
| `import torch` | `import mindspore as ms` |
| `torch.nn.Module` | `ms.nn.Cell` |
| `forward()` | `construct()` |
| `torch.cat()` | `ms.mint.cat()` |
| `torch.nn.functional.scaled_dot_product_attention` | `mindone.diffusers.models.layers_compat.scaled_dot_product_attention` |

## Reference Documents

| File | Purpose |
|------|---------|
| [01-overview.md](references/01-overview.md) | Framework & architecture overview |
| [02-api-mapping.md](references/02-api-mapping.md) | API mappings |
| [03-migration-guide.md](references/03-migration-guide.md) | Migration workflow |
| [04-support-status.md](references/04-support-status.md) | Support status & priorities |
| [env.md](references/env.md) | Environment setup |
| [guardrails.md](references/guardrails.md) | Migration guidelines |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `torch not defined` | `auto_convert.py` should handle - check unmapped log |
| Shape mismatch | Check `dim` vs `axis` parameter names |
| Accuracy loss | Verify attention mask handling (boolean mask inversion) |

## References

- [mindone.diffusers docs](https://github.com/mindspore-lab/mindone/tree/master/mindone/diffusers)
- [HF diffusers docs](https://huggingface.co/docs/diffusers)
- [layers_compat.py](https://github.com/mindspore-lab/mindone/blob/master/mindone/diffusers/models/layers_compat.py)