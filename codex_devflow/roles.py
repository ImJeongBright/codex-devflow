"""Core worker identities and their fixed permission boundaries."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    SCOUT = "scout"
    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    REPAIRER = "repairer"

    @property
    def sandbox(self):
        return "workspace-write" if self in (Role.IMPLEMENTER, Role.REPAIRER) else "read-only"


MODEL_PRESETS = ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra", "gpt-6-sol",
                 "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5")
REASONING_PRESETS = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")


@dataclass(frozen=True)
class WorkerPolicy:
    role: Role
    model: str
    reasoning_effort: str

    def __post_init__(self):
        if not isinstance(self.role, Role):
            raise ValueError("Worker role must be a Core Role")
        if (not isinstance(self.model, str) or not self.model
                or any(char.isspace() or ord(char) < 32 for char in self.model)
                or self.model.startswith("-")):
            raise ValueError("Model must be a non-empty model ID without whitespace or leading '-' ")
        if self.reasoning_effort not in REASONING_PRESETS:
            raise ValueError(f"Invalid reasoning effort: {self.reasoning_effort!r}")

    @property
    def sandbox(self):
        return self.role.sandbox

    def to_dict(self):
        return {"role": self.role.value, "model": self.model,
                "reasoning_effort": self.reasoning_effort, "sandbox": self.sandbox}


def recommended_roles():
    return {role.value: {"model": "gpt-6.1-sol" if role == Role.PLANNER else "gpt-6-luna",
                         "reasoning_effort": "high" if role == Role.PLANNER else "max"}
            for role in Role}


def policies(roles=None):
    values = recommended_roles()
    if roles is not None:
        if not isinstance(roles, dict):
            raise ValueError("roles must be an object")
        for name, fields in roles.items():
            Role(name)
            if not isinstance(fields, dict) or set(fields) - {"model", "reasoning_effort"}:
                raise ValueError(f"Invalid policy fields for {name}")
            values[name].update(fields)
    return {role: WorkerPolicy(role, **values[role.value]) for role in Role}
