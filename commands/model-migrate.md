---
description: Top-level model migration entry that analyzes the source repo, selects the correct migration route, executes the migration flow, and verifies the result
---

# Model Migrate

Load the `model-migrate` skill and follow its four-stage workflow:

1. migration analysis
2. route selection
3. migration build
4. verification and report

## When to Use

- Converting Hugging Face or standalone PyTorch repos to MindSpore-oriented targets
- Migrating custom model architectures
- Porting standalone PyTorch projects
- Starting migration without forcing the user to choose `hf-transformers` or `hf-diffusers` up front

## Common Scenarios

- Hugging Face transformers migrations
- Hugging Face diffusers migrations
- Academic paper implementations
- Custom neural network architectures
