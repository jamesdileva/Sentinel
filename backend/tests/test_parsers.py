"""Sprint 3: parser correctness against fixture content."""

from pathlib import Path

from app.parsers import (
    FastAPIParser,
    FlaskParser,
    JavaScriptParser,
    NodeParser,
    PythonParser,
    ReactParser,
    SQLParser,
    TypeScriptParser,
)

FIXTURES = Path(__file__).parent / "fixtures"
PY_MAIN = FIXTURES / "sample_python_project" / "app" / "main.py"
PY_SERVICE = FIXTURES / "sample_python_project" / "app" / "services" / "__init__.py"
REACT_APP = FIXTURES / "sample_react_project" / "src" / "App.tsx"
REACT_CARD = FIXTURES / "sample_react_project" / "src" / "components" / "Card.tsx"
API_TS = FIXTURES / "sample_react_project" / "src" / "api.ts"
PACKAGE_JSON = FIXTURES / "sample_react_project" / "package.json"


def test_python_parser_structure():
    parsed = PythonParser().parse_file(str(PY_MAIN))
    assert parsed.language == "python"
    assert {f["name"] for f in parsed.structure["functions"]} >= {
        "health",
        "create_item",
        "get_item",
    }
    assert "fastapi" in parsed.dependencies


def test_python_parser_classes_and_methods():
    parsed = PythonParser().parse_file(str(PY_SERVICE))
    classes = parsed.structure["classes"]
    assert {c["name"] for c in classes} == {"Item", "Service"}
    service = next(c for c in classes if c["name"] == "Service")
    assert "create" in service["methods"]
    assert "list_items" in service["methods"]


def test_fastapi_parser_routes():
    parsed = FastAPIParser().parse_file(str(PY_MAIN))
    routes = parsed.structure["routes"]
    by_path = {r["path"]: r for r in routes}
    assert by_path["/health"]["method"] == "GET"
    assert by_path["/items"]["method"] == "POST"
    assert by_path["/items/{item_id}"]["method"] == "GET"
    assert by_path["/items/{item_id}"]["handler"] == "get_item"


def test_flask_parser_route():
    content = """
from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return "hi"

@app.route("/user/<name>", methods=["POST"])
def user(name):
    return name
"""
    parsed = FlaskParser().extract_structure(content)
    routes = {r["path"]: r["handler"] for r in parsed["routes"]}
    assert routes == {"/": "index", "/user/<name>": "user"}


def test_javascript_parser_imports_and_exports():
    parsed = JavaScriptParser().parse_file(str(API_TS))
    assert "axios" in parsed.dependencies
    assert "Item" in parsed.structure["exports"]


def test_typescript_parser_interfaces():
    parsed = TypeScriptParser().parse_file(str(API_TS))
    assert "Item" in parsed.structure["interfaces"]
    assert parsed.language == "typescript"


def test_react_parser_language_per_suffix(tmp_path):
    tsx = ReactParser().parse_file(str(REACT_APP))
    ts = ReactParser().parse_file(str(API_TS))
    jsx_file = tmp_path / "Widget.jsx"
    jsx_file.write_text("export default function Widget() { return <div />; }")
    jsx = ReactParser().parse_file(str(jsx_file))
    assert tsx.language == "typescript"
    assert ts.language == "typescript"
    assert jsx.language == "javascript"


def test_react_parser_components_hooks_jsx():
    parsed = ReactParser().parse_file(str(REACT_APP))
    names = {c["name"] for c in parsed.structure["components"]}
    assert "Dashboard" in names
    assert "StatusText" in names
    assert "useState" in parsed.structure["hooks"]
    assert "useEffect" in parsed.structure["hooks"]
    assert "Card" in parsed.structure["jsx_elements"]


def test_react_parser_arrow_component():
    parsed = ReactParser().parse_file(str(REACT_CARD))
    assert {c["name"] for c in parsed.structure["components"]} == {"Card"}
    assert "CardProps" in parsed.structure["interfaces"]


def test_node_parser_project_model():
    parsed = NodeParser().parse_file(str(PACKAGE_JSON))
    assert parsed.structure["name"] == "sample-react-project"
    assert "react" in parsed.structure["dependencies"]
    assert "test" in parsed.structure["scripts"]
    assert "typescript" in parsed.dependencies


def test_sql_parser_tables():
    content = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL,
    age INTEGER
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    total REAL
);

SELECT * FROM users WHERE age > 21;
"""
    parsed = SQLParser().extract_structure(content)
    tables = {t["name"]: t for t in parsed["tables"]}
    assert set(tables) == {"users", "orders"}
    assert [c["name"] for c in tables["users"]["columns"]] == ["id", "email", "age"]
    assert "SELECT" in parsed["statements"]
