# Factory Interface

This directory defines the contract for querying factory knowledge assets.

## Card Types

| Type | Description |
|------|-------------|
| `known_failure` | Known failure patterns with symptoms and fixes |
| `operator` | Operator implementation details and status |
| `model` | Model configuration and expected behavior |
| `trick` | Optimization techniques and algorithm tricks |

## Interface

`FactoryClient` (in `interface.py`) defines two methods:

- `query(card_type, keywords, platform?)` — list of matching cards
- `get(card_type, name)` — single card or None

## Current State

Factory is not yet built. `stub.py` provides a `StubFactoryClient` that
returns empty results. SKILL.md instructions handle this gracefully with
conditional steps: "if factory query tooling is available..."

## When Factory Is Built

Replace `StubFactoryClient` with a real implementation that connects to
ms-factory. The interface contract (`FactoryClient` ABC) stays the same.
