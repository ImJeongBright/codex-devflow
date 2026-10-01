import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from codex_devflow.backend import CodexCliBackend
from codex_devflow.cli import main
from codex_devflow.config import configuration, global_config_path
from codex_devflow.roles import Role, policies, recommended_roles
from codex_devflow.terminal import Cancelled, TerminalInput, TerminalProgress
from codex_devflow.workflow import Workflow
from test_devflow import RepositoryCase, SOURCE


def args(repo, **values):
    result = argparse.Namespace(repo=repo, validate=None, timeout=None, max_repairs=None,
                                role_model=None, role_reasoning=None)
    for key, value in values.items():
        setattr(result, key, value)
    return result


class RoleTests(unittest.TestCase):
    def test_exact_core_roles_and_defaults(self):
        self.assertEqual({r.value for r in Role}, {"scout", "planner", "implementer", "reviewer", "repairer"})
        for role, policy in policies().items():
            self.assertEqual(policy.model, "gpt-6.1-sol" if role == Role.PLANNER else "gpt-6-luna")
            self.assertEqual(policy.reasoning_effort, "high" if role == Role.PLANNER else "max")
            self.assertEqual(policy.sandbox, "workspace-write" if role in (Role.IMPLEMENTER, Role.REPAIRER) else "read-only")

    def test_invalid_role_policy(self):
        for value in ({"unknown": {}}, {"scout": {"sandbox": "danger-full-access"}},
                      {"reviewer": {"model": ""}}, {"reviewer": {"model": "bad model"}},
                      {"planner": {"reasoning_effort": "invented"}}, {"scout": None}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policies(value)


class ConfigTests(RepositoryCase):
    def write_global(self, value):
        path = global_config_path()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(value))

    def test_all_layers_merge_by_role_and_field(self):
        self.write_global({"roles": {"planner": {"model": "global-planner", "reasoning_effort": "low"},
                                     "scout": {"model": "global-scout"}}})
        (self.repo / ".codex-devflow.json").write_text(json.dumps({
            "roles": {"planner": {"model": "project-planner"}}, "max_repairs": 2}))
        value = configuration(self.repo, args(self.repo, role_reasoning=["planner=high"],
                                              role_model=["reviewer=custom-reviewer"], max_repairs=0))
        self.assertEqual(value["roles"]["planner"], {"model": "project-planner", "reasoning_effort": "high"})
        self.assertEqual(value["roles"]["scout"]["model"], "global-scout")
        self.assertEqual(value["roles"]["reviewer"], {"model": "custom-reviewer", "reasoning_effort": "max"})
        self.assertEqual(value["roles"]["implementer"], recommended_roles()["implementer"])
        self.assertEqual(value["max_repairs"], 0)
        self.assertEqual(recommended_roles()["planner"]["model"], "gpt-6.1-sol")

    def test_global_overrides_builtins(self):
        self.write_global({"roles": {"scout": {"model": "custom", "reasoning_effort": "low"}}})
        self.assertEqual(configuration(self.repo, args(self.repo))["roles"]["scout"],
                         {"model": "custom", "reasoning_effort": "low"})

    def test_invalid_configuration_never_starts_workers(self):
        for override in ("unknown=gpt-6-luna", "planner", "planner="):
            with self.subTest(override=override), redirect_stderr(io.StringIO()), patch("codex_devflow.cli.Workflow") as workflow:
                self.assertEqual(main(["feature", "task", "--repo", str(self.repo), "--role-model", override]), 2)
                workflow.assert_not_called()

    def test_bad_global_json_reports_path(self):
        self.write_global({})
        global_config_path().write_text("{")
        with self.assertRaisesRegex(ValueError, "config.json"):
            configuration(self.repo, args(self.repo))


class PolicyEvidenceTests(RepositoryCase):
    def test_policy_matches_every_subprocess_and_artifact(self):
        events = []
        overrides = {"reviewer": {"model": "custom-reviewer", "reasoning_effort": "high"}}
        record, directory = Workflow(CodexCliBackend(str(self.executable)), self.repo, "Update app", ["exit 0"],
                                      roles=overrides, progress=events.append).run()
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual(record["workers"], record["steps"])
        self.assertEqual(record["settings"]["roles"]["reviewer"], overrides["reviewer"])
        for worker in record["workers"]:
            command = worker["process"]["command"]
            self.assertEqual(command[command.index("--model") + 1], worker["model"])
            self.assertEqual(json.loads(command[command.index("--config") + 1].split("=", 1)[1]), worker["reasoning_effort"])
            self.assertEqual(command[command.index("--sandbox") + 1], worker["sandbox"])
            self.assertEqual(worker["exit_code"], 0)
            self.assertFalse(worker["timed_out"])
            self.assertTrue(worker["started_at"])
            self.assertTrue(worker["finished_at"])
            self.assertGreater(worker["elapsed_seconds"], 0)
            self.assertEqual(worker["usage"], [{"input_tokens": 10, "output_tokens": 2}])
            self.assertEqual(json.loads(Path(worker["directory"], "result.json").read_text()), worker)
        self.assertEqual(record["metrics"]["roles"]["reviewer"]["run_count"], 1)
        self.assertIn("custom-reviewer", (directory / "exec.md").read_text())
        self.assertEqual([e["role"] for e in events if e["event"] == "worker_started"],
                         [w["role"] for w in record["workers"]])
        self.assertEqual(events[-1]["event"], "finished")

    def test_simple_records_only_executed_roles(self):
        record, _ = self.workflow("simple")
        self.assertEqual([w["role"] for w in record["workers"]], ["scout", "implementer"])
        self.assertEqual(set(record["metrics"]["roles"]), {"scout", "implementer"})

    def test_unavailable_model_or_effort_has_no_fallback(self):
        for model, effort in (("invalid-model", "max"), ("limited-model", "ultra")):
            with self.subTest(model=model):
                record, _ = Workflow(CodexCliBackend(str(self.executable)), self.repo, "task", ["exit 0"],
                                      roles={"scout": {"model": model, "reasoning_effort": effort}}).run()
                self.assertEqual(record["status"], "error")
                self.assertEqual(len(record["workers"]), 1)
                self.assertEqual(record["workers"][0]["model"], model)
                self.assertEqual(record["workers"][0]["reasoning_effort"], effort)
                self.assertEqual(record["workers"][0]["exit_code"], 5)
                self.assertIn("Unavailable model", Path(record["workers"][0]["process"]["stdout_path"]).read_text())

    def test_timeout_retains_policy_and_result(self):
        record, _ = self.workflow("timeout", timeout=0.2)
        worker, = record["workers"]
        self.assertEqual(worker["role"], "scout")
        self.assertEqual(worker["model"], "gpt-6-luna")
        self.assertEqual(worker["reasoning_effort"], "max")
        self.assertTrue(worker["timed_out"])
        self.assertEqual(worker["status"], "error")

    def test_progress_failure_does_not_change_workflow(self):
        def broken(event):
            raise BrokenPipeError()
        record, _ = Workflow(CodexCliBackend(str(self.executable)), self.repo, "task", ["exit 0"], progress=broken).run()
        self.assertEqual(record["status"], "succeeded")

    def test_interrupted_worker_preserves_policy_and_available_usage(self):
        env = {**os.environ, "DEVFLOW_TEST_MODE": "interrupt-worker"}
        cli = subprocess.Popen([sys.executable, "-m", "codex_devflow", "feature", "Update app", "--repo", str(self.repo),
                                "--codex", str(self.executable), "--validate", "exit 0"], cwd=SOURCE,
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not (self.repo / "worker.ready").exists():
                self.assertIsNone(cli.poll())
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.01)
            cli.send_signal(signal.SIGTERM)
            out, err = cli.communicate(timeout=10)
            self.assertEqual(cli.returncode, 130, err)
            record = json.loads(Path(json.loads(out)["run_dir"], "run.json").read_text())
            worker = record["workers"][-1]
            self.assertEqual(worker["role"], "implementer")
            self.assertEqual(worker["status"], "interrupted")
            self.assertEqual(worker["model"], "gpt-6-luna")
            self.assertEqual(worker["reasoning_effort"], "max")
            self.assertEqual(worker["usage"], [{"input_tokens": 7}])
            self.assertTrue(worker["finished_at"])
            self.assertIsInstance(worker["exit_code"], int)
        finally:
            if cli.poll() is None:
                cli.send_signal(signal.SIGTERM)
            cli.communicate(timeout=10)


class InputTests(RepositoryCase):
    def collect(self, text):
        return TerminalInput(io.StringIO(text), io.StringIO()).collect(args(self.repo))

    def test_task_and_enter_use_defaults_without_model_input(self):
        selection = self.collect("Update app\n\n")
        self.assertEqual(selection.task, "Update app")
        self.assertEqual(selection.repo, self.repo)
        self.assertEqual(selection.settings["roles"], recommended_roles())

    def test_multiline_task(self):
        selection = self.collect(":multi\nFirst line\nSecond line\n.\n\n")
        self.assertEqual(selection.task, "First line\nSecond line")

    def test_customize_only_reviewer_and_save_preserves_validation(self):
        path = self.repo / ".codex-devflow.json"
        path.write_text('{"validation_commands":["exit 0"],"max_repairs":2}')
        selection = self.collect("Update app\nc\n4\nc\ncustom-reviewer\n5\n\ns\n\n")
        fields = selection.settings["roles"]
        self.assertEqual(fields["reviewer"], {"model": "custom-reviewer", "reasoning_effort": "high"})
        for role in (Role.SCOUT, Role.PLANNER, Role.IMPLEMENTER, Role.REPAIRER):
            self.assertEqual(fields[role.value], recommended_roles()[role.value])
        saved = json.loads(path.read_text())
        self.assertEqual(saved["validation_commands"], ["exit 0"])
        self.assertEqual(saved["max_repairs"], 2)
        self.assertEqual(saved["roles"], fields)

    def test_cancel_and_eof(self):
        for text in ("q\n", "Update app\nq\n", ""):
            with self.subTest(text=text), self.assertRaises(Cancelled):
                self.collect(text)

    def test_non_tty_missing_task_is_usage_error(self):
        with redirect_stderr(io.StringIO()), patch("codex_devflow.cli.TerminalInput") as terminal:
            with self.assertRaises(SystemExit) as exc:
                main(["feature", "--repo", str(self.repo)])
            self.assertEqual(exc.exception.code, 2)
            terminal.assert_not_called()

    def test_direct_task_never_opens_interactive_ui(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True
        with patch("sys.stdin", Tty()), redirect_stdout(Tty()), redirect_stderr(io.StringIO()), \
                patch("codex_devflow.cli.TerminalInput") as terminal:
            self.assertEqual(main(["feature", "Update app", "--repo", str(self.repo),
                                   "--codex", str(self.executable), "--validate", "exit 0"]), 0)
            terminal.assert_not_called()

    def run_pty(self, input_text):
        master, slave = pty.openpty()
        cli = subprocess.Popen([sys.executable, "-m", "codex_devflow", "feature", "--repo", str(self.repo),
                                "--codex", str(self.executable), "--validate", "exit 0"],
                               cwd=SOURCE, stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)
        output = bytearray()
        try:
            os.write(master, input_text.encode())
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output.extend(chunk)
                elif cli.poll() is not None:
                    break
            cli.wait(timeout=2)
        finally:
            if cli.poll() is None:
                cli.kill()
                cli.wait()
            os.close(master)
        return cli.returncode, output.decode(errors="replace")

    def test_real_pty_default_interactive_flow_and_live_progress(self):
        code, output = self.run_pty("Update app\n\n")
        self.assertEqual(code, 0, output)
        for text in ("Task", "Worker policy", "gpt-6.1-sol / high", "[running] scout", "[running] Validation", "[running] Finalize", "[succeeded] DevFlow", "Exec:"):
            self.assertIn(text, output)
        record_path, = (self.repo / ".codex-devflow/runs").glob("*/run.json")
        record = json.loads(record_path.read_text())
        self.assertEqual(record["status"], "succeeded")
        self.assertEqual(record["settings"]["roles"], recommended_roles())

    def test_real_pty_cancel_starts_no_workers(self):
        code, output = self.run_pty("q\n")
        self.assertEqual(code, 130, output)
        self.assertFalse((self.repo / ".codex-devflow/runs").exists())

    def test_real_pty_customization_applies_only_to_reviewer(self):
        code, output = self.run_pty("Update app\nc\n4\n2\n5\n\n\n")
        self.assertEqual(code, 0, output)
        path, = (self.repo / ".codex-devflow/runs").glob("*/run.json")
        record = json.loads(path.read_text())
        for worker in record["workers"]:
            self.assertEqual(worker["model"], "gpt-6.1-sol" if worker["role"] in ("planner", "reviewer") else "gpt-6-luna")
            self.assertEqual(worker["reasoning_effort"], "high" if worker["role"] in ("planner", "reviewer") else "max")
        self.assertFalse((self.repo / ".codex-devflow.json").exists())

    def test_failure_progress_includes_stdout_and_stderr(self):
        out, err = self.repo / "out.log", self.repo / "err.log"
        out.write_text("2 tests failed")
        err.write_text("assertion details")
        stream = io.StringIO()
        TerminalProgress(stream)({"event": "validation_result", "command": "test command",
                                  "exit_code": 1, "timed_out": False,
                                  "stdout_path": str(out), "stderr_path": str(err)})
        self.assertIn("2 tests failed", stream.getvalue())
        self.assertIn("assertion details", stream.getvalue())

    def test_progress_shows_validation_failure_and_repair_budget(self):
        stream = io.StringIO()
        with patch.dict(os.environ, DEVFLOW_TEST_MODE="repair"):
            record, _ = Workflow(CodexCliBackend(str(self.executable)), self.repo, "Update app",
                                  [f"{sys.executable} -B -c 'from app import value; assert value == 2'"],
                                  progress=TerminalProgress(stream)).run()
        self.assertEqual(record["status"], "succeeded")
        for text in ("[exit 1]", "AssertionError", "Repairer 1/1", "Repair attempts 1"):
            self.assertIn(text, stream.getvalue())


if __name__ == "__main__":
    unittest.main()
