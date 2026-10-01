"""Protocol fixture for subprocess integration tests; never contacts Codex."""

import json
import os
from pathlib import Path
import sys
import time

args = sys.argv[1:]
prompt = sys.stdin.read()
role = prompt.split("ROLE: ", 1)[1].splitlines()[0]
mode = os.environ.get("DEVFLOW_TEST_MODE", "planned")
repo = Path(args[args.index("--cd") + 1])
schema = json.loads(Path(args[args.index("--output-schema") + 1]).read_text())
response = Path(args[args.index("--output-last-message") + 1])
model = args[args.index("--model") + 1]
effort = json.loads(args[args.index("--config") + 1].split("=", 1)[1])
if model == "invalid-model" or (model == "limited-model" and effort == "ultra"):
    print(json.dumps({"type": "turn.failed", "error": {"message": "Unavailable model or unsupported effort"}}))
    sys.exit(5)
if mode == "interrupt-worker" and role == "implementer":
    print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7}}), flush=True)
    (repo / "worker.ready").touch()
    time.sleep(60)
if mode == "timeout":
    time.sleep(30)
if mode == "exit":
    print("fixture failure", file=sys.stderr)
    sys.exit(7)
if mode == "invalid":
    response.write_text('{"schema_version": 99}')
    sys.exit(0)
if mode == "missing":
    sys.exit(0)
if role == "scout":
    data = {key: False for key, value in schema["properties"].items() if value["type"] == "boolean"}
    data.update(schema_version=1, scope="local" if mode == "simple" else "multi-module",
                affected_areas=["app.py"], regression_risk="low", suggested_reviews=[], rationale="fixture")
elif role == "planner":
    data = {key: "test plan" for key in ("problem", "current_behavior", "goal", "validation", "risks")}
    data.update(schema_version=1, affected_components=["app.py"], steps=["Implement", "Validate"])
elif role in ("implementer", "repairer"):
    (repo / "app.py").write_text("value = 2\n" if role == "repairer" or mode != "repair" else "value = 0\n")
    (repo / "new file.txt").write_text("new\n")
    data = dict(schema_version=1, summary="Updated app", plan_deviations=[], limitations=[])
elif role == "reviewer":
    count_file = repo / ".codex-devflow" / "fixture-review-count"
    count = int(count_file.read_text()) if count_file.exists() else 0
    count_file.write_text(str(count + 1))
    failed = mode == "review-fail" or (mode == "review-repair" and count == 0)
    data = dict(schema_version=1, passed=not failed, findings=[dict(
        finding="Fix value", severity="high", repair_recommendation="Set value to 2")] if failed else [])
else:
    raise RuntimeError(role)
response.write_text(json.dumps(data))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}))
