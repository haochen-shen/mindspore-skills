"""Stub factory client. Returns empty results.

Used until ms-factory is built. SKILL.md instructions should
handle the empty-result case gracefully.
"""

from typing import List, Optional

from .interface import Card, FactoryClient


class StubFactoryClient(FactoryClient):
    """Stub implementation that returns no results."""

    def query(
        self,
        card_type: str,
        keywords: List[str],
        platform: Optional[str] = None,
    ) -> List[Card]:
        return []

    def get(self, card_type: str, name: str) -> Optional[Card]:
        return None
