# MindSpore API To Operator Mapping

Use this note when resolving a public MindSpore API to the internal operator
identity that should drive routing, dispatch inspection, or backward analysis.

## Mapping Rules

- Start from the public export site, not from a guessed Primitive name.
- Preserve meaningful suffixes such as `_ext`, `_scalar`, `_inplace`, and
  `_grad`.
- Treat `functional_overload` exports as branch sets until the active
  `op_yaml` branch is known.
- Treat `Tensor.xxx_` as a distinct public API surface, not as the plain
  functional operator.

## Common Patterns

| Public API pattern | Internal identity rule | Example |
| --- | --- | --- |
| `from ... import foo_ext as foo` | keep the `_ext` internal symbol | `mint.linspace` -> `linspace_ext` -> `LinSpaceExt` |
| `from ... import foo_scalar as foo` | keep the `_scalar` internal symbol | `add_scalar` -> `AddScalar` |
| `functional_overload.foo` | inspect `ops/api_def/foo.yaml` branch by branch | `max` -> `max_op.yaml`, `max_dim_op.yaml`, `maximum_op.yaml` |
| wrapper in `ops.function.*` | inspect wrapper body before resolving `op_yaml` | `divide` -> wrapper -> `div.yaml` |
| `Tensor.foo_` | keep inplace identity | `Tensor.sub_` stays in the inplace family |

## Minimal Output

When you finish API resolution, record:

- public API name
- internal function symbol
- active `op_yaml`
- Primitive/operator name
- whether backward is required

## Related References

- `./api-resolution.md`
- `./backend-dispatch.md`
