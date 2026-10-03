"""Architecture: simulation must not import DB / API / UI layers."""

import ast
from pathlib import Path

import app.simulation

FORBIDDEN = {
    "fastapi",
    "starlette",
    "sqlalchemy",
    "alembic",
    "openai",
    "mcp",
    "app.api",
    "app.application",
    "app.infrastructure",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_simulation_does_not_import_outer_layers() -> None:
    root = Path(app.simulation.__file__).parent
    violations: list[str] = []
    for path in root.rglob("*.py"):
        for name in _imports(path):
            for banned in FORBIDDEN:
                if name == banned or name.startswith(banned + "."):
                    violations.append(f"{path.name}: {name}")
    assert not violations
