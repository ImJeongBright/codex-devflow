"""Small local CLI and strict project configuration."""

import argparse
import json
from pathlib import Path
import signal
import sys

from .backend import CodexCliBackend
from .config import configuration
from .repository import root
from .terminal import Cancelled, TerminalInput, TerminalProgress
from .workflow import Workflow


def main(argv=None):
    parser = argparse.ArgumentParser(prog="codex-devflow", description="Local Codex development workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    feature = sub.add_parser("feature", help="Analyze, implement, validate, and record a development task")
    feature.add_argument("task", nargs="?")
    feature.add_argument("--repo", type=Path, default=Path.cwd())
    feature.add_argument("--validate", action="append", help="Shell command; repeat for multiple checks (overrides config)")
    feature.add_argument("--timeout", type=float, help="Timeout in seconds per Codex process/validation command")
    feature.add_argument("--max-repairs", type=int)
    feature.add_argument("--codex", default="codex", help="Codex CLI executable path")
    feature.add_argument("--role-model", action="append", metavar="ROLE=MODEL")
    feature.add_argument("--role-reasoning", action="append", metavar="ROLE=EFFORT")
    args = parser.parse_args(argv)
    if args.task is None and not (sys.stdin.isatty() and sys.stdout.isatty()):
        parser.error("Task is required when stdin/stdout are not TTY; pass feature '<task>'")
    previous = signal.getsignal(signal.SIGTERM)
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    try:
        if args.task is None:
            selected = TerminalInput().collect(args)
            repo, task, settings = selected.repo, selected.task, selected.settings
        else:
            if not args.task.strip():
                raise ValueError("Task must not be empty")
            repo, task = root(args.repo), args.task
            settings = configuration(repo, args)
        progress = TerminalProgress() if sys.stdout.isatty() else None
        workflow = Workflow(CodexCliBackend(args.codex), repo, task, progress=progress, **settings)
        record, directory = workflow.run()
    except (Cancelled, KeyboardInterrupt):
        print("codex-devflow: Cancelled", file=sys.stderr)
        return 130
    except (ValueError, OSError) as exc:
        print(f"codex-devflow: {exc}", file=sys.stderr)
        return 2
    finally:
        signal.signal(signal.SIGTERM, previous)
    print(json.dumps({"status": record["status"], "workflow": record["workflow"],
                      "run_dir": str(directory), "error": record["error"]}, ensure_ascii=False))
    return {"succeeded": 0, "failed": 1, "error": 2, "unverified": 3, "interrupted": 130}[record["status"]]
