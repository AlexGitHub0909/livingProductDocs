from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_delivery.py"
SPEC = importlib.util.spec_from_file_location("validate_delivery", SCRIPT)
assert SPEC and SPEC.loader
validate_delivery = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validate_delivery
SPEC.loader.exec_module(validate_delivery)


class ValidateDeliveryTest(unittest.TestCase):
    def make_project(self) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, object]]:
        temporary = tempfile.TemporaryDirectory()
        project = Path(temporary.name)
        document_paths = {
            "product_requirements": "docs/product.md",
            "test_cases": "docs/tests.md",
            "data_dictionary": "docs/data.md",
            "operations_manual": "docs/manual.md",
        }
        for path in document_paths.values():
            document = project / path
            document.parent.mkdir(parents=True, exist_ok=True)
            document.write_text("# Document\n\n## Version History\n\n| Version | Date | Changes |\n", encoding="utf-8")

        coverage = {
            dimension: {"status": "PASS", "evidence": [f"reviewed:{dimension}"]}
            for dimension in validate_delivery.REQUIRED_COVERAGE
        }
        manifest: dict[str, object] = {
            "status": "FINAL_COMPLETE",
            "scope": {
                "statement": "Current-state documentation for the selected product scope.",
                "baseline": "commit:test-baseline",
                "roots": ["."],
                "included": ["selected product flows"],
                "excluded": [],
                "requested_deliverables": list(document_paths),
            },
            "coverage": coverage,
            "deliverables": [
                {
                    "kind": kind,
                    "path": path,
                    "status": "COMPLETE",
                    "contract_checks": {
                        check: "PASS"
                        for check in validate_delivery.DELIVERABLE_CONTRACT_CHECKS[kind]
                    },
                }
                for kind, path in document_paths.items()
            ],
            "open_items": [],
            "checks": {check: "PASS" for check in validate_delivery.REQUIRED_CHECKS},
        }
        return temporary, project, manifest

    def test_accepts_complete_scoped_delivery(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertTrue(result["ready"])
        self.assertEqual([], result["errors"])

    def test_cli_returns_success_for_complete_delivery(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        manifest_path = project / "delivery-manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(manifest_path),
                "--project",
                str(project),
                "--format",
                "json",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["ready"])

    def test_rejects_missing_coverage_dimension(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        del manifest["coverage"]["product_intent"]

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("product_intent" in error for error in result["errors"]))

    def test_rejects_unknown_deliverable_kind_without_a_contract(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        manifest["scope"]["requested_deliverables"].append("miscellaneous_notes")

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("unsupported kinds" in error for error in result["errors"]))

    def test_rejects_blocking_open_item(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        manifest["open_items"] = [
            {"id": "OPEN-1", "blocking": True, "question": "Which policy is authoritative?"}
        ]

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("blocking" in error.lower() for error in result["errors"]))

    def test_rejects_product_requirements_without_product_intent_evidence(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        manifest["coverage"]["product_intent"] = {
            "status": "NOT_APPLICABLE",
            "reason": "No product decision was available.",
        }

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("product_intent" in error for error in result["errors"]))

    def test_rejects_invalid_scope_root_and_empty_evidence(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        manifest["scope"]["roots"] = ["missing-component"]
        manifest["coverage"]["flows"]["evidence"] = [""]

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("missing-component" in error for error in result["errors"]))
        self.assertTrue(any("coverage.flows.evidence" in error for error in result["errors"]))

    def test_rejects_missing_document_and_version_record(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        (project / "docs/tests.md").unlink()
        (project / "docs/data.md").write_text("# Data dictionary\n", encoding="utf-8")

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("does not exist" in error for error in result["errors"]))
        self.assertTrue(any("version record" in error for error in result["errors"]))

    def test_rejects_incomplete_deliverable_contract(self) -> None:
        temporary, project, manifest = self.make_project()
        self.addCleanup(temporary.cleanup)
        product = next(item for item in manifest["deliverables"] if item["kind"] == "product_requirements")
        del product["contract_checks"]["acceptance_and_gaps"]

        result = validate_delivery.validate_manifest(manifest, project)

        self.assertFalse(result["ready"])
        self.assertTrue(any("acceptance_and_gaps" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
