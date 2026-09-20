from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
        self.assertNotIn("interface", audit_docs.classify("app/Services/OrderService.php"))

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

            changed = audit_docs.tracked_changes(project, None)
            self.assertEqual(["docs/user guide.md", "src/new page.tsx"], changed)

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


if __name__ == "__main__":
    unittest.main()
