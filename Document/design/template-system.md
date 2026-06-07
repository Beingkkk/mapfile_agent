---
title: 模板资源体系
description: 模板资源结构、覆盖文件、生成链路、TemplateMapper、FieldDescriptor
---

## 2. 模板资源体系

### 2.1 主模板 `mapfile-schema-8-4.json`

该 Schema 由 mappyfile 项目维护，定义了 MapServer 8.4 的所有合法对象和属性。它是一个**自包含的完整 schema**（无外部 `$ref`），所有对象类型（MAP / LAYER / CLASS / STYLE / WEB 等）都在 `properties` 中直接或间接定义。

**我们从中提取的信息**：

| 字段 | 示例 | 用途 |
|------|------|------|
| `properties.{key}.type` | `"string"`, `"number"`, `"array"`, `"object"` | 决定前端控件类型（`object` 统一映射到 `ObjectViewer`） |
| `properties.{key}.enum` | `["on","off",0,1,2,3,4,5]` | 下拉选择框选项 |
| `properties.{key}.default` | `0`, `"png"` | 默认值（可被覆盖文件覆盖） |
| `properties.{key}.minimum/maximum` | `min: -360, max: 360` | 数值范围校验 |
| `properties.{key}.items` | `{ "type": "number" }` | 数组元素类型 |
| `properties.{key}.oneOf` | RGB 数组 或 hex 字符串 | 联合类型处理 |
| `additionalProperties` | `true` / `false` | 是否允许自定义属性 |

**Schema 不足需要补全的地方**（由覆盖文件补充）：

- **必填性**：Schema 没有 `required` 列表，必填规则由 `required.json` 补全
- **阶段归属**：参数属于 datasource/style/service/cache 哪个阶段，由 `phase-map.json` 映射
- **业务别名**：Schema 中没有 "红色" → `[255,0,0]` 这类别名，由 `aliases.json` 补全
- **条件依赖**：`connectiontype=postgis` 时 `connection` 必填，由 `dependencies.json` 补全
- **自定义属性白名单**：由 `custom-allowed.json` 定义（不完全依赖 schema 的 `additionalProperties`）

### 2.2 对象类型分层

所有覆盖文件**按对象类型分层**编写，而不是按带索引的扁平路径（如 `layers.0.type`）。

例如 `aliases.json`：

```json
{
  "LAYER": {
    "connectiontype": {
      "shapefile": "local",
      "shp": "local",
      "postgis": "postgis",
      "数据库": "postgis"
    },
    "type": {
      "点": "point",
      "线": "line",
      "面": "polygon"
    }
  },
  "STYLE": {
    "color": {
      "红": [255, 0, 0],
      "蓝": [0, 0, 255]
    }
  }
}
```

`required.json`：

```json
{
  "MAP": {
    "required": ["name", "imagetype"],
    "required_when": {}
  },
  "LAYER": {
    "required": ["name", "type", "connectiontype", "projection"],
    "required_when": {
      "connection": "connectiontype in ['postgis', 'ogr', 'wms']",
      "data": "connectiontype != 'wms'"
    }
  },
  "STYLE": {
    "required": [],
    "required_when": {
      "symbol": "parent.type == 'point'",
      "size": "parent.type == 'point'",
      "width": "parent.type in ['line', 'polygon']",
      "outlinecolor": "parent.type == 'polygon'"
    }
  }
}
```

生成脚本运行时会将对象类型规则展开为带索引的扁平路径（`layers.N.type`），写入 `mapguide_rules.json`。

### 2.3 业务补全文件

```
SourceCode/data/templates/
├── mapfile-schema-8-4.json # MapServer 官方 JSON Schema（类型、枚举、默认值）
├── aliases.json            # 别名映射（自然语言 → 参数值）
├── required.json           # 必填/条件必填规则（按对象类型，含服务类型条件）
├── phase-map.json          # 对象类型 → 阶段归属
├── defaults-override.json  # 覆盖/补充 schema 默认值
├── dependencies.json       # 跨字段依赖边（含服务类型条件）
├── custom-allowed.json     # 自定义属性白名单
├── service-metadata.json   # 服务类型 → METADATA 参数白名单映射
└── object-fields.json      # Schema 未覆盖的对象补充字段（METADATA、CACHE 等）
```

### 2.4 默认值优先级

同一个参数可能有多个默认值来源，优先级如下：

```
defaults-override.json  >  schema default  >  无默认值
```

| 场景 | 示例 | 最终规则来源 |
|------|------|-------------|
| Schema 有，业务也一致 | `imagetype` → `"png"` | schema default（override 不写） |
| Schema 没有，业务补充 | `wms_enable_request` → `"*"` | defaults-override.json |
| Schema 有，业务不同 | `projection` → `["init=epsg:3857"]` | defaults-override.json |
| 条件默认值 | `STYLE.color` 根据 `LAYER.type` 不同 | defaults-override.json 的 `conditional` 块 |
| 服务通用前缀 | `ows_title` 作为 WMS/WFS/WCS 的公共默认值 | defaults-override.json |

条件默认值示例：

```json
{
  "STYLE": {
    "conditional": {
      "parent.type == 'point'": {
        "color": [128, 128, 128],
        "symbol": "circle",
        "size": 8
      },
      "parent.type == 'polygon'": {
        "color": [200, 200, 200],
        "outlinecolor": [128, 128, 128],
        "width": 1
      }
    }
  }
}
```

### 2.5 生成链路

```
输入源（人工维护）
  ├── mapfile-schema-8-4.json       ← mappyfile 官方 schema
  ├── aliases.json
  ├── required.json
  ├── phase-map.json
  ├── defaults-override.json
  ├── dependencies.json
  ├── custom-allowed.json
  ├── service-metadata.json         ← 服务类型参数白名单
  └── object-fields.json            ← Schema 未覆盖字段
              │
              ▼
     scripts/generate_rules.py      ← 确定性合并脚本
              │
              ▼
  SourceCode/data/mapguide_rules.json  ← 运行时唯一读取
```

`mapguide_rules.json` 的结构：

```json
{
  "version": "1.0.0",
  "mapserver_version": "8.4",
  "object_types": {
    "MAP":     { "fields": { "name": {...}, ... }, "required": [...] },
    "LAYER":   { ... },
    "CLASS":   { ... },
    "STYLE":   { ... },
    "LABEL":   { ... },   // schema 定义，defaults-override.json 补充
    "WEB":     { ... },
    "METADATA":{ ... },
    "CACHE":   { ... }   // 完全由 object-fields.json 提供，schema 无定义
  },
  "flat_params": {
    "map.name": {...},
    "layers.0.name": {...},
    ...
  },
  "aliases": {...},
  "dependencies": [...],
  "phase_map": {...},
  "custom_allowed": {...}
}
```

运行时 `TemplateMapper` 只加载 `mapguide_rules.json` 一份文件，无需每次合并 schema + 覆盖文件。

### 2.6 服务类型与 METADATA 参数体系

新增模板资源 `service-metadata.json`，定义不同 OGC 服务对应的 METADATA 参数白名单：

```json
{
  "services": ["wms", "wfs", "wcs"],
  "common_prefix": "ows",
  "metadata_fields": {
    "ows": {
      "title": { "type": "string", "phase": "service", "required": false },
      "onlineresource": { "type": "string", "phase": "service", "required": false },
      "enable_request": { "type": "string", "phase": "service", "default": "*" }
    },
    "wms": {
      "title": { "type": "string", "phase": "service", "required": false },
      "onlineresource": { "type": "string", "phase": "service", "required": false },
      "enable_request": { "type": "string", "phase": "service", "default": "*" },
      "srs": { "type": "string", "phase": "service", "default": "EPSG:3857 EPSG:4326" },
      "extent": { "type": "string", "phase": "service", "required": false }
    },
    "wfs": {
      "title": { "type": "string", "phase": "service", "required": false },
      "onlineresource": { "type": "string", "phase": "service", "required": false },
      "enable_request": { "type": "string", "phase": "service", "default": "*" },
      "srs": { "type": "string", "phase": "service", "default": "EPSG:4326" }
    },
    "wcs": {
      "title": { "type": "string", "phase": "service", "required": false },
      "onlineresource": { "type": "string", "phase": "service", "required": false },
      "enable_request": { "type": "string", "phase": "service", "default": "*" },
      "srs": { "type": "string", "phase": "service", "default": "EPSG:3857" },
      "extent": { "type": "string", "phase": "service", "required": false }
    }
  }
}
```

**参数可见性规则**：

1. `ows_*` 参数**始终显示**（无论勾选哪些服务）
2. `wms_*` 参数仅当勾选 WMS 时显示
3. `wfs_*` 参数仅当勾选 WFS 时显示
4. `wcs_*` 参数仅当勾选 WCS 时显示
5. `gml_include_items` 等 WFS 专属 LAYER 参数仅当勾选 WFS 时显示
6. 取消勾选后，已填写的隐藏参数值**保留在 params 中**，只是不在 UI 上渲染

**通用前缀回退机制**（运行时逻辑，非模板定义）：

MapServer 在解析 METADATA 时，如果找不到服务专用前缀（如 `wms_title`），会回退到 `ows_title`。本应用**不实现**这一回退逻辑——后端直接按用户填写的值写入 METADATA，MapServer 在运行时自行处理。LLM 在回答时可以建议用户使用 `ows_*` 简化配置。

---

## 3. TemplateMapper 类设计

`TemplateMapper` 是后端唯一接触模板规则的入口。运行时它**只读取 `mapguide_rules.json`**，不直接读 schema 或覆盖文件。生成阶段由 `generate_rules.py` 负责把 schema + 覆盖文件合并成一份运行时规则。

```python
class TemplateMapper:
    """
    模板资源映射器：运行时读取 mapguide_rules.json。

    职责：
    1. 加载统一的 mapguide_rules.json
    2. 把规则中的字段定义解析为 FieldDescriptor
    3. 判断必填性、阶段归属、自定义属性允许性
    4. 为 LLM 上下文生成参数摘要（非完整 schema）
    """

    def __init__(self, rules_path: str):
        self.rules = load_json(rules_path)
        self.object_types = self.rules.get("object_types", {})
        self.flat_params = self.rules.get("flat_params", {})
        self.aliases = self.rules.get("aliases", {})
        self.dependencies = self.rules.get("dependencies", [])
        self.phase_map = self.rules.get("phase_map", {})
        self.custom_allowed = self.rules.get("custom_allowed", {})

    def get_object_type(self, object_type: str) -> dict:
        """获取某对象类型的完整规则。"""
        return self.object_types.get(object_type.upper(), {})

    def get_field_descriptor(self, object_type: str, field: str) -> FieldDescriptor:
        """
        获取字段描述符。

        返回：
            FieldDescriptor(
                key="angle",
                value_type="float",
                default=0,
                enum=None,
                min=-360,
                max=360,
                phase="service",
                required=False,
                derived=False,
                editable=True,
            )
        """
        obj = self.get_object_type(object_type)
        field_def = obj.get("fields", {}).get(field, {})
        return FieldDescriptor(
            key=field,
            value_type=field_def.get("value_type", "string"),
            default=field_def.get("default"),
            enum=field_def.get("enum"),
            min=field_def.get("min"),
            max=field_def.get("max"),
            phase=field_def.get("phase", "service"),
            required=field in obj.get("required", []),
            derived=field_def.get("derived", False),
            editable=field_def.get("editable", True),
            custom=False,
        )

    def allows_custom_properties(self, object_type: str) -> bool:
        """该对象类型是否允许添加自定义属性。"""
        return self.custom_allowed.get(object_type.upper(), False)

    def list_all_fields(self, object_type: str) -> list[str]:
        """列出某对象类型的所有预定义字段。"""
        obj = self.get_object_type(object_type)
        return list(obj.get("fields", {}).keys())

    def resolve_alias(self, object_type: str, field: str, alias: str) -> Any:
        """解析别名。"""
        return self.aliases.get(object_type.upper(), {}).get(field, {}).get(alias)

    def get_llm_context_summary(self, object_type: str) -> str:
        """
        为 LLM Prompt 生成该对象类型的参数摘要。

        不是把整个 schema 扔给 LLM，而是生成精简摘要：
        - 只包含 field name + value_type + required + 一句话描述
        """
        ...
```

### 3.1 FieldDescriptor

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class FieldDescriptor:
    key: str
    value_type: str           # string | enum | integer | float | boolean | color | array | object | expression
    default: Any = None
    enum: list[Any] | None = None
    min: Any = None
    max: Any = None
    phase: str = "service"    # datasource | style | service | cache
    required: bool = False
    derived: bool = False     # 是否为推导字段（值由其他字段自动计算，不可编辑）
    editable: bool = True     # 是否可编辑（嵌套对象字段未展开时标记为 false）
    custom: bool = False
    custom_desc: str = ""
```

### 3.2 自定义属性的 Schema 处理

当 `additionalProperties: true` 时，该对象允许自定义属性。自定义属性的 `FieldDescriptor` 由用户在 UI 中指定：

```python
custom_desc = FieldDescriptor(
    key="filter",
    value_type="string",
    phase="datasource",
    required=False,
    custom=True,
    custom_desc="要素过滤条件",
)
```

自定义属性仍然要经过 `TemplateMapper.get_field_descriptor()` 包装，统一参与校验和导出。

---
