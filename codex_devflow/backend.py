"""Codex-specific CLI details live behind the execution backend protocol."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Protocol

from .process import ProcessInterrupted, ProcessResult, run_process
from .roles import WorkerPolicy
from .schema import validate


@dataclass
class BackendResult:
    process: ProcessResult
    data: dict | None
    usage: list[dict]
    error: str | None


class CodexExecutionBackend(Protocol):
    def execute(self, *, repo: Path, prompt: str, schema: dict, policy: WorkerPolicy,
                timeout: float, output_dir: Path) -> BackendResult: ...


def collect_usage(path):
    usage = []
    with Path(path).open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and isinstance(event.get("usage"), dict):
                usage.append(event["usage"])
    return usage


class CodexCliBackend:
    def __init__(self, executable="codex"):
        self.executable = executable

    def execute(self, *, repo, prompt, schema, policy, timeout, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        schema_path = output_dir / "schema.json"
        response_path = output_dir / "response.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        command = [self.executable, "-a", "never", "exec", "--ephemeral",
                   "--model", policy.model,
                   "--config", "model_reasoning_effort=" + json.dumps(policy.reasoning_effort),
                   "--sandbox", policy.sandbox,
                   "--json", "--color", "never", "--cd", str(repo),
                   "--output-schema", str(schema_path),
                   "--output-last-message", str(response_path), "-"]
        try:
            result = run_process(command, repo, timeout, output_dir, prompt)
        except ProcessInterrupted as exc:
            exc.usage = collect_usage(exc.result.stdout_path)
            raise
        usage = collect_usage(result.stdout_path)
        data, error = None, result.error
        if result.timed_out:
            error = "Codex process timed out"
        elif result.exit_code != 0:
            error = error or f"Codex process exited with {result.exit_code}"
        else:
            try:
                data = json.loads(response_path.read_text(encoding="utf-8"))
                validate(data, schema)
                if "passed" in data and not data["passed"] and not data["findings"]:
                    raise ValueError("Failed review requires a finding")
            except (OSError, ValueError) as exc:
                error = f"Invalid Codex structured output: {exc}"
                data = None
        return BackendResult(result, data, usage, error)
