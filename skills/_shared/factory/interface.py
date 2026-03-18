"""Factory client interface contract.

Main agent skills and sub-skills call these methods to retrieve
knowledge cards. When ms-factory is built, replace stub.py with
a real implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Card:
    """A single factory knowledge card."""

    card_type: str
    name: str
    summary: str
    content: Dict = field(default_factory=dict)


class FactoryClient(ABC):
    """Abstract interface for querying factory knowledge assets."""

    @abstractmethod
    def query(
        self,
        card_type: str,
        keywords: List[str],
        platform: Optional[str] = None,
    ) -> List[Card]:
        """Search cards by type and keywords."""
        ...

    @abstractmethod
    def get(self, card_type: str, name: str) -> Optional[Card]:
        """Get a specific card by type and name."""
        ...
