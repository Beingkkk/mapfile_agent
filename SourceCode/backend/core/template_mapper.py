"""TemplateMapper — runtime rule file reader.

DC-002: TemplateMapper  DC-003: FieldDescriptor

plan-template-system §3.2–§3.3
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FieldDescriptor:
    """Metadata descriptor for a single configuration field."""

    key: str
    value_type: str  # string | enum | integer | float | boolean | color | array | object | expression
    default: Any = None
    enum: list[Any] | None = None
    min: Any = None
    max: Any = None
    phase: str = "service"  # datasource | style | service | cache
    required: bool = False
    required_when: str | None = None  # condition expression for conditional required
    derived: bool = False
    editable: bool = True
    custom: bool = False
    custom_desc: str = ""


class TemplateMapper:
    """Single runtime entry-point for reading mapguide_rules.json."""

    def __init__(self, rules_path: str) -> None:
        path = Path(rules_path)
        if not path.exists():
            raise FileNotFoundError(f"Rules file not found: {rules_path}")

        with open(path, encoding="utf-8") as f:
            self._rules: dict[str, Any] = json.load(f)

        self._object_types: dict[str, dict] = self._rules.get("object_types", {})
        self._aliases: dict[str, dict] = self._rules.get("aliases", {})
        self._custom_allowed: dict[str, bool] = self._rules.get("custom_allowed", {})

    def get_object_type(self, object_type: str) -> dict | None:
        """Return the full rule dict for an object type (fields, required, etc.)."""
        return self._object_types.get(object_type)

    def get_field_descriptor(self, object_type: str, field: str) -> FieldDescriptor | None:
        """Build a FieldDescriptor from the rules for (object_type, field)."""
        obj_rules = self._object_types.get(object_type)
        if obj_rules is None:
            return None

        field_def = obj_rules.get("fields", {}).get(field)
        if field_def is None:
            return None

        # Determine if the field is required based on object-level rules
        required_fields = set(obj_rules.get("required", []))
        required_fields.update(obj_rules.get("business_required", []))

        return FieldDescriptor(
            key=field_def["key"],
            value_type=field_def["value_type"],
            enum=field_def.get("enum"),
            default=field_def.get("default"),
            min=field_def.get("min"),
            max=field_def.get("max"),
            phase=field_def.get("phase", "service"),
            required=field in required_fields,
            required_when=field_def.get("required_when"),
            derived=field_def.get("derived", False),
            editable=field_def.get("editable", True),
        )

    def allows_custom_properties(self, object_type: str) -> bool:
        """Return whether the object type permits user-defined custom properties."""
        return self._custom_allowed.get(object_type, False)

    def list_all_fields(self, object_type: str) -> list[str]:
        """Return all field names for an object type."""
        obj_rules = self._object_types.get(object_type)
        if obj_rules is None:
            return []
        return list(obj_rules.get("fields", {}).keys())

    def resolve_alias(self, object_type: str, field: str, alias: str) -> Any:
        """Resolve a human-friendly alias to its canonical value.

        Falls back to returning the original alias when no mapping exists.
        """
        field_aliases = self._aliases.get(object_type, {}).get(field, {})
        return field_aliases.get(alias, alias)

    def get_service_metadata(self) -> dict[str, Any]:
        """Return the service_metadata section from rules."""
        return self._rules.get("service_metadata", {})

    def get_llm_context_summary(self, object_type: str) -> str:
        """Generate a concise field summary suitable for LLM prompts."""
        obj_rules = self._object_types.get(object_type)
        if obj_rules is None:
            return ""

        fields = obj_rules.get("fields", {})
        if not fields:
            return ""

        lines = [f"{object_type} fields (phase={self._rules.get('phase_map', {}).get(object_type, 'service')}):"]
        for name, fd in fields.items():
            vtype = fd.get("value_type", "string")
            phase = fd.get("phase", "service")
            default = fd.get("default")
            derived = " [derived]" if fd.get("derived") else ""
            lines.append(f"  - {name}: {vtype} (phase={phase}){derived}")
            if default is not None:
                lines.append(f"      default: {default}")

        return "\n".join(lines)
