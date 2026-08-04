"""Node.js project parser — reads package.json as the project model."""

import json
from pathlib import Path

from app.parsers.base import BaseParser, ParsedFile


class NodeParser(BaseParser):
    """Parses package.json into a Node project model (scripts + dependencies)."""

    def supported_languages(self) -> list[str]:
        return ["json"]

    def parse_file(self, file_path: str) -> ParsedFile:
        content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return ParsedFile(
            path=file_path,
            language="json",
            content=content,
            structure=self.extract_structure(content),
            dependencies=self._extract_dependencies(content),
        )

    def extract_structure(self, content: str) -> dict:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {"error": "invalid_json"}
        return {
            "name": data.get("name", ""),
            "version": data.get("version", ""),
            "scripts": data.get("scripts", {}),
            "dependencies": list(data.get("dependencies", {})),
            "devDependencies": list(data.get("devDependencies", {})),
        }

    @staticmethod
    def _extract_dependencies(content: str) -> list[str]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        return sorted(
            set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))
        )
