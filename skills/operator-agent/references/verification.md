# Verification

Always verify:

- build success
- operator registration or import success
- minimal forward execution
- backward execution when required
- artifact locations and reuse instructions

Report modified files, build outputs, and known risks.

## MindSpore Verification Modes

Select the verification branch that matches the requested delivery:

- smoke verification for all builds
- `op_info` ST generation when API-facing test coverage is expected
- remote deploy-and-test when remote evidence or stability proof is required

Use the imported verification workflows under
`workflows/verification/mindspore/op-info/` when the request includes ST
coverage, remote evidence, or op_info repair work.
