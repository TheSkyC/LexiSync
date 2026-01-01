# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class RetrievalBackend(ABC):
    @abstractmethod
    def name(self) -> str:
        """Return the display name of the backend."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if required dependencies are installed."""
        pass

    @abstractmethod
    def build_index(self, data_list: List[Dict[str, str]], progress_callback=None, check_cancel=None) -> bool:
        """
        Build index from data.
        progress_callback: function(int) -> None
        """
        pass

    @abstractmethod
    def retrieve(self, query: str, limit: int = 5, threshold: float = 0.0) -> List[Dict]:
        """Retrieve similar items."""
        pass

    @abstractmethod
    def clear(self):
        """Clear memory."""
        pass