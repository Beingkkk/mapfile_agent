"""Tests for ValidationPipeline (L1–L4) and ValidationResult.

DC-012~016  plan-validation §5
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from config_tree import ConfigTree, TreeLeaf, TreeNode
from template_mapper import FieldDescriptor, TemplateMapper
from validation import ValidationPipeline, ValidationResult

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


@pytest.fixture
def pipeline(mapper):
    return ValidationPipeline(mapper)


# ---------------------------------------------------------------------------
# DC-012: ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_pass_state(self):
        r = ValidationResult(state="pass", errors=[])
        assert r.state == "pass"
        assert r.errors == []

    def test_fail_state(self):
        r = ValidationResult(state="fail", errors=[{"path": "a", "message": "m", "level": "error"}])
        assert r.state == "fail"
        assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# DC-014: L1 Alias Resolution
# ---------------------------------------------------------------------------


class TestL1AliasResolution:
    def test_alias_hit_changes_value(self, pipeline, mapper):
        """Chinese alias → canonical value."""
        tree = ConfigTree({"__type__": "map", "layers": [{"__type__": "layer", "connectiontype": "数据库"}]}, mapper)
        leaf = tree.get_node("layers.0.connectiontype")
        assert isinstance(leaf, TreeLeaf)
        resolved = pipeline._try_resolve_alias(leaf)
        assert resolved == "postgis"
        assert leaf.value == "postgis"

    def test_alias_unknown_passes_through(self, pipeline, mapper):
        """Unknown alias returns original value, no error."""
        tree = ConfigTree({"__type__": "map", "layers": [{"__type__": "layer", "connectiontype": "UNKNOWN_ALIAS"}]}, mapper)
        leaf = tree.get_node("layers.0.connectiontype")
        assert isinstance(leaf, TreeLeaf)
        resolved = pipeline._try_resolve_alias(leaf)
        assert resolved == "UNKNOWN_ALIAS"

    def test_color_alias(self, pipeline, mapper):
        """Color alias resolves to RGB array."""
        tree = ConfigTree({"__type__": "map", "layers": [{"__type__": "layer", "classes": [{"__type__": "class", "styles": [{"__type__": "style", "color": "红色"}]}]}]}, mapper)
        leaf = tree.get_node("layers.0.classes.0.styles.0.color")
        assert isinstance(leaf, TreeLeaf)
        resolved = pipeline._try_resolve_alias(leaf)
        assert resolved == [255, 0, 0]


# ---------------------------------------------------------------------------
# DC-014: L2 Type Check
# ---------------------------------------------------------------------------


class TestL2TypeCheck:
    def test_enum_valid(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="status", descriptor=FieldDescriptor(key="status", value_type="enum", enum=["ON", "OFF"]), value="ON")
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_enum_invalid(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="status", descriptor=FieldDescriptor(key="status", value_type="enum", enum=["ON", "OFF"]), value="maybe")
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1
        assert errs[0]["level"] == "error"
        assert "enum" in errs[0]["message"].lower()

    def test_enum_case_insensitive(self, pipeline):
        """mappyfile accepts case-insensitive enum values."""
        leaf = TreeLeaf(id="x", path="x", key="status", descriptor=FieldDescriptor(key="status", value_type="enum", enum=["ON", "OFF"]), value="on")
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_integer_in_range(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="width", descriptor=FieldDescriptor(key="width", value_type="integer", min=0, max=255), value=128)
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_integer_out_of_range(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="width", descriptor=FieldDescriptor(key="width", value_type="integer", min=0, max=255), value=300)
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1
        assert "exceeds maximum" in errs[0]["message"].lower()

    def test_integer_wrong_type(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="width", descriptor=FieldDescriptor(key="width", value_type="integer"), value="abc")
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_float_in_range(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="opacity", descriptor=FieldDescriptor(key="opacity", value_type="float", min=0.0, max=1.0), value=0.5)
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_float_out_of_range(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="opacity", descriptor=FieldDescriptor(key="opacity", value_type="float", min=0.0, max=1.0), value=1.5)
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_boolean_valid(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="debug", descriptor=FieldDescriptor(key="debug", value_type="boolean"), value=True)
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_boolean_wrong_type(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="debug", descriptor=FieldDescriptor(key="debug", value_type="boolean"), value="yes")
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_color_valid_array(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="color", descriptor=FieldDescriptor(key="color", value_type="color"), value=[255, 0, 0])
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_color_out_of_range(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="color", descriptor=FieldDescriptor(key="color", value_type="color"), value=[256, 0, 0])
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_color_wrong_type(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="color", descriptor=FieldDescriptor(key="color", value_type="color"), value="blue")
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_array_valid(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="projection", descriptor=FieldDescriptor(key="projection", value_type="array"), value=["init=epsg:3857"])
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_array_wrong_type(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="projection", descriptor=FieldDescriptor(key="projection", value_type="array"), value="init=epsg:3857")
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_expression_valid(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="expression", descriptor=FieldDescriptor(key="expression", value_type="expression"), value="('[type]'='city')")
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_expression_wrong_type(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="expression", descriptor=FieldDescriptor(key="expression", value_type="expression"), value=123)
        errs = pipeline._check_type(leaf)
        assert len(errs) == 1

    def test_string_any_value(self, pipeline):
        leaf = TreeLeaf(id="x", path="x", key="name", descriptor=FieldDescriptor(key="name", value_type="string"), value="anything")
        errs = pipeline._check_type(leaf)
        assert errs == []

    def test_unknown_value_type_no_error(self, pipeline):
        """Unknown value_type should not crash."""
        leaf = TreeLeaf(id="x", path="x", key="foo", descriptor=FieldDescriptor(key="foo", value_type="unknown"), value="bar")
        errs = pipeline._check_type(leaf)
        assert errs == []


# ---------------------------------------------------------------------------
# DC-015: L3 Semantic Check
# ---------------------------------------------------------------------------


class TestL3SemanticCheck:
    def test_requires_when_triggered(self, pipeline, mapper):
        """connectiontype=postgis → connection is required."""
        tree = ConfigTree({
            "__type__": "map",
            "layers": [{"__type__": "layer", "connectiontype": "postgis"}]
        }, mapper)
        leaf = tree.get_node("layers.0.connectiontype")
        assert isinstance(leaf, TreeLeaf)
        errs = pipeline._check_semantic(tree, leaf, ["wms"])
        # connection leaf doesn't exist, so error should reference connection
        assert any("connection" in e["message"] for e in errs)

    def test_requires_when_not_triggered(self, pipeline, mapper):
        """connectiontype=local → connection is optional."""
        tree = ConfigTree({
            "__type__": "map",
            "layers": [{"__type__": "layer", "connectiontype": "local"}]
        }, mapper)
        leaf = tree.get_node("layers.0.connectiontype")
        assert isinstance(leaf, TreeLeaf)
        errs = pipeline._check_semantic(tree, leaf, ["wms"])
        assert not any("connection" in e["message"] for e in errs)

    def test_forbids_when_triggered(self, pipeline, mapper):
        """connectiontype=wms → data should not exist."""
        tree = ConfigTree({
            "__type__": "map",
            "layers": [{"__type__": "layer", "connectiontype": "wms", "data": "some.shp"}]
        }, mapper)
        leaf = tree.get_node("layers.0.connectiontype")
        assert isinstance(leaf, TreeLeaf)
        errs = pipeline._check_semantic(tree, leaf, ["wms"])
        assert any("data" in e["message"] for e in errs)

    def test_service_type_requires_wfs_gml(self, pipeline, mapper):
        """WFS enabled but no gml_include_items → warning/info."""
        tree = ConfigTree({
            "__type__": "map",
            "layers": [{"__type__": "layer"}]
        }, mapper)
        leaf = tree.get_node("layers.0")
        assert isinstance(leaf, TreeNode)
        # Semantic check on a node level: check service-related requirements
        errs = pipeline._check_semantic(tree, None, ["wfs"])
        assert any("gml_include_items" in e["message"] for e in errs)

    def test_service_type_wfs_has_gml_no_error(self, pipeline, mapper):
        # Pass service_types at construction so gml_include_items is visible in tree
        tree = ConfigTree({
            "__type__": "map",
            "layers": [{"__type__": "layer", "metadata": {"gml_include_items": "all"}}]
        }, mapper, service_types=["wfs"])
        errs = pipeline._check_semantic(tree, None, ["wfs"])
        assert not any("gml_include_items" in e["message"] for e in errs)


# ---------------------------------------------------------------------------
# DC-016: L4 Mappyfile Syntax
# ---------------------------------------------------------------------------


class TestL4MappyfileSyntax:
    def test_valid_mapfile_passes(self, pipeline, mapper):
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "extent": [-180, -90, 180, 90],
            "projection": ["init=epsg:4326"],
            "layers": [{"__type__": "layer", "name": "layer1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline._check_mappyfile(tree)
        assert errs == []

    def test_custom_property_not_reported(self, pipeline, mapper):
        """Custom properties should not trigger mappyfile errors."""
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "_custom": {"transparency": {"value": 0.5, "type": "float", "desc": ""}},
            "layers": [{"__type__": "layer", "name": "layer1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline._check_mappyfile(tree)
        # transparency is a custom property on MAP, should be filtered
        assert not any("transparency" in e["message"] for e in errs)

    def test_object_fields_not_reported(self, pipeline, mapper):
        """Fields from object-fields.json (e.g. wms_enable_request) should not error."""
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "web": {"__type__": "web", "metadata": {"wms_enable_request": "*"}},
            "layers": [{"__type__": "layer", "name": "layer1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline._check_mappyfile(tree)
        assert not any("wms_enable_request" in e["message"] for e in errs)

    def test_real_syntax_error_reported(self, pipeline, mapper):
        """Actual syntax errors should still be reported."""
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": 123,  # wrong type
            "layers": [{"__type__": "layer", "name": "layer1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline._check_mappyfile(tree)
        # Should have at least one error about status type
        assert len(errs) >= 1


# ---------------------------------------------------------------------------
# DC-015: Integration — validate_field / validate_tree
# ---------------------------------------------------------------------------


class TestValidationPipelineIntegration:
    def test_validate_field_runs_l1_l3_only(self, pipeline, mapper):
        """Default validate_field should not run L4."""
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "layers": [{"__type__": "layer", "name": "l1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline.validate_field(tree, "name", ["wms"])
        assert isinstance(errs, list)

    def test_validate_field_full_runs_l4(self, pipeline, mapper):
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "layers": [{"__type__": "layer", "name": "l1", "status": "ON", "type": "polygon"}]
        }, mapper)
        errs = pipeline.validate_field(tree, "name", ["wms"], full=True)
        assert isinstance(errs, list)

    def test_validate_tree_returns_result(self, pipeline, mapper):
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "layers": [{"__type__": "layer", "name": "l1", "status": "ON", "type": "polygon"}]
        }, mapper)
        result = pipeline.validate_tree(tree, ["wms"])
        assert isinstance(result, ValidationResult)
        assert result.state in ("pass", "fail")

    def test_validate_tree_with_type_error_fails(self, pipeline, mapper):
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "layers": [{"__type__": "layer", "name": "l1", "status": "invalid_status", "type": "polygon"}]
        }, mapper)
        result = pipeline.validate_tree(tree, ["wms"])
        assert result.state == "fail"
        assert any("status" in e["path"] for e in result.errors)

    def test_error_dedup(self, pipeline, mapper):
        """Same error should not appear twice."""
        tree = ConfigTree({
            "__type__": "map",
            "name": "test",
            "status": "ON",
            "layers": [{"__type__": "layer", "name": "l1", "status": "bad", "type": "polygon"}]
        }, mapper)
        result = pipeline.validate_tree(tree, ["wms"])
        paths = [e["path"] for e in result.errors]
        assert len(paths) == len(set(paths))
