"""Tests for ConfigTree, TreeNode, and TreeLeaf."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/core is on PYTHONPATH
_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from config_tree import ConfigTree, TreeLeaf, TreeNode
from template_mapper import FieldDescriptor, TemplateMapper

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


@pytest.fixture
def empty_map():
    """Minimal mappyfile MAP dict."""
    return {"__type__": "map"}


@pytest.fixture
def map_with_layer():
    return {
        "__type__": "map",
        "name": "test_map",
        "status": "on",
        "layers": [
            {
                "__type__": "layer",
                "name": "layer1",
                "status": "on",
                "connectiontype": "postgis",
            },
        ],
    }


@pytest.fixture
def map_with_class_and_style():
    return {
        "__type__": "map",
        "layers": [
            {
                "__type__": "layer",
                "name": "layer1",
                "classes": [
                    {
                        "__type__": "class",
                        "name": "class1",
                        "styles": [
                            {"__type__": "style", "color": [255, 0, 0]},
                        ],
                        "labels": [
                            {"__type__": "label", "text": "[name]"},
                        ],
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Phase 1: TreeNode / TreeLeaf basics
# ---------------------------------------------------------------------------


class TestTreeNode:
    def test_create(self):
        node = TreeNode(id="map_0", path="map", object_type="MAP")
        assert node.id == "map_0"
        assert node.path == "map"
        assert node.object_type == "MAP"
        assert node.children == []
        assert node.expanded is True

    def test_leaves_and_nodes(self):
        leaf1 = TreeLeaf(
            id="map_name", path="map.name", key="name",
            descriptor=FieldDescriptor(key="name", value_type="string"),
            value="test",
        )
        leaf2 = TreeLeaf(
            id="map_status", path="map.status", key="status",
            descriptor=FieldDescriptor(key="status", value_type="enum"),
            value="on",
        )
        subnode = TreeNode(id="layer_0", path="layers.0", object_type="LAYER")
        node = TreeNode(id="map", path="map", object_type="MAP", children=[leaf1, subnode, leaf2])

        assert node.leaves() == [leaf1, leaf2]
        assert node.nodes() == [subnode]


class TestTreeLeaf:
    def test_create(self):
        fd = FieldDescriptor(key="name", value_type="string")
        leaf = TreeLeaf(id="map_name", path="map.name", key="name", descriptor=fd, value="test")
        assert leaf.key == "name"
        assert leaf.value == "test"
        assert leaf.user_modified is False
        assert leaf.errors == []


# ---------------------------------------------------------------------------
# Phase 2: ConfigTree build — simple MAP
# ---------------------------------------------------------------------------


class TestConfigTreeBuildSimple:
    def test_build_empty_map(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        assert tree.root.object_type == "MAP"
        assert tree.root.path == "map"

    def test_build_map_with_fields(self, mapper):
        params = {"__type__": "map", "name": "my_map", "status": "on"}
        tree = ConfigTree(params, mapper)
        leaf = tree.get_node("map.name")
        assert leaf is not None
        assert isinstance(leaf, TreeLeaf)
        assert leaf.value == "my_map"

    def test_build_map_layers(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        layer_node = tree.get_node("layers.0")
        assert layer_node is not None
        assert isinstance(layer_node, TreeNode)
        assert layer_node.object_type == "LAYER"

    def test_build_nested_class(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        class_node = tree.get_node("layers.0.classes.0")
        assert class_node is not None
        assert class_node.object_type == "CLASS"

    def test_build_nested_style(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        style_node = tree.get_node("layers.0.classes.0.styles.0")
        assert style_node is not None
        assert style_node.object_type == "STYLE"

    def test_build_nested_label(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        label_node = tree.get_node("layers.0.classes.0.labels.0")
        assert label_node is not None
        assert label_node.object_type == "LABEL"


# ---------------------------------------------------------------------------
# Phase 3: Service type filtering
# ---------------------------------------------------------------------------


class TestConfigTreeServiceFiltering:
    def test_ows_always_visible(self, mapper):
        params = {
            "__type__": "map",
            "web": {
                "__type__": "web",
                "metadata": {
                    "ows_title": "My Map",
                    "wms_title": "WMS Title",
                },
            },
        }
        # Without WMS, wms_* should not be visible; ows_* should still be visible
        tree = ConfigTree(params, mapper, service_types=[])
        ows_leaf = tree.get_node("web.metadata.ows_title")
        wms_leaf = tree.get_node("web.metadata.wms_title")
        assert ows_leaf is not None
        assert wms_leaf is None

    def test_wms_field_visible_when_wms_enabled(self, mapper):
        params = {
            "__type__": "map",
            "web": {
                "__type__": "web",
                "metadata": {
                    "wms_title": "WMS Title",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=["wms"])
        leaf = tree.get_node("web.metadata.wms_title")
        assert leaf is not None
        assert leaf.value == "WMS Title"

    def test_wfs_field_visible_when_wfs_enabled(self, mapper):
        params = {
            "__type__": "map",
            "web": {
                "__type__": "web",
                "metadata": {
                    "wfs_title": "WFS Title",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=["wfs"])
        leaf = tree.get_node("web.metadata.wfs_title")
        assert leaf is not None
        assert leaf.value == "WFS Title"

    def test_wfs_field_hidden_when_wfs_disabled(self, mapper):
        params = {
            "__type__": "map",
            "web": {
                "__type__": "web",
                "metadata": {
                    "wfs_title": "WFS Title",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=["wms"])
        leaf = tree.get_node("web.metadata.wfs_title")
        assert leaf is None

    def test_wcs_field_visible_when_wcs_enabled(self, mapper):
        params = {
            "__type__": "map",
            "web": {
                "__type__": "web",
                "metadata": {
                    "wcs_title": "WCS Title",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=["wcs"])
        leaf = tree.get_node("web.metadata.wcs_title")
        assert leaf is not None

    def test_gml_field_visible_when_wfs_enabled(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "name": "l1",
                    "metadata": {
                        "gml_featureid": "id",
                    },
                },
            ],
        }
        tree = ConfigTree(params, mapper, service_types=["wfs"])
        leaf = tree.get_node("layers.0.metadata.gml_featureid")
        assert leaf is not None

    def test_gml_field_hidden_when_wfs_disabled(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "name": "l1",
                    "metadata": {
                        "gml_featureid": "id",
                    },
                },
            ],
        }
        tree = ConfigTree(params, mapper, service_types=["wms"])
        leaf = tree.get_node("layers.0.metadata.gml_featureid")
        assert leaf is None


# ---------------------------------------------------------------------------
# Phase 4: Custom properties
# ---------------------------------------------------------------------------


class TestConfigTreeCustomProperties:
    def test_custom_property_expanded(self, mapper):
        params = {
            "__type__": "map",
            "_custom": {
                "my_filter": {"value": "type='a'", "type": "string", "desc": "Custom filter"},
            },
        }
        tree = ConfigTree(params, mapper)
        leaf = tree.get_node("map.my_filter")
        assert leaf is not None
        assert leaf.value == "type='a'"
        assert leaf.descriptor.custom is True


# ---------------------------------------------------------------------------
# Phase 5: Data access
# ---------------------------------------------------------------------------


class TestConfigTreeAccess:
    def test_get_node_root(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        assert tree.get_node("map") == tree.root

    def test_get_node_none_for_missing(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        assert tree.get_node("map.nonexistent") is None

    def test_get_node_nested(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        node = tree.get_node("layers.0")
        assert node is not None
        assert node.object_type == "LAYER"

    def test_get_node_leaf(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        leaf = tree.get_node("layers.0.name")
        assert leaf is not None
        assert isinstance(leaf, TreeLeaf)
        assert leaf.value == "layer1"


# ---------------------------------------------------------------------------
# Phase 6: Data mutation
# ---------------------------------------------------------------------------


class TestConfigTreeUpdateValue:
    def test_update_value_writes_to_params(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        tree.update_value("name", "updated_name")
        assert tree.params["name"] == "updated_name"

    def test_update_value_updates_leaf(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        tree.update_value("name", "updated_name")
        leaf = tree.get_node("name")
        assert leaf.value == "updated_name"

    def test_update_value_nested(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        tree.update_value("layers.0.name", "new_layer_name")
        assert tree.params["layers"][0]["name"] == "new_layer_name"

    def test_update_value_user_modified_flag(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        tree.update_value("name", "x")
        leaf = tree.get_node("name")
        assert leaf.user_modified is True

    def test_update_value_system_modified(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        tree.update_value("name", "x", user_modified=False)
        leaf = tree.get_node("name")
        assert leaf.user_modified is False


class TestConfigTreeAddObject:
    def test_add_layer(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        new_node = tree.add_object("map", "LAYER")
        assert new_node.object_type == "LAYER"
        assert tree.params["layers"][0]["__type__"] == "layer"

    def test_add_class(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        new_node = tree.add_object("layers.0", "CLASS")
        assert new_node.object_type == "CLASS"
        assert tree.params["layers"][0]["classes"][0]["__type__"] == "class"

    def test_add_style(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        new_node = tree.add_object("layers.0.classes.0", "STYLE")
        assert new_node.object_type == "STYLE"
        assert len(tree.params["layers"][0]["classes"][0]["styles"]) == 2

    def test_add_label(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        new_node = tree.add_object("layers.0.classes.0", "LABEL")
        assert new_node.object_type == "LABEL"
        assert len(tree.params["layers"][0]["classes"][0]["labels"]) == 2

    def test_add_metadata(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        new_node = tree.add_object("layers.0", "METADATA")
        assert new_node.object_type == "METADATA"
        assert "metadata" in tree.params["layers"][0]

    def test_add_web(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        new_node = tree.add_object("map", "WEB")
        assert new_node.object_type == "WEB"
        assert tree.params["web"]["__type__"] == "web"

    def test_add_cache(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        new_node = tree.add_object("map", "CACHE")
        assert new_node.object_type == "CACHE"
        assert "cache" in tree.params


class TestConfigTreeRemoveObject:
    def test_remove_layer(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        tree.remove_object("layers.0")
        assert tree.params.get("layers") in (None, [])

    def test_remove_class(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        tree.remove_object("layers.0.classes.0")
        assert tree.params["layers"][0].get("classes") in (None, [])

    def test_remove_style(self, mapper, map_with_class_and_style):
        tree = ConfigTree(map_with_class_and_style, mapper)
        tree.remove_object("layers.0.classes.0.styles.0")
        assert tree.params["layers"][0]["classes"][0].get("styles") in (None, [])

    def test_remove_metadata(self, mapper, map_with_layer):
        params = {
            "__type__": "map",
            "layers": [
                {"__type__": "layer", "name": "l1", "metadata": {"title": "t"}},
            ],
        }
        tree = ConfigTree(params, mapper)
        tree.remove_object("layers.0.metadata")
        assert "metadata" not in tree.params["layers"][0]


class TestConfigTreeAddCustomProperty:
    def test_add_custom(self, mapper, empty_map):
        tree = ConfigTree(empty_map, mapper)
        tree.add_custom_property("map", "custom_key", "custom_value", "string", "desc")
        assert tree.params["_custom"]["custom_key"]["value"] == "custom_value"
        leaf = tree.get_node("map.custom_key")
        assert leaf is not None
        assert leaf.value == "custom_value"
        assert leaf.descriptor.custom is True


# ---------------------------------------------------------------------------
# Phase 7: Serialization — 7 mandatory transforms
# ---------------------------------------------------------------------------


class TestConfigTreeSerialize:
    def test_transform_1_custom_expansion(self, mapper):
        params = {
            "__type__": "map",
            "name": "x",
            "_custom": {"filter": {"value": "type='a'", "type": "string"}},
        }
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert "_custom" not in result
        assert result["filter"] == "type='a'"
        assert result["name"] == "x"

    def test_transform_2_cache_strip(self, mapper):
        params = {"__type__": "map", "name": "x", "cache": {"type": "disk"}}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert "cache" not in result
        assert result["name"] == "x"

    def test_transform_3_array_wrap_layers(self, mapper):
        params = {"__type__": "map", "layers": {"name": "x"}}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert isinstance(result["layers"], list)
        assert result["layers"][0]["name"] == "x"

    def test_transform_3_array_wrap_classes(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "classes": {"name": "c1"},
                },
            ],
        }
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert isinstance(result["layers"][0]["classes"], list)

    def test_transform_3_array_wrap_styles(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "classes": [
                        {
                            "__type__": "class",
                            "styles": {"color": [255, 0, 0]},
                        },
                    ],
                },
            ],
        }
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert isinstance(result["layers"][0]["classes"][0]["styles"], list)

    def test_transform_3_array_wrap_labels(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "classes": [
                        {
                            "__type__": "class",
                            "labels": {"text": "[name]"},
                        },
                    ],
                },
            ],
        }
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert isinstance(result["layers"][0]["classes"][0]["labels"], list)

    def test_transform_4_status_bool_to_string(self, mapper):
        params = {"__type__": "map", "status": True}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["status"] == "ON"

    def test_transform_4_status_false_to_off(self, mapper):
        params = {"__type__": "map", "status": False}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["status"] == "OFF"

    def test_transform_4_status_string_unchanged(self, mapper):
        params = {"__type__": "map", "status": "on"}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["status"] == "on"

    def test_transform_5_projection_array_guard(self, mapper):
        params = {"__type__": "map", "projection": ["init=epsg:3857"]}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["projection"] == ["init=epsg:3857"]

    def test_transform_6_extent_array_guard(self, mapper):
        params = {"__type__": "map", "extent": [-180, -90, 180, 90]}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["extent"] == [-180, -90, 180, 90]

    def test_transform_7_color_rgb_guard(self, mapper):
        params = {
            "__type__": "map",
            "layers": [
                {
                    "__type__": "layer",
                    "classes": [
                        {
                            "__type__": "class",
                            "styles": [{"__type__": "style", "color": [255, 0, 0]}],
                        },
                    ],
                },
            ],
        }
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["layers"][0]["classes"][0]["styles"][0]["color"] == [255, 0, 0]

    def test_nested_dict_preserved(self, mapper):
        """Ensure nested dicts (like __type__) survive serialization."""
        params = {"__type__": "map", "name": "x"}
        tree = ConfigTree(params, mapper)
        result = tree.to_mappyfile_dict()
        assert result["__type__"] == "map"
        assert result["name"] == "x"

    def test_list_of_dicts_preserved(self, mapper, map_with_layer):
        tree = ConfigTree(map_with_layer, mapper)
        result = tree.to_mappyfile_dict()
        assert isinstance(result["layers"], list)
        assert result["layers"][0]["name"] == "layer1"


# ---------------------------------------------------------------------------
# Auto-fill service defaults (proposal-0015)
# ---------------------------------------------------------------------------


class TestAutoFillServiceDefaults:
    """Tests for ConfigTree.auto_fill_service_defaults()."""

    def test_fill_wms_defaults(self, mapper):
        """勾选 WMS 时自动填充 wms_enable_request 和 wms_srs 默认值."""
        params = {"__type__": "map"}
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wms"])

        web_meta = params.get("web", {}).get("metadata", {})
        assert web_meta.get("wms_enable_request") == "*"
        assert web_meta.get("wms_srs") == "EPSG:3857 EPSG:4326"
        assert web_meta.get("wms_include_items") == "all"
        # Verify return value
        assert len(filled) == 3
        assert any(f["field"] == "wms_enable_request" for f in filled)

    def test_fill_wfs_defaults(self, mapper):
        """勾选 WFS 时自动填充 wfs_enable_request 和 wfs_srs 默认值."""
        params = {"__type__": "map"}
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wfs"])

        web_meta = params.get("web", {}).get("metadata", {})
        assert web_meta.get("wfs_enable_request") == "*"
        assert web_meta.get("wfs_srs") == "EPSG:4326"

    def test_fill_wcs_defaults(self, mapper):
        """勾选 WCS 时自动填充 wcs_enable_request 和 wcs_srs 默认值."""
        params = {"__type__": "map"}
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wcs"])

        web_meta = params.get("web", {}).get("metadata", {})
        assert web_meta.get("wcs_enable_request") == "*"
        assert web_meta.get("wcs_srs") == "EPSG:3857"

    def test_no_override_existing_value(self, mapper):
        """已有值时不应被覆盖."""
        params = {
            "__type__": "map",
            "web": {
                "metadata": {
                    "wms_enable_request": "GetMap,GetCapabilities",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wms"])

        web_meta = params["web"]["metadata"]
        assert web_meta["wms_enable_request"] == "GetMap,GetCapabilities"
        # wms_srs should still be filled since it didn't exist
        assert web_meta.get("wms_srs") == "EPSG:3857 EPSG:4326"
        # Only wms_srs and wms_include_items should be in filled list
        assert len(filled) == 2

    def test_skip_when_ows_variant_exists(self, mapper):
        """如果 ows_* 通用字段已存在，跳过对应服务专用字段."""
        params = {
            "__type__": "map",
            "web": {
                "metadata": {
                    "ows_enable_request": "*",
                    "ows_srs": "EPSG:4326",
                },
            },
        }
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wms"])

        web_meta = params["web"]["metadata"]
        # wms_enable_request should NOT be filled because ows_enable_request exists
        assert "wms_enable_request" not in web_meta
        # wms_srs should NOT be filled because ows_srs exists
        assert "wms_srs" not in web_meta
        # wms_include_items is NOT a common suffix, so it SHOULD be filled
        assert web_meta.get("wms_include_items") == "all"
        assert len(filled) == 1
        assert filled[0]["field"] == "wms_include_items"

    def test_multiple_services_at_once(self, mapper):
        """同时勾选多个服务时，各自填充对应默认值."""
        params = {"__type__": "map"}
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["wms", "wfs"])

        web_meta = params.get("web", {}).get("metadata", {})
        assert web_meta.get("wms_enable_request") == "*"
        assert web_meta.get("wfs_enable_request") == "*"
        # WMS and WFS fields should not conflict
        assert web_meta.get("wms_srs") == "EPSG:3857 EPSG:4326"
        assert web_meta.get("wfs_srs") == "EPSG:4326"
        assert len(filled) == 5  # 3 WMS + 2 WFS

    def test_no_fill_for_unknown_service(self, mapper):
        """未知服务类型不产生错误."""
        params = {"__type__": "map"}
        tree = ConfigTree(params, mapper, service_types=[])

        filled = tree.auto_fill_service_defaults(["unknown_svc"])

        assert filled == []
        assert "web" not in params or params.get("web", {}).get("metadata", {}) == {}
