#!/usr/bin/env python3
"""Discover project boundaries and evidence candidates without assuming a fixed layout."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path


AUDIT_SCRIPT = Path(__file__).with_name("audit_docs.py")
AUDIT_SPEC = importlib.util.spec_from_file_location("living_product_docs_audit", AUDIT_SCRIPT)
assert AUDIT_SPEC and AUDIT_SPEC.loader
audit_docs = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = audit_docs
AUDIT_SPEC.loader.exec_module(audit_docs)


MANIFEST_HINTS = {
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "Package.swift": "swift",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
    "composer.json": "php",
    "deno.json": "deno",
    "deno.jsonc": "deno",
    "go.mod": "go",
    "package.json": "node",
    "pnpm-workspace.yaml": "pnpm-workspace",
    "pom.xml": "maven",
    "pubspec.yaml": "dart",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "settings.gradle": "gradle",
    "settings.gradle.kts": "gradle",
}

MANIFEST_SUFFIX_HINTS = {
    ".csproj": "dotnet",
    ".fsproj": "dotnet",
    ".sln": "dotnet",
    ".vbproj": "dotnet",
}


def manifest_hint(path: str) -> str | None:
    name = Path(path).name
    if name in MANIFEST_HINTS:
        return MANIFEST_HINTS[name]
    return MANIFEST_SUFFIX_HINTS.get(Path(name).suffix.lower())


def find_git_roots(
    project: Path,
    ignore_patterns: list[str],
    use_default_ignores: bool,
) -> list[str]:
    roots: set[str] = set()
    for root, dirs, files in os.walk(project):
        if ".git" in dirs or ".git" in files:
            relative = Path(root).relative_to(project)
            roots.add(audit_docs.normalize(relative) or ".")
        retained: list[str] = []
        for directory in sorted(dirs):
            if directory == ".git":
                continue
            if use_default_ignores and directory in audit_docs.IGNORED_DIRS:
                continue
            relative_dir = audit_docs.normalize((Path(root) / directory).relative_to(project))
            if any(audit_docs.matches_pattern(relative_dir, pattern) for pattern in ignore_patterns):
                continue
            retained.append(directory)
        dirs[:] = retained
    return sorted(roots)


def component_for(path: str, roots: list[str]) -> str:
    candidates = [
        root
        for root in roots
        if root == "." or path == root or path.startswith(f"{root}/")
    ]
    return max(
        candidates,
        key=lambda item: (0 if item == "." else len(Path(item).parts), len(item)),
    )


def discover(project: Path, config: dict[str, object] | None) -> dict[str, object]:
    project = project.expanduser().resolve()
    normalized_config = audit_docs.normalize_config(config)
    ignore_patterns = normalized_config["ignore_patterns"]
    use_default_ignores = normalized_config["use_default_ignores"]
    assert isinstance(ignore_patterns, list)
    assert isinstance(use_default_ignores, bool)

    scan_errors: list[str] = []
    files = sorted(
        audit_docs.iter_files(
            project,
            ignore_patterns,
            use_default_ignores,
            scan_errors,
        )
    )
    manifests = sorted(path for path in files if manifest_hint(path))
    component_roots = {"."}
    component_roots.update(
        audit_docs.normalize(Path(path).parent) or "."
        for path in manifests
    )
    ordered_roots = sorted(component_roots, key=lambda item: (item.count("/"), item))

    inventory = audit_docs.bucket(files, normalized_config)
    assigned: dict[str, list[str]] = {root: [] for root in ordered_roots}
    for path in files:
        assigned[component_for(path, ordered_roots)].append(path)

    components: list[dict[str, object]] = []
    for root in ordered_roots:
        component_files = assigned[root]
        component_manifests = [
            path
            for path in manifests
            if (audit_docs.normalize(Path(path).parent) or ".") == root
        ]
        component_inventory = audit_docs.bucket(component_files, normalized_config)
        components.append(
            {
                "root": root,
                "manifests": component_manifests,
                "runtime_hints": sorted({manifest_hint(path) for path in component_manifests if manifest_hint(path)}),
                "evidence_counts": {
                    category: len(paths)
                    for category, paths in component_inventory.items()
                },
                "evidence_samples": {
                    category: paths[:20]
                    for category, paths in component_inventory.items()
                },
            }
        )

    limitations: list[str] = []
    if not manifests:
        limitations.append("No recognized manifest was found; component boundaries require manual confirmation.")
    if scan_errors:
        limitations.append("At least one path could not be read; discovery is incomplete.")
    for category, message in (
        ("tests", "No test candidate was detected."),
        ("data_structure", "No data-structure candidate was detected."),
        ("documentation", "No documentation candidate was detected."),
    ):
        if category not in inventory:
            limitations.append(message)

    return {
        "project": str(project),
        "configuration": normalized_config,
        "git_roots": find_git_roots(project, ignore_patterns, use_default_ignores),
        "manifests": manifests,
        "components": components,
        "evidence_inventory": inventory,
        "scan_errors": scan_errors,
        "limitations": limitations,
        "disclaimer": "Candidates require manual confirmation through runtime registration and call relationships.",
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Project discovery candidates",
        "",
        f"- Project: `{report['project']}`",
        f"- Git roots: {len(report['git_roots'])}",
        f"- Manifests: {len(report['manifests'])}",
        f"- Components: {len(report['components'])}",
        "",
        "## Components",
        "",
    ]
    for component in report["components"]:
        lines.append(f"### `{component['root']}`")
        lines.append(f"- Runtime hints: {', '.join(component['runtime_hints']) or 'unknown'}")
        lines.append(f"- Manifests: {', '.join(component['manifests']) or 'none'}")
        counts = component["evidence_counts"]
        lines.append(
            "- Evidence: "
            + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "none")
        )
        lines.append("")

    lines.extend(["## Limitations", ""])
    if report["limitations"]:
        lines.extend(f"- {item}" for item in report["limitations"])
    else:
        lines.append("- No structural limitation detected by the scanner.")
    lines.extend(["", f"> {report['disclaimer']}"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Project directory to inspect")
    parser.add_argument("--config", type=Path, help="Optional audit topology configuration")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        print(f"Project directory does not exist: {project}", file=sys.stderr)
        return 2
    try:
        config = audit_docs.load_config(args.config.expanduser().resolve()) if args.config else None
        report = discover(project, config)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 1 if report["scan_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
