"""Interactive input and progress adapters; workflow has no terminal dependency."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import sys

from .config import configuration, save_project_roles
from .catalog import load_model_catalog
from .repository import root
from .roles import REASONING_PRESETS, Role, policies


class Cancelled(Exception):
    pass


@dataclass
class Selection:
    repo: Path
    task: str
    settings: dict


class TerminalInput:
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout

    def show(self, message):
        print(message, file=self.stdout, flush=True)

    def ask(self, prompt):
        print(prompt, end="", file=self.stdout, flush=True)
        line = self.stdin.readline()
        if not line:
            raise Cancelled("Input closed")
        return line.rstrip("\r\n")

    def repository(self, candidate):
        while True:
            try:
                return root(candidate)
            except (ValueError, OSError) as exc:
                self.show(f"Repository: {exc}")
                candidate = self.ask("Git repository path (q to cancel): ").strip()
                if candidate == "q":
                    raise Cancelled("Cancelled")

    def task(self):
        while True:
            value = self.ask("Task (:multi for multiple lines, q to cancel): ")
            if value == "q":
                raise Cancelled("Cancelled")
            if value == ":multi":
                self.show("Enter task lines. Finish with a single '.'; q cancels.")
                lines = []
                while True:
                    line = self.ask("> ")
                    if line == "q":
                        raise Cancelled("Cancelled")
                    if line == ".":
                        break
                    lines.append(line)
                value = "\n".join(lines)
            if value.strip():
                return value
            self.show("Task must not be empty.")

    def choose(self, label, options, current, *, custom=False, labels=None):
        if labels is None:
            self.show(f"{label}: " + " | ".join(f"{i}. {value}" for i, value in enumerate(options, 1)))
        else:
            self.show(f"{label}:")
            for i, value in enumerate(labels, 1):
                self.show(f"  {i}. {value}")
        while True:
            value = self.ask(f"Choice [Enter keeps {current}]" + (" / c custom" if custom else "") + ": ")
            if not value:
                return current
            if value == "q":
                raise Cancelled("Cancelled")
            if value == "c" and custom:
                model = self.ask("Custom model ID: ").strip()
                if model == "q":
                    raise Cancelled("Cancelled")
                try:
                    policies({Role.SCOUT.value: {"model": model}})
                except ValueError as exc:
                    self.show(str(exc))
                    continue
                return model
            if value.isdigit() and 1 <= int(value) <= len(options):
                return options[int(value) - 1]
            self.show("Choose a listed number, Enter, or q to cancel.")

    def customize(self, roles):
        result = deepcopy(roles)
        names = list(Role)
        catalog = load_model_catalog()
        self.show(catalog.source)
        if not catalog.models:
            self.show("No listed models in the Codex cache. Use c to enter a custom model ID.")
        while True:
            self.show("Customize roles: " + " | ".join(f"{i}. {role.value}" for i, role in enumerate(names, 1)))
            choice = self.ask("Role [Enter done, q cancel]: ").strip()
            if not choice:
                return result
            if choice == "q":
                raise Cancelled("Cancelled")
            if not choice.isdigit() or not 1 <= int(choice) <= len(names):
                self.show("Choose a role number.")
                continue
            name = names[int(choice) - 1].value
            fields = result[name]
            fields["model"] = self.choose("Model", [model.model for model in catalog.models],
                                          fields["model"], custom=True,
                                          labels=[model.label for model in catalog.models])
            selected = next((model for model in catalog.models if model.model == fields["model"]), None)
            if selected is not None and selected.reasoning:
                self.show("Supported reasoning (Codex cache): " + ", ".join(selected.reasoning))
                if fields["reasoning_effort"] not in selected.reasoning:
                    self.show(f"Current effort {fields['reasoning_effort']} is not listed for this model. "
                              "Choose a supported effort; unsupported combinations fail at execution.")
            fields["reasoning_effort"] = self.choose("Reasoning", REASONING_PRESETS, fields["reasoning_effort"])
            policies(result)

    def collect(self, args):
        self.show("Codex DevFlow")
        repo = self.repository(args.repo)
        settings = configuration(repo, args)
        self.show(f"Repository: {repo}")
        task = self.task()
        while True:
            self.show("Worker policy (effective defaults):")
            for name, fields in settings["roles"].items():
                self.show(f"  {name}: {fields['model']} / {fields['reasoning_effort']}")
            self.show("Validation: " + ("; ".join(settings["validation_commands"]) or "unavailable (no commands)"))
            choice = self.ask("[Enter/r] Run only | [c] Customize roles | [s] Save project default | [q] Cancel: ").strip().lower()
            if choice in ("", "r"):
                return Selection(repo, task, settings)
            if choice == "q":
                raise Cancelled("Cancelled")
            if choice == "c":
                settings["roles"] = self.customize(settings["roles"])
            elif choice == "s":
                save_project_roles(repo, settings["roles"])
                self.show("Project role defaults saved. Press Enter to run, or q to cancel execution.")
            else:
                self.show("Choose Run, Customize, Save, or Cancel.")


class TerminalProgress:
    def __init__(self, stream=None):
        self.stream = stream if stream is not None else sys.stderr

    def __call__(self, event):
        kind = event["event"]
        if kind == "preparation_started":
            message = f"[running] Repository evidence — {event['repository']}"
        elif kind == "preparation_finished":
            message = "[completed] Repository evidence"
        elif kind == "worker_started":
            message = f"[running] {event['role']} — {event['model']} / {event['reasoning_effort']}"
        elif kind == "worker_finished":
            message = (f"[{event['status']}] {event['role']} — {event['elapsed_seconds']:.1f}s"
                       + (f" | {event['error']}" if event.get("error") else ""))
        elif kind == "validation_started":
            message = f"[running] Validation attempt {event['attempt']}"
        elif kind == "validation_command":
            message = f"[running] {event['command']}"
        elif kind == "validation_result":
            message = f"[{'timeout' if event['timed_out'] else 'exit ' + str(event['exit_code'])}] {event['command']}"
            if event["exit_code"] != 0 or event["timed_out"]:
                for field in ("stdout_path", "stderr_path"):
                    try:
                        path = Path(event[field])
                        with path.open("rb") as stream:
                            stream.seek(max(0, path.stat().st_size - 1500))
                            tail = stream.read().decode(errors="replace").strip()
                        if tail:
                            message += "\n" + tail
                    except OSError:
                        pass
        elif kind == "validation_finished":
            message = f"[{event['status']}] Validation"
        elif kind == "repair_started":
            message = f"[running] Repairer {event['attempt']}/{event['limit']}"
        elif kind == "finalize_started":
            message = "[running] Finalize"
        elif kind == "finished":
            record = event["record"]
            validation = record["validation"][-1]["status"] if record["validation"] else "not run"
            review = ("passed" if record["reviews"][-1]["passed"] else "failed") if record["reviews"] else "not run"
            message = (f"[{record['status']}] DevFlow | Changed files {len(record['changed_files'])} | "
                       f"Validation {validation} | Review {review} | Repair attempts {len(record['repairs'])} | "
                       f"Elapsed {record['elapsed_seconds']:.1f}s\nExec: {event['run_dir']}/exec.md")
        else:
            return
        print(message, file=self.stream, flush=True)
