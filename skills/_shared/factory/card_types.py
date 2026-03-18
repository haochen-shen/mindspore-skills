"""Canonical factory card types.

Keep aligned with ms-factory schema. Do not add types here
unless the factory side formally adopts them.
"""

CARD_TYPES = {
    "known_failure": "Known failure patterns with symptoms and fixes",
    "operator": "Operator implementation details and status",
    "model": "Model configuration and expected behavior",
    "trick": "Optimization techniques and algorithm tricks",
}
