# Plan: Validation

> **模块**：四层校验体系
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M3（校验系统）
> **对应 design**：`design/validation.md`
> **前置依赖**：`plan-config-tree` DC-005~011（TreeNode/TreeLeaf/ConfigTree）

---

## 1. 模块概述

校验体系提供四层防御：别名解析 → 类型检查 → 语义检查 → mappyfile 语法。每层负责不同维度的错误拦截，且触发时机不同（字段失焦只做 L1-L3，手动/导出做全部四层）。

**核心复杂度**：L4（mappyfile 语法校验）的 false positive 过滤——mappyfile 会拒绝 schema 外部字段（如自定义属性），但我们的业务允许这些字段存在。

**包含内容**：
- `backend/core/validation.py` — ValidationPipeline, ValidationResult

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| 字段失焦：只执行 L1-L3（不完整 map 无法做 mappyfile） | `spec.md` §4.2 |
| 添加/删除节点、手动校验、导出：执行全部四层 | `spec.md` §4.2 |
| L4 false positive 必须过滤（自定义属性 + object-fields） | `spike/v1_result.md` |
| 校验错误格式统一：`{path, message, level}` | `design/core-services.md` §7.4 |
| 服务类型影响语义校验（WFS 需要 gml_* 等） | `design/template-system.md` §2.6 |

---

## 3. 接口定义

### 3.1 ValidationResult

```python
# DC-012: backend/core/validation.py

@dataclass
class ValidationResult:
    state: str           # pass | fail
    errors: list[dict]   # [{path: str, message: str, level: str}]
```

### 3.2 ValidationPipeline

```python
# DC-013: backend/core/validation.py

class ValidationPipeline:
    def __init__(self, mapper: TemplateMapper) -> None: ...

    # DC-014: 字段级校验（失焦用）
    def validate_field(
        self, tree: ConfigTree, path: str,
        service_types: list[str], full: bool = False
    ) -> list[dict]: ...

    # DC-015: 完整树校验（手动/导出用）
    def validate_tree(
        self, tree: ConfigTree, service_types: list[str]
    ) -> ValidationResult: ...
```

### 3.3 内部校验方法

```python
# DC-016: backend/core/validation.py

class ValidationPipeline:
    # L1: 别名解析
    def _try_resolve_alias(self, leaf: TreeLeaf) -> Any: ...

    # L2: 类型检查
    def _check_type(self, leaf: TreeLeaf) -> list[dict]: ...

    # L3: 语义检查
    def _check_semantic(
        self, tree: ConfigTree, leaf: TreeLeaf, service_types: list[str]
    ) -> list[dict]: ...

    # L4: mappyfile 语法 + false positive 过滤
    def _check_mappyfile(self, tree: ConfigTree) -> list[dict]: ...
```

---

## 4. 四层校验详情

| 层级 | 方法 | 输入 | 输出 | 失败处理 |
|------|------|------|------|----------|
| **L1** | `_try_resolve_alias` | leaf.value | 转换后的值 / None | 静默替换，不报错 |
| **L2** | `_check_type` | leaf.descriptor + value | 错误列表 | 字段标红 |
| **L3** | `_check_semantic` | tree + leaf + service_types | 错误列表 | 字段标红 |
| **L4** | `_check_mappyfile` | tree.to_mappyfile_dict() | 错误列表 | 全局错误面板 |

### L1: 别名解析示例

```python
# "红色" → [255, 0, 0]
# "shapefile" → "local"
# "数据库" → "postgis"
mapper.resolve_alias("STYLE", "color", "红色")  # [255, 0, 0]
```

### L2: 类型检查覆盖

- `value_type == "enum"` → 值必须在 `enum` 列表中
- `value_type == "integer"` → int + min/max 范围
- `value_type == "float"` → float + min/max 范围
- `value_type == "boolean"` → bool
- `value_type == "color"` → [R, G, B] 且 0-255
- `value_type == "array"` → list
- `value_type == "expression"` → string（语法不校验）

### L3: 语义检查规则来源

`dependencies.json` 定义：
- 条件必填：`connectiontype == 'postgis'` → `connection` 必填
- 互斥：某字段与另一字段不能同时存在
- 推导：某字段值由其他字段自动计算

### L4: False Positive 过滤

```python
# mappyfile 会报错的字段，但我们允许：
ALLOWED_NON_SCHEMA_KEYS = {
    # custom-allowed.json 中的字段
    # object-fields.json 中的字段
    # 用户自定义属性
}
```

---

## 5. 测试策略

### 5.1 单元测试

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-012 | `tests/unit/test_validation_result.py` | ValidationResult 创建、状态判断 |
| DC-014 | `tests/unit/test_validation_l1.py` | 别名解析成功、别名不存在（不报错）、别名替换 |
| DC-014 | `tests/unit/test_validation_l2.py` | enum/integer/float/boolean/color/array 各类型错误 |
| DC-015 | `tests/unit/test_validation_l3.py` | 条件必填触发/不触发、互斥、推导 |
| DC-016 | `tests/unit/test_validation_l4.py` | mappyfile 语法通过、false positive 过滤 |
| DC-015 | `tests/unit/test_validation_tree.py` | 完整树校验、错误去重、状态判定 |

### 5.2 关键测试数据

```python
# L2 测试用例
L2_TEST_CASES = [
    {"type": "enum", "enum": ["on", "off"], "value": "maybe", "should_fail": True},
    {"type": "integer", "min": 0, "max": 255, "value": 300, "should_fail": True},
    {"type": "color", "value": [256, 0, 0], "should_fail": True},  # R > 255
    {"type": "color", "value": "blue", "should_fail": True},      # 字符串
    {"type": "array", "value": ["init=epsg:3857"], "should_fail": False},
]

# L3 测试用例
L3_TEST_CASES = [
    # connectiontype=postgis → connection 必填
    {"field": "connection", "condition": "connectiontype=='postgis'", "should_fail": True},
    # connectiontype=local → connection 可选
    {"field": "connection", "condition": "connectiontype=='local'", "should_fail": False},
]

# L4 测试用例
L4_TEST_CASES = [
    # 自定义属性不应报错
    {"has_custom": True, "custom_key": "transparency", "should_report": False},
    # object-fields.json 中的字段不应报错
    {"key": "wms_enable_request", "should_report": False},
]
```

---

## 6. 任务清单

### Phase 1: L1 别名解析（TDD）

- [ ] [RED] `test_validation_l1.py` — 别名命中、别名不存在、别名替换
- [ ] [GREEN] `validation.py` — _try_resolve_alias
- [ ] [REFACTOR] 提取别名缓存

### Phase 2: L2 类型检查（TDD）

- [ ] [RED] `test_validation_l2.py` — 各 value_type 边界用例
- [ ] [GREEN] `validation.py` — _check_type
- [ ] [RED] `test_validation_l2.py` — enum 大小写不敏感（mappyfile 特性）
- [ ] [GREEN] 补充 case-insensitive 处理
- [ ] [REFACTOR] 类型检查分发器

### Phase 3: L3 语义检查（TDD）

- [ ] [RED] `test_validation_l3.py` — 条件必填触发/不触发
- [ ] [GREEN] `validation.py` — _check_semantic
- [ ] [RED] `test_validation_l3.py` — 服务类型条件（WFS 需要 gml_*）
- [ ] [GREEN] 补充 service_types 传入
- [ ] [REFACTOR] 依赖表达式解析器

### Phase 4: L4 mappyfile 语法（TDD）

- [ ] [RED] `test_validation_l4.py` — 合法 mapfile 通过
- [ ] [GREEN] `validation.py` — _check_mappyfile
- [ ] [RED] `test_validation_l4.py` — false positive 过滤
- [ ] [GREEN] 自定义属性白名单过滤
- [ ] [REFACTOR] 错误消息格式化

### Phase 5: 整合

- [ ] [RED] `test_validation_tree.py` — 完整树校验、错误去重
- [ ] [GREEN] validate_tree 整合
- [ ] [REFACTOR] 性能优化（遍历优化）

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| L4 false positive | mappyfile 拒绝 schema 外部字段的完整边界未完全摸清 | **高** — 需充分测试 |
| L3 依赖表达式 | `dependencies.json` 中的条件表达式需安全求值 | 中 — 使用受限表达式求值 |
| 性能 | 完整树校验遍历所有叶子，大规模时可能慢 | 低 — 先实现再优化 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
