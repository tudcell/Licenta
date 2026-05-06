"""Architecture guardrails for clean layered dependencies.

Layout (one persistence folder, no split between `repository` and
`infrastructure`):

    domain          - pure business types and rules; no I/O, no frameworks
    service         - use-cases that orchestrate domain + infrastructure
    infrastructure  - SQL/JSON/pickle adapters, event bus, etc.
    api             - HTTP/WebSocket delivery layer
    utils           - cross-cutting helpers (no layer responsibility)
"""

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


def _violations(base: Path, forbidden: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    for path in _iter_python_files(base):
        imports = _collect_imports(path)
        bad = sorted(name for name in imports if name.startswith(forbidden))
        if bad:
            issues.append(f"{path.relative_to(ROOT)} -> {bad}")
    return issues


def test_domain_layer_is_self_contained():
    """Domain may only depend on stdlib, third-party, or other domain modules."""
    forbidden = ("src.api", "src.service", "src.infrastructure", "src.utils", "src.repository")
    issues = _violations(SRC / "domain", forbidden)
    assert not issues, "\n".join(["Domain layer dependency violations:", *issues])


def test_service_layer_does_not_depend_on_api():
    issues = _violations(SRC / "service", ("src.api",))
    assert not issues, "\n".join(["Service layer dependency violations:", *issues])


def test_infrastructure_does_not_depend_on_service_or_api():
    issues = _violations(SRC / "infrastructure", ("src.api", "src.service"))
    assert not issues, "\n".join(["Infrastructure layer dependency violations:", *issues])


def test_api_routes_do_not_depend_on_infrastructure_or_old_paths():
    """Routes must go through the service layer; they cannot reach into
    persistence, and they cannot import the old `repository` / `database`
    modules that have since been removed."""
    forbidden = ("src.repository", "src.api.database", "src.infrastructure")
    issues = _violations(SRC / "api" / "routes", forbidden)
    assert not issues, "\n".join(["API route dependency violations:", *issues])


def test_no_legacy_repository_folder():
    """The old `src/repository/` was redundant with `src/infrastructure/` and
    has been removed; this guardrail prevents it from coming back."""
    legacy = SRC / "repository"
    assert not legacy.exists(), f"Legacy folder reappeared: {legacy.relative_to(ROOT)}"
