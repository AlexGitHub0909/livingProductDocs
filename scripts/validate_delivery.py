#!/usr/bin/env python3
"""Validate whether a scoped product-document delivery can be called complete."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


AUDIT_SCRIPT = Path(__file__).with_name("audit_docs.py")
AUDIT_SPEC = importlib.util.spec_from_file_location("living_product_docs_audit_for_delivery", AUDIT_SCRIPT)
assert AUDIT_SPEC and AUDIT_SPEC.loader
audit_docs = importlib.util.module_from_spec(AUDIT_SPEC)
sys.modules[AUDIT_SPEC.name] = audit_docs
AUDIT_SPEC.loader.exec_module(audit_docs)


REQUIRED_COVERAGE = (
    "topology",
    "product_intent",
    "flows",
    "interfaces",
    "data",
    "tests",
    "existing_documents",
)

REQUIRED_CHECKS = (
    "topology_sampled",
    "evidence_traceability",
    "cross_document_consistency",
    "version_records",
    "writing_quality",
    "fresh_validation",
)

ALLOWED_COVERAGE_STATUSES = {"PASS", "NOT_APPLICABLE"}

DELIVERABLE_CONTRACT_CHECKS = {
    "product_requirements": (
        "audience_and_scope",
        "flows_and_exceptions",
        "rules_states_and_permissions",
        "acceptance_and_gaps",
    ),
    "test_cases": (
        "case_traceability",
        "executable_preconditions_and_steps",
        "expected_results_and_data",
        "negative_boundary_and_recovery",
        "coverage_and_evidence",
    ),
    "data_dictionary": (
        "entities_fields_and_types",
        "constraints_and_relations",
        "value_sources_and_writes",
        "sensitivity_and_retention",
        "migration_and_compatibility",
    ),
    "operations_manual": (
        "roles_and_entry",
        "observable_fields_and_actions",
        "ordered_steps_and_results",
        "errors_recovery_and_handoff",
        "applicability_and_version",
    ),
}


def within_project(project: Path, relative: str) -> Path | None:
    candidate = (project / relative).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        return None
    return candidate


def validate_manifest(manifest: dict[str, object], project: Path) -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(manifest, dict):
        return {"ready": False, "errors": ["Manifest must be a JSON object."], "warnings": []}

    if manifest.get("status") != "FINAL_COMPLETE":
        errors.append("status must be FINAL_COMPLETE before final delivery.")

    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object.")
        scope = {}
    if not isinstance(scope.get("statement"), str) or not scope.get("statement", "").strip():
        errors.append("scope.statement is required.")
    if not isinstance(scope.get("baseline"), str) or not scope.get("baseline", "").strip():
        errors.append("scope.baseline is required.")
    roots = scope.get("roots")
    if not isinstance(roots, list) or not roots or not all(
        isinstance(item, str) and item.strip() for item in roots
    ):
        errors.append("scope.roots must be a non-empty list of non-blank strings.")
    else:
        for root in roots:
            path = within_project(project, root)
            if path is None or not path.is_dir():
                errors.append(f"scope root does not exist inside the project: {root}")
    included = scope.get("included")
    if not isinstance(included, list) or not included or not all(
        isinstance(item, str) and item.strip() for item in included
    ):
        errors.append("scope.included must be a non-empty list of non-blank strings.")
    excluded = scope.get("excluded")
    if not isinstance(excluded, list) or not all(
        isinstance(item, str) and item.strip() for item in excluded
    ):
        errors.append("scope.excluded must be a list of non-blank strings.")
    requested = scope.get("requested_deliverables")
    if not isinstance(requested, list) or not requested or not all(
        isinstance(item, str) and item.strip() for item in requested
    ):
        errors.append("scope.requested_deliverables must be a non-empty list of non-blank strings.")
        requested = []
    elif len(requested) != len(set(requested)):
        errors.append("scope.requested_deliverables must not contain duplicates.")
    unsupported = sorted(set(requested) - set(DELIVERABLE_CONTRACT_CHECKS))
    if unsupported:
        errors.append(
            "scope.requested_deliverables contains unsupported kinds: "
            + ", ".join(unsupported)
        )

    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object.")
        coverage = {}
    for dimension in REQUIRED_COVERAGE:
        item = coverage.get(dimension)
        if not isinstance(item, dict):
            errors.append(f"coverage.{dimension} is required.")
            continue
        status = item.get("status")
        if status not in ALLOWED_COVERAGE_STATUSES:
            errors.append(f"coverage.{dimension}.status must be PASS or NOT_APPLICABLE.")
        elif status == "PASS":
            evidence = item.get("evidence")
            if not isinstance(evidence, list) or not evidence or not all(
                isinstance(value, str) and value.strip() for value in evidence
            ):
                errors.append(f"coverage.{dimension}.evidence must contain at least one reference.")
        elif not isinstance(item.get("reason"), str) or not item.get("reason", "").strip():
            errors.append(f"coverage.{dimension}.reason is required when status is NOT_APPLICABLE.")

    deliverables = manifest.get("deliverables")
    if not isinstance(deliverables, list):
        errors.append("deliverables must be a list.")
        deliverables = []
    by_kind: dict[str, list[dict[str, object]]] = {}
    for item in deliverables:
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str):
            errors.append("Every deliverable must be an object with a string kind.")
            continue
        by_kind.setdefault(item["kind"], []).append(item)

    for kind in requested:
        matches = by_kind.get(kind, [])
        if len(matches) != 1:
            errors.append(f"Requested deliverable {kind} must appear exactly once.")
            continue
        item = matches[0]
        if item.get("status") != "COMPLETE":
            errors.append(f"Deliverable {kind} must have status COMPLETE.")
        required_contract_checks = DELIVERABLE_CONTRACT_CHECKS.get(kind, ())
        contract_checks = item.get("contract_checks")
        if required_contract_checks and not isinstance(contract_checks, dict):
            errors.append(f"Deliverable {kind} requires contract_checks.")
            contract_checks = {}
        if isinstance(contract_checks, dict):
            for check in required_contract_checks:
                if contract_checks.get(check) != "PASS":
                    errors.append(f"Deliverable {kind} contract_checks.{check} must be PASS.")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative.strip():
            errors.append(f"Deliverable {kind} requires a path.")
            continue
        path = within_project(project, relative)
        if path is None:
            errors.append(f"Deliverable {kind} path is outside the project: {relative}")
        elif not path.is_file():
            errors.append(f"Deliverable {kind} does not exist: {relative}")
        elif not audit_docs.has_version_record(project, relative):
            errors.append(f"Deliverable {kind} has no recognizable version record: {relative}")

    required_pass_coverage = {
        "product_requirements": "product_intent",
        "test_cases": "tests",
        "data_dictionary": "data",
        "operations_manual": "interfaces",
    }
    for kind, dimension in required_pass_coverage.items():
        if kind in requested:
            item = coverage.get(dimension)
            if not isinstance(item, dict) or item.get("status") != "PASS":
                errors.append(f"coverage.{dimension} must be PASS when {kind} is requested.")

    open_items = manifest.get("open_items")
    if not isinstance(open_items, list):
        errors.append("open_items must be a list.")
    else:
        for index, item in enumerate(open_items):
            if not isinstance(item, dict):
                errors.append(f"open_items[{index}] must be an object.")
                continue
            if not isinstance(item.get("id"), str) or not item.get("id", "").strip():
                errors.append(f"open_items[{index}].id is required.")
            if not isinstance(item.get("blocking"), bool):
                errors.append(f"open_items[{index}].blocking must be true or false.")
            if not isinstance(item.get("question"), str) or not item.get("question", "").strip():
                errors.append(f"open_items[{index}].question is required.")
        blocking = [item for item in open_items if isinstance(item, dict) and item.get("blocking") is True]
        if blocking:
            errors.append(f"{len(blocking)} blocking open item(s) remain.")
        non_blocking = [item for item in open_items if isinstance(item, dict) and item.get("blocking") is False]
        if non_blocking:
            warnings.append(f"{len(non_blocking)} non-blocking open item(s) remain and must be disclosed.")

    checks = manifest.get("checks")
    if not isinstance(checks, dict):
        errors.append("checks must be an object.")
        checks = {}
    for check in REQUIRED_CHECKS:
        if checks.get(check) != "PASS":
            errors.append(f"checks.{check} must be PASS.")

    return {"ready": not errors, "errors": errors, "warnings": warnings}


def render_markdown(result: dict[str, object]) -> str:
    lines = [
        "# Delivery gate result",
        "",
        f"- Ready: `{'yes' if result['ready'] else 'no'}`",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in result["errors"] or ["None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in result["warnings"] or ["None"])
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Delivery manifest JSON")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project root for document paths")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Cannot read delivery manifest: {error}", file=sys.stderr)
        return 2
    project = args.project.expanduser().resolve()
    if not project.is_dir():
        print(f"Project directory does not exist: {project}", file=sys.stderr)
        return 2

    result = validate_manifest(manifest, project)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(result), end="")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
