"""Tests for scripts/generate_rules.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# scripts/generate_rules.py lives outside the package tree; load it dynamically.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("generate_rules", SCRIPTS_DIR / "generate_rules.py")
assert _spec is not None and _spec.loader is not None
gr = importlib.util.module_from_spec(_spec)
sys.modules["generate_rules"] = gr
_spec.loader.exec_module(gr)


# -----------------------------------------------------------------------------
# load_json
# -----------------------------------------------------------------------------


class TestLoadJson:
    def test_loads_existing_json(self, tmp_path: Path) -> None:
        path = tmp_path / "sample.json"
        path.write_text(json.dumps({"a": 1}), encoding="utf-8")
        assert gr.load_json(path) == {"a": 1}

    def test_returns_empty_dict_when_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.json"
        assert gr.load_json(path) == {}


# -----------------------------------------------------------------------------
# resolve_schema_path
# -----------------------------------------------------------------------------


class TestResolveSchemaPath:
    def test_resolves_nested_keys(self) -> None:
        schema = {"a": {"b": {"c": {"name": "x"}}}}
        assert gr.resolve_schema_path(schema, ["a", "b", "c"]) == {"name": "x"}

    def test_returns_empty_dict_on_missing_key(self) -> None:
        schema = {"a": {"b": {}}}
        assert gr.resolve_schema_path(schema, ["a", "b", "c"]) == {}

    def test_returns_empty_dict_when_intermediate_is_not_dict(self) -> None:
        schema = {"a": [1, 2, 3]}
        assert gr.resolve_schema_path(schema, ["a", "b"]) == {}

    def test_returns_empty_dict_when_final_is_not_dict(self) -> None:
        schema = {"a": [1, 2, 3]}
        assert gr.resolve_schema_path(schema, ["a"]) == {}


# -----------------------------------------------------------------------------
# infer_value_type
# -----------------------------------------------------------------------------


class TestInferValueType:
    def test_enum_present_returns_enum(self) -> None:
        assert gr.infer_value_type({"enum": ["ON", "OFF"]}) == "enum"

    def test_oneof_with_enum_returns_enum(self) -> None:
        assert gr.infer_value_type({"oneOf": [{"enum": ["A"]}, {"type": "array"}]}) == "enum"

    def test_oneof_with_color_ref_returns_color(self) -> None:
        assert gr.infer_value_type({"oneOf": [{"$ref": "#/color"}]}) == "color"

    @pytest.mark.parametrize(
        "raw_type,expected",
        [
            ("string", "string"),
            ("number", "float"),
            ("integer", "integer"),
            ("boolean", "boolean"),
            ("array", "array"),
            ("object", "object"),
        ],
    )
    def test_mapped_types(self, raw_type: str, expected: str) -> None:
        assert gr.infer_value_type({"type": raw_type}) == expected

    @pytest.mark.parametrize(
        "key",
        ["color", "outlinecolor", "imagecolor", "backgroundcolor"],
    )
    def test_color_inferred_from_key_name(self, key: str) -> None:
        assert gr.infer_value_type({"type": "unknown", "_key": key}) == "color"

    @pytest.mark.parametrize("key", ["data", "filter", "requires"])
    def test_expression_inferred_from_key_name(self, key: str) -> None:
        assert gr.infer_value_type({"type": "unknown", "_key": key}) == "expression"

    def test_unknown_fallback_to_string(self) -> None:
        assert gr.infer_value_type({"type": "unknown", "_key": "something"}) == "string"


# -----------------------------------------------------------------------------
# is_nested_object
# -----------------------------------------------------------------------------


class TestIsNestedObject:
    def test_object_with_properties_is_nested(self) -> None:
        assert gr.is_nested_object({"type": "object", "properties": {"x": {}}}) is True

    def test_object_without_properties_is_not_nested(self) -> None:
        assert gr.is_nested_object({"type": "object"}) is False

    def test_array_with_items_properties_is_nested(self) -> None:
        assert gr.is_nested_object({"type": "array", "items": {"properties": {"x": {}}}}) is True

    def test_array_with_items_allof_is_nested(self) -> None:
        assert gr.is_nested_object({"type": "array", "items": {"allOf": []}}) is True

    def test_array_with_items_ref_is_nested(self) -> None:
        assert gr.is_nested_object({"type": "array", "items": {"$ref": "#"}}) is True

    def test_primitive_is_not_nested(self) -> None:
        assert gr.is_nested_object({"type": "string"}) is False


# -----------------------------------------------------------------------------
# extract_field_info
# -----------------------------------------------------------------------------


class TestExtractFieldInfo:
    def test_extracts_from_schema_definition(self) -> None:
        info = gr.extract_field_info("name", {
            "type": "string",
            "description": "Map name",
            "default": "default_map",
        })
        assert info["value_type"] == "string"
        assert info["description"] == "Map name"
        assert info["default"] == "default_map"
        assert info["editable"] is True

    def test_extracts_enum_from_schema(self) -> None:
        info = gr.extract_field_info("status", {"enum": ["ON", "OFF"]})
        assert info["value_type"] == "enum"
        assert info["enum"] == ["ON", "OFF"]

    def test_extracts_object_fields_simplified_format(self) -> None:
        info = gr.extract_field_info("wmts_enable", {
            "value_type": "boolean",
            "description": "Enable WMTS",
            "default": True,
        })
        assert info["value_type"] == "boolean"
        assert info["default"] is True
        assert info["description"] == "Enable WMTS"

    def test_oneof_enums_get_merged(self) -> None:
        info = gr.extract_field_info("projection", {
            "oneOf": [
                {"enum": ["epsg:4326"]},
                {"type": "array"},
            ]
        })
        assert info["enum"] == ["epsg:4326"]
        assert info["value_type"] == "enum"

    def test_min_max_aliases(self) -> None:
        info = gr.extract_field_info("opacity", {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        })
        assert info["min"] == 0
        assert info["max"] == 100

    def test_min_items_max_items_aliases(self) -> None:
        info = gr.extract_field_info("extent", {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
        })
        assert info["min_items"] == 4
        assert info["max_items"] == 4


# -----------------------------------------------------------------------------
# build_object_type_rules
# -----------------------------------------------------------------------------


class TestBuildObjectTypeRules:
    def test_builds_fields_from_schema(self) -> None:
        schema_fields = {
            "name": {"type": "string", "description": "Name"},
            "status": {"enum": ["ON", "OFF"]},
        }
        overrides = {
            "phase_map": {"MAP": "service"},
        }
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert "name" in rules["fields"]
        assert rules["fields"]["name"]["value_type"] == "string"
        assert rules["fields"]["status"]["value_type"] == "enum"

    def test_default_override_priority(self) -> None:
        schema_fields = {
            "name": {"type": "string", "default": "schema_default"},
        }
        overrides = {
            "phase_map": {"MAP": "service"},
            "defaults": {"MAP": {"name": "override_default"}},
        }
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["name"]["default"] == "override_default"

    def test_schema_default_used_when_no_override(self) -> None:
        schema_fields = {
            "name": {"type": "string", "default": "schema_default"},
        }
        overrides = {"phase_map": {"MAP": "service"}}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["name"]["default"] == "schema_default"

    def test_default_none_when_no_default(self) -> None:
        schema_fields = {"name": {"type": "string"}}
        overrides = {"phase_map": {"MAP": "service"}}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["name"]["default"] is None

    def test_phase_from_phase_map(self) -> None:
        schema_fields = {"name": {"type": "string"}}
        overrides = {"phase_map": {"MAP": "datasource"}}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["name"]["phase"] == "datasource"

    def test_unexpanded_nested_object_marked_non_editable(self) -> None:
        schema_fields = {
            "validation": {"type": "object", "properties": {"default": {}}},
        }
        overrides = {
            "phase_map": {"MAP": "service"},
        }
        # MAP.validation is not in EXPANDED_NESTED_FIELDS["MAP"] which is {"layers", "web"}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["validation"]["editable"] is False

    def test_expanded_nested_object_remains_editable(self) -> None:
        schema_fields = {
            "layers": {"type": "array", "items": {"properties": {}}},
        }
        overrides = {"phase_map": {"MAP": "service"}}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["fields"]["layers"]["editable"] is True

    def test_object_fields_supplement_schema(self) -> None:
        schema_fields = {}
        overrides = {
            "phase_map": {"CACHE": "cache"},
            "object_fields": {
                "CACHE": {
                    "type": {"value_type": "enum", "enum": ["disk", "sqlite"]},
                },
            },
        }
        rules = gr.build_object_type_rules("CACHE", schema_fields, overrides)
        assert "type" in rules["fields"]
        assert rules["fields"]["type"]["value_type"] == "enum"

    def test_skips_internal_meta_fields(self) -> None:
        schema_fields = {"__internal": {"type": "string"}, "name": {"type": "string"}}
        overrides = {"phase_map": {"MAP": "service"}}
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert "__internal" not in rules["fields"]
        assert "name" in rules["fields"]

    def test_required_rules_in_output(self) -> None:
        schema_fields = {"name": {"type": "string"}}
        overrides = {
            "phase_map": {"MAP": "service"},
            "required": {
                "MAP": {
                    "required": ["name"],
                    "business_required": ["extent"],
                    "required_when": {"projection": ["extent"]},
                },
            },
        }
        rules = gr.build_object_type_rules("MAP", schema_fields, overrides)
        assert rules["required"] == ["name"]
        assert rules["business_required"] == ["extent"]
        assert rules["required_when"] == {"projection": ["extent"]}


# -----------------------------------------------------------------------------
# build_flat_params
# -----------------------------------------------------------------------------


class TestBuildFlatParams:
    def test_builds_map_level_paths(self) -> None:
        object_types = {
            "MAP": {
                "fields": {
                    "name": {"key": "name", "value_type": "string"},
                },
            },
        }
        flat = gr.build_flat_params(object_types)
        assert "map.name" in flat
        assert flat["map.name"]["path"] == "map.name"

    def test_builds_layer_placeholder_paths(self) -> None:
        object_types = {
            "LAYER": {
                "fields": {
                    "connectiontype": {"key": "connectiontype", "value_type": "enum"},
                },
            },
        }
        flat = gr.build_flat_params(object_types)
        assert "layers.N.connectiontype" in flat

    def test_builds_nested_class_style_label_paths(self) -> None:
        object_types = {
            "CLASS": {"fields": {"name": {}}},
            "STYLE": {"fields": {"color": {}}},
            "LABEL": {"fields": {"text": {}}},
        }
        flat = gr.build_flat_params(object_types)
        assert "layers.N.classes.M.name" in flat
        assert "layers.N.classes.M.styles.K.color" in flat
        assert "layers.N.classes.M.labels.P.text" in flat

    def test_builds_web_and_metadata_paths(self) -> None:
        object_types = {
            "WEB": {"fields": {"template": {}}},
            "METADATA": {"fields": {"wms_title": {}}},
        }
        flat = gr.build_flat_params(object_types)
        assert "map.web.template" in flat
        assert "map.web.metadata.wms_title" in flat
        # LAYER metadata shares the same field definitions
        assert "layers.N.metadata.wms_title" in flat

    def test_builds_cache_paths(self) -> None:
        object_types = {
            "CACHE": {"fields": {"type": {}}},
        }
        flat = gr.build_flat_params(object_types)
        assert "cache.type" in flat

    def test_missing_object_type_is_silent(self) -> None:
        flat = gr.build_flat_params({})
        assert flat == {}


# -----------------------------------------------------------------------------
# inject_derived_params
# -----------------------------------------------------------------------------


class TestInjectDerivedParams:
    def test_marks_derived_fields(self) -> None:
        object_types = {
            "METADATA": {
                "fields": {
                    "wms_onlineresource": {"derived": False},
                    "wms_title": {"derived": False},
                },
            },
            "CACHE": {
                "fields": {
                    "grid": {"derived": False},
                },
            },
        }
        dependencies = [
            {"relation": "derives", "target": "METADATA.wms_onlineresource"},
            {"relation": "derives", "target": "CACHE.grid"},
            {"relation": "requires", "target": "METADATA.wms_title"},
        ]
        gr.inject_derived_params(object_types, dependencies)
        assert object_types["METADATA"]["fields"]["wms_onlineresource"]["derived"] is True
        assert object_types["CACHE"]["fields"]["grid"]["derived"] is True
        assert object_types["METADATA"]["fields"]["wms_title"]["derived"] is False


# -----------------------------------------------------------------------------
# main() integration smoke
# -----------------------------------------------------------------------------


class TestMainIntegration:
    def test_main_generates_rules_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        output_dir = tmp_path
        output_file = output_dir / "mapguide_rules.json"

        monkeypatch.setattr(gr, "main", lambda: _run_main_with_output(repo_root, output_file))
        gr.main()

        assert output_file.exists()
        rules = json.loads(output_file.read_text(encoding="utf-8"))
        assert rules["version"] == "1.0.0"
        assert rules["mapserver_version"] == "8.4"
        assert "object_types" in rules
        assert "flat_params" in rules
        assert set(rules["object_types"].keys()) == {
            "MAP", "LAYER", "CLASS", "STYLE", "LABEL", "WEB", "METADATA", "CACHE"
        }


def _run_main_with_output(repo_root: Path, output_file: Path) -> int:
    """Run main logic with a custom output path for testing."""
    templates_dir = repo_root / "data" / "templates"
    data_dir = output_file.parent

    schema = gr.load_json(templates_dir / "mapfile-schema-8-4.json")
    overrides = {
        "aliases": gr.load_json(templates_dir / "aliases.json"),
        "required": gr.load_json(templates_dir / "required.json"),
        "phase_map": gr.load_json(templates_dir / "phase-map.json"),
        "defaults": gr.load_json(templates_dir / "defaults-override.json"),
        "dependencies": gr.load_json(templates_dir / "dependencies.json"),
        "custom_allowed": gr.load_json(templates_dir / "custom-allowed.json"),
        "object_fields": gr.load_json(templates_dir / "object-fields.json"),
        "service_metadata": gr.load_json(templates_dir / "service-metadata.json"),
    }

    for key in list(overrides.keys()):
        if isinstance(overrides[key], dict):
            overrides[key].pop("_description", None)

    object_types: dict[str, dict] = {}
    for object_type, keys in gr.SCHEMA_LOCATIONS.items():
        schema_fields = gr.resolve_schema_path(schema, keys)
        object_types[object_type] = gr.build_object_type_rules(object_type, schema_fields, overrides)

    object_types["CACHE"] = gr.build_object_type_rules("CACHE", {}, overrides)

    dependencies = overrides.get("dependencies", {}).get("edges", [])
    gr.inject_derived_params(object_types, dependencies)

    rules = {
        "version": "1.0.0",
        "mapserver_version": "8.4",
        "description": "MapGuide unified rules",
        "object_types": object_types,
        "flat_params": gr.build_flat_params(object_types),
        "aliases": overrides["aliases"],
        "dependencies": overrides["dependencies"],
        "phase_map": overrides["phase_map"],
        "custom_allowed": overrides["custom_allowed"],
        "service_metadata": overrides["service_metadata"],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    return 0
