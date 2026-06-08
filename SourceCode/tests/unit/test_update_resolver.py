"""Tests for UpdateResolver.

DC-021  plan-backend-llm §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_LLM = Path(__file__).resolve().parent.parent.parent / "backend" / "llm"
if str(_BACKEND_LLM) not in sys.path:
    sys.path.insert(0, str(_BACKEND_LLM))

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from template_mapper import TemplateMapper
from update_resolver import UpdateResolver

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


class TestUpdateResolverInit:
    def test_can_instantiate(self):
        ur = UpdateResolver()
        assert ur is not None


class TestNormalizePath:
    def test_square_brackets_to_dots(self):
        assert UpdateResolver._normalize_path("layers[0].name") == "layers.0.name"

    def test_already_normalized(self):
        assert UpdateResolver._normalize_path("layers.0.name") == "layers.0.name"

    def test_multiple_brackets(self):
        assert UpdateResolver._normalize_path("layers[0].classes[1].name") == "layers.0.classes.1.name"

    def test_no_brackets(self):
        assert UpdateResolver._normalize_path("name") == "name"

    def test_mixed_brackets_and_dots(self):
        assert UpdateResolver._normalize_path("layers[0].styles.0.color") == "layers.0.styles.0.color"


class TestCoerceValue:
    def test_projection_string_to_array(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.projection", "init=epsg:4326", mapper
        )
        assert result == ["init=epsg:4326"]

    def test_projection_array_preserved(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.projection", ["init=epsg:4326"], mapper
        )
        assert result == ["init=epsg:4326"]

    def test_status_bool_true_to_on(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.status", True, mapper
        )
        assert result == "ON"

    def test_status_bool_false_to_off(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.status", False, mapper
        )
        assert result == "OFF"

    def test_status_string_preserved(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.status", "ON", mapper
        )
        assert result == "ON"

    def test_color_alias_red(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.classes.0.styles.0.color", "红色", mapper
        )
        assert result == [255, 0, 0]

    def test_color_array_preserved(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.classes.0.styles.0.color", [128, 128, 128], mapper
        )
        assert result == [128, 128, 128]

    def test_integer_string_coerced(self, mapper):
        result = UpdateResolver._coerce_value(
            "map.maxsize", "256", mapper
        )
        assert result == 256
        assert isinstance(result, int)

    def test_float_string_coerced(self, mapper):
        result = UpdateResolver._coerce_value(
            "map.angle", "45.5", mapper
        )
        assert result == 45.5
        assert isinstance(result, float)

    def test_unknown_field_passthrough(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.some_unknown_field", "hello", mapper
        )
        assert result == "hello"

    def test_enum_string_passthrough(self, mapper):
        result = UpdateResolver._coerce_value(
            "layers.0.type", "polygon", mapper
        )
        assert result == "polygon"


class TestResolve:
    def test_resolve_normalizes_path(self, mapper):
        ur = UpdateResolver()
        update = {"path": "layers[0].name", "value": "roads"}
        result = ur.resolve(update, mapper)
        assert result["path"] == "layers.0.name"
        assert result["value"] == "roads"

    def test_resolve_coerces_projection(self, mapper):
        ur = UpdateResolver()
        update = {"path": "layers.0.projection", "value": "init=epsg:4326"}
        result = ur.resolve(update, mapper)
        assert result["value"] == ["init=epsg:4326"]

    def test_resolve_coerces_status(self, mapper):
        ur = UpdateResolver()
        update = {"path": "layers.0.status", "value": False}
        result = ur.resolve(update, mapper)
        assert result["value"] == "OFF"

    def test_resolve_missing_path_key_raises(self, mapper):
        ur = UpdateResolver()
        with pytest.raises((KeyError, ValueError)):
            ur.resolve({"value": "test"}, mapper)

    def test_resolve_preserves_extra_keys(self, mapper):
        ur = UpdateResolver()
        update = {"path": "name", "value": "test", "desc": "layer name"}
        result = ur.resolve(update, mapper)
        assert result.get("desc") == "layer name"
