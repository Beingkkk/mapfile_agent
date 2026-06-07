---
title: 核心数据结构
description: ConfigSession、ConfigTree、TreeNode/TreeLeaf、扁平路径寻址、UpdateResolver
---

## 4. 核心数据结构

### 4.1 ConfigSession：会话根容器

`ConfigSession` 是一次配置任务的完整状态容器，内存驻留，重置即销毁。

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ConfigSession:
    session_id: str
    intent_message: str | None = None          # 用户初始意图，永不丢失
    params: dict[str, Any] = field(default_factory=dict)  # mappyfile-compatible dict
    tree: ConfigTree | None = None
    history: DialogueHistory = field(default_factory=DialogueHistory)
    validation_state: str = "idle"             # idle | checking | pass | fail
    validation_errors: list[dict] = field(default_factory=list)
    focus_param: str | None = None             # 当前关注路径
    service_types: list[str] = field(default_factory=lambda: ["wms"])  # wms | wfs | wcs
    mapcache_enabled: bool = False             # 是否启用 MapCache(WMTS/TMS)

    def __post_init__(self):
        if not self.params:
            # 初始化一棵空 MAP（默认展开，无预置 LAYER，默认勾选 WMS）
            self.params = mappyfile.create("map")
        # 尝试从 data/init_session_intent.json 读取默认意图（不强求用户输入）
        if self.intent_message is None:
            self.intent_message = self._load_default_intent()
```

**状态边界**：

- `params` 是**唯一真实数据源**，直接传给 `mappyfile.dumps()` 和 `mappyfile.validate()`
- `tree` 是 `params` 的**业务视图**，加了行号、UI 状态、错误标记
- `history` 只保存 QA 对话和意图
- `validation_*` 字段缓存最后一次校验结果，供前端渲染

### 4.2 ConfigTree：业务隔离层

`ConfigTree` 封装 mappyfile dict，提供前端友好的树模型。

> **前端渲染方案**：采用**分层渲染**，不使用 Naive UI 的 `n-tree`。
> > **V3 验证结论**（`spike/v3_result.md`）：自定义递归组件方案验证通过。280 节点、4 层嵌套（MAP→LAYER→CLASS→STYLE/LABEL）渲染无卡顿，ObjectCard 140 行 < 200 行约束。
>
> - **对象节点**（MAP / LAYER / CLASS / STYLE / LABEL / WEB / METADATA / CACHE）渲染为 `ObjectCard` 组件：可展开/折叠、显示 Phase 颜色徽章、支持增删子对象。
> - **属性叶子**在 `ObjectCard` 内部以表单列表渲染，通过统一的 `FieldEditor` 组件按 `value_type` 自动分发到对应控件（string→输入框、integer/float→数字输入、boolean→开关、enum→下拉、array→多数字输入、color→RGB+预览）。
> - **STYLE / LABEL** 作为最底层对象节点渲染为 `ObjectCard`（无进一步子对象），不内联在父 CLASS 中——独立卡片在验证中表现更清晰，展开/折叠状态独立管理。
> - `editable=false` 的字段（如 `config`、`legend` 等 schema 外部对象）不在树中渲染。
> - 前端界面**不显示行号**，用扁平路径（如 `layers.0.name`）标识节点位置。

```python
@dataclass
class TreeNode:
    id: str                              # 全局唯一 id，如 "layer_0_class_0"
    path: str                            # 扁平路径，如 "layers.0.classes.0"
    object_type: str                     # MAP | LAYER | CLASS | STYLE | LABEL | WEB | METADATA | CACHE
    children: list[TreeNode | TreeLeaf] = field(default_factory=list)
    expanded: bool = True                # UI 展开状态（默认全部展开）

    def leaves(self) -> list[TreeLeaf]:
        return [c for c in self.children if isinstance(c, TreeLeaf)]

    def nodes(self) -> list[TreeNode]:
        return [c for c in self.children if isinstance(c, TreeNode)]


@dataclass
class TreeLeaf:
    id: str
    path: str                            # 如 "layers.0.name"
    key: str                             # 字段名
    descriptor: FieldDescriptor
    value: Any
    user_modified: bool = False          # 用户是否手动修改过（用于"仅必填"模式判断）
    errors: list[str] = field(default_factory=list)


class ConfigTree:
    def __init__(self, params: dict, mapper: TemplateMapper, service_types: list[str] | None = None):
        self.params = params
        self.mapper = mapper
        self.service_types = service_types or ["wms"]
        self.root = self._build_tree(params, path="map", object_type="MAP")

    # ─────────────────────────────────────────
    # 构造与渲染
    # ─────────────────────────────────────────
    def _build_tree(self, obj: dict, path: str, object_type: str) -> TreeNode:
        """递归地把 mappyfile dict 转成 TreeNode + TreeLeaf。"""
        node = TreeNode(id=self._make_id(path), path=path, object_type=object_type)

        # 1. 预定义字段（按 schema 顺序，含服务类型过滤）
        for field in self.mapper.list_all_fields(object_type):
            # METADATA 字段：按服务类型过滤可见性
            if object_type == "METADATA" and not self._is_metadata_field_visible(field):
                continue
            # LAYER 字段：按服务类型过滤可见性
            if object_type == "LAYER" and not self._is_layer_field_visible(field):
                continue
            if field in obj:
                value = obj[field]
                leaf = TreeLeaf(
                    id=self._make_id(f"{path}.{field}"),
                    path=f"{path}.{field}",
                    key=field,
                    descriptor=self.mapper.get_field_descriptor(object_type, field),
                    value=value,
                )
                node.children.append(leaf)

        # 2. 自定义属性（从 _custom 展开）
        for field, meta in obj.get("_custom", {}).items():
            leaf = TreeLeaf(
                id=self._make_id(f"{path}.{field}"),
                path=f"{path}.{field}",
                key=field,
                descriptor=FieldDescriptor(
                    key=field,
                    value_type=meta["type"],
                    custom=True,
                    custom_desc=meta.get("desc", ""),
                ),
                value=meta["value"],
            )
            node.children.append(leaf)

        # 3. 子对象（LAYER / CLASS / STYLE / WEB / METADATA / CACHE）
        #    递归构建，保持 mappyfile 输出顺序
        node.children.extend(self._build_children(obj, path, object_type))

        return node

    def _is_metadata_field_visible(self, field: str) -> bool:
        """METADATA 字段按服务类型过滤可见性。"""
        # ows_* 始终可见
        if field.startswith("ows_"):
            return True
        # wms_* 仅当 WMS 勾选时可见
        if field.startswith("wms_") and "wms" not in self.service_types:
            return False
        # wfs_* 仅当 WFS 勾选时可见
        if field.startswith("wfs_") and "wfs" not in self.service_types:
            return False
        # wcs_* 仅当 WCS 勾选时可见
        if field.startswith("wcs_") and "wcs" not in self.service_types:
            return False
        # gml_* 仅当 WFS 勾选时可见（位于 LAYER.METADATA 下）
        if field.startswith("gml_") and "wfs" not in self.service_types:
            return False
        return True

    def _is_layer_field_visible(self, field: str) -> bool:
        """LAYER 字段按服务类型过滤可见性（不含 METADATA 子字段）。"""
        # WFS 专属字段（当前 LAYER 级别无 WFS 专属直接字段）
        wfs_fields = set()
        if field in wfs_fields and "wfs" not in self.service_types:
            return False
        # WCS 专属字段（当前无 WCS 专属 LAYER 字段）
        wcs_fields = set()
        if field in wcs_fields and "wcs" not in self.service_types:
            return False
        return True

    def _build_children(self, obj: dict, parent_path: str, parent_type: str) -> list[TreeNode]:
        """根据对象类型构建子对象节点。"""
        children: list[TreeNode] = []
        if parent_type == "MAP":
            if "web" in obj:
                children.append(self._build_tree(obj["web"], f"{parent_path}.web", "WEB"))
            for i, layer in enumerate(obj.get("layers", [])):
                children.append(self._build_tree(layer, f"layers.{i}", "LAYER"))
            if "cache" in obj:
                children.append(self._build_tree(obj["cache"], "cache", "CACHE"))
        elif parent_type == "LAYER":
            if "metadata" in obj:
                children.append(self._build_tree(obj["metadata"], f"{parent_path}.metadata", "METADATA"))
            for i, cls in enumerate(obj.get("classes", [])):
                children.append(self._build_tree(cls, f"{parent_path}.classes.{i}", "CLASS"))
        elif parent_type == "CLASS":
            for i, style in enumerate(obj.get("styles", [])):
                children.append(self._build_tree(style, f"{parent_path}.styles.{i}", "STYLE"))
            for i, label in enumerate(obj.get("labels", [])):
                children.append(self._build_tree(label, f"{parent_path}.labels.{i}", "LABEL"))
        elif parent_type == "WEB":
            if "metadata" in obj:
                children.append(self._build_tree(obj["metadata"], f"{parent_path}.metadata", "METADATA"))
        return children

    def _make_id(self, path: str) -> str:
        return path.replace(".", "_").replace("[", "").replace("]", "")

    # ─────────────────────────────────────────
    # 数据访问
    # ─────────────────────────────────────────
    def get_node(self, path: str) -> TreeNode | TreeLeaf | None:
        """按 path 查找节点。"""
        ...

    # ─────────────────────────────────────────
    # 数据变更
    # ─────────────────────────────────────────
    def update_value(self, path: str, value: Any, user_modified: bool = True) -> None:
        """更新叶子节点值，同时写回 params dict。"""
        node = self.get_node(path)
        if isinstance(node, TreeLeaf):
            node.value = value
            node.user_modified = user_modified
            self._write_to_params(path, value)

    def add_object(self, parent_path: str, object_type: str) -> TreeNode:
        """在指定父节点下添加新的子对象（如添加 LAYER）。"""
        ...

    def remove_object(self, path: str) -> None:
        """删除对象节点。"""
        ...

    def add_custom_property(self, parent_path: str, key: str, value: Any,
                            prop_type: str, desc: str = "") -> None:
        """添加自定义属性。"""
        parent = self._resolve_dict(parent_path)
        parent.setdefault("_custom", {})[key] = {
            "value": value,
            "type": prop_type,
            "desc": desc,
        }
        self.root = self._build_tree(self.params, "map", "MAP")

    # ─────────────────────────────────────────
    # 序列化
    # ─────────────────────────────────────────
    def to_mappyfile_dict(self) -> dict:
        """生成可直接传给 mappyfile.dumps() 的字典。

        过滤掉内部节点（cache、_custom），展开自定义属性。
        """
        return self._filter_and_expand(self.params)

    def _filter_and_expand(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k in {"_custom", "cache"}:
                    # _custom 展开为普通 key
                    if k == "_custom":
                        for ck, cv in v.items():
                            result[ck] = self._filter_and_expand(cv["value"])
                    # cache 完全跳过（Mapfile 无此对象）
                    continue
                result[k] = self._filter_and_expand(v)
            return result
        if isinstance(obj, list):
            return [self._filter_and_expand(i) for i in obj]
        return obj

    def _write_to_params(self, path: str, value: Any) -> None:
        """把 path 对应的值写回 self.params。"""
        ...

    def _resolve_dict(self, path: str) -> dict:
        """把 path 解析为 params 中的 dict 引用。"""
        ...
```

### 4.3 通过扁平路径定位 param_update

LLM 返回的参数更新**只使用扁平路径**，不使用行号：

```json
{
  "thought": "用户需要把连接类型改为 postgis",
  "action": "answer",
  "params_update": [
    {"path": "layers.0.connectiontype", "value": "postgis"},
    {"path": "layers.0.name", "value": "buildings"}
  ],
  "question": "已帮你把 LAYER[0].connectiontype 改为 postgis，同时把图层名设为 buildings。"
}
```

后端解析策略（极简）：

```python
class UpdateResolver:
    def resolve(self, update: dict) -> str:
        if "path" not in update:
            raise InvalidUpdate(update)
        return update["path"]
```

**路径是稳定标识符**：树结构变化不影响路径的语义（`layers.0.name` 始终指向第一个 LAYER 的 name），不需要行号重算、反向映射或容错逻辑。ConfigTree 的 `get_node(path)` 直接按点分隔路径查找节点。

---
