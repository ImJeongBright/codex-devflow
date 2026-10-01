"""Layered global/project/run settings and explicit project policy persistence."""

import json
import math
import os
from pathlib import Path
import tempfile

from .roles import Role, policies, recommended_roles


def global_config_path():
    directory = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return directory.expanduser() / "codex-devflow" / "config.json"


def read_config(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read config {path}: {exc}") from exc
    if not isinstance(value, dict) or set(value) - {
        "validation_commands", "timeout_seconds", "max_repairs", "roles"
    }:
        raise ValueError(f"Invalid or unknown settings in {path}")
    validate_settings(value)
    return value


def validate_settings(settings):
    if "validation_commands" in settings:
        commands = settings["validation_commands"]
        if not isinstance(commands, list) or any(not isinstance(c, str) or not c.strip() for c in commands):
            raise ValueError("validation_commands must be a list of non-empty shell commands")
    if "timeout_seconds" in settings:
        timeout = settings["timeout_seconds"]
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
    if "max_repairs" in settings:
        repairs = settings["max_repairs"]
        if type(repairs) is not int or repairs < 0:
            raise ValueError("max_repairs must be a non-negative integer")
    if "roles" in settings:
        policies(settings["roles"])


def role_overrides(items, field):
    result = {}
    for value in items or []:
        name, separator, setting = value.partition("=")
        if not separator:
            raise ValueError(f"Expected ROLE=VALUE, got {value!r}")
        try:
            Role(name)
        except ValueError:
            raise ValueError(f"Unknown Core Role: {name!r}") from None
        result.setdefault(name, {})[field] = setting
    policies(result)
    return result


def configuration(repo, args, *, global_path=None):
    settings = {"validation_commands": [], "timeout_seconds": 600, "max_repairs": 1,
                "roles": recommended_roles()}
    layers = [read_config(global_path if global_path is not None else global_config_path()),
              read_config(repo / ".codex-devflow.json")]
    run = {}
    for key, option in (("validation_commands", "validate"), ("timeout_seconds", "timeout"),
                        ("max_repairs", "max_repairs")):
        value = getattr(args, option, None)
        if value is not None:
            run[key] = value
    for option, field in (("role_model", "model"), ("role_reasoning", "reasoning_effort")):
        for name, fields in role_overrides(getattr(args, option, None), field).items():
            run.setdefault("roles", {}).setdefault(name, {}).update(fields)
    validate_settings(run)
    for layer in [*layers, run]:
        for key, value in layer.items():
            if key == "roles":
                for name, fields in value.items():
                    settings["roles"][name].update(fields)
            else:
                settings[key] = value
    validate_settings(settings)
    return settings


def save_project_roles(repo, roles):
    policies(roles)
    path = repo / ".codex-devflow.json"
    if path.is_symlink():
        raise ValueError("Refusing to replace a symlink project config")
    settings = read_config(path)
    settings["roles"] = roles
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=repo,
                                     prefix=".codex-devflow-", suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
