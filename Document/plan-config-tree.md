# Plan: Config Tree

> **模块**：配置树数据层
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M1（配置树编辑）
> **对应 design**：`design/data-structures.md`
> **前置依赖**：`plan-template-system` DC-002~003（TemplateMapper + FieldDescriptor）

---

## 1. 模块概述

配置树数据层是整个系统的**数据根基**。`ConfigSession` 持有 `params`（mappyfile-compatible dict），`ConfigTree` 将其包装为前端友好的树模型（TreeNode/TreeLeaf）。所有其他模块（校验、导出、LLM）都依赖本模块。

**核心复杂度**：`to_mappyfile_dict()` 的 7 条强制变换规则，来自 V1 spike 对 mappyfile 1.1.1 的 62 个用例验证。

**包含内容**：
- `backend/core/session.py` — ConfigSession
- `backend/core/config_tree.py` — ConfigTree, TreeNode, TreeLeaf

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| `params` 是唯一真实数据源 | `constitution.md` §4.3 |
| 纯内存，无持久化 | `constitution.md` §4.3 |
| 扁平路径寻址（`layers.0.name`），无行号 | `design/data-structures.md` §4.3 |
| `to_mappyfile_dict()` 必须执行 7 条强制变换 | `spike/v1_result.md` |
| 服务类型过滤是纯 UI 行为，隐藏字段值保留 | `design/template-system.md` §2.6 |
| 自定义属性存储在 `_custom` 键下，序列化时展开 | `design/data-structures.md` §4.2 |

---

## 3. 接口定义

### 3.1 ConfigSession — 会话根容器

```python
# DC-004: backend/core/session.py

@dataclass
class ConfigSession:
    session_id: str
    intent_message: str | None = None
    params: dict[str, Any] = field(default_factory=lambda: mappyfile.create("map"))
    tree: ConfigTree | None = None
    history: DialogueHistory = field(default_factory=DialogueHistory)
    validation_state: str = "idle"  # idle | checking | pass | fail
    validation_errors: list[dict] = field(default_factory=list)
    focus_param: str | None = None
    service_types: list[str] = field(default_factory=lambda: ["wms"])
    mapcache_enabled: bool = False

    def __post_init__(self):
        if self.tree is None and self.params:
            self.tree = ConfigTree(self.params, get_mapper(), self.service_types)

    @classmethod
    def from_mapfile_content(
        cls, session_id: str, content: str, mapper: TemplateMapper
    ) -> "ConfigSession": ...

    def set_focus(self, path: str | None) -> None: ...
    def apply_llm_updates(self, updates: list[dict]) -> None: ...
```

### 3.2 TreeNode / TreeLeaf — 树模型

```python
# DC-005: backend/core/config_tree.py

@dataclass
class TreeNode:
    id: str                              # 全局唯一 id，如 "layer_0_class_0"
    path: str                            # 扁平路径，如 "layers.0.classes.0"
    object_type: str                     # MAP | LAYER | CLASS | STYLE | LABEL | WEB | METADATA | CACHE
    children: list[TreeNode | TreeLeaf] = field(default_factory=list)
    expanded: bool = True

    def leaves(self) -> list[TreeLeaf]: ...
    def nodes(self) -> list[TreeNode]: ...

@dataclass
class TreeLeaf:
    id: str
    path: str
    key: str
    descriptor: FieldDescriptor
    value: Any
    user_modified: bool = False
    errors: list[str] = field(default_factory=list)
```

### 3.3 ConfigTree — 业务隔离层

```python
# DC-006: backend/core/config_tree.py

class ConfigTree:
    def __init__(
        self, params: dict, mapper: TemplateMapper,
        service_types: list[str] | None = None
    ) -> None: ...

    # DC-007: 构造
    def _build_tree(self, obj: dict, path: str, object_type: str) -> TreeNode: ...
    def _build_children(self, obj: dict, parent_path: str, parent_type: str) -> list[TreeNode]: ...

    # DC-008: 服务类型过滤
    def _is_metadata_field_visible(self, field: str) -> bool: ...
    def _is_layer_field_visible(self, field: str) -> bool: ...

    # DC-009: 数据访问
    def get_node(self, path: str) -> TreeNode | TreeLeaf | None: ...

    # DC-010: 数据变更
    def update_value(self, path: str, value: Any, user_modified: bool = True) -> None: ...
    def add_object(self, parent_path: str, object_type: str) -> TreeNode: ...
    def remove_object(self, path: str) -> None: ...
    def add_custom_property(
        self, parent_path: str, key: str, value: Any,
        prop_type: str, desc: str = ""
    ) -> None: ...

    # DC-011: 序列化（7 条强制变换）
    def to_mappyfile_dict(self) -> dict: ...
    def _filter_and_expand(self, obj: Any) -> Any: ...
```

### 3.4 7 条强制变换规则

```python
# DC-011 内部实现约束

# 变换 1: _custom 展开 → 提升为普通 key
# 变换 2: cache 跳过 → 不是 Mapfile 对象
# 变换 3: 数组包裹 → layers/classes/styles/labels 必须是列表
# 变换 4: 枚举布尔转换 → status 字段字符串化
# 变换 5: PROJECTION 数组守卫 → 保持列表
# 变换 6: Extent 数组守卫 → 保持 4 元素列表
# 变换 7: Color RGB 数组守卫 → 保持 [R, G, B]
```

---

## 4. 数据流

### 4.1 初始化流程

```
mappyfile.create("map") → ConfigSession.params
  → ConfigTree._build_tree() → TreeNode + TreeLeaf
  → 前端渲染
```

### 4.2 编辑参数

```
WS: tree_update { updates }
  → ConfigTree.update_value() → 写回 params + 更新 leaf
  → ValidationPipeline.validate_field() → 错误写回 leaf.errors
  → WS: tree_state { params_snapshot, validation_state, errors }
```

### 4.3 导出序列化

```
ConfigTree.to_mappyfile_dict()
  ├── _custom 展开为普通 key
  ├── cache 完全跳过
  ├── layers/classes/styles/labels 数组包裹
  ├── status 字符串化
  ├── projection 数组守卫
  ├── extent 数组守卫
  └── color RGB 数组守卫
  → mappyfile.dumps()
```

---

## 5. 测试策略

### 5.1 单元测试

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-004 | `tests/unit/test_session.py` | 初始化、from_mapfile、focus 切换、apply_updates |
| DC-005 | `tests/unit/test_config_tree.py` | TreeNode/TreeLeaf 创建、leaves/nodes 方法 |
| DC-007 | `tests/unit/test_config_tree_build.py` | 递归构建、服务类型过滤、自定义属性展开 |
| DC-008 | `tests/unit/test_config_tree_build.py` | ows_* 始终可见、wms/wfs/wcs 条件可见、gml_* WFS 条件 |
| DC-009 | `tests/unit/test_config_tree_access.py` | 路径查找、多级嵌套 |
| DC-010 | `tests/unit/test_config_tree_mutate.py` | update_value、add/remove 对象、自定义属性 |
| DC-011 | `tests/unit/test_config_tree_serialize.py` | 7 条变换各覆盖、端到端 mappyfile 验证 |

### 5.2 关键测试数据

```python
# 测试用例：7 条变换
TEST_CASES = [
    # 变换 1: _custom 展开
    {"input": {"name": "x", "_custom": {"filter": {"value": "type='a'", "type": "string"}}},
     "expected": {"name": "x", "filter": "type='a'"}},
    # 变换 2: cache 跳过
    {"input": {"name": "x", "cache": {"type": "disk"}},
     "expected": {"name": "x"}},
    # 变换 3: 数组包裹
    {"input": {"layers": {"name": "x"}},
     "expected": {"layers": [{"name": "x"}]}},
    # 变换 4: status 字符串化
    {"input": {"status": True},
     "expected": {"status": "ON"}},
    # 变换 5: projection 数组守卫
    {"input": {"projection": ["init=epsg:3857"]},
     "expected": {"projection": ["init=epsg:3857"]}},
    # 变换 6: extent 数组守卫
    {"input": {"extent": [-180, -90, 180, 90]},
     "expected": {"extent": [-180, -90, 180, 90]}},
    # 变换 7: color RGB 数组守卫
    {"input": {"color": [255, 0, 0]},
     "expected": {"color": [255, 0, 0]}},
]
```

---

## 6. 任务清单

### Phase 1: 数据模型（TDD）

- [ ] [RED] `test_session.py` — ConfigSession 初始化、默认 MAP 创建
- [ ] [GREEN] `session.py` — ConfigSession
- [ ] [RED] `test_tree_node.py` — TreeNode/TreeLeaf 基础操作
- [ ] [GREEN] `config_tree.py` — TreeNode + TreeLeaf
- [ ] [REFACTOR] 提取路径解析工具函数

### Phase 2: 树构建（TDD）

- [ ] [RED] `test_config_tree_build.py` — 简单 MAP 构建、嵌套 LAYER/CLASS/STYLE
- [ ] [GREEN] `config_tree.py` — ConfigTree._build_tree()
- [ ] [RED] `test_config_tree_build.py` — 服务类型过滤（METADATA 字段可见性）
- [ ] [GREEN] `config_tree.py` — _is_metadata_field_visible + _is_layer_field_visible
- [ ] [RED] `test_config_tree_build.py` — 自定义属性从 _custom 展开
- [ ] [GREEN] `config_tree.py` — _custom 处理
- [ ] [REFACTOR] 子对象构建统一化

### Phase 3: 数据变更（TDD）

- [ ] [RED] `test_config_tree_mutate.py` — update_value 写回 params
- [ ] [GREEN] `config_tree.py` — update_value
- [ ] [RED] `test_config_tree_mutate.py` — add_object / remove_object
- [ ] [GREEN] `config_tree.py` — add_object + remove_object
- [ ] [RED] `test_config_tree_mutate.py` — add_custom_property
- [ ] [GREEN] `config_tree.py` — add_custom_property
- [ ] [REFACTOR] 变更后重建树的优化

### Phase 4: 序列化（TDD）

- [ ] [RED] `test_config_tree_serialize.py` — 7 条变换各覆盖
- [ ] [GREEN] `config_tree.py` — to_mappyfile_dict() + _filter_and_expand()
- [ ] [RED] `test_config_tree_serialize.py` — 端到端 mappyfile.dumps() 验证
- [ ] [GREEN] 集成 mappyfile 验证
- [ ] [REFACTOR] 变换规则可配置化

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| `spike/v3_result.md` | V3 验证了递归渲染可行性，但前端组件尚未实现 | 低 — 由 `plan-frontend` 处理 |
| `ConfigTree._build_tree()` | 递归构建在真实大规模数据下的性能未知 | 中 — 如 >500 节点需优化 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
