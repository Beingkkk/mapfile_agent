"""UpdateResolver — normalize LLM update paths and coerce values.

DC-021  plan-backend-llm §3.5

Handles V2-discovered common type errors:
- projection: str → [str]
- status: bool → "ON"/"OFF"
- numeric strings → int/float when value_type matches
"""

from __future__ import annotations

import re
from typing import Any

from template_mapper import FieldDescriptor, TemplateMapper


class UpdateResolver:
    """Resolve and coerce LLM-suggested parameter updates."""

    def resolve(self, update: dict, mapper: TemplateMapper) -> dict:
        """Normalize path and coerce value for a single update dict.

        Returns a new dict with normalized ``path`` and coerced ``value``.
        """
        path = update.get("path")
        if path is None:
            raise ValueError("Update dict must contain 'path' key")

        value = update.get("value")
        normalized_path = self._normalize_path(str(path))
        coerced_value = self._coerce_value(normalized_path, value, mapper)

        result = dict(update)
        result["path"] = normalized_path
        result["value"] = coerced_value
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Path normalization
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Convert ``layers[0]`` notation to ``layers.0``."""
        return re.sub(r"\[(\d+)\]", r".\1", path)

    # ─────────────────────────────────────────────────────────────────────────
    # Value coercion
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _coerce_value(path: str, value: Any, mapper: TemplateMapper) -> Any:
        """Coerce a value based on the field's value_type."""
        object_type = UpdateResolver._infer_object_type(path)
        field = UpdateResolver._extract_field_name(path)

        if field is None:
            return value

        desc = mapper.get_field_descriptor(object_type, field)
        if desc is None:
            # Try alias resolution for color / enum values
            resolved = mapper.resolve_alias(object_type, field, value)
            if resolved != value:
                return resolved
            return value

        # Always try alias resolution first (colors, enums, etc.)
        if isinstance(value, str):
            resolved = mapper.resolve_alias(object_type, field, value)
            if resolved != value:
                return resolved

        return UpdateResolver._coerce_by_descriptor(value, desc)

    @staticmethod
    def _coerce_by_descriptor(value: Any, desc: FieldDescriptor) -> Any:
        """Apply type-specific coercion rules."""
        vt = desc.value_type

        # Special case: projection must be an array
        if desc.key == "projection" and isinstance(value, str):
            return [value]

        # Special case: status bool → enum string
        if desc.key == "status" and isinstance(value, bool):
            return "ON" if value else "OFF"

        # Integer coercion
        if vt == "integer" and isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return value

        # Float coercion
        if vt == "float" and isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value

        # Boolean coercion
        if vt == "boolean" and isinstance(value, str):
            low = value.lower()
            if low in ("true", "on", "yes", "1"):
                return True
            if low in ("false", "off", "no", "0"):
                return False
            return value

        # Color: try alias resolution
        if vt == "color" and isinstance(value, str):
            # This would need a color alias map; for now, return as-is
            # The alias resolution above handles known color names
            return value

        return value

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _infer_object_type(path: str) -> str:
        """Infer object type from flat path.

        e.g. 'layers.0.classes.0.styles.0.color' → 'STYLE'
        """
        parts = path.split(".")
        type_map = {
            "layers": "LAYER",
            "classes": "CLASS",
            "styles": "STYLE",
            "labels": "LABEL",
            "web": "WEB",
            "metadata": "METADATA",
            "cache": "CACHE",
        }
        for part in reversed(parts):
            if part in type_map:
                return type_map[part]
        return "MAP"

    @staticmethod
    def _extract_field_name(path: str) -> str | None:
        """Extract the leaf field name from a flat path.

        e.g. 'layers.0.name' → 'name'
        """
        parts = path.split(".")
        # Last part is the field name (skip numeric indices)
        for part in reversed(parts):
            if not part.isdigit():
                return part
        return None
