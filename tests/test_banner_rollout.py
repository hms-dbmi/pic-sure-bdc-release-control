#!/usr/bin/env python3
import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JENKINS_ROOT = Path(os.environ["JENKINS_ROOT"])
INFRASTRUCTURE_ROOT = Path(os.environ["BDC_INFRASTRUCTURE_ROOT"])
VALIDATOR = JENKINS_ROOT / "jenkins-docker/scripts/validate-banner-rollout.py"


class BdcReleaseTupleTest(unittest.TestCase):
    def validate(self, **overrides):
        selections = {
            "run_database_migrations": "true",
            "include_api": "true",
            "include_psama": "true",
            "include_frontend": "true",
            **overrides,
        }
        return subprocess.run(
            [
                "python3",
                str(VALIDATOR),
                "--deployment",
                "BDC",
                "--build-spec",
                str(ROOT / "build-spec.json"),
                "--jenkins-source-commit",
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=JENKINS_ROOT,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                "--release-control-commit",
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                "--controller-deployment",
                "bdc",
                "--artifact-bucket",
                "synthetic-bucket",
                "--controller-artifact-bucket",
                "synthetic-bucket",
                "--run-database-migrations",
                selections["run_database_migrations"],
                "--include-api",
                selections["include_api"],
                "--include-psama",
                selections["include_psama"],
                "--include-frontend",
                selections["include_frontend"],
            ],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )

    def test_exact_bdc_tuple_passes(self):
        result = self.validate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            json.loads((ROOT / "build-spec.json").read_text(encoding="utf-8"))["banner_rollout"]["tupleSha256"],
            result.stdout.strip(),
        )

    def test_each_required_selection_fails_closed(self):
        for selection in (
            "run_database_migrations",
            "include_api",
            "include_psama",
            "include_frontend",
        ):
            with self.subTest(selection=selection):
                result = self.validate(**{selection: "false"})
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)

    def test_no_moving_component_refs_remain(self):
        spec = json.loads((ROOT / "build-spec.json").read_text(encoding="utf-8"))
        self.assertRegex(spec["infrastructure_git_hash"], r"^[0-9a-f]{40}$")
        for application in spec["application"]:
            self.assertRegex(application["git_hash"], r"^[0-9a-f]{40}$")
        self.assertEqual(
            "JENKINS_CHECKED_OUT_GIT_COMMIT",
            spec["banner_rollout"]["releaseControl"]["resolvedCommitSource"],
        )

    def test_tuple_pins_the_logging_capable_executable_infrastructure(self):
        spec = json.loads((ROOT / "build-spec.json").read_text(encoding="utf-8"))
        logging_commit = "d10cecdeb89f14f8c672a81347ffa70d9b001ab3"
        self.assertEqual(logging_commit, spec["infrastructure_git_hash"])
        self.assertEqual(
            logging_commit,
            spec["banner_rollout"]["components"]["infrastructure"]["commit"],
        )
        template = subprocess.run(
            [
                "git",
                "show",
                f"{spec['infrastructure_git_hash']}:app-infrastructure/template-renderer/templates/operations.env.tftpl",
            ],
            cwd=INFRASTRUCTURE_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, template.returncode, template.stderr)
        self.assertIn("LOGGING_SERVICE_URL=http://pic-sure-logging", template.stdout)
        self.assertIn("LOGGING_API_KEY=${logging_api_key}", template.stdout)
        jenkins_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=JENKINS_ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(jenkins_commit, spec["banner_rollout"]["components"]["jenkins"]["commit"])

    def test_contract_matches_bundled_authoritative_bytes(self):
        backend_root = Path(os.environ["BACKEND_ROOT"])
        authoritative = backend_root / ".github/banner-rollout-contract.json"
        bundled = JENKINS_ROOT / "jenkins-docker/scripts/banner-rollout-contract.json"
        self.assertEqual(authoritative.read_bytes(), bundled.read_bytes())
        spec = json.loads((ROOT / "build-spec.json").read_text(encoding="utf-8"))
        self.assertEqual(
            json.loads(authoritative.read_text(encoding="utf-8")),
            spec["banner_rollout"]["contract"],
        )


if __name__ == "__main__":
    unittest.main()
