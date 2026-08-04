"""Base parser interface — docs/02 §8.1."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedFile:
    """Structural summary of a parsed source file."""

    path: str
    language: str
    content: str
    structure: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)


class BaseParser(ABC):
    """A parser understands one family of languages and extracts structure."""

    @abstractmethod
    def parse_file(self, file_path: str) -> ParsedFile:
        """Parse a file on disk into a ParsedFile."""

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Language names (extension-based) this parser handles."""

    @abstractmethod
    def extract_structure(self, content: str) -> dict:
        """Extract an AST-like structural summary from source text."""
