#!/usr/bin/env python3
import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JENKINS_ROOT = Path(
    os.environ.get("JENKINS_ROOT", ROOT.parent / "avillachlab-jenkins")
)
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
            "e62b9d8a5be23d050939bd744d522b5e20d1ccf6bdb0a9e248a6e121dbff5449",
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


if __name__ == "__main__":
    unittest.main()
