"""Tests for TemplateMapper and FieldDescriptor."""

from __future__ import annotations

from pathlib import Path

import pytest

# TemplateMapper lives inside backend/core which is not on PYTHONPATH
# in test runs; add it relative to this test file.
BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(BACKEND_CORE) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BACKEND_CORE))

from template_mapper import FieldDescriptor, TemplateMapper

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mapper():
    """Fresh TemplateMapper backed by the real rules file."""
    return TemplateMapper(str(RULES_PATH))


# -----------------------------------------------------------------------------
# FieldDescriptor
# -----------------------------------------------------------------------------


class TestFieldDescriptor:
    def test_create_with_all_fields(self) -> None:
        fd = FieldDescriptor(
            key="status",
            value_type="enum",
            enum=["ON", "OFF"],
            default="ON",
            phase="service",
            derived=False,
            editable=True,
        )
        assert fd.key == "status"
        assert fd.value_type == "enum"
        assert fd.enum == ["ON", "OFF"]
        assert fd.default == "ON"
        assert fd.phase == "service"
        assert fd.derived is False
        assert fd.editable is True

    def test_defaults(self) -> None:
        fd = FieldDescriptor(key="name", value_type="string")
        assert fd.default is None
        assert fd.enum is None
        assert fd.min is None
        assert fd.max is None
        assert fd.phase == "service"
        assert fd.required is False
        assert fd.derived is False
        assert fd.editable is True
        assert fd.custom is False
        assert fd.custom_desc == ""

    def test_custom_fields(self) -> None:
        fd = FieldDescriptor(
            key="custom_prop",
            value_type="string",
            custom=True,
            custom_desc="User-defined property",
        )
        assert fd.custom is True
        assert fd.custom_desc == "User-defined property"


# -----------------------------------------------------------------------------
# TemplateMapper — init & basic loading
# -----------------------------------------------------------------------------


class TestTemplateMapperInit:
    def test_loads_rules_file(self) -> None:
        mapper = TemplateMapper(str(RULES_PATH))
        assert mapper._rules is not None
        assert "object_types" in mapper._rules
        assert "aliases" in mapper._rules

    def test_missing_rules_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            TemplateMapper(str(RULES_PATH.parent / "nonexistent.json"))


# -----------------------------------------------------------------------------
# TemplateMapper — get_object_type
# -----------------------------------------------------------------------------


class TestGetObjectType:
    def test_returns_rules_for_known_type(self, mapper: TemplateMapper) -> None:
        rules = mapper.get_object_type("MAP")
        assert rules is not None
        assert "fields" in rules
        assert "required" in rules
        assert "business_required" in rules
        assert "required_when" in rules

    def test_returns_none_for_unknown_type(self, mapper: TemplateMapper) -> None:
        assert mapper.get_object_type("UNKNOWN_TYPE") is None

    def test_all_expected_types_present(self, mapper: TemplateMapper) -> None:
        expected = {"MAP", "LAYER", "CLASS", "STYLE", "LABEL", "WEB", "METADATA", "CACHE"}
        for obj_type in expected:
            assert mapper.get_object_type(obj_type) is not None, f"{obj_type} missing"


# -----------------------------------------------------------------------------
# TemplateMapper — get_field_descriptor
# -----------------------------------------------------------------------------


class TestGetFieldDescriptor:
    def test_returns_descriptor_for_known_field(self, mapper: TemplateMapper) -> None:
        fd = mapper.get_field_descriptor("MAP", "status")
        assert fd is not None
        assert fd.key == "status"
        assert fd.value_type == "enum"

    def test_descriptor_has_correct_type(self, mapper: TemplateMapper) -> None:
        fd = mapper.get_field_descriptor("MAP", "name")
        assert fd is not None
        assert fd.value_type == "string"

    def test_descriptor_has_numeric_range(self, mapper: TemplateMapper) -> None:
        fd = mapper.get_field_descriptor("MAP", "angle")
        assert fd is not None
        assert fd.min == -360
        assert fd.max == 360

    def test_descriptor_has_array_items_range(self, mapper: TemplateMapper) -> None:
        fd = mapper.get_field_descriptor("MAP", "extent")
        assert fd is not None
        assert fd.value_type == "array"

    def test_descriptor_for_color_field(self, mapper: TemplateMapper) -> None:
        fd = mapper.get_field_descriptor("STYLE", "color")
        assert fd is not None
        assert fd.value_type == "color"

    def test_returns_none_for_unknown_object_type(self, mapper: TemplateMapper) -> None:
        assert mapper.get_field_descriptor("UNKNOWN", "name") is None

    def test_returns_none_for_unknown_field(self, mapper: TemplateMapper) -> None:
        assert mapper.get_field_descriptor("MAP", "nonexistent_field") is None


# -----------------------------------------------------------------------------
# TemplateMapper — allows_custom_properties
# -----------------------------------------------------------------------------


class TestAllowsCustomProperties:
    def test_true_for_map(self, mapper: TemplateMapper) -> None:
        assert mapper.allows_custom_properties("MAP") is True

    def test_false_for_style(self, mapper: TemplateMapper) -> None:
        assert mapper.allows_custom_properties("STYLE") is False

    def test_false_for_label(self, mapper: TemplateMapper) -> None:
        assert mapper.allows_custom_properties("LABEL") is False

    def test_true_for_metadata(self, mapper: TemplateMapper) -> None:
        assert mapper.allows_custom_properties("METADATA") is True

    def test_false_for_unknown_type(self, mapper: TemplateMapper) -> None:
        assert mapper.allows_custom_properties("UNKNOWN") is False


# -----------------------------------------------------------------------------
# TemplateMapper — list_all_fields
# -----------------------------------------------------------------------------


class TestListAllFields:
    def test_returns_list_of_strings(self, mapper: TemplateMapper) -> None:
        fields = mapper.list_all_fields("MAP")
        assert isinstance(fields, list)
        assert all(isinstance(f, str) for f in fields)

    def test_map_has_expected_fields(self, mapper: TemplateMapper) -> None:
        fields = mapper.list_all_fields("MAP")
        assert "name" in fields
        assert "status" in fields
        assert "extent" in fields

    def test_returns_empty_for_unknown_type(self, mapper: TemplateMapper) -> None:
        assert mapper.list_all_fields("UNKNOWN") == []


# -----------------------------------------------------------------------------
# TemplateMapper — resolve_alias
# -----------------------------------------------------------------------------


class TestResolveAlias:
    def test_resolves_chinese_alias(self, mapper: TemplateMapper) -> None:
        # 中文别名: "点" → "point"
        result = mapper.resolve_alias("LAYER", "type", "点")
        assert result == "point"

    def test_resolves_english_alias(self, mapper: TemplateMapper) -> None:
        result = mapper.resolve_alias("LAYER", "connectiontype", "shapefile")
        assert result == "local"

    def test_resolves_color_alias(self, mapper: TemplateMapper) -> None:
        result = mapper.resolve_alias("STYLE", "color", "red")
        assert result == [255, 0, 0]

    def test_returns_original_for_unknown_alias(self, mapper: TemplateMapper) -> None:
        result = mapper.resolve_alias("LAYER", "type", "totally_unknown_value")
        assert result == "totally_unknown_value"

    def test_returns_original_for_unknown_field(self, mapper: TemplateMapper) -> None:
        result = mapper.resolve_alias("LAYER", "nonexistent", "whatever")
        assert result == "whatever"

    def test_returns_original_for_unknown_object_type(self, mapper: TemplateMapper) -> None:
        result = mapper.resolve_alias("UNKNOWN", "type", "whatever")
        assert result == "whatever"


# -----------------------------------------------------------------------------
# TemplateMapper — get_llm_context_summary
# -----------------------------------------------------------------------------


class TestGetLlmContextSummary:
    def test_returns_non_empty_string(self, mapper: TemplateMapper) -> None:
        summary = mapper.get_llm_context_summary("LAYER")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_includes_field_names(self, mapper: TemplateMapper) -> None:
        summary = mapper.get_llm_context_summary("LAYER")
        # Should mention at least some field names
        assert "name" in summary or "type" in summary

    def test_includes_phase_info(self, mapper: TemplateMapper) -> None:
        summary = mapper.get_llm_context_summary("LAYER")
        assert "datasource" in summary.lower() or "phase" in summary.lower()

    def test_returns_empty_for_unknown_type(self, mapper: TemplateMapper) -> None:
        assert mapper.get_llm_context_summary("UNKNOWN") == ""
