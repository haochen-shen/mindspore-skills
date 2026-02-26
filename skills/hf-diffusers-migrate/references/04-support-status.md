# Migration Support Status Guide

This guide explains how to check the current support status for migration. For **version-independent compatibility**, this skill works with any HF diffusers version.

## Check Official Support Status

To verify if a model/pipeline is already supported in mindone.diffusers:

1. **Visit the official SUPPORT_LIST.md**:
   - https://github.com/mindspore-lab/mindone/blob/master/mindone/diffusers/SUPPORT_LIST.md

2. **Search for your model** in the support table

3. **Check the status columns**:
   - `inference_fp32` - FP32 inference support
   - `inference_fp16` - FP16 inference support
   - `training_fp32` - FP32 training support
   - `training_fp16` - FP16 training support

## What Each Status Means

| Status Icon | Meaning |
|-------------|---------|
| `✅` | Fully tested and supported |
| `✖️` | Not yet verified or not working |
| `-` | Not applicable (e.g., training for inference-only models) |

## Universal Migration Approach

This skill's `auto_convert.py` is **version-agnostic** and designed to work with:

### Always Auto-Converted
- PyTorch tensor operations → MindSpore `mint.*` functions
- `torch.nn` modules → `mindspore.nn` modules
- `forward()` → `construct()` method names
- Common diffutils imports → mindone equivalents

### May Require Manual Review
- Custom attention implementations
- Device-specific code (CUDA, XLA)
- Dynamic module loading
- Version-specific API changes

### Check Before Migration

1. **New model?** Check SUPPORT_LIST.md first
2. **Similar models exist?** Look at existing mindone implementations as reference
3. **Transformers dependencies?** Verify compatibility with mindone.diffusers.transformers

## Quick Decision Flow

```
┌─────────────────────────────────────┐
│  Want to migrate a diffusers model?  │
└─────────────────┬───────────────────┘
                  │
        ┌─────────▼─────────┐
        │ Check SUPPORT_    │
        │ LIST.md online   │
        └─────────┬─────────┘
                  │
        ┌─────────▼─────────┐
     ✅  │ Already supported? │
        └─────────┬─────────┘
                  │
         ┌────────┴────────┐
         │                 │
        YES               NO
         │                 │
         ▼                 ▼
┌─────────────────┐ ┌─────────────────┐
│ Use existing    │ │ Run this skill  │
│ mindone model   │ │ to migrate      │
└─────────────────┘ └─────────────────┘
```

## Component Migration Priorities

When migrating new models, follow this order:

| Priority | Component | Reason |
|----------|-----------|--------|
| 1 | **Schedulers** | Common across all pipelines |
| 2 | **Models** (UNet, Transformer, VAE, Autoencoder) | Core architecture |
| 3 | **Pipelines** | Orchestrates the workflow |
| 4 | **Loaders** (LoRA, IP-Adapter) | Optional extensions |
| 5 | **Tests** | Validate migration |

## Related References

| File | Purpose |
|------|---------|
| [01-overview.md](01-overview.md) | Framework & architecture overview |
| [02-api-mapping.md](02-api-mapping.md) | Detailed API mappings |
| [03-migration-guide.md](03-migration-guide.md) | Step-by-step migration workflow |

## Links

- **Official Support List**: https://github.com/mindspore-lab/mindone/blob/master/mindone/diffusers/SUPPORT_LIST.md
- **mindone.diffusers Repository**: https://github.com/mindspore-lab/mindone/tree/master/mindone/diffusers
- **HF diffusers Repository**: https://github.com/huggingface/diffusers