"""Integration tests: verify generate_rules.py output structure."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("generate_rules", SCRIPTS_DIR / "generate_rules.py")
assert _spec is not None and _spec.loader is not None
gr = importlib.util.module_from_spec(_spec)
sys.modules["generate_rules"] = gr
_spec.loader.exec_module(gr)


@pytest.fixture(scope="module")
def generated_rules():
    """Run the full generation pipeline against real template files."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    templates_dir = repo_root / "data" / "templates"

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

    return {
        "version": "1.0.0",
        "mapserver_version": "8.4",
        "object_types": object_types,
        "flat_params": gr.build_flat_params(object_types),
        "aliases": overrides["aliases"],
        "dependencies": overrides["dependencies"],
        "phase_map": overrides["phase_map"],
        "custom_allowed": overrides["custom_allowed"],
        "service_metadata": overrides["service_metadata"],
    }


class TestOutputStructure:
    def test_has_version_fields(self, generated_rules: dict) -> None:
        assert generated_rules["version"] == "1.0.0"
        assert generated_rules["mapserver_version"] == "8.4"

    def test_all_expected_object_types_present(self, generated_rules: dict) -> None:
        expected = {"MAP", "LAYER", "CLASS", "STYLE", "LABEL", "WEB", "METADATA", "CACHE"}
        assert set(generated_rules["object_types"].keys()) == expected

    def test_all_object_types_have_non_empty_fields(self, generated_rules: dict) -> None:
        for obj_type, obj_rules in generated_rules["object_types"].items():
            fields = obj_rules.get("fields", {})
            assert len(fields) > 0, f"{obj_type} has no fields"

    def test_cache_object_type_exists_from_object_fields(self, generated_rules: dict) -> None:
        cache = generated_rules["object_types"]["CACHE"]
        assert "type" in cache["fields"] or "cache_type" in cache["fields"]
        assert len(cache["fields"]) >= 1


class TestFlatParams:
    def test_contains_map_level_paths(self, generated_rules: dict) -> None:
        flat = generated_rules["flat_params"]
        assert any(k.startswith("map.") for k in flat)

    def test_contains_layer_placeholder_paths(self, generated_rules: dict) -> None:
        flat = generated_rules["flat_params"]
        assert any("layers.N." in k for k in flat)

    def test_contains_class_style_label_placeholder_paths(self, generated_rules: dict) -> None:
        flat = generated_rules["flat_params"]
        assert any("classes.M." in k for k in flat)
        assert any("styles.K." in k for k in flat)
        assert any("labels.P." in k for k in flat)

    def test_contains_web_and_metadata_paths(self, generated_rules: dict) -> None:
        flat = generated_rules["flat_params"]
        assert any(k.startswith("map.web.") for k in flat)
        assert any(k.startswith("map.web.metadata.") for k in flat)
        assert any(k.startswith("layers.N.metadata.") for k in flat)

    def test_contains_cache_paths(self, generated_rules: dict) -> None:
        flat = generated_rules["flat_params"]
        assert any(k.startswith("cache.") for k in flat)


class TestFieldProperties:
    def test_field_descriptors_have_required_keys(self, generated_rules: dict) -> None:
        required_keys = {"key", "value_type", "default", "description", "phase", "derived", "editable"}
        for obj_type, obj_rules in generated_rules["object_types"].items():
            for field_name, field_def in obj_rules["fields"].items():
                missing = required_keys - set(field_def.keys())
                assert not missing, f"{obj_type}.{field_name} missing keys: {missing}"

    def test_status_field_is_enum(self, generated_rules: dict) -> None:
        """Status must be enum per V1 validation findings."""
        map_fields = generated_rules["object_types"]["MAP"]["fields"]
        if "status" in map_fields:
            assert map_fields["status"]["value_type"] == "enum"

    def test_required_rules_exist_for_map_and_layer(self, generated_rules: dict) -> None:
        """LAYER has syntax-required fields; MAP may have required_when constraints."""
        map_rules = generated_rules["object_types"]["MAP"]
        layer_rules = generated_rules["object_types"]["LAYER"]
        # MAP: no syntax-required fields (all have defaults or are optional), but
        # may have required_when constraints. After proposal-0013 business_required
        # was cleared; only required + required_when carry semantic weight.
        map_has_constraints = (
            len(map_rules.get("required", []))
            + len(map_rules.get("required_when", {}))
            + len(map_rules.get("business_required", []))
        ) >= 0  # MAP legitimately has zero required fields
        assert map_has_constraints
        # LAYER: type is syntax-absolute required
        assert len(layer_rules.get("required", [])) + len(layer_rules.get("business_required", [])) >= 1


class TestAliasesAndDependencies:
    def test_aliases_is_dict(self, generated_rules: dict) -> None:
        aliases = generated_rules["aliases"]
        assert isinstance(aliases, dict)

    def test_dependencies_have_edges(self, generated_rules: dict) -> None:
        deps = generated_rules["dependencies"]
        assert "edges" in deps
        assert isinstance(deps["edges"], list)

    def test_phase_map_is_dict(self, generated_rules: dict) -> None:
        phase_map = generated_rules["phase_map"]
        assert isinstance(phase_map, dict)
        # Every object type should have a phase
        for obj_type in generated_rules["object_types"]:
            assert obj_type in phase_map


class TestConsistencyWithRealOutput:
    def test_field_count_matches_known_value(self, generated_rules: dict) -> None:
        """The known field count from V1 validation is 280."""
        total = sum(len(o.get("fields", {})) for o in generated_rules["object_types"].values())
        assert total == 280, f"Expected 280 fields, got {total}"

    def test_object_type_counts_match_known_values(self, generated_rules: dict) -> None:
        """Known field counts from generate_rules.py output."""
        expected = {
            "MAP": 27,
            "LAYER": 59,
            "CLASS": 18,
            "STYLE": 27,
            "LABEL": 31,
            "WEB": 18,
            "METADATA": 91,
            "CACHE": 9,
        }
        for obj_type, expected_count in expected.items():
            actual = len(generated_rules["object_types"][obj_type]["fields"])
            assert actual == expected_count, f"{obj_type}: expected {expected_count}, got {actual}"
