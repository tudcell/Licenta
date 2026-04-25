"""Architecture guardrails for clean layered dependencies."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)


def _collect_imports(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(1) for match in IMPORT_PATTERN.finditer(text)}


def _iter_python_files(base: Path):
    for path in base.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def test_repository_layer_does_not_depend_on_service_or_api_layers():
    repository_dir = SRC / "repository"
    forbidden_prefixes = ("src.service", "src.api")

    violations: list[str] = []
    for path in _iter_python_files(repository_dir):
        imports = _collect_imports(path)
        forbidden = [name for name in imports if name.startswith(forbidden_prefixes)]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)} -> {sorted(forbidden)}")

    assert not violations, "\n".join(["Repository layer import violations:", *violations])


def test_domain_layer_does_not_depend_on_repository_service_or_api_layers():
    domain_dir = SRC / "domain"
    forbidden_prefixes = ("src.repository", "src.service", "src.api")

    violations: list[str] = []
    for path in _iter_python_files(domain_dir):
        imports = _collect_imports(path)
        forbidden = [name for name in imports if name.startswith(forbidden_prefixes)]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)} -> {sorted(forbidden)}")

    assert not violations, "\n".join(["Domain layer import violations:", *violations])


def test_service_layer_does_not_depend_on_api_layer():
    service_dir = SRC / "service"
    forbidden_prefixes = ("src.api",)

    violations: list[str] = []
    for path in _iter_python_files(service_dir):
        imports = _collect_imports(path)
        forbidden = [name for name in imports if name.startswith(forbidden_prefixes)]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)} -> {sorted(forbidden)}")

    assert not violations, "\n".join(["Service layer import violations:", *violations])


