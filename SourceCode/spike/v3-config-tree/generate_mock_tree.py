#!/usr/bin/env python3
"""
从 mapguide_rules.json 生成 V3 spike 所需的 mock_tree.js
生成带模拟值的嵌套树结构：MAP → LAYER → CLASS → STYLE/LABEL
"""
import json
import random
import os

# 固定随机种子，保证可复现
random.seed(42)

RULES_PATH = os.path.join(os.path.dirname(__file__), "../../data/mapguide_rules.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "src/data/mock_tree.js")

PHASE_COLORS = {
    "datasource": "blue",
    "style": "orange",
    "service": "green",
    "cache": "purple",
}


def mock_value(field_def):
    """根据字段定义生成模拟值"""
    vt = field_def.get("value_type", "string")
    enum = field_def.get("enum")
    default = field_def.get("default")
    min_v = field_def.get("min")
    max_v = field_def.get("max")
    min_items = field_def.get("min_items")
    max_items = field_def.get("max_items")
    key = field_def.get("key", "")

    # 有默认值优先用默认值
    if default is not None:
        return default

    if enum:
        return enum[0]

    if vt == "string":
        if "path" in key or "file" in key:
            return "/data/example.shp"
        if "connection" in key and key != "connectiontype":
            return "host=localhost dbname=gis user=postgres"
        if key == "name":
            return "example"
        if key == "projection":
            return ["init=epsg:3857"]
        if key == "template":
            return "template.html"
        if key == "header" or key == "footer":
            return "header.html"
        if key == "symbol":
            return "circle"
        if key == "filter":
            return "[type]='road'"
        if key == "expression":
            return "([type] = 'road')"
        return "example_value"

    if vt == "integer":
        lo = min_v if min_v is not None else 0
        hi = max_v if max_v is not None else 100
        return random.randint(int(lo), int(hi))

    if vt == "float":
        lo = min_v if min_v is not None else 0.0
        hi = max_v if max_v is not None else 100.0
        return round(random.uniform(lo, hi), 2)

    if vt == "boolean":
        return True

    if vt == "array":
        if min_items == 4 and max_items == 4:
            return [-180, -90, 180, 90]  # extent
        if min_items == 2 and max_items == 2:
            return [800, 600]  # size
        if min_items == 3 and max_items == 3:
            return [255, 0, 0]  # color-like
        return ["item1", "item2"]

    if vt == "color":
        return [random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]

    if vt == "enum":
        return "on"

    if vt == "object":
        return {}

    return None


def build_field_node(key, field_def, path_prefix):
    """构建叶子字段节点"""
    phase = field_def.get("phase", "service")
    return {
        "type": "field",
        "name": key,
        "path": f"{path_prefix}.{key}" if path_prefix else key,
        "value": mock_value(field_def),
        "valueType": field_def.get("value_type", "string"),
        "phase": phase,
        "phaseColor": PHASE_COLORS.get(phase, "gray"),
        "required": field_def.get("required", False),
        "default": field_def.get("default"),
        "description": field_def.get("description", ""),
        "enum": field_def.get("enum"),
        "min": field_def.get("min"),
        "max": field_def.get("max"),
        "editable": field_def.get("editable", True),
    }


def build_object_node(object_type, name, path, children, phase_override=None):
    """构建对象容器节点"""
    phase = phase_override or "service"
    return {
        "type": "object",
        "objectType": object_type,
        "name": name,
        "path": path,
        "phase": phase,
        "phaseColor": PHASE_COLORS.get(phase, "gray"),
        "children": children,
    }


def build_fields(object_type, rules, path_prefix, include_keys=None, exclude_keys=None):
    """为对象类型构建字段列表"""
    fields_def = rules["object_types"][object_type]["fields"]
    nodes = []
    for key, fd in fields_def.items():
        if include_keys and key not in include_keys:
            continue
        if exclude_keys and key in exclude_keys:
            continue
        if not fd.get("editable", True):
            continue
        nodes.append(build_field_node(key, fd, path_prefix))
    return nodes


def build_tree(rules):
    """构建完整模拟树"""

    # --- STYLE ---
    style_fields = build_fields("STYLE", rules, "layers.0.classes.0.styles.0")
    style_node = build_object_node("STYLE", "styles.0", "layers.0.classes.0.styles.0", style_fields, "style")

    # --- LABEL ---
    label_fields = build_fields("LABEL", rules, "layers.0.classes.0.labels.0")
    label_node = build_object_node("LABEL", "labels.0", "layers.0.classes.0.labels.0", label_fields, "style")

    # --- CLASS ---
    class_fields = build_fields("CLASS", rules, "layers.0.classes.0", exclude_keys={"styles", "labels"})
    class_children = class_fields + [style_node, label_node]
    class_node = build_object_node("CLASS", "classes.0", "layers.0.classes.0", class_children, "style")

    # --- LAYER METADATA ---
    layer_metadata_fields = build_fields("METADATA", rules, "layers.0.metadata")
    layer_metadata_node = build_object_node("METADATA", "metadata", "layers.0.metadata", layer_metadata_fields, "service")

    # --- LAYER ---
    layer_fields = build_fields("LAYER", rules, "layers.0", exclude_keys={"classes", "metadata"})
    layer_children = layer_fields + [layer_metadata_node, class_node]
    layer_node = build_object_node("LAYER", "layers.0", "layers.0", layer_children, "datasource")

    # --- WEB METADATA ---
    web_metadata_fields = build_fields("METADATA", rules, "web.metadata")
    # 只选几个WMS相关的metadata字段作为示例
    wms_meta_keys = ["wms_title", "wms_abstract", "wms_enable_request", "wms_srs", "ows_enable_request", "ows_title"]
    web_metadata_fields = [f for f in web_metadata_fields if f["name"] in wms_meta_keys or f["name"].startswith("ows_")]
    web_metadata_node = build_object_node("METADATA", "metadata", "web.metadata", web_metadata_fields, "service")

    # --- WEB ---
    web_fields = build_fields("WEB", rules, "web", exclude_keys={"metadata"})
    web_children = web_fields + [web_metadata_node]
    web_node = build_object_node("WEB", "web", "web", web_children, "service")

    # --- CACHE ---
    cache_fields = build_fields("CACHE", rules, "cache")
    cache_node = build_object_node("CACHE", "cache", "cache", cache_fields, "cache")

    # --- MAP ---
    map_fields = build_fields("MAP", rules, "", exclude_keys={"layers", "web", "cache"})
    map_children = map_fields + [web_node, layer_node, cache_node]
    map_node = build_object_node("MAP", "MAP", "", map_children, "datasource")

    return map_node


def count_nodes(node):
    """统计节点数量"""
    if node.get("type") == "field":
        return 1
    count = 1
    for c in node.get("children", []):
        count += count_nodes(c)
    return count


def main():
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        rules = json.load(f)

    tree = build_tree(rules)
    total = count_nodes(tree)

    # 生成 JS 文件
    js_content = f"""// 由 generate_mock_tree.py 从 mapguide_rules.json 自动生成
// 总节点数: {total}

export const mockTree = {json.dumps(tree, ensure_ascii=False, indent=2)};

export const phaseColors = {json.dumps(PHASE_COLORS, ensure_ascii=False, indent=2)};

// 统计信息
export const stats = {{
  totalNodes: {total},
  objectTypes: ["MAP", "LAYER", "CLASS", "STYLE", "LABEL", "WEB", "METADATA", "CACHE"],
}};
"""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"[OK] mock_tree.js generated: {OUTPUT_PATH}")
    print(f"  Total nodes: {total}")
    print(f"  Object types: MAP, LAYER, CLASS, STYLE, LABEL, WEB, METADATA, CACHE")


if __name__ == "__main__":
    main()
