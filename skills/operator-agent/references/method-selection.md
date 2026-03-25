# Method Selection

`operator-agent` supports only two methods:

- `custom-access`
- `native-framework`

Choose `custom-access` when the user wants fast validation, plugin delivery, or
no framework-source modification.

Choose `native-framework` when the user wants framework-native integration,
source-tree changes, framework rebuild, or a new wheel.

## MindSpore Policy

MindSpore operator routing inherits the legacy operator builder shelf and folds
it into the two supported methods.

### Legacy Builder Shelf

- `cpu-plugin-builder` -> `custom-access`
- `cpu-native-builder` -> `native-framework`
- `npu-native-builder` -> `native-framework`
- `npu-plugin-builder` -> planned
- `gpu-native-builder` -> planned
- `gpu-plugin-builder` -> planned

### Backend Normalization

- Normalize `Ascend` and `aclnn` to `NPU`.
- Report normalized backends using `CPU`, `GPU`, or `NPU`.

### Routing Defaults

- CPU default: `custom-access`
- CPU explicit in-tree integration or wheel delivery: `native-framework`
- NPU default: `native-framework`
- `Ascend` and ACLNN adaptation: `native-framework`
- GPU: roadmap only, no active implementation path

### Decision Log

Record all of the following:

- normalized backend
- selected method
- builder shelf mapping used for the decision
- why the alternative route was rejected
