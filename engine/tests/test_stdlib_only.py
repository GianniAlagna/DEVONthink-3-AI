"""The engine runtime may import only the Python standard library (SPEC §5, brief §2.3)."""
import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "dt3agent"


def foreign_imports(source: str) -> set[str]:
    """Top-level modules imported by `source` that are neither stdlib nor dt3agent."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return {m for m in found if m not in sys.stdlib_module_names and m != "dt3agent"}


def test_checker_flags_third_party_imports():
    src = "import json\nimport requests\nfrom yaml import safe_load\nfrom . import x\nfrom dt3agent.rules import a\n"
    assert foreign_imports(src) == {"requests", "yaml"}


def test_engine_package_uses_stdlib_only():
    files = sorted(PACKAGE.rglob("*.py"))
    assert files, "engine package not found"
    offenders = {str(f.relative_to(PACKAGE)): foreign_imports(f.read_text(encoding="utf-8")) for f in files}
    assert {k: v for k, v in offenders.items() if v} == {}
