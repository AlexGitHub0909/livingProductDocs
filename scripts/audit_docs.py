#!/usr/bin/env python3
"""Inventory documentation evidence and flag likely synchronization gaps.

This helper is intentionally framework-neutral. It finds evidence candidates and
change patterns; it does not decide whether a product document is complete.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


IGNORED_DIRS = {
    ".git",
    ".next",
    ".nuxt",
    ".venv",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "output",
    "target",
    "vendor",
}

DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
SOURCE_EXTENSIONS = {
    ".cs",
    ".dart",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
}

VERSION_PATTERN = re.compile(
    r"版本(?:更新|变更)?记录|变更记录|修订记录|version\s+history|revision\s+history|changelog",
    re.IGNORECASE,
)


@dataclass
class Finding:
    level: str
    code: str
    message: str


def run_git(project: Path, *args: str) -> tuple[int, str]:
    process = subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return process.returncode, process.stdout.strip()


def normalize(path: str | Path) -> str:
    return str(path).replace(os.sep, "/").lstrip("./")


def iter_files(project: Path) -> Iterable[str]:
    for root, dirs, files in os.walk(project):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for filename in sorted(files):
            full_path = Path(root) / filename
            try:
                relative = full_path.relative_to(project)
            except ValueError:
                continue
            yield normalize(relative)


def is_test_file(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    return (
        any(part in {"test", "tests", "e2e", "integration-tests"} for part in Path(lower).parts)
        or name.startswith("test_")
        or re.search(r"[._-](test|spec)\.[a-z0-9]+$", name) is not None
    )


def classify(path: str) -> set[str]:
    lower = normalize(path).lower()
    suffix = Path(lower).suffix
    parts = set(Path(lower).parts)
    categories: set[str] = set()

    if suffix in DOC_EXTENSIONS:
        categories.add("documentation")
    if is_test_file(lower):
        categories.add("tests")
    if suffix in SOURCE_EXTENSIONS and not is_test_file(lower):
        categories.add("source")
    if suffix in DOC_EXTENSIONS and any(
        token in lower for token in ("requirement", "requirements", "product", "prd", "需求", "产品")
    ):
        categories.add("product_docs")
    if suffix in DOC_EXTENSIONS and any(
        token in lower for token in ("manual", "handbook", "guide", "playbook", "runbook", "手册", "操作指南")
    ):
        categories.add("manuals")
    if suffix in DOC_EXTENSIONS and any(
        token in lower for token in ("data-dictionary", "data_dictionary", "dictionary", "数据字典")
    ):
        categories.add("data_dictionary")
    if (
        any(part in {"migration", "migrations", "schema", "schemas", "models", "entities"} for part in parts)
        or any(token in lower for token in ("prisma.schema", "schema.sql", "structure.sql"))
    ):
        categories.add("data_structure")
    if any(part in {"route", "routes", "controller", "controllers", "api", "apis"} for part in parts) or any(
        token in lower for token in ("openapi", "swagger", "asyncapi")
    ):
        categories.add("api")
    if suffix in {".tsx", ".jsx", ".vue", ".svelte", ".dart", ".swift"} or any(
        part in {"pages", "screens", "views", "components", "app"} for part in parts
    ):
        categories.add("interface")
    if any(part in {"services", "jobs", "workers", "commands", "handlers", "domain"} for part in parts):
        categories.add("behavior")

    return categories


def tracked_changes(project: Path, base: str | None) -> list[str]:
    changed: set[str] = set()

    if base:
        code, output = run_git(project, "diff", "--name-only", f"{base}...HEAD")
        if code != 0:
            raise RuntimeError(f"Cannot compare with base ref: {base}")
        changed.update(filter(None, output.splitlines()))

    code, output = run_git(project, "status", "--porcelain=v1", "--untracked-files=all")
    if code == 0:
        for line in output.splitlines():
            if len(line) < 4:
                continue
            candidate = line[3:]
            if " -> " in candidate:
                candidate = candidate.split(" -> ", 1)[1]
            changed.add(candidate.strip('"'))

    return sorted(normalize(path) for path in changed if path)


def has_version_record(project: Path, relative: str) -> bool:
    path = project / relative
    if path.suffix.lower() not in DOC_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > 2_000_000:
            return False
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return VERSION_PATTERN.search(content[:30_000]) is not None


def bucket(paths: Iterable[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in paths:
        for category in classify(path):
            result.setdefault(category, []).append(path)
    return {key: sorted(set(values)) for key, values in sorted(result.items())}


def build_findings(changed: dict[str, list[str]]) -> list[Finding]:
    present = set(changed)
    findings: list[Finding] = []

    def warn(condition: bool, code: str, message: str) -> None:
        if condition:
            findings.append(Finding("warning", code, message))

    source_changed = bool(present & {"source", "interface", "behavior", "api", "data_structure"})
    docs_changed = bool(present & {"product_docs", "manuals", "data_dictionary"})

    warn(
        source_changed and not docs_changed,
        "SOURCE_WITHOUT_DELIVERY_DOCS",
        "Application behavior changed but no product, manual, or data-dictionary document changed.",
    )
    warn(
        "interface" in present and "manuals" not in present and "product_docs" not in present,
        "INTERFACE_WITHOUT_USER_DOCS",
        "Interface files changed but no product requirement or user-facing manual changed.",
    )
    warn(
        "data_structure" in present and "data_dictionary" not in present,
        "DATA_WITHOUT_DICTIONARY",
        "Data structure files changed but no data-dictionary document changed.",
    )
    warn(
        bool(present & {"source", "interface", "behavior", "api", "data_structure"}) and "tests" not in present,
        "BEHAVIOR_WITHOUT_TEST_CHANGE",
        "Behavior-related files changed but no test file changed; confirm whether existing coverage is sufficient.",
    )
    return findings


def audit(project: Path, base: str | None) -> dict[str, object]:
    files = sorted(iter_files(project))
    changed_files = tracked_changes(project, base)
    inventory = bucket(files)
    changed = bucket(changed_files)

    long_lived_docs = sorted(
        set(inventory.get("product_docs", []))
        | set(inventory.get("manuals", []))
        | set(inventory.get("data_dictionary", []))
    )
    missing_version = [path for path in long_lived_docs if not has_version_record(project, path)]

    _, branch = run_git(project, "branch", "--show-current")
    _, head = run_git(project, "rev-parse", "HEAD")

    findings = build_findings(changed)
    for path in missing_version:
        findings.append(
            Finding(
                "notice",
                "MISSING_VERSION_RECORD",
                f"Long-lived delivery document has no recognizable version record: {path}",
            )
        )

    return {
        "project": str(project),
        "git": {"branch": branch or None, "head": head or None, "base": base},
        "changed_files": changed_files,
        "changed_categories": changed,
        "inventory": inventory,
        "findings": [asdict(item) for item in findings],
    }


def render_markdown(report: dict[str, object]) -> str:
    git = report["git"]
    lines = [
        "# Product documentation evidence audit",
        "",
        f"- Project: `{report['project']}`",
        f"- Branch: `{git['branch'] or 'unknown'}`",
        f"- HEAD: `{git['head'] or 'unknown'}`",
        f"- Base: `{git['base'] or 'working tree only'}`",
        "",
        "## Changed files",
        "",
    ]

    changed_files = report["changed_files"]
    if changed_files:
        lines.extend(f"- `{path}`" for path in changed_files)
    else:
        lines.append("- No changes detected for the selected comparison.")

    lines.extend(["", "## Findings", ""])
    findings = report["findings"]
    if findings:
        lines.extend(f"- **{item['level'].upper()} {item['code']}**: {item['message']}" for item in findings)
    else:
        lines.append("- No structural synchronization warning detected.")

    lines.extend(["", "## Evidence inventory", ""])
    inventory = report["inventory"]
    for category, paths in inventory.items():
        lines.append(f"### {category} ({len(paths)})")
        lines.extend(f"- `{path}`" for path in paths[:50])
        if len(paths) > 50:
            lines.append(f"- ... {len(paths) - 50} more")
        lines.append("")

    lines.append("> This report identifies evidence candidates and likely gaps; it does not prove document completeness.")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project directory to inspect")
    parser.add_argument("--base", help="Git base ref used for committed-change comparison")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warning findings exist")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        print(f"Project directory does not exist: {project}", file=sys.stderr)
        return 2

    try:
        report = audit(project, args.base)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")

    has_warning = any(item["level"] == "warning" for item in report["findings"])
    return 1 if args.strict and has_warning else 0


if __name__ == "__main__":
    raise SystemExit(main())
