# Proposal-0004: ConfigSession + ConfigTree

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-07
> **对应 Plan**: `plan-config-tree` Phase 1~4
> **影响范围**:
> - `backend/core/session.py` — ConfigSession
> - `backend/core/config_tree.py` — ConfigTree, TreeNode, TreeLeaf
> - `backend/core/history.py` — DialogueHistory（最小占位）
> - `tests/unit/test_session.py`
> - `tests/unit/test_config_tree.py`

---

## 目标

实现配置树数据层——`ConfigSession`（会话根容器）和 `ConfigTree`（业务隔离层 + 树模型），为前端渲染、验证管道、LLM 更新和 Mapfile 导出提供统一的数据接口。

**核心复杂度**：`to_mappyfile_dict()` 的 7 条强制变换规则，来自 V1 spike 对 mappyfile 1.1.1 的 62 个用例验证。

**原则**：
- `params` 是唯一真实数据源；`tree` 是其业务视图
- 纯内存，无持久化
- 扁平路径寻址（`layers.0.name`），无行号
- 服务类型过滤是纯 UI 行为，隐藏字段值保留在 params 中

---

## 变更内容

### [ADDED] `backend/core/session.py`

实现 `ConfigSession` dataclass：
- `session_id`, `intent_message`, `params`, `tree`, `history`, `validation_state`, `validation_errors`, `focus_param`, `service_types`, `mapcache_enabled`
- `__post_init__`：当 `tree is None` 时从 `params` 自动构建 `ConfigTree`
- `set_focus(path)`：切换当前关注参数，重置 QA round counter
- `apply_llm_updates(updates)`：批量应用 LLM 建议的更新到 tree

### [ADDED] `backend/core/config_tree.py`

实现三层组件：

**`TreeNode`**（dataclass）：对象节点，含 `id`, `path`, `object_type`, `children`, `expanded`
- `leaves()` / `nodes()` 筛选方法

**`TreeLeaf`**（dataclass）：属性叶子，含 `id`, `path`, `key`, `descriptor`, `value`, `user_modified`, `errors`

**`ConfigTree`**（class）：业务隔离层
- `__init__`：从 params + TemplateMapper + service_types 构建整棵树
- `_build_tree`：递归构造 TreeNode + TreeLeaf
- `_build_children`：按对象类型构建子对象（MAP→WEB/LAYER/CACHE, LAYER→METADATA/CLASS, CLASS→STYLE/LABEL, WEB→METADATA）
- `_is_metadata_field_visible` / `_is_layer_field_visible`：服务类型过滤
- `get_node(path)`：按扁平路径查找节点
- `update_value(path, value)`：更新叶子值并写回 params
- `add_object(parent_path, object_type)`：添加子对象
- `remove_object(path)`：删除对象节点
- `add_custom_property(...)`：在 _custom 下添加自定义属性并重建树
- `to_mappyfile_dict()`：7 条强制变换的序列化输出
- `_filter_and_expand(obj)`：递归执行变换 1-7
- `_write_to_params(path, value)` / `_resolve_dict(path)`：路径解析与值回写

### [ADDED] `backend/core/history.py`

最小 `DialogueHistory` 占位实现（完整实现归属 plan-backend-llm）：
- `messages: list[dict]`
- `round_count: int = 0`
- `reset_on_focus_change()`：focus 切换时重置 round counter（保留初始 intent）

### [ADDED/MODIFIED] `tests/unit/test_session.py`

覆盖：
- ConfigSession 初始化（默认 MAP、service_types、自动构建 tree）
- `set_focus` 行为
- `apply_llm_updates` 批量更新

### [ADDED/MODIFIED] `tests/unit/test_config_tree.py`

覆盖 plan 中 DC-005~DC-011 的全部用例：
- TreeNode/TreeLeaf 基础操作
- `_build_tree`：简单 MAP、嵌套 LAYER/CLASS/STYLE
- 服务类型过滤：METADATA 字段（ows_* 始终可见、wms/wfs/wcs/gml_* 条件可见）
- 自定义属性从 _custom 展开
- `get_node` 路径查找
- `update_value` 写回 params
- `add_object` / `remove_object`
- `add_custom_property`
- `to_mappyfile_dict`：7 条变换各覆盖（含 status 布尔转字符串、数组包裹、_custom 展开、cache 跳过、projection/extent/color 守卫）

---

## 验收标准

- [x] `pytest tests/unit/test_session.py -v` 全部通过（12 项）
- [x] `pytest tests/unit/test_config_tree.py -v` 全部通过（56 项）
- [x] `to_mappyfile_dict()` 的 7 条变换全部有独立测试覆盖
- [x] 服务类型过滤至少覆盖 ows_*/wms_*/wfs_*/wcs_*/gml_* 前缀规则
- [x] 代码符合类型注解规范，通过 `mypy --ignore-missing-imports` 检查

---

## 依赖

- proposal-0001（目录结构）
- proposal-0003（TemplateMapper + FieldDescriptor）
- `data/mapguide_rules.json` 已生成

---

*Approved by: SDD 流程 — plan-config-tree Phase 1~4 既定任务*
