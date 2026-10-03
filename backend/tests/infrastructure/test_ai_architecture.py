"""Adapters must not import Domain DB write paths."""

from __future__ import annotations

import ast
from pathlib import Path

import app.infrastructure.ai
import app.infrastructure.mcp


FORBIDDEN_WRITES = {
    "app.infrastructure.db.uow",
    "app.infrastructure.db.repositories",
    "app.infrastructure.db.ai_repo",
    "SqlAlchemyUnitOfWork",
}


def _imports_and_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            for alias in node.names:
                found.add(alias.name)
    return found


def test_ai_and_fabricate_adapters_cannot_write_domain_db() -> None:
    roots = [
        Path(app.infrastructure.ai.__file__).parent,
        Path(app.infrastructure.mcp.__file__).parent,
    ]
    files: list[Path] = []
    for root in roots:
        for path in root.glob("*.py"):
            name = path.name
            if name.startswith("mock_") or name in {
                "openai_provider.py",
                "equipment_providers.py",
                "fabricate.py",
                "petri_pilot.py",
            }:
                files.append(path)
    violations: list[str] = []
    for path in files:
        names = _imports_and_names(path)
        for banned in FORBIDDEN_WRITES:
            if banned in names:
                violations.append(f"{path.name}: {banned}")
    assert not violations
