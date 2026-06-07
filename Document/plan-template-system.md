# Plan: Template System

> **模块**：模板资源体系
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M1（配置树编辑）, §4.3 可维护性
> **对应 design**：`design/template-system.md`

---

## 1. 模块概述

模板资源体系是 MapGuide 的「规则引擎」——它定义了配置树的结构、参数类型、默认值、枚举范围、必填规则等。运行时 `TemplateMapper` 只读取一份生成的 `mapguide_rules.json`。

**本模块是风险最低的先行模块**：`generate_rules.py` 已完整交付，只需补充测试。先完成本模块可建立 TDD 信心，并为 `plan-config-tree` 提供依赖。

**包含内容**：
- `scripts/generate_rules.py` — 规则合并器（已交付）
- `backend/core/template_mapper.py` — TemplateMapper + FieldDescriptor
- `data/templates/*.json` — 模板资源（人工维护）
- `data/mapguide_rules.json` — 运行时规则（生成产物）

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| `mapguide_rules.json` 是运行时**唯一**读取的规则文件 | `constitution.md` §4.5 |
| 模板资源（`data/templates/*.json`）人工维护，git 跟踪 | `constitution.md` §4.5 |
| 修改模板后必须重新运行 `generate_rules.py` 并验证输出 | `conventions.md` §14.3 |
| 字段默认值优先级：override > schema default > None | `design/template-system.md` §2.4 |

---

## 3. 接口定义

### 3.1 generate_rules.py — 规则合并器

```python
# DC-001: scripts/generate_rules.py

"""
确定性合并脚本。输入 9 个模板资源文件，输出统一的 mapguide_rules.json。

合并规则：
- value_type: schema enum → "enum"; schema type → mapped type; unknown → "string"
- default: defaults-override.json > schema default > None
- required / required_when: from required.json
- phase: from phase-map.json
- aliases: from aliases.json
- dependencies: from dependencies.json
- custom_allowed: from custom-allowed.json
- service_metadata: from service-metadata.json
- object_fields: from object-fields.json
- Nested objects not in EXPANDED_NESTED_FIELDS → editable: false
"""

SCHEMA_LOCATIONS = {
    "MAP": ["properties"],
    "LAYER": ["properties", "layers", "items", "properties"],
    "CLASS": ["properties", "layers", "items", "properties", "classes", "items", "properties"],
    "STYLE": ["properties", "layers", "items", "properties", "classes", "items", "properties", "styles", "items", "properties"],
    "LABEL": ["properties", "layers", "items", "properties", "classes", "items", "properties", "labels", "items", "properties"],
    "WEB": ["properties", "web", "properties"],
    "METADATA": ["properties", "web", "properties", "metadata", "properties"],
}

EXPANDED_NESTED_FIELDS = {"layers", "classes", "styles", "labels", "web", "metadata"}

def generate_rules(templates_dir: str, output_path: str) -> None: ...
def _load_json(path: str) -> dict: ...
def _extract_schema_object(schema: dict, path: list[str]) -> dict: ...
def _merge_field_defs(schema_field: dict, overrides: dict) -> dict: ...
def _build_flat_params(object_types: dict) -> dict: ...
def _apply_service_metadata(object_types: dict, service_meta: dict) -> None: ...
```

### 3.2 TemplateMapper — 运行时规则查询

```python
# DC-002: backend/core/template_mapper.py

class TemplateMapper:
    """运行时读取 mapguide_rules.json 的唯一入口。"""

    def __init__(self, rules_path: str) -> None: ...
    def get_object_type(self, object_type: str) -> dict: ...
    def get_field_descriptor(self, object_type: str, field: str) -> FieldDescriptor: ...
    def allows_custom_properties(self, object_type: str) -> bool: ...
    def list_all_fields(self, object_type: str) -> list[str]: ...
    def resolve_alias(self, object_type: str, field: str, alias: str) -> Any: ...
    def get_llm_context_summary(self, object_type: str) -> str: ...
```

### 3.3 FieldDescriptor — 字段元数据

```python
# DC-003: backend/core/template_mapper.py

@dataclass
class FieldDescriptor:
    key: str
    value_type: str  # string | enum | integer | float | boolean | color | array | object | expression
    default: Any = None
    enum: list[Any] | None = None
    min: Any = None
    max: Any = None
    phase: str = "service"  # datasource | style | service | cache
    required: bool = False
    derived: bool = False
    editable: bool = True
    custom: bool = False
    custom_desc: str = ""
```

---

## 4. 数据流

```
data/templates/*.json (人工维护)
  → scripts/generate_rules.py (DC-001)
  → SourceCode/data/mapguide_rules.json
  → TemplateMapper.__init__() (DC-002)
  → FieldDescriptor (DC-003)
```

---

## 5. 测试策略

### 5.1 单元测试

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-001 | `tests/unit/test_generate_rules.py` | 字段计数、类型映射、默认值优先级、flat_params 索引、service_metadata 合并 |
| DC-002 | `tests/unit/test_template_mapper.py` | 加载 rules、字段查询、别名解析、custom 判断、llm 摘要 |
| DC-003 | `tests/unit/test_template_mapper.py` | FieldDescriptor 创建、属性访问 |

### 5.2 集成测试

| 场景 | 测试文件 |
|------|----------|
| 生成产物结构完整性 | `tests/integration/test_rules_output.py` |
| 所有 object_types 字段非空 | `tests/integration/test_rules_output.py` |

### 5.3 回归验证命令

```bash
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py
"/c/Users/PC/.conda/envs/gis-agent/python" -c "import json; r=json.load(open('data/mapguide_rules.json')); print(f'Objects: {len(r[\"object_types\"])}, Fields: {sum(len(o[\"fields\"]) for o in r[\"object_types\"].values())}')"
```

---

## 6. 任务清单

### Phase 1: generate_rules.py 补测试（已有代码）

- [ ] [RED] `test_generate_rules.py` — 测试 `_load_json`、字段合并逻辑、flat_params 生成
- [ ] [GREEN] 为现有函数添加测试（代码已存在）
- [ ] [RED] `test_generate_rules_integration.py` — 端到端生成验证
- [ ] [GREEN] 集成测试通过
- [ ] [REFACTOR] 提取合并逻辑为独立可测试函数

### Phase 2: TemplateMapper（TDD）

- [ ] [RED] `test_template_mapper.py` — 加载、查询、别名解析
- [ ] [GREEN] `template_mapper.py` — TemplateMapper
- [ ] [RED] `test_field_descriptor.py` — dataclass 创建、属性访问
- [ ] [GREEN] `template_mapper.py` — FieldDescriptor
- [ ] [REFACTOR] 缓存优化（rules 文件只加载一次）

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| `generate_rules.py` | 有完整代码但无单元测试 | **高** — Phase 1 必须完成 |
| `data/templates/*.json` | 无 schema 校验，人工维护可能出错 | 中 — 通过生成后验证兜底 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
