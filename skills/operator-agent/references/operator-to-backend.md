# MindSpore Operator To Backend Mapping

Use this note after the operator identity has already been resolved.

Its job is narrower than `api-resolution.md`: determine the normalized backend
label and the likely static implementation route for the resolved operator
branch.

## Backend Normalization

- `CPU` stays `CPU`
- `GPU` stays `GPU`
- `Ascend` normalizes to `NPU`
- `aclnn` normalizes to `NPU`

Always report the normalized backend as one of `CPU`, `GPU`, or `NPU`.

## MindSpore Routing Facts

| Normalized backend | Default route | Notes |
| --- | --- | --- |
| `CPU` | `custom-access` | use `native-framework` only when in-tree integration or a wheel is required |
| `NPU` | `native-framework` | ACLNN/Ascend adaptation flows land here |
| `GPU` | roadmap only | do not pretend an active route exists |

## Static Dispatch Checks

For a resolved `op_yaml` branch, inspect:

1. `dispatch.enable`
2. whether `Ascend: XxxAscend` is present
3. `aclnn_config.yaml` evidence for auto-generated ACLNN mappings
4. customize source evidence for PyBoost and KBK when `Ascend: XxxAscend` is used

## Decision Log

Record:

- raw backend wording from the request
- normalized backend
- selected method
- evidence used for the routing decision
- rejected alternative and why

## Related References

- `./method-selection.md`
- `./backend-dispatch.md`
