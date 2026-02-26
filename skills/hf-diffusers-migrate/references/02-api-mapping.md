# API Mapping Reference

> **Note**: Most of these conversions are handled automatically by `auto_convert.py`. Use the tool first:
> ```bash
> python auto_convert.py --src_root /path/to/hf/diffusers --dst_root /path/to/mindone/diffusers
> ```

## Module Mapping

| PyTorch | MindSpore |
|---------|-----------|
| `import torch` | `import mindspore as ms` |
| `import torch.nn as nn` | `from mindspore import nn` |
| `import torch.nn.functional as F` | `from mindspore import mint` |
| `torch.Tensor` | `ms.Tensor` |
| `torch.nn.Module` | `ms.nn.Cell` |
| `forward()` | `construct()` |

**Key Points:**
- `mint` module provides PyTorch-compatible APIs
- `ops` contains functional operators that may differ in signature

## Direct Mint Equivalents (Same API)

| PyTorch | MindSpore |
|---------|-----------|
| `torch.randn()` → `mint.randn()` | `torch.zeros()` → `mint.zeros()` |
| `torch.ones()` → `mint.ones()` | `torch.empty()` → `mint.empty()` |
| `torch.sum()` → `mint.sum()` | `torch.mean()` → `mint.mean()` |
| `torch.cat()` → `mint.cat()` | `torch.stack()` → `mint.stack()` |
| `torch.matmul()` → `mint.matmul()` | `torch.where()` → `mint.where()` |
| `torch.clamp()` → `mint.clamp()` | `torch.split()` → `mint.split()` |
| `torch.transpose()` → `mint.transpose()` | `torch.permute()` → `mint.permute()` |
| `torch.reshape()` → `mint.reshape()` | `torch.allclose()` → `mint.allclose()` |
| `torch.sigmoid()` → `mint.sigmoid()` | `torch.tanh()` → `mint.tanh()` |

## Differences to Note

| PyTorch | MindSpore |
|---------|-----------|
| `tensor.numpy()` | `tensor.asnumpy()` |
| `torch.nn.Module` | `ms.nn.Cell` |
| `forward()` | `construct()` |

## nn Module Layers

| PyTorch | MindSpore |
|---------|-----------|
| `torch.nn.Linear(in, out)` | `mint.nn.Linear(in, out)` |
| `torch.nn.Conv2d(...)` | `mint.nn.Conv2d(...)` |
| `torch.nn.ConvTranspose2d(...)` | `mint.nn.ConvTranspose2d(...)` |
| `torch.nn.GroupNorm(...)` | `mint.nn.GroupNorm(...)` |
| `torch.nn.LayerNorm(...)` | `mint.nn.LayerNorm(...)` |
| `torch.nn.BatchNorm2d(...)` | `mint.nn.BatchNorm2d(...)` |

## Data Types

| PyTorch | MindSpore |
|---------|-----------|
| `torch.float32` | `ms.float32` |
| `torch.float16` | `ms.float16` |
| `torch.bfloat16` | `ms.bfloat16` |
| `torch.int32` | `ms.int32` |
| `torch.int64` | `ms.int64` |
| `torch.bool` | `ms.bool_` |

## MindSpore-Specific Features

```python
# Context mode
ms.set_context(mode=ms.PYNATIVE_MODE)  # Eager execution (debugging)
ms.set_context(mode=ms.GRAPH_MODE)     # Graph execution (performance)

# Device placement (implicit vs explicit)
ms.set_context(device_target="Ascend")  # or "GPU", "CPU"
# No need for .to(device) on tensors
```

## Layers Compatibility Module

For version-aware implementations:

```python
from mindone.diffusers.models.layers_compat import (
    conv_transpose2d,
    interpolate,
    scaled_dot_product_attention,
)

output = scaled_dot_product_attention(query, key, value, backend="flash")
```

## Utility Functions

```python
from mindone.diffusers.utils.mindspore_utils import randn_tensor
sample = randn_tensor(shape=(4, 3, 64, 64), dtype=ms.float16)
```

## References

- [pytorch_api_mapping.md](api_mapping/pytorch_api_mapping.md) - Complete API mapping
- [MindSpore API Documentation](https://www.mindspore.cn/docs/en/master/index.html)