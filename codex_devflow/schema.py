"""The small JSON Schema subset used by our versioned worker contracts."""


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def enum(*values):
    return {"type": "string", "enum": list(values)}


TEXT = {"type": "string"}
TEXTS = {"type": "array", "items": TEXT}
VERSION = {"type": "integer", "enum": [1]}
RISK_FLAGS = ("database_change", "transaction_change", "async_processing",
              "concurrency", "retry_or_idempotency", "migration", "external_integration")
ANALYSIS = obj({
    "schema_version": VERSION,
    "scope": enum("local", "multi-module", "unknown"),
    "affected_areas": TEXTS,
    **{key: {"type": "boolean"} for key in RISK_FLAGS},
    "regression_risk": enum("low", "medium", "high", "unknown"),
    "suggested_reviews": TEXTS,
    "rationale": TEXT,
})
PLAN = obj({"schema_version": VERSION, **{key: TEXT for key in (
    "problem", "current_behavior", "goal", "validation", "risks")},
    "affected_components": TEXTS, "steps": TEXTS})
CHANGE = obj({"schema_version": VERSION, "summary": TEXT,
              "plan_deviations": TEXTS, "limitations": TEXTS})
REVIEW = obj({"schema_version": VERSION, "passed": {"type": "boolean"},
              "findings": {"type": "array", "items": obj({
                  "finding": TEXT, "severity": enum("low", "medium", "high", "critical"),
                  "repair_recommendation": TEXT})}})


def validate(value, schema, path="$ "):
    kind = schema["type"]
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int}
    if type(value) is not types[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: unsupported value {value!r}")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError(f"{path}: missing or unexpected fields")
        for key, item in value.items():
            validate(item, schema["properties"][key], f"{path}.{key}")
    elif kind == "array":
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")


def select_workflow(analysis):
    validate(analysis, ANALYSIS)
    return "simple" if (analysis["scope"] == "local"
                        and analysis["regression_risk"] == "low"
                        and not any(analysis[key] for key in RISK_FLAGS)) else "planned"
