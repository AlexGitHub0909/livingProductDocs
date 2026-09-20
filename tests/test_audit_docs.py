from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_docs.py"
SPEC = importlib.util.spec_from_file_location("audit_docs", SCRIPT)
assert SPEC and SPEC.loader
audit_docs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_docs
SPEC.loader.exec_module(audit_docs)


class AuditDocsTest(unittest.TestCase):
    def test_classifies_common_evidence_without_framework_assumptions(self) -> None:
        self.assertIn("interface", audit_docs.classify("src/screens/settings.tsx"))
        self.assertIn("tests", audit_docs.classify("tests/settings_test.py"))
        self.assertIn("data_structure", audit_docs.classify("db/migrations/001_add_status.sql"))
        self.assertIn("data_dictionary", audit_docs.classify("docs/data-dictionary.md"))
        self.assertIn("manuals", audit_docs.classify("docs/user-manual.md"))
        self.assertIn("manuals", audit_docs.classify("knowledge/guides/account.md"))
        self.assertNotIn("interface", audit_docs.classify("app/Services/OrderService.php"))

    def test_product_document_keywords_use_semantic_boundaries(self) -> None:
        dependency_manifest = audit_docs.classify("backend/requirements.txt")
        production_runbook = audit_docs.classify("docs/specs/production-runbook.md")
        productivity_notes = audit_docs.classify("docs/productivity-notes.md")

        self.assertNotIn("product_docs", dependency_manifest)
        self.assertNotIn("product_docs", production_runbook)
        self.assertIn("manuals", production_runbook)
        self.assertNotIn("product_docs", productivity_notes)

    def test_normalize_preserves_dot_prefixed_directories(self) -> None:
        self.assertEqual(".github/workflows/check.yml", audit_docs.normalize(".github/workflows/check.yml"))
        self.assertEqual("docs/guide.md", audit_docs.normalize("./docs/guide.md"))

    def test_detects_version_record_near_document_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            document = project / "docs" / "requirements.md"
            document.parent.mkdir()
            document.write_text("# Requirements\n\n## Version History\n\n- V1\n", encoding="utf-8")
            self.assertTrue(audit_docs.has_version_record(project, "docs/requirements.md"))

    def test_version_record_must_be_near_document_start(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            document = project / "docs" / "requirements.md"
            document.parent.mkdir()
            document.write_text("# Requirements\n" + ("content\n" * 1_200) + "## Changelog\n", encoding="utf-8")
            self.assertFalse(audit_docs.has_version_record(project, "docs/requirements.md"))

    def test_changelog_mention_is_not_a_version_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            document = project / "docs" / "requirements.md"
            document.parent.mkdir()
            document.write_text(
                "# Requirements\n\nFor release details, see the changelog in another repository.\n",
                encoding="utf-8",
            )
            self.assertFalse(audit_docs.has_version_record(project, "docs/requirements.md"))

    def test_warns_when_data_changes_without_dictionary_or_tests(self) -> None:
        findings = audit_docs.build_findings(
            {"data_structure": ["db/migrations/001_add_status.sql"]}
        )
        codes = {finding.code for finding in findings}
        self.assertIn("DATA_WITHOUT_DICTIONARY", codes)
        self.assertIn("BEHAVIOR_WITHOUT_TEST_CHANGE", codes)

    def test_audit_reports_changed_interface_and_missing_docs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
            page = project / "src" / "pages" / "home.tsx"
            page.parent.mkdir(parents=True)
            page.write_text("export default function Home() { return null }\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", "."], check=True)
            subprocess.run(["git", "-C", str(project), "commit", "-qm", "baseline"], check=True)
            page.write_text("export default function Home() { return <main /> }\n", encoding="utf-8")

            report = audit_docs.audit(project, None)
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("INTERFACE_WITHOUT_USER_DOCS", codes)
            self.assertIn("BEHAVIOR_WITHOUT_TEST_CHANGE", codes)

    def test_tracks_paths_with_spaces_and_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(project), "config", "user.name", "Test"], check=True)
            tracked = project / "docs" / "user guide.md"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("# Guide\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(project), "add", "."], check=True)
            subprocess.run(["git", "-C", str(project), "commit", "-qm", "baseline"], check=True)
            tracked.write_text("# Updated guide\n", encoding="utf-8")
            untracked = project / "src" / "new page.tsx"
            untracked.parent.mkdir(parents=True)
            untracked.write_text("export default function Page() { return null }\n", encoding="utf-8")
            leading_space = project / " leading page.tsx"
            leading_space.write_text("export default function Page() { return null }\n", encoding="utf-8")

            changed = audit_docs.tracked_changes(project, None)
            self.assertEqual(
                {" leading page.tsx", "docs/user guide.md", "src/new page.tsx"},
                set(changed),
            )

    def test_audit_works_outside_a_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            document = project / "docs" / "product-requirements.md"
            document.parent.mkdir(parents=True)
            document.write_text("# Requirements\n\n## Version History\n", encoding="utf-8")

            report = audit_docs.audit(project, None)
            self.assertEqual([], report["changed_files"])
            self.assertIn("product_docs", report["inventory"])
            self.assertIsNone(report["git"]["head"])

    def test_audit_reports_directory_scan_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)

            def failing_walk(*args, **kwargs):
                kwargs["onerror"](PermissionError(13, "Permission denied", str(project / "restricted")))
                return iter(())

            with mock.patch.object(audit_docs.os, "walk", side_effect=failing_walk):
                report = audit_docs.audit(project, None)

            codes = {item["code"] for item in report["findings"]}
            self.assertIn("SCAN_INCOMPLETE", codes)
            self.assertEqual(1, len(report["scan_errors"]))

    def test_custom_patterns_support_nonstandard_project_topology(self) -> None:
        config = {
            "use_default_heuristics": False,
            "category_patterns": {
                "interface": ["modules/storefront/templates/**"],
                "api": ["modules/gateway/contracts/**"],
            },
        }

        template_categories = audit_docs.classify(
            "modules/storefront/templates/checkout.html",
            config,
        )
        contract_categories = audit_docs.classify(
            "modules/gateway/contracts/orders.proto",
            config,
        )

        self.assertIn("interface", template_categories)
        self.assertIn("api", contract_categories)
        self.assertNotIn("behavior", template_categories)

    def test_audit_can_ignore_project_specific_generated_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            source = project / "capabilities" / "checkout" / "workflow.custom"
            source.parent.mkdir(parents=True)
            source.write_text("workflow", encoding="utf-8")
            generated = project / "generated-client" / "screen.tsx"
            generated.parent.mkdir(parents=True)
            generated.write_text("generated", encoding="utf-8")
            config = {
                "use_default_heuristics": False,
                "ignore_patterns": ["generated-client/**"],
                "category_patterns": {
                    "behavior": ["capabilities/**/workflow.custom"],
                },
            }

            report = audit_docs.audit(project, None, config)

            self.assertEqual(["capabilities/checkout/workflow.custom"], report["inventory"]["behavior"])
            self.assertNotIn("generated-client/screen.tsx", report["inventory"].get("interface", []))

    def test_project_can_disable_default_directory_ignores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            first_party_source = project / "vendor" / "portal" / "screen.tsx"
            first_party_source.parent.mkdir(parents=True)
            first_party_source.write_text("export default function Screen() { return null }\n", encoding="utf-8")

            report = audit_docs.audit(
                project,
                None,
                {"use_default_ignores": False},
            )

            self.assertIn("vendor/portal/screen.tsx", report["inventory"]["interface"])

    def test_rejects_unknown_configuration_categories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "audit.json"
            config_path.write_text(
                '{"category_patterns": {"imaginary": ["modules/**"]}}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Unknown category"):
                audit_docs.load_config(config_path)

    def test_cli_applies_custom_topology_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "project"
            source = project / "modules" / "gateway" / "contracts" / "orders.proto"
            source.parent.mkdir(parents=True)
            source.write_text("service Orders {}\n", encoding="utf-8")
            config_path = workspace / "topology.json"
            config_path.write_text(
                '{"use_default_heuristics": false, '
                '"category_patterns": {"api": ["modules/gateway/contracts/**"]}}',
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(project),
                    "--config",
                    str(config_path),
                    "--format",
                    "json",
                ],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            report = json.loads(completed.stdout)

            self.assertFalse(report["configuration"]["use_default_heuristics"])
            self.assertEqual(["modules/gateway/contracts/orders.proto"], report["inventory"]["api"])


if __name__ == "__main__":
    unittest.main()
