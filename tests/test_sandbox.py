"""Tests for Blastbox policy gate and sandbox runner. Run with:
python3 -m unittest discover -s tests -v
"""

import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import llm, policy, runner  # noqa: E402

CSV = "item,price,qty\ncoffee,350,3\ncoffee,350,2\nbeans,1200,1\n"
GOOD = (
    "import csv\n"
    "from collections import defaultdict\n"
    "totals = defaultdict(int)\n"
    "with open('input.csv') as fh:\n"
    "    for row in csv.DictReader(fh):\n"
    "        totals[row['item']] += int(row['price']) * int(row['qty'])\n"
    "for item in sorted(totals):\n"
    "    print(f'{item}: {totals[item]}')\n"
)


class PolicyTests(unittest.TestCase):
    def test_good_code_passes(self):
        self.assertEqual(policy.check(GOOD), (True, ""))

    def test_blocked_import_socket(self):
        allowed, reason = policy.check("import socket\nprint(1)\n")
        self.assertFalse(allowed)
        self.assertIn("socket", reason)

    def test_blocked_import_os(self):
        self.assertFalse(policy.check("import os\nprint(os.getcwd())\n")[0])

    def test_blocked_open_other_file(self):
        self.assertFalse(policy.check("open('/etc/passwd').read()\n")[0])

    def test_blocked_open_write_mode(self):
        self.assertFalse(policy.check("open('input.csv', 'w').write('x')\n")[0])

    def test_blocked_eval_and_dunder(self):
        self.assertFalse(policy.check("eval('1+1')\n")[0])
        self.assertFalse(policy.check("x = ().__class__\n")[0])

    def test_unlisted_import_blocked(self):
        self.assertFalse(policy.check("import pandas\nprint(1)\n")[0])


class RunnerTests(unittest.TestCase):
    def test_happy_path_real_output(self):
        result = runner.run(GOOD, CSV)
        self.assertEqual(result["status"], "ok")
        self.assertIn("coffee: 1750", result["stdout"])
        self.assertIn("beans: 1200", result["stdout"])
        self.assertEqual(result["code_sha256"], hashlib.sha256(GOOD.encode()).hexdigest())
        self.assertEqual(result["input_sha256"], hashlib.sha256(CSV.encode()).hexdigest())

    def test_hostile_code_blocked_before_execution(self):
        result = runner.run("import socket\nprint('pwned')\n", CSV)
        self.assertEqual(result["status"], "blocked")
        self.assertNotIn("pwned", result["stdout"])

    def test_runtime_error_reported_not_hidden(self):
        result = runner.run("import csv\nprint(1/0)\n", CSV)
        self.assertEqual(result["status"], "error")
        self.assertIn("ZeroDivisionError", result["stderr"])

    def test_timeout(self):
        result = runner.run("import csv\nwhile True:\n    pass\n", CSV, timeout_s=2)
        self.assertEqual(result["status"], "timeout")

    def test_docker_command_is_locked_down(self):
        cmd = runner.docker_command("blastbox-sandbox:latest", "/in/input.csv", "/work")
        for flag in ("--network", "none", "--cap-drop", "ALL", "--read-only"):
            self.assertIn(flag, cmd)
        self.assertIn("/in/input.csv:/work/input.csv:ro", cmd)
        self.assertNotIn("/etc", " ".join(cmd))

    def test_docker_backend_missing_binary_reports_error(self):
        from unittest import mock
        # Mock the missing binary: the host running the tests may or may
        # not have a docker CLI installed (this sandbox gained one), so
        # the no-binary path is controlled here, not assumed.
        with mock.patch.object(runner.shutil, "which", return_value=None):
            result = runner.run(GOOD, CSV, backend="docker")
        self.assertEqual(result["status"], "error")
        self.assertIn("docker", result["reason"])

    def test_docker_backend_wiring_with_mock(self):
        import subprocess as sp
        from unittest import mock
        fake = sp.CompletedProcess(args=[], returncode=0, stdout="coffee: 1750\n", stderr="")
        with mock.patch.object(runner.shutil, "which", return_value="/usr/bin/docker"):
            with mock.patch.object(runner.subprocess, "run", return_value=fake) as run_mock:
                result = runner.run(GOOD, CSV, backend="docker")
        self.assertEqual(result["status"], "ok")
        self.assertIn("coffee: 1750", result["stdout"])
        cmd = run_mock.call_args[0][0]
        self.assertIn("--network", cmd)
        self.assertIn("none", cmd)


class LlmTests(unittest.TestCase):
    def test_prompt_names_input_and_question(self):
        prompt = llm.build_prompt("Total per item?", CSV)
        self.assertIn("input.csv", prompt)
        self.assertIn("Total per item?", prompt)
        self.assertIn("item,price,qty", prompt)

    def test_parse_completion(self):
        payload = {"choices": [{"message": {"content": "print(1)\n"}}]}
        self.assertEqual(llm.parse_completion(payload), "print(1)")


if __name__ == "__main__":
    unittest.main()
