from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseAstWalker(ABC):
    """Abstract Base Class for language-specific AST walkers."""

    @abstractmethod
    def parse_file(self, content: bytes):
        """Parses raw source code bytes into a syntax tree."""
        pass

    @abstractmethod
    def extract_imports(self, root_node) -> List[Dict[str, Any]]:
        """Extracts module import statements."""
        pass

    @abstractmethod
    def extract_calls(self, root_node) -> List[Dict[str, Any]]:
        """Extracts function and method call signatures."""
        pass