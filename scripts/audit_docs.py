#!/usr/bin/env python3
"""Inventory documentation evidence and flag likely synchronization gaps.

This helper is intentionally framework-neutral. It finds evidence candidates and
change patterns; it does not decide whether a product document is complete.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


IGNORED_DIRS = {
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

VERSION_HEADING_PATTERN = re.compile(
    r"^\s{0,3}(?:(?:#{1,6})\s+|\*\*\s*)?"
    r"(?:版本(?:更新|变更)?记录|变更记录|修订记录|version\s+history|revision\s+history|changelog)"
    r"(?:\s*\*\*)?\s*(?::.*)?$",
    re.IGNORECASE | re.MULTILINE,
)

VERSION_TABLE_PATTERN = re.compile(
    r"^\s*\|[^\n]*(?:版本|version|revision)[^\n]*\|[^\n]*(?:日期|date|更新范围|changes?)[^\n]*\|",
    re.IGNORECASE | re.MULTILINE,
)

PRODUCT_DOC_TERM_PATTERN = re.compile(
    r"(?:^|[/_.\s-])(?:requirements?|product|prd)(?=$|[/_.\s-])",
    re.IGNORECASE,
)

MANUAL_TERM_PATTERN = re.compile(
    r"(?:^|[/_.\s-])(?:manuals?|handbooks?|guides?|playbooks?|runbooks?)(?=$|[/_.\s-])",
    re.IGNORECASE,
)

PYTHON_REQUIREMENTS_PATTERN = re.compile(
    r"requirements(?:[-_.][a-z0-9]+)*\.txt",
    re.IGNORECASE,
)

KNOWN_CATEGORIES = {
    "api",
    "behavior",
    "data_dictionary",
    "data_structure",
    "documentation",
    "interface",
    "manuals",
    "product_docs",
    "source",
    "tests",
}

DEFAULT_CONFIG: dict[str, object] = {
    "use_default_heuristics": True,
    "use_default_ignores": True,
    "ignore_patterns": [],
    "category_patterns": {},
}


@dataclass
class Finding:
    level: str
    code: str
    message: str


def run_git(project: Path, *args: str) -> tuple[int, str]:
    try:
        process = subprocess.run(
            ["git", "-C", str(project), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return process.returncode, process.stdout


def normalize(path: str | Path) -> str:
    normalized = str(path).replace(os.sep, "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def normalize_config(config: dict[str, object] | None = None) -> dict[str, object]:
    if config is None:
        return {
            "use_default_heuristics": True,
            "use_default_ignores": True,
            "ignore_patterns": [],
            "category_patterns": {},
        }
    if not isinstance(config, dict):
        raise ValueError("Audit configuration must be a JSON object")

    unknown_keys = set(config) - set(DEFAULT_CONFIG)
    if unknown_keys:
        raise ValueError(f"Unknown configuration key: {sorted(unknown_keys)[0]}")

    use_defaults = config.get("use_default_heuristics", True)
    if not isinstance(use_defaults, bool):
        raise ValueError("use_default_heuristics must be true or false")

    use_default_ignores = config.get("use_default_ignores", True)
    if not isinstance(use_default_ignores, bool):
        raise ValueError("use_default_ignores must be true or false")

    ignore_patterns = config.get("ignore_patterns", [])
    if not isinstance(ignore_patterns, list) or not all(isinstance(item, str) for item in ignore_patterns):
        raise ValueError("ignore_patterns must be a list of strings")

    category_patterns = config.get("category_patterns", {})
    if not isinstance(category_patterns, dict):
        raise ValueError("category_patterns must be an object")

    normalized_patterns: dict[str, list[str]] = {}
    for category, patterns in category_patterns.items():
        if category not in KNOWN_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError(f"category_patterns.{category} must be a list of strings")
        normalized_patterns[category] = patterns

    return {
        "use_default_heuristics": use_defaults,
        "use_default_ignores": use_default_ignores,
        "ignore_patterns": ignore_patterns,
        "category_patterns": normalized_patterns,
    }


def load_config(path: Path) -> dict[str, object]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read audit configuration: {path}: {error}") from error
    return normalize_config(content)


def matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = normalize(path)
    normalized_pattern = normalize(pattern)
    if fnmatch.fnmatchcase(normalized_path.lower(), normalized_pattern.lower()):
        return True
    if normalized_pattern.endswith("/**"):
        root = normalized_pattern[:-3].rstrip("/")
        return normalized_path.lower() == root.lower() or normalized_path.lower().startswith(f"{root.lower()}/")
    return False


def iter_files(
    project: Path,
    ignore_patterns: Iterable[str] = (),
    use_default_ignores: bool = True,
    scan_errors: list[str] | None = None,
) -> Iterable[str]:
    patterns = tuple(ignore_patterns)

    def record_error(error: OSError) -> None:
        if scan_errors is None:
            return
        target = error.filename or "unknown path"
        try:
            display_target = normalize(Path(target).relative_to(project))
        except (TypeError, ValueError):
            display_target = normalize(target)
        reason = error.strerror or str(error)
        scan_errors.append(f"{display_target}: {reason}")

    for root, dirs, files in os.walk(project, onerror=record_error):
        retained_dirs: list[str] = []
        for directory in sorted(dirs):
            if directory == ".git" or (use_default_ignores and directory in IGNORED_DIRS):
                continue
            relative_dir = normalize((Path(root) / directory).relative_to(project))
            if any(matches_pattern(relative_dir, pattern) for pattern in patterns):
                continue
            retained_dirs.append(directory)
        dirs[:] = retained_dirs
        for filename in sorted(files):
            full_path = Path(root) / filename
            try:
                relative = full_path.relative_to(project)
            except ValueError:
                continue
            normalized = normalize(relative)
            if any(matches_pattern(normalized, pattern) for pattern in patterns):
                continue
            yield normalized


def is_test_file(path: str) -> bool:
    lower = path.lower()
    name = Path(lower).name
    return (
        any(part in {"test", "tests", "e2e", "integration-tests"} for part in Path(lower).parts)
        or name.startswith("test_")
        or re.search(r"[._-](test|spec)\.[a-z0-9]+$", name) is not None
    )


def classify(path: str, config: dict[str, object] | None = None) -> set[str]:
    normalized_config = normalize_config(config)
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

    if normalized_config["use_default_heuristics"]:
        is_python_requirements = PYTHON_REQUIREMENTS_PATTERN.fullmatch(Path(lower).name) is not None
        if suffix in DOC_EXTENSIONS and not is_python_requirements and (
            PRODUCT_DOC_TERM_PATTERN.search(lower) is not None or any(token in lower for token in ("需求", "产品"))
        ):
            categories.add("product_docs")
        if suffix in DOC_EXTENSIONS and (
            MANUAL_TERM_PATTERN.search(lower) is not None or any(token in lower for token in ("手册", "操作指南"))
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
            part in {"pages", "screens", "views", "components"} for part in parts
        ):
            categories.add("interface")
        if any(part in {"services", "jobs", "workers", "commands", "handlers", "domain"} for part in parts):
            categories.add("behavior")

    category_patterns = normalized_config["category_patterns"]
    assert isinstance(category_patterns, dict)
    for category, patterns in category_patterns.items():
        if any(matches_pattern(lower, pattern) for pattern in patterns):
            categories.add(category)

    return categories


def tracked_changes(project: Path, base: str | None) -> list[str]:
    changed: set[str] = set()

    if base:
        code, output = run_git(project, "diff", "--name-only", "-z", f"{base}...HEAD")
        if code != 0:
            raise RuntimeError(f"Cannot compare with base ref: {base}")
        changed.update(filter(None, output.split("\0")))

    code, output = run_git(project, "diff", "--name-only", "-z", "HEAD")
    if code == 0:
        changed.update(filter(None, output.split("\0")))
    else:
        # Unborn repositories have no HEAD yet. Read staged and unstaged paths
        # independently so the scanner remains useful during initial setup.
        for args in (
            ("diff", "--cached", "--name-only", "-z"),
            ("diff", "--name-only", "-z"),
        ):
            fallback_code, fallback_output = run_git(project, *args)
            if fallback_code == 0:
                changed.update(filter(None, fallback_output.split("\0")))

    code, output = run_git(project, "ls-files", "--others", "--exclude-standard", "-z")
    if code == 0:
        changed.update(filter(None, output.split("\0")))

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
    document_head = content[:8_000]
    return (
        VERSION_HEADING_PATTERN.search(document_head) is not None
        or VERSION_TABLE_PATTERN.search(document_head) is not None
    )


def bucket(paths: Iterable[str], config: dict[str, object] | None = None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in paths:
        for category in classify(path, config):
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


def audit(
    project: Path,
    base: str | None,
    config: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized_config = normalize_config(config)
    ignore_patterns = normalized_config["ignore_patterns"]
    assert isinstance(ignore_patterns, list)
    use_default_ignores = normalized_config["use_default_ignores"]
    assert isinstance(use_default_ignores, bool)
    scan_errors: list[str] = []
    files = sorted(iter_files(project, ignore_patterns, use_default_ignores, scan_errors))
    changed_files = [
        path
        for path in tracked_changes(project, base)
        if not any(matches_pattern(path, pattern) for pattern in ignore_patterns)
    ]
    inventory = bucket(files, normalized_config)
    changed = bucket(changed_files, normalized_config)

    long_lived_docs = sorted(
        set(inventory.get("product_docs", []))
        | set(inventory.get("manuals", []))
        | set(inventory.get("data_dictionary", []))
    )
    missing_version = [path for path in long_lived_docs if not has_version_record(project, path)]

    _, branch = run_git(project, "branch", "--show-current")
    _, head = run_git(project, "rev-parse", "HEAD")
    branch = branch.strip()
    head = head.strip()

    findings = build_findings(changed)
    if scan_errors:
        findings.insert(
            0,
            Finding(
                "warning",
                "SCAN_INCOMPLETE",
                f"Could not read {len(scan_errors)} path(s); the evidence inventory is incomplete.",
            ),
        )
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
        "configuration": normalized_config,
        "scan_errors": scan_errors,
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
        f"- Default heuristics: `{'enabled' if report['configuration']['use_default_heuristics'] else 'disabled'}`",
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

    scan_errors = report["scan_errors"]
    if scan_errors:
        lines.extend(["", "## Scan errors", ""])
        lines.extend(f"- `{error}`" for error in scan_errors[:20])
        if len(scan_errors) > 20:
            lines.append(f"- ... {len(scan_errors) - 20} more")

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
    parser.add_argument("--config", type=Path, help="Optional JSON file with project-specific topology mappings")
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
        config = load_config(args.config.expanduser().resolve()) if args.config else None
        report = audit(project, args.base, config)
    except (RuntimeError, ValueError) as error:
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
