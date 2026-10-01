"""Read Codex's local model catalog without credentials or network requests."""

from dataclasses import dataclass
import json
import os
from pathlib import Path

from .roles import MODEL_PRESETS, REASONING_PRESETS, Role, WorkerPolicy


@dataclass(frozen=True)
class ModelChoice:
    model: str
    display_name: str
    reasoning: tuple[str, ...] = ()

    @property
    def label(self):
        return (f"{self.display_name} ({self.model})"
                if self.display_name != self.model else self.model)


@dataclass(frozen=True)
class ModelCatalog:
    models: tuple[ModelChoice, ...]
    source: str


def model_cache_path():
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    return home / "models_cache.json"


def load_model_catalog(path=None):
    path = Path(path) if path is not None else model_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise ValueError("Invalid model catalog")
    except (OSError, ValueError):
        return ModelCatalog(tuple(ModelChoice(model, model) for model in MODEL_PRESETS),
                            "Built-in model list (Codex cache unavailable; access is checked at execution)")
    choices = {}
    for item in data["models"]:
        if not isinstance(item, dict) or item.get("visibility") != "list":
            continue
        model = item.get("slug")
        try:
            WorkerPolicy(Role.SCOUT, model, "max")
        except ValueError:
            continue
        if model in choices:
            continue
        label = item.get("display_name")
        if (not isinstance(label, str) or not label.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in label)):
            label = model
        levels = item.get("supported_reasoning_levels")
        reasoning = tuple(dict.fromkeys(level["effort"] for level in levels
                                        if isinstance(level, dict)
                                        and level.get("effort") in REASONING_PRESETS)) if isinstance(levels, list) else ()
        choices[model] = ModelChoice(model, label.strip(), reasoning)
    # Preserve the existing default-model shortcuts; retain catalog order for the rest.
    ordered = [choices.pop(model) for model in MODEL_PRESETS[:2] if model in choices]
    return ModelCatalog(tuple(ordered + list(choices.values())),
                        f"Codex model cache: {path} (access is checked at execution)")
