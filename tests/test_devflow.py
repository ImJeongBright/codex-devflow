import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from codex_devflow import repository, schema
from codex_devflow.backend import CodexCliBackend
from codex_devflow.cli import configuration
from codex_devflow.process import ProcessInterrupted, ProcessResult, run_process
from codex_devflow.workflow import Workflow, repository_lock, write_json


SOURCE = Path(__file__).resolve().parents[1]


def analysis():
    return {"schema_version": 1, "scope": "local", "affected_areas": ["app.py"],
            **{key: False for key in schema.RISK_FLAGS}, "regression_risk": "low",
            "suggested_reviews": [], "rationale": "Small local change"}


class PolicyTests(unittest.TestCase):
    def test_local_low_risk_is_simple(self):
        self.assertEqual(schema.select_workflow(analysis()), "simple")

    def test_each_risk_routes_to_planned(self):
        for flag in schema.RISK_FLAGS:
            with self.subTest(flag=flag):
                self.assertEqual(schema.select_workflow({**analysis(), flag: True}), "planned")
        for key, value in (("scope", "multi-module"), ("scope", "unknown"),
                           ("regression_risk", "medium"), ("regression_risk", "unknown")):
            self.assertEqual(schema.select_workflow({**analysis(), key: value}), "planned")

    def test_bad_schema_rejected(self):
        for value in ({}, {**analysis(), "schema_version": 2}, {**analysis(), "schema_version": True},
                      {**analysis(), "database_change": "false"}, {**analysis(), "extra": 1}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                schema.select_workflow(value)


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="devflow test ")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        global_env = patch.dict(os.environ, XDG_CONFIG_HOME=str(self.repo / "user-config"))
        global_env.start()
        self.addCleanup(global_env.stop)
        repository.git(self.repo, "init", "-q")
        (self.repo / "app.py").write_text("value = 1\n")
        repository.git(self.repo, "add", "app.py")
        repository.git(self.repo, "-c", "user.name=DevFlow Test", "-c", "user.email=test@example.invalid",
                       "commit", "-qm", "baseline")
        # Outside target, so fixture executable never enters the project diff.
        self.executable = self.repo / ".codex-devflow" / "fake-codex"
        self.executable.parent.mkdir()
        self.executable.write_text(f"#!{sys.executable}\n" + (SOURCE / "tests/fake_codex.py").read_text())
        self.executable.chmod(0o755)

    def workflow(self, mode="planned", commands=None, repairs=1, timeout=5):
        if commands is None:
            commands = [f"{sys.executable} -B -c 'from app import value; assert value == 2'"]
        with patch.dict(os.environ, DEVFLOW_TEST_MODE=mode):
            return Workflow(CodexCliBackend(str(self.executable)), self.repo, "Update app value",
                            commands, timeout, repairs).run()


class WorkflowTests(RepositoryCase):
    def test_planned_end_to_end_artifacts_and_context(self):
        record, directory = self.workflow()
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual([s["role"] for s in record["steps"]], ["scout", "planner", "implementer", "reviewer"])
        self.assertEqual(record["changed_files"], ["app.py", "new file.txt"])
        self.assertEqual(record["metrics"]["codex_run_count"], 4)
        self.assertEqual(len(record["metrics"]["usage"]), 4)
        for filename in ("task.json", "analysis.json", "plan.md", "plan.json", "validation.json",
                         "review.json", "repair.json", "run.json", "exec.md", "changes.diff"):
            self.assertTrue((directory / filename).is_file(), filename)
        for step in record["steps"]:
            argv = step["process"]["command"]
            self.assertEqual(argv[argv.index("--sandbox") + 1],
                             "workspace-write" if step["role"] == "implementer" else "read-only")
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        review_prompt = Path(record["steps"][-1]["directory"], "prompt.txt").read_text()
        for text in ("Update app value", "test plan", "new file.txt", '"status": "passed"'):
            self.assertIn(text, review_prompt)

    def test_simple_skips_plan_review(self):
        record, _ = self.workflow("simple")
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual([s["role"] for s in record["steps"]], ["scout", "implementer"])
        self.assertEqual(record["reviews"], [])

    def test_validation_repair_then_revalidate_and_rereview(self):
        record, directory = self.workflow("repair")
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual([v["status"] for v in record["validation"]], ["failed", "passed"])
        self.assertEqual(len(record["repairs"]), 1)
        self.assertEqual(len(record["reviews"]), 2)
        self.assertFalse(record["metrics"]["first_pass_validation"])
        self.assertEqual(record["repairs"][0]["status"], "completed")
        self.assertEqual(record["repairs"][0]["result"], record["changes"][-1])
        self.assert_repair_artifacts(record, directory)

    def test_review_failure_repairs(self):
        record, _ = self.workflow("review-repair")
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual([r["passed"] for r in record["reviews"]], [False, True])

    def test_review_failure_stops_at_limit(self):
        record, directory = self.workflow("review-fail", repairs=1)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(record["repairs"]), 1)
        self.assertEqual(len(record["validation"]), 2)
        self.assertEqual(record["repairs"][0]["status"], "completed")
        self.assertEqual(record["repairs"][0]["result"], record["changes"][-1])
        self.assert_repair_artifacts(record, directory)

    def assert_repair_artifacts(self, record, directory):
        self.assertEqual(json.loads((directory / "repair.json").read_text()), record["repairs"])
        self.assertEqual(json.loads((directory / "run.json").read_text()), record)
        execution = (directory / "exec.md").read_text()
        repairs = json.loads(execution.split("## Repair history\n\n```json\n", 1)[1]
                             .split("\n```", 1)[0])
        self.assertEqual(repairs, record["repairs"])
        self.assertIn(f"Status: **{record['status']}**", execution)

    def test_repair_worker_error_finalizes_repair(self):
        self.check_repair_worker_failure(OSError("repair execution failed"), "error",
                                         "OSError: repair execution failed")

    def test_repair_worker_interruption_finalizes_repair(self):
        self.check_repair_worker_failure(KeyboardInterrupt(), "interrupted",
                                         "Run interrupted by signal/user")

    def check_repair_worker_failure(self, failure, status, error):
        execute = CodexCliBackend.execute
        roles = []

        def execute_until_repair(backend, **kwargs):
            role = kwargs["prompt"].split("\nROLE: ", 1)[1].split("\n", 1)[0]
            roles.append(role)
            if role == "repairer":
                raise failure
            return execute(backend, **kwargs)

        with patch.object(CodexCliBackend, "execute", new=execute_until_repair):
            record, directory = self.workflow("repair", repairs=1)
        self.assertEqual(record["status"], status)
        self.assertEqual(record["error"], error)
        self.assertEqual(record["stage"], "repairer")
        self.assertEqual(roles, ["scout", "planner", "implementer", "reviewer", "repairer"])
        self.assertEqual([step["role"] for step in record["steps"]], roles)
        self.assertEqual(record["steps"][-1]["status"], status)
        self.assertEqual(record["metrics"]["codex_run_count"], 5)
        self.assertEqual(record["metrics"]["repair_attempts"], 1)
        self.assertEqual(record["settings"]["max_repairs"], 1)
        self.assertEqual(record["metrics"]["validation_attempts"], 1)
        self.assertEqual([v["status"] for v in record["validation"]], ["failed"])
        self.assertEqual(len(record["reviews"]), 1)
        self.assertEqual(len(record["changes"]), 1)
        repair, = record["repairs"]
        self.assertEqual(repair["attempt"], 1)
        self.assertEqual(repair["status"], status)
        self.assertEqual(repair["error"], error)
        self.assertEqual(repair["validation"], record["validation"][0])
        self.assertEqual(repair["review"], record["reviews"][0])
        self.assertNotIn("result", repair)
        self.assert_repair_artifacts(record, directory)

    def test_zero_repairs_and_all_validation_commands_recorded(self):
        record, _ = self.workflow(commands=["exit 9", "printf evidence"], repairs=0)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(len(record["repairs"]), 0)
        self.assertEqual([c["exit_code"] for c in record["validation"][0]["commands"]], [9, 0])

    def test_missing_validation_is_unverified_even_with_passing_review(self):
        record, _ = self.workflow(commands=[])
        self.assertEqual(record["status"], "unverified")
        self.assertEqual(record["validation"][0]["status"], "unavailable")
        self.assertIsNone(record["metrics"]["first_pass_validation"])

    def test_codex_failures_preserve_final_artifacts(self):
        for mode in ("invalid", "missing", "exit", "timeout"):
            with self.subTest(mode=mode):
                record, directory = self.workflow(mode, timeout=0.2)
                self.assertEqual(record["status"], "error")
                self.assertIsNotNone(record["error"])
                self.assertTrue((directory / "exec.md").exists())
                self.assertEqual(len(record["repairs"]), 0)

    def test_validation_timeout_is_failure(self):
        record, _ = self.workflow(commands=["sleep 30"], timeout=0.2, repairs=0)
        self.assertEqual(record["status"], "failed")
        self.assertTrue(record["validation"][0]["commands"][0]["timed_out"])

    def test_preexisting_changes_are_preserved_and_not_counted(self):
        (self.repo / "my notes.txt").write_text("keep me")
        record, directory = self.workflow()
        self.assertNotIn("my notes.txt", record["changed_files"])
        self.assertIn("my notes.txt", (directory / "baseline.diff").read_text())
        self.assertEqual((self.repo / "my notes.txt").read_text(), "keep me")

    def test_lock_prevents_simultaneous_run(self):
        with repository_lock(self.repo), self.assertRaisesRegex(ValueError, "Another DevFlow"):
            self.workflow()

    def test_interruption_finalizes_run(self):
        with patch.object(CodexCliBackend, "execute", side_effect=KeyboardInterrupt):
            record, directory = self.workflow()
        self.assertEqual(record["status"], "interrupted")
        self.assertEqual(record["steps"][0]["status"], "interrupted")
        self.assertTrue((directory / "exec.md").exists())

    def test_worker_saves_process_evidence_before_reraising_interruption(self):
        backend = CodexCliBackend(str(self.executable))
        workflow = Workflow(backend, self.repo, "Update app", ["exit 0"])
        directory = workflow.run_dir / "steps" / "01-implementer"
        directory.mkdir(parents=True)
        process = ProcessResult([str(self.executable), "exec"], -signal.SIGKILL, 1.25, False,
                                str(directory / "stdout.log"), str(directory / "stderr.log"))
        interruption = ProcessInterrupted(process)
        with patch.object(backend, "execute", side_effect=interruption):
            with self.assertRaises(ProcessInterrupted) as raised:
                workflow.worker("implementer", "Implement the task.", schema.CHANGE)
        self.assertIs(raised.exception, interruption)
        step, = workflow.record["steps"]
        self.assertEqual(step["status"], "interrupted")
        self.assertEqual(step["process"], process.to_dict())
        self.assertEqual(step["usage"], [])
        self.assertEqual(step["error"], str(interruption))
        self.assertEqual(json.loads((directory / "result.json").read_text()), step)
        self.assertEqual(json.loads((workflow.run_dir / "run.json").read_text()), workflow.record)

    def test_interruption_between_validation_commands(self):
        def interrupt_after_command(path, value):
            write_json(path, value)
            if (path.name == "validation.json" and value[0]["status"] == "running"
                    and len(value[0]["commands"]) == 1):
                raise KeyboardInterrupt

        with patch("codex_devflow.workflow.write_json", side_effect=interrupt_after_command):
            record, directory = self.workflow(commands=["printf completed", "touch not-run"])
        self.assertEqual(record["status"], "interrupted")
        attempt, = record["validation"]
        self.assertEqual(attempt["status"], "interrupted")
        command, = attempt["commands"]
        self.assertEqual(command["exit_code"], 0)
        self.assertEqual(Path(command["stdout_path"]).read_text(), "completed")
        self.assertFalse((self.repo / "not-run").exists())
        self.assertEqual(json.loads((directory / "validation.json").read_text()), record["validation"])
        self.assertEqual(json.loads((directory / "run.json").read_text()), record)
        self.assertEqual(record["reviews"], [])
        self.assertEqual(record["repairs"], [])

    def test_missing_executable_is_recorded(self):
        record, _ = Workflow(CodexCliBackend("/does-not-exist/codex"), self.repo,
                             "task", [], 1, 0).run()
        self.assertEqual(record["status"], "error")
        self.assertIsNone(record["steps"][0]["process"]["exit_code"])

    def test_cli_exit_codes_and_config(self):
        (self.repo / ".codex-devflow.json").write_text(json.dumps({"validation_commands": ["exit 0"]}))
        args = [sys.executable, "-m", "codex_devflow", "feature", "Update app", "--repo", str(self.repo),
                "--codex", str(self.executable)]
        result = subprocess.run(args, cwd=SOURCE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "succeeded")
        (self.repo / ".codex-devflow.json").unlink()
        result = subprocess.run(args, cwd=SOURCE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "unverified")

    def test_cli_failure_exit_codes(self):
        args = [sys.executable, "-m", "codex_devflow", "feature", "Update app", "--repo", str(self.repo),
                "--max-repairs", "0", "--timeout", "1"]
        for executable, command, code, status in (
            (str(self.executable), "exit 9", 1, "failed"),
            (str(self.executable), "sleep 30", 1, "failed"),
            ("/does-not-exist/codex", "exit 0", 2, "error"),
        ):
            with self.subTest(command=command, status=status):
                result = subprocess.run(args + ["--codex", executable, "--validate", command],
                                        cwd=SOURCE, capture_output=True, text=True, timeout=15,
                                        env={**os.environ, "DEVFLOW_TEST_MODE": "planned"})
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], status)

    def test_config_rejects_bad_values_and_cli_overrides(self):
        args = argparse.Namespace(validate=None, timeout=None, max_repairs=None)
        path = self.repo / ".codex-devflow.json"
        for value in ({"max_repairs": -1}, {"max_repairs": True}, {"timeout_seconds": 0},
                      {"timeout_seconds": float("nan")}, {"timeout_seconds": True},
                      {"validation_commands": "exit 0"}, {"validation_commands": [""]}, {"extra": 1}):
            with self.subTest(value=value):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    configuration(self.repo, args)
        path.write_text('{"validation_commands": ["exit 1"], "max_repairs": 2}')
        args.validate, args.max_repairs = ["exit 0"], 0
        self.assertEqual(configuration(self.repo, args)["validation_commands"], ["exit 0"])
        self.assertEqual(configuration(self.repo, args)["max_repairs"], 0)


class ValidationSignalTests(RepositoryCase):
    def test_sigint_preserves_validation_evidence_and_kills_children(self):
        self.check_interruption(signal.SIGINT)

    def test_sigterm_preserves_validation_evidence_and_kills_children(self):
        self.check_interruption(signal.SIGTERM)

    def check_interruption(self, signum):
        script = self.repo / "wait_validation.py"
        script.write_text("""import os
from pathlib import Path
import subprocess
import sys
import time

role = sys.argv[1]
Path(role + '.pid').write_text(str(os.getpid()))
if role == 'parent':
    subprocess.Popen([sys.executable, __file__, 'child'])
    deadline = time.monotonic() + 10
    while not Path('child.ready').exists():
        if time.monotonic() >= deadline:
            sys.exit('Child did not become ready')
        time.sleep(0.01)
with Path(role + '.heartbeat').open('ab', buffering=0) as heartbeat:
    print(role + ' stdout before interruption', flush=True)
    print(role + ' stderr before interruption', file=sys.stderr, flush=True)
    Path(role + '.ready').touch()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        heartbeat.write(b'.')
        time.sleep(0.05)
""")
        commands = ["printf completed", "exec " + shlex.join([sys.executable, str(script), "parent"]),
                    "touch not-run"]
        args = [sys.executable, "-m", "codex_devflow", "feature", "Update app", "--repo", str(self.repo),
                "--codex", str(self.executable), "--timeout", "30", "--max-repairs", "1"]
        for command in commands:
            args.extend(["--validate", command])
        cli = subprocess.Popen(args, cwd=SOURCE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True,
                               env={**os.environ, "DEVFLOW_TEST_MODE": "planned"})
        try:
            deadline = time.monotonic() + 10
            while not (self.repo / "parent.ready").exists():
                if cli.poll() is not None:
                    stdout, stderr = cli.communicate(timeout=2)
                    self.fail(f"CLI exited before validation was ready: {cli.returncode}\n{stdout}\n{stderr}")
                if time.monotonic() >= deadline:
                    self.fail("Validation process and child did not become ready")
                time.sleep(0.01)
            pids = [int((self.repo / f"{role}.pid").read_text()) for role in ("parent", "child")]
            for pid in pids:
                self.assertEqual(os.getpgid(pid), pids[0])
            self.assertNotEqual(os.getpgid(cli.pid), pids[0])
            heartbeats = [self.repo / f"{role}.heartbeat" for role in ("parent", "child")]
            initial_sizes = [path.stat().st_size for path in heartbeats]
            deadline = time.monotonic() + 10
            while not all(path.stat().st_size > size for path, size in zip(heartbeats, initial_sizes)):
                self.assertIsNone(cli.poll(), "CLI exited before both heartbeats advanced")
                if time.monotonic() >= deadline:
                    self.fail("Validation parent and child heartbeats did not advance")
                time.sleep(0.01)
            # Signal only the CLI; the runner must terminate the validation group.
            cli.send_signal(signum)
            stdout, stderr = cli.communicate(timeout=10)
            self.assertEqual(cli.returncode, 130, stderr)
            # Observe for many heartbeat intervals without relying on zombie reaping or ps.
            time.sleep(0.1)
            stopped_sizes = [path.stat().st_size for path in heartbeats]
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                time.sleep(0.05)
                self.assertEqual([path.stat().st_size for path in heartbeats], stopped_sizes,
                                 "Validation parent or child kept running after interruption")

            summary = json.loads(stdout)
            self.assertEqual(summary["status"], "interrupted")
            directory = Path(summary["run_dir"])
            record = json.loads((directory / "run.json").read_text())
            validation = json.loads((directory / "validation.json").read_text())
            execution = (directory / "exec.md").read_text()
            exec_validation = json.loads(execution.split("## Validation\n\n```json\n", 1)[1]
                                         .split("\n```", 1)[0])
            self.assertEqual(validation, record["validation"])
            self.assertEqual(validation, exec_validation)
            self.assertEqual(record["status"], "interrupted")
            self.assertEqual(record["stage"], "validate")
            self.assertTrue(record["finished_at"])
            self.assertIn("Status: **interrupted**", execution)
            attempt, = validation
            self.assertEqual(attempt["status"], "interrupted")
            completed, interrupted = attempt["commands"]
            self.assertEqual(completed["command"], commands[0])
            self.assertEqual(completed["exit_code"], 0)
            self.assertEqual(Path(completed["stdout_path"]).read_text(), "completed")
            self.assertEqual(interrupted["command"], commands[1])
            self.assertEqual(interrupted["status"], "interrupted")
            self.assertIsInstance(interrupted["exit_code"], int)
            self.assertNotEqual(interrupted["exit_code"], 0)
            self.assertFalse(interrupted["timed_out"])
            self.assertIsNone(interrupted["error"])
            self.assertGreater(interrupted["elapsed_seconds"], 0)
            self.assertLessEqual(interrupted["elapsed_seconds"], record["elapsed_seconds"])
            for stream in ("stdout", "stderr"):
                path = Path(interrupted[f"{stream}_path"])
                self.assertEqual(path, directory / "validation" / "1" / "2" / f"{stream}.log")
                self.assertEqual(path.read_text().splitlines(),
                                 [f"{role} {stream} before interruption" for role in ("child", "parent")])
            self.assertFalse((self.repo / "not-run").exists())
            self.assertFalse((self.executable.parent / "fixture-review-count").exists())
            self.assertEqual([step["role"] for step in record["steps"]], ["scout", "planner", "implementer"])
            self.assertEqual(sorted(path.name for path in (directory / "steps").iterdir()),
                             ["01-scout", "02-planner", "03-implementer"])
            self.assertEqual(record["reviews"], [])
            self.assertEqual(record["repairs"], [])
            self.assertEqual(json.loads((directory / "review.json").read_text()), [])
            self.assertEqual(json.loads((directory / "repair.json").read_text()), [])
        finally:
            if cli.poll() is None:
                cli.kill()
            # The validation process leads its own group, separate from the CLI.
            pid_path = self.repo / "parent.pid"
            if pid_path.exists() and pid_path.read_text().strip():
                try:
                    os.killpg(int(pid_path.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            cli.communicate(timeout=5)


class ProcessTests(unittest.TestCase):
    def test_timeout_kills_child_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "child-survived"
            child = "import time,pathlib; time.sleep(1); pathlib.Path('child-survived').touch()"
            parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(30)"
            result = run_process([sys.executable, "-c", parent], root, 0.2, root / "logs")
            self.assertTrue(result.timed_out)
            time.sleep(1)
            self.assertFalse(sentinel.exists())

    def test_stdout_stderr_and_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_process(["/bin/sh", "-c", "printf out; printf err >&2; exit 4"], directory, 2, directory)
            self.assertEqual(result.exit_code, 4)
            self.assertEqual(Path(result.stdout_path).read_text(), "out")
            self.assertEqual(Path(result.stderr_path).read_text(), "err")


if __name__ == "__main__":
    unittest.main()
