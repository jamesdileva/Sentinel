"""FastAPI parser — extracts route definitions from Python source via AST.

A route is a function decorated with a FastAPI-style decorator:
`@app.get("/path")`, `@router.post(...)`, etc.
"""

import ast

from app.parsers.base import ParsedFile  # noqa: F401 (re-export)
from app.parsers.python_parser import PythonParser

_ROUTE_METHODS = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "websocket",
    "route",
}


class FastAPIParser(PythonParser):
    """Python parser extended with FastAPI route extraction."""

    def supported_languages(self) -> list[str]:
        return ["python"]

    def extract_structure(self, content: str) -> dict:
        structure = super().extract_structure(content)
        structure["routes"] = self._extract_routes(content)
        return structure

    def _extract_routes(self, content: str) -> list[dict]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        routes: list[dict] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = self._route_from_decorator(decorator, node.name, node.lineno)
                if route:
                    routes.append(route)
        return routes

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr, function_name: str, lineno: int
    ) -> dict | None:
        if isinstance(decorator, ast.Call) and isinstance(
            decorator.func, ast.Attribute
        ):
            method = decorator.func.attr
            if method in _ROUTE_METHODS:
                args = [
                    ast.literal_eval(a)
                    for a in decorator.args
                    if isinstance(a, ast.Constant)
                ]
                return {
                    "method": method.upper(),
                    "path": args[0] if args else "",
                    "handler": function_name,
                    "line": lineno,
                }
        return None


class FlaskParser(PythonParser):
    """Python parser extended with Flask `@app.route(...)` extraction."""

    def supported_languages(self) -> list[str]:
        return ["python"]

    def extract_structure(self, content: str) -> dict:
        structure = super().extract_structure(content)
        structure["routes"] = self._extract_routes(content)
        return structure

    def _extract_routes(self, content: str) -> list[dict]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        routes: list[dict] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = self._route_from_decorator(decorator, node.name, node.lineno)
                if route:
                    routes.append(route)
        return routes

    @staticmethod
    def _route_from_decorator(
        decorator: ast.expr, function_name: str, lineno: int
    ) -> dict | None:
        if isinstance(decorator, ast.Call) and isinstance(
            decorator.func, ast.Attribute
        ):
            if decorator.func.attr == "route":
                args = [
                    ast.literal_eval(a)
                    for a in decorator.args
                    if isinstance(a, ast.Constant)
                ]
                return {
                    "method": "ANY",
                    "path": args[0] if args else "",
                    "handler": function_name,
                    "line": lineno,
                }
        return None
