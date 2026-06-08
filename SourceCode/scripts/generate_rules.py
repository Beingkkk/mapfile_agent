#!/usr/bin/env python3
"""
generate_rules.py

从 mapfile-schema-8-4.json + 业务覆盖文件生成统一的 mapguide_rules.json。

================================================================================
数据来源层级（前置资源 → 派生资源）
================================================================================

【前置资源 1】MapServer 官方 JSON Schema
  来源: SourceCode/data/templates/mapfile-schema-8-4.json
  内容: Mapfile 语法规范 — 所有合法关键字、类型、枚举、范围、默认值

【前置资源 2】业务覆盖文件（人工维护）
  来源: SourceCode/data/templates/*.json
  内容:
    - aliases.json        自然语言/中文 → 参数值
    - required.json       必填/条件必填规则
    - phase-map.json      对象类型 → 阶段归属
    - defaults-override.json  默认值覆盖/补充
    - dependencies.json   跨字段依赖
    - custom-allowed.json 自定义属性白名单

【本脚本产物】mapguide_rules.json（最终派生资源）
  说明: 运行时唯一读取的规则文件。TemplateMapper 只加载此文件。
  输出: SourceCode/data/mapguide_rules.json

================================================================================
合并规则
================================================================================

  1. value_type:
       - Schema 有 enum                 → "enum"
       - Schema 类型已知                → 映射为内部类型
       - Schema 类型为 unknown 但有 enum → "enum"
       - 否则 fallback 到 "string"
  2. enum_values: 优先使用 Schema 的 enum；aliases.json 只提供别名映射，不改变合法值域
  3. default: defaults-override.json > schema default > None
  4. range: 从 Schema 的 minimum/maximum/minItems/maxItems 提取
  5. required / required_when / business_required: 从 required.json 继承
  6. phase: 从 phase-map.json 的对象类型映射（同一对象类型内所有字段共享阶段）
  7. aliases: 从 aliases.json 继承
  8. dependencies: 从 dependencies.json 继承
  9. custom_allowed: 从 custom-allowed.json 继承
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


# 对象类型在 JSON Schema 中的提取路径
SCHEMA_LOCATIONS = {
    "MAP": ["properties"],
    "LAYER": ["properties", "layers", "items", "properties"],
    "CLASS": ["properties", "layers", "items", "properties", "classes", "items", "properties"],
    "STYLE": [
        "properties", "layers", "items", "properties",
        "classes", "items", "properties", "styles", "items", "properties"
    ],
    "LABEL": [
        "properties", "layers", "items", "properties",
        "classes", "items", "properties", "labels", "items", "properties"
    ],
    "WEB": ["properties", "web", "properties"],
    "METADATA": ["properties", "web", "properties", "metadata", "properties"],
}

# 这些嵌套对象字段已有独立的 SCHEMA_LOCATIONS 路径展开，其余嵌套对象标记为不可编辑
EXPANDED_NESTED_FIELDS: dict[str, set[str]] = {
    "MAP": {"layers", "web"},
    "LAYER": {"classes", "metadata", "validation"},
    "CLASS": {"styles", "labels", "metadata", "validation"},
    "STYLE": set(),
    "LABEL": set(),
    "WEB": {"metadata", "validation"},
    "METADATA": set(),
    "CACHE": set(),
}

# JSON Schema 类型 → 内部 value_type
TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}



def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_schema_path(schema: dict, keys: list[str]) -> dict:
    current: Any = schema
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return {}
    return current if isinstance(current, dict) else {}


def infer_value_type(field_schema: dict) -> str:
    """根据 JSON Schema 字段定义推断内部 value_type。"""
    # enum 优先
    if "enum" in field_schema:
        return "enum"

    # oneOf 中如果有 enum 也认为是 enum
    if "oneOf" in field_schema:
        for opt in field_schema["oneOf"]:
            if "enum" in opt:
                return "enum"
            if "$ref" in opt and "color" in str(opt.get("$ref", "")).lower():
                return "color"

    raw_type = field_schema.get("type", "unknown")
    if raw_type in TYPE_MAP:
        return TYPE_MAP[raw_type]

    # 未知类型但字段名有业务暗示
    key = field_schema.get("_key", "").lower()
    if key in ("color", "outlinecolor", "imagecolor", "backgroundcolor"):
        return "color"
    if key in ("data", "filter", "requires"):
        return "expression"

    return "string"


def is_nested_object(field_schema: dict) -> bool:
    """检测字段是否代表一个内部有子字段但未展开的嵌套对象/数组。"""
    if field_schema.get("type") == "object" and field_schema.get("properties"):
        return True
    if field_schema.get("type") == "array":
        items = field_schema.get("items", {})
        if any(k in items for k in ("properties", "allOf", "$ref")):
            return True
    return False


def extract_field_info(field: str, field_schema: dict) -> dict[str, Any]:
    """从 JSON Schema 字段定义或 object-fields.json 中提取内部字段描述所需信息。"""
    field_schema = dict(field_schema)
    field_schema["_key"] = field

    # 来自 object-fields.json 的简化格式：直接提供 value_type/description/default/enum
    if "value_type" in field_schema:
        return {
            "value_type": field_schema["value_type"],
            "enum": field_schema.get("enum", []),
            "default": field_schema.get("default"),
            "description": field_schema.get("description", ""),
            "min": field_schema.get("min") or field_schema.get("minimum"),
            "max": field_schema.get("max") or field_schema.get("maximum"),
            "min_items": field_schema.get("min_items") or field_schema.get("minItems"),
            "max_items": field_schema.get("max_items") or field_schema.get("maxItems"),
            "editable": True,
        }

    info = {
        "value_type": infer_value_type(field_schema),
        "enum": field_schema.get("enum", []),
        "default": field_schema.get("default"),
        "description": field_schema.get("description", ""),
        "min": field_schema.get("minimum"),
        "max": field_schema.get("maximum"),
        "min_items": field_schema.get("minItems"),
        "max_items": field_schema.get("maxItems"),
        "editable": True,
    }

    # oneOf 中如果包含 enum 和 array，合并为更丰富的类型描述
    if "oneOf" in field_schema and not info["enum"]:
        enums = []
        for opt in field_schema["oneOf"]:
            if "enum" in opt:
                enums.extend(opt["enum"])
        if enums:
            info["enum"] = enums
            info["value_type"] = "enum"

    return info


def build_object_type_rules(
    object_type: str,
    schema_fields: dict[str, dict],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """为单个对象类型构建规则。"""
    fields: dict[str, dict] = {}

    # 合并 object-fields.json 中定义的业务补充字段（用于 METADATA / CACHE 等 schema 未枚举的场景）
    extra_fields = overrides.get("object_fields", {}).get(object_type, {})
    all_fields = dict(schema_fields)
    all_fields.update(extra_fields)

    expanded = EXPANDED_NESTED_FIELDS.get(object_type, set())

    for field, field_schema in all_fields.items():
        # 跳过 mappyfile 内部元字段
        if field.startswith("__"):
            continue

        info = extract_field_info(field, field_schema)

        # 检测是否为未展开的嵌套对象/数组，标记为不可编辑
        if is_nested_object(field_schema) and field not in expanded:
            info["editable"] = False

        # 应用 defaults-override
        override_default = overrides.get("defaults", {}).get(object_type, {}).get(field)
        if override_default is not None:
            info["default"] = override_default

        # 阶段：同一对象类型内所有字段共享
        info["phase"] = overrides.get("phase_map", {}).get(object_type, "service")

        fields[field] = {
            "key": field,
            "value_type": info["value_type"],
            "enum": info["enum"] if info["enum"] else None,
            "default": info["default"],
            "description": info["description"],
            "min": info["min"],
            "max": info["max"],
            "min_items": info["min_items"],
            "max_items": info["max_items"],
            "phase": info["phase"],
            "derived": False,
            "editable": info.get("editable", True),
        }

    # 应用 required 规则
    required_cfg = overrides.get("required", {}).get(object_type, {})

    return {
        "fields": fields,
        "required": required_cfg.get("required", []),
        "business_required": required_cfg.get("business_required", []),
        "required_when": required_cfg.get("required_when", {}),
    }


def build_flat_params(object_types: dict[str, dict]) -> dict[str, dict]:
    """把对象类型规则展开为带索引的扁平路径（主要用于 Prompt 和运行时快速索引）。"""
    flat: dict[str, dict] = {}

    # MAP
    for field, info in object_types.get("MAP", {}).get("fields", {}).items():
        flat[f"map.{field}"] = {**info, "path": f"map.{field}"}

    # LAYER / CLASS / STYLE / LABEL 使用 N/M/K/P 占位符
    for field, info in object_types.get("LAYER", {}).get("fields", {}).items():
        flat[f"layers.N.{field}"] = {**info, "path": f"layers.N.{field}"}

    for field, info in object_types.get("CLASS", {}).get("fields", {}).items():
        flat[f"layers.N.classes.M.{field}"] = {**info, "path": f"layers.N.classes.M.{field}"}

    for field, info in object_types.get("STYLE", {}).get("fields", {}).items():
        flat[f"layers.N.classes.M.styles.K.{field}"] = {**info, "path": f"layers.N.classes.M.styles.K.{field}"}

    for field, info in object_types.get("LABEL", {}).get("fields", {}).items():
        flat[f"layers.N.classes.M.labels.P.{field}"] = {**info, "path": f"layers.N.classes.M.labels.P.{field}"}

    # WEB / METADATA
    for field, info in object_types.get("WEB", {}).get("fields", {}).items():
        flat[f"map.web.{field}"] = {**info, "path": f"map.web.{field}"}

    for field, info in object_types.get("METADATA", {}).get("fields", {}).items():
        flat[f"map.web.metadata.{field}"] = {**info, "path": f"map.web.metadata.{field}"}
        # LAYER 级别 metadata 共享同一套字段定义
        flat[f"layers.N.metadata.{field}"] = {**info, "path": f"layers.N.metadata.{field}"}
        # CLASS 级别 metadata 同样共享同一套字段定义
        flat[f"layers.N.classes.M.metadata.{field}"] = {**info, "path": f"layers.N.classes.M.metadata.{field}"}

    # CACHE
    for field, info in object_types.get("CACHE", {}).get("fields", {}).items():
        flat[f"cache.{field}"] = {**info, "path": f"cache.{field}"}

    return flat


def inject_derived_params(object_types: dict[str, dict], dependencies: list[dict]) -> None:
    """根据 dependencies 中的 derives 关系，把目标字段标记为 derived。"""
    derived_targets = {edge["target"] for edge in dependencies if edge.get("relation") == "derives"}

    # 简化：根据字段名模糊匹配（METADATA.wms_onlineresource, CACHE.grid）
    for obj_type, obj_rules in object_types.items():
        for field, info in obj_rules.get("fields", {}).items():
            full_name = f"{obj_type}.{field}"
            if full_name in derived_targets:
                info["derived"] = True


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    templates_dir = repo_root / "data" / "templates"
    data_dir = repo_root / "data"

    # 加载前置资源
    schema = load_json(templates_dir / "mapfile-schema-8-4.json")
    overrides = {
        "aliases": load_json(templates_dir / "aliases.json"),
        "required": load_json(templates_dir / "required.json"),
        "phase_map": load_json(templates_dir / "phase-map.json"),
        "defaults": load_json(templates_dir / "defaults-override.json"),
        "dependencies": load_json(templates_dir / "dependencies.json"),
        "custom_allowed": load_json(templates_dir / "custom-allowed.json"),
        "object_fields": load_json(templates_dir / "object-fields.json"),
        "service_metadata": load_json(templates_dir / "service-metadata.json"),
    }

    # 清理内部描述字段
    for key in list(overrides.keys()):
        if isinstance(overrides[key], dict):
            overrides[key].pop("_description", None)

    # 构建各对象类型规则
    object_types: dict[str, dict] = {}
    for object_type, keys in SCHEMA_LOCATIONS.items():
        schema_fields = resolve_schema_path(schema, keys)
        object_types[object_type] = build_object_type_rules(object_type, schema_fields, overrides)

    # CACHE 不在 Mapfile Schema 中，完全由 object-fields.json 提供字段定义
    object_types["CACHE"] = build_object_type_rules("CACHE", {}, overrides)

    # 注入 derived 标记
    dependencies = overrides.get("dependencies", {}).get("edges", [])
    inject_derived_params(object_types, dependencies)

    # 构建统一规则
    rules = {
        "version": "1.0.0",
        "mapserver_version": "8.4",
        "description": "MapGuide 统一规则文件：合并 mapfile-schema-8-4.json 与业务覆盖规则",
        "object_types": object_types,
        "flat_params": build_flat_params(object_types),
        "aliases": overrides["aliases"],
        "dependencies": overrides["dependencies"],
        "phase_map": overrides["phase_map"],
        "custom_allowed": overrides["custom_allowed"],
        "service_metadata": overrides["service_metadata"],
    }

    # 写入产物
    output_path = data_dir / "mapguide_rules.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    # 统计
    field_count = sum(len(obj.get("fields", {})) for obj in object_types.values())
    alias_count = sum(
        sum(len(v2) for v2 in v1.values())
        for v1 in overrides["aliases"].values()
        if isinstance(v1, dict)
    )
    dep_count = len(dependencies)

    print(f"Generated: {output_path}")
    print(f"  Object types: {len(object_types)}")
    print(f"  Total fields: {field_count}")
    print(f"  Aliases:      {alias_count}")
    print(f"  Dependencies: {dep_count}")

    for obj_type, obj_rules in object_types.items():
        req = obj_rules.get("required", [])
        when = obj_rules.get("required_when", {})
        biz = obj_rules.get("business_required", [])
        fields = len(obj_rules.get("fields", {}))
        print(f"  {obj_type:10s}: {fields} fields, {len(req)} required, {len(when)} required_when, {len(biz)} business_required")

    return 0


if __name__ == "__main__":
    sys.exit(main())
