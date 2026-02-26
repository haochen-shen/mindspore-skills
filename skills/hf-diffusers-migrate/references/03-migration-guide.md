# Migration Workflow

```
HF Diffusers → auto_convert.py → Manual Fixes → Validation
```

## Using auto_convert.py

```bash
# Convert folder - ALL Python files (use with caution)
python auto_convert.py --src_root /path/to/src --dst_root /path/to/dst

# Convert SPECIFIC files only (recommended for selective migration)
python auto_convert.py --src_root /path/to/src --dst_root /path/to/dst \
    --files "models/controlnet.py" "pipelines/flux/*.py"

# Convert single file in place
python auto_convert.py --src_file /path/to/file.py --inplace
```

**IMPORTANT:** Use `--files` to specify exact file patterns to avoid modifying unrelated files.

### Auto-converted:
- Imports: `torch` → `mindspore.mint`, `torch.nn` → `mindspore.nn`
- Classes: `nn.Module` → `nn.Cell`, `forward()` → `construct()`
- Tensor ops: 200+ functions (`torch.cat` → `mint.cat`, etc.)
- Device cleanup: `.to(device)`, `.to("cuda")`, `.to("cpu")`, `.cuda()`, `.cpu()`, `torch.cuda.is_available()`, `device=` params, `device = torch.device(...)`
- Module cleanup: XLA code, `USE_PEFT_BACKEND`, `replace_example_docstring`, `is_torch_xla_available`
- Module mapping: `torch_utils` → `mindspore_utils`

## Post-Conversion Manual Fixes

### New_Zeros
```python
tensor.new_zeros(shape) → ms.new_zeros((shape))
# Note: MindSpore requires tuple wrap: (shape) instead of shape
```
**Quick Search Patterns:**
```bash
grep -n "\.new_zeros(" file.py
```

### Retrieve Latents
```python
# PyTorch (with hasattr checks)
def retrieve_latents(encoder_output: ms.Tensor, generator: Optional[ms.Generator] = None, sample_mode: str = "sample"):
    if hasattr(encoder_output, "latent_dist") and sample_mode == "sample":
        return encoder_output.latent_dist.sample(generator)
    elif hasattr(encoder_output, "latent_dist") and sample_mode == "argmax":
        return encoder_output.latent_dist.mode()
    elif hasattr(encoder_output, "latents"):
        return encoder_output.latents
    else:
        raise AttributeError("Could not access latents of provided encoder_output")

# MindSpore (CRITICAL: Use vae.diag_gauss_dist directly)
def retrieve_latents(vae, encoder_output: ms.Tensor, generator=None, sample_mode="sample"):
    if sample_mode == "sample":
        return vae.diag_gauss_dist.sample(encoder_output, generator=generator)
    elif sample_mode == "argmax":
        return vae.diag_gauss_dist.mode(encoder_output)
    return encoder_output
```

**CRITICAL: vae.encode() returns a tuple - requires [0] index**
```python
# WRONG - Missing [0] index
retrieve_latents(self.vae, self.vae.encode(control_image), generator=generator)

# CORRECT - Add [0] to extract tensor from tuple
retrieve_latents(self.vae, self.vae.encode(control_image)[0], generator=generator)

# For list comprehension with generator
image_latents = [
    retrieve_latents(self.vae, self.vae.encode(image[i:i+1])[0])  # Add [0]
    for i in range(image.shape[0])
]

# For single encode call
image_latents = retrieve_latents(self.vae, self.vae.encode(image)[0])  # Add [0]
```

**IMPORTANT NOTES:**
1. In mindone, `vae.encode()` returns a **tuple** containing the encoder output
2. You **must** access the first element with `[0]` to get the actual tensor
3. Search for all `retrieve_latents()` calls with `vae.encode()` and add `[0]`
```
**Quick Search Patterns:**
```bash
grep -n " latent_dist" file.py
grep -n "retrieve_latents" file.py
grep -n "vae\\.encode(" file.py
```

### Tokenizer (NP tensors)
```python
# PyTorch
txt_tokens = self.tokenizer(txt, return_tensors="pt").to(device)
encoder_hidden_states = self.text_encoder(input_ids=txt_tokens.input_ids, ...)
some_func(txt_tokens.attention_mask)  # Direct usage

# MindSpore
txt_tokens = self.tokenizer(txt, return_tensors="np")  # NP, not PT
encoder_hidden_states = self.text_encoder(input_ids=ms.tensor(txt_tokens.input_ids), ...)
some_func(ms.tensor(txt_tokens.attention_mask))  # WRAP ALL mentions

# IMPORTANT: Wrap ALL tokenizer outputs with ms.tensor()
# Use grep to find all txt_tokens.* accesses in the file
```

**Required for ALL tokenizer outputs:**
- `ms.tensor(txt_tokens.input_ids)`
- `ms.tensor(txt_tokens.attention_mask)`
- `ms.tensor(txt_tokens.XXX)` (any other field)

**Quick Search Patterns:**
```bash
grep -n 'return_tensors="pt"' file.py
grep -n "txt_tokens\." file.py
```

### Attention
```python
from mindone.diffusers.models.layers_compat import scaled_dot_product_attention
output = scaled_dot_product_attention(q, k, v, attn_mask=mask, backend="flash")
```
**Quick Search Patterns:**
```bash
grep -n "F\.scaled_dot_product_attention\|torch\.nn\.functional\.scaled_dot_product_attention" file.py
```

## Model/Pipeline Registration

Edit `__init__.py` files:
```bash
mindone/diffusers/__init__.py              # Top-level exports
mindone/diffusers/models/__init__.py       # Model exports
mindone/diffusers/pipelines/__init__.py    # Pipeline exports
```

```python
# Add import and export
from .mypipeline import MyPipeline
__all__ = [..., "MyPipeline"]
```

## Validation

```python
import numpy as np
ms_np = ms_output.asnumpy()
assert np.allclose(hf_np, ms_np, rtol=1e-3, atol=1e-3)
```

## References

- [02-api-mapping.md](02-api-mapping.md) - Complete API reference
- [04-support-status.md](04-support-status.md) - Current support status