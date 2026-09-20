from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "discover_project.py"
SPEC = importlib.util.spec_from_file_location("discover_project", SCRIPT)
assert SPEC and SPEC.loader
discover_project = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = discover_project
SPEC.loader.exec_module(discover_project)


class DiscoverProjectTest(unittest.TestCase):
    def test_assigns_evidence_to_a_top_level_component(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            manifest = project / "service" / "package.json"
            source = project / "service" / "src" / "index.ts"
            manifest.parent.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            manifest.write_text('{"name": "service"}', encoding="utf-8")
            source.write_text("export const ready = true\n", encoding="utf-8")

            report = discover_project.discover(project, None)
            component = next(item for item in report["components"] if item["root"] == "service")

            self.assertGreater(component["evidence_counts"].get("source", 0), 0)

    def test_git_root_discovery_respects_custom_ignore_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            nested_git = project / "vendor" / "partner" / ".git"
            nested_git.mkdir(parents=True)

            report = discover_project.discover(
                project,
                {"use_default_ignores": False},
            )

            self.assertIn("vendor/partner", report["git_roots"])

    def test_discovers_components_in_a_nonstandard_monorepo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            files = {
                "package.json": '{"private": true}',
                "pnpm-workspace.yaml": "packages:\n  - modules/*\n",
                "modules/portal/package.json": '{"name": "portal"}',
                "modules/portal/ui/account.tsx": "export default function Account() { return null }\n",
                "modules/gateway/pyproject.toml": "[project]\nname = 'gateway'\nversion = '0.1.0'\n",
                "modules/gateway/contracts/orders.proto": "service Orders {}\n",
                "modules/gateway/verification/orders.check": "scenario\n",
                "knowledge/product/requirements.md": "# Requirements\n",
            }
            for relative, content in files.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            config = {
                "use_default_heuristics": False,
                "category_patterns": {
                    "interface": ["modules/portal/ui/**"],
                    "api": ["modules/gateway/contracts/**"],
                    "tests": ["modules/gateway/verification/**"],
                    "product_docs": ["knowledge/product/**"],
                },
            }
            report = discover_project.discover(project, config)

            roots = {component["root"] for component in report["components"]}
            self.assertIn(".", roots)
            self.assertIn("modules/portal", roots)
            self.assertIn("modules/gateway", roots)
            self.assertIn("interface", report["evidence_inventory"])
            self.assertIn("api", report["evidence_inventory"])
            self.assertIn("tests", report["evidence_inventory"])
            self.assertEqual([], report["scan_errors"])

    def test_discovers_java_service_without_assuming_frontend_backend_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            files = {
                "services/catalog/pom.xml": "<project />\n",
                "services/catalog/src/main/java/example/App.java": "class App {}\n",
                "services/catalog/src/test/java/example/AppTest.java": "class AppTest {}\n",
                "services/catalog/src/main/resources/schema.sql": "create table products(id bigint);\n",
            }
            for relative, content in files.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            report = discover_project.discover(project, None)
            component = next(item for item in report["components"] if item["root"] == "services/catalog")

            self.assertIn("maven", component["runtime_hints"])
            self.assertGreater(component["evidence_counts"].get("source", 0), 0)
            self.assertGreater(component["evidence_counts"].get("tests", 0), 0)
            self.assertGreater(component["evidence_counts"].get("data_structure", 0), 0)


if __name__ == "__main__":
    unittest.main()
