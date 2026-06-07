---
title: 核心服务
description: 后端架构总览、ConfigSession、ValidationPipeline、ExportService、ImportService、核心类一览
---

## 7. 核心类与交互逻辑

### 7.1 架构总览

架构采用"配置树为主、LLM 被动应答"模式。核心类分成三层：

```
┌─────────────────────────────────────────────────────┐
│  WebSocket API 层 (main.py)                          │
│  - 接收 tree_update / question / validate / export  │
├─────────────────────────────────────────────────────┤
│  应用服务层                                          │
│  - ConfigSession   会话状态                          │
│  - ConfigTree      配置树（业务视图）                 │
│  - QAService       LLM 问答服务                      │
│  - ValidationPipeline  四层校验                      │
│  - ExportService   导出 .map / .xml                  │
├─────────────────────────────────────────────────────┤
│  基础设施层                                          │
│  - TemplateMapper  规则映射                          │
│  - PromptBuilder   Prompt 组装                       │
│  - LLMClient       Anthropic SDK 封装                │
│  - UpdateResolver  路径解析                          │
│  - DialogueHistory 精简历史                          │
└─────────────────────────────────────────────────────┘
```

### 7.2 ConfigSession：一次任务的完整状态

```python
@dataclass
class ConfigSession:
    session_id: str
    intent_message: str | None = None
    params: dict[str, Any] = field(default_factory=lambda: mappyfile.create("map"))
    tree: ConfigTree | None = None
    history: DialogueHistory = field(default_factory=DialogueHistory)
    validation_state: str = "idle"
    validation_errors: list[dict] = field(default_factory=list)
    focus_param: str | None = None

    def __post_init__(self):
        if self.tree is None and self.params:
            self.tree = ConfigTree(self.params, get_mapper())

    @classmethod
    def from_mapfile_content(cls, session_id: str, content: str, mapper: TemplateMapper) -> "ConfigSession":
        """
        从已有 Mapfile 文本内容创建会话。

        流程：
        1. mappyfile.loads(content) 解析为 dict
        2. 以解析结果作为 params 创建 ConfigSession
        3. ConfigTree._build_tree() 自动处理自定义属性标记
        4. 返回未校验的 session（由调用方触发 validate_tree）
        """
        try:
            parsed = mappyfile.loads(content)
        except Exception as e:
            raise MapfileParseError(f"Mapfile 语法解析失败: {e}") from e

        session = cls(session_id=session_id, params=parsed)
        session.tree = ConfigTree(parsed, mapper)
        # 清空历史（保留 intent_message）
        session.history = DialogueHistory()
        if session.intent_message:
            session.history.intent_message = session.intent_message
        session.focus_param = None
        return session

    def set_focus(self, path: str | None):
        """切换关注点，同步更新历史。"""
        if path == self.focus_param:
            return
        self.focus_param = path
        self.history.set_focus(path)

    def apply_llm_updates(self, updates: list[dict]) -> None:
        """解析并应用 LLM 返回的更新。"""
        resolver = UpdateResolver()
        for u in updates:
            path = resolver.resolve(u)
            self.tree.update_value(path, u["value"], user_modified=False)
```

### 7.3 QAService：LLM 问答服务

`QAService` 处理用户主动提问，不主动引导用户填参。

```python
@dataclass
class QAResult:
    bot_message: str
    params_update: list[dict]            # 已应用的更新（供前端高亮）
    validation_state: str                # idle | checking | pass | fail
    validation_errors: list[dict]
    can_export: bool
    focus_param: str | None


class QAService:
    def __init__(self,
                 mapper: TemplateMapper,
                 prompt_builder: PromptBuilder,
                 llm_client: LLMClient,
                 validator: ValidationPipeline):
        self.mapper = mapper
        self.prompt = prompt_builder
        self.llm = llm_client
        self.validator = validator

    async def answer(self, session: ConfigSession, question: str) -> QAResult:
        # 1. 记录用户问题
        session.history.add_message("user", question)

        # 2. 组装 Prompt
        prompt = self.prompt.render(
            intent=session.history.to_prompt_context(),
            map_snapshot=self._render_map_snapshot(session.tree),
            focus_param=session.focus_param,
            context_summary=self._build_context_summary(session),
            validation_errors=session.validation_errors,
        )

        # 3. 调用 LLM
        raw = await self.llm.chat(prompt)
        output = LLMOutput.parse(raw)

        # 4. 应用参数更新（如果有）
        if output.params_update:
            session.apply_llm_updates(output.params_update)

        # 5. 触发校验
        result = self.validator.validate_tree(session.tree)
        session.validation_state = result.state
        session.validation_errors = result.errors

        # 6. 记录 LLM 回答
        session.history.add_message("bot", output.question)

        return QAResult(
            bot_message=output.question,
            params_update=output.params_update,
            validation_state=session.validation_state,
            validation_errors=session.validation_errors,
            can_export=self._can_export(session),
            focus_param=session.focus_param,
        )

    def _render_map_snapshot(self, tree: ConfigTree) -> str:
        """生成当前 map 的 YAML 风格快照，用于 Prompt。"""
        ...

    def _build_context_summary(self, session: ConfigSession) -> str:
        """根据关注点生成参数摘要。"""
        if not session.focus_param:
            return ""
        # 从 path 推断 object_type
        node = session.tree.get_node(session.focus_param)
        if isinstance(node, TreeLeaf):
            return self.mapper.get_llm_context_summary(node.descriptor.key)
        if isinstance(node, TreeNode):
            return self.mapper.get_llm_context_summary(node.object_type)
        return ""

    def _can_export(self, session: ConfigSession) -> bool:
        return (
            session.validation_state == "pass"
            and not session.validation_errors
            and session.tree is not None
        )
```

### 7.4 ValidationPipeline：四层校验

```python
@dataclass
class ValidationResult:
    state: str                     # pass | fail
    errors: list[dict]             # [{path, message, line?, level}]


class ValidationPipeline:
    def __init__(self, mapper: TemplateMapper):
        self.mapper = mapper

    def validate_field(self, tree: ConfigTree, path: str, service_types: list[str], full: bool = False) -> list[dict]:
        """校验单个字段（实时校验用）。"""
        errors = []
        node = tree.get_node(path)
        if not isinstance(node, TreeLeaf):
            return errors

        # Layer 1: 别名解析（如果用户输入是别名，尝试转换）
        alias_value = self._try_resolve_alias(node)
        if alias_value is not None and alias_value != node.value:
            tree.update_value(path, alias_value, user_modified=False)
            node = tree.get_node(path)  # 重新获取

        # Layer 2: 类型校验
        errors.extend(self._check_type(node))

        # Layer 3: 语义校验（传入 service_types 用于条件判断）
        errors.extend(self._check_semantic(tree, node, service_types))

        # Layer 4: mappyfile（仅在 full=True 时执行）
        if full:
            errors.extend(self._check_mappyfile(tree))

        node.errors = [e["message"] for e in errors if e["path"] == path]
        return errors

    def validate_tree(self, tree: ConfigTree, service_types: list[str]) -> ValidationResult:
        """完整校验树（手动校验/导出前用）。"""
        all_errors: list[dict] = []

        for leaf in tree.root.leaves():
            all_errors.extend(self.validate_field(tree, leaf.path, service_types, full=False))

        # 递归校验所有子对象
        def walk(node: TreeNode):
            for child in node.nodes():
                for leaf in child.leaves():
                    all_errors.extend(self.validate_field(tree, leaf.path, service_types, full=False))
                walk(child)
        walk(tree.root)

        # 最后执行 mappyfile 语法校验
        all_errors.extend(self._check_mappyfile(tree))

        # 去重
        seen = set()
        unique = []
        for e in all_errors:
            key = (e.get("path"), e.get("message"))
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return ValidationResult(
            state="pass" if not unique else "fail",
            errors=unique,
        )

    def _try_resolve_alias(self, leaf: TreeLeaf) -> Any:
        if leaf.descriptor.custom:
            return None
        return self.mapper.resolve_alias(
            leaf.descriptor.phase,  # 这里应使用 object_type，示例简化
            leaf.descriptor.key,
            str(leaf.value),
        )

    def _check_type(self, leaf: TreeLeaf) -> list[dict]:
        ...

    def _check_semantic(self, tree: ConfigTree, leaf: TreeLeaf, service_types: list[str]) -> list[dict]:
        ...

    def _check_mappyfile(self, tree: ConfigTree) -> list[dict]:
        try:
            mf_dict = tree.to_mappyfile_dict()
            mf = mappyfile.loads(mappyfile.dumps(mf_dict))
            errors = mappyfile.validate(mf, version=8.4) or []
            return [{"path": "", "message": str(e), "level": "syntax"} for e in errors]
        except Exception as e:
            return [{"path": "", "message": f"Mapfile 语法错误: {e}", "level": "syntax"}]
```

### 7.5 PromptBuilder：组装 L0-L5

```python
class PromptBuilder:
    def __init__(self, templates_dir: str):
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir))
        self.framework = self.env.get_template("_framework.j2")

    def render(self,
               intent: str,
               map_snapshot: str,
               focus_param: str | None,
               context_summary: str,
               validation_errors: list[dict],
               recent_messages: str = "") -> str:
        return self.framework.render(
            intent=intent,
            map_snapshot=map_snapshot,
            focus_param=focus_param or "无",
            context_summary=context_summary,
            validation_errors=validation_errors,
            recent_messages=recent_messages,
        )
```

### 7.6 ExportService：导出

```python
class ExportService:
    def export(self, session: ConfigSession) -> dict[str, bytes]:
        if session.validation_state != "pass":
            raise ValidationError("校验未通过，无法导出")

        outputs = {}
        services = session.service_types.copy()

        # Mapfile（一份文件包含所有已勾选服务）
        mf_dict = session.tree.to_mappyfile_dict()
        outputs[f"{session.params.get('name', 'map')}.map"] = mappyfile.dumps(mf_dict).encode("utf-8")

        # MapCache XML（WMTS/TMS）
        if session.mapcache_enabled and "cache" in session.params:
            from backend.mapcache.generator import MapCacheGenerator
            xml = MapCacheGenerator().render(session.params)
            outputs["mapcache.xml"] = xml.encode("utf-8")
            # MapCache 导出时追加 wmts/tms 到服务摘要
            services.append("wmts")
            services.append("tms")

        return outputs

    def get_service_summary(self, session: ConfigSession) -> str:
        """生成导出确认弹窗的服务类型摘要。"""
        parts = []
        for svc in session.service_types:
            parts.append(svc.upper())
        if session.mapcache_enabled:
            parts.append("MapCache(WMTS/TMS)")
        if not parts:
            parts.append("WMS(默认)")
        return " + ".join(parts)

    # 前端收到 export_result 后：
    # 1. 确认弹窗显示服务类型摘要（如"含 WMS + WFS + MapCache(WMTS/TMS)"）
    # 2. 调用 Electron dialog.showSaveDialog 选择保存目录
    # 3. Electron 主进程接收 base64 内容，写入用户选择的目录
    # 4. 前端显示保存成功提示
```

### 7.7 ImportService：导入

```python
class ImportService:
    """
    Mapfile 导入服务：解析已有 .map 文件 → 新建 ConfigSession。

    职责：
    1. 调用 mappyfile.loads() 解析文本为 dict
    2. 以解析结果新建 ConfigSession（销毁旧 session）
    3. ConfigTree 自动标记未知字段为 custom=True
    4. 触发四层完整校验，返回结果
    """

    def __init__(self, mapper: TemplateMapper, validator: ValidationPipeline):
        self.mapper = mapper
        self.validator = validator

    def import_mapfile(self, session_id: str, content: str,
                       old_session: ConfigSession | None = None) -> tuple[ConfigSession, ValidationResult]:
        """
        导入 Mapfile 内容。

        参数：
            session_id: 新 session 的 ID
            content: Mapfile 文本内容（UTF-8）
            old_session: 旧 session（用于提取 intent_message，可选）

        返回：
            (新 ConfigSession, 校验结果)

        异常：
            MapfileParseError: mappyfile.loads() 解析失败
        """
        # 1. 解析
        new_session = ConfigSession.from_mapfile_content(session_id, content, self.mapper)

        # 2. 保留旧 session 的 intent_message（如果有）
        if old_session and old_session.intent_message:
            new_session.history.intent_message = old_session.intent_message

        # 3. 完整校验
        result = self.validator.validate_tree(new_session.tree)
        new_session.validation_state = result.state
        new_session.validation_errors = result.errors

        return new_session, result
```

### 7.8 核心类一览（后端）

| 类 | 文件 | 职责 |
|----|------|------|
| `ConfigSession` | `backend/core/session.py` | 单次任务完整状态容器 |
| `ConfigTree` | `backend/core/config_tree.py` | 配置树业务视图、行号计算 |
| `TreeNode` / `TreeLeaf` | `backend/core/config_tree.py` | 树节点/叶子模型 |
| `TemplateMapper` | `backend/core/template_mapper.py` | mapguide_rules.json 映射 |
| `FieldDescriptor` | `backend/core/template_mapper.py` | 统一字段描述 |
| `ValidationPipeline` | `backend/core/validation.py` | 四层校验 |
| `DialogueHistory` | `backend/core/history.py` | 精简会话历史 |
| `QAService` | `backend/core/qa_service.py` | LLM 问答服务 |
| `PromptBuilder` | `backend/llm/prompt_builder.py` | Prompt 组装 |
| `LLMClient` | `backend/llm/llm_client.py` | LLM 调用 |
| `LLMOutput` | `backend/llm/llm_output.py` | 响应解析 |
| `UpdateResolver` | `backend/llm/update_resolver.py` | 路径解析 |
| `ExportService` | `backend/core/export_service.py` | 导出 .map / .xml |
| `ImportService` | `backend/core/import_service.py` | 导入 .map → ConfigSession |
| `QAResult` / `ValidationResult` | `backend/core/result_types.py` | 前后端契约 |

### 7.8 前端组件一览

采用**分层渲染**方案，不使用 Naive UI 的 `n-tree`。

> **V3 验证结论**（`spike/v3_result.md`）：3 个核心组件验证通过，280 节点、4 层嵌套、7 种 `value_type` 控件映射全部覆盖。

**核心组件**：

| 组件 | 文件 | 职责 | 行数（参考） |
|------|------|------|-------------|
| `ConfigTreePanel` | `frontend/src/components/ConfigTreePanel.vue` | 左栏容器：工具栏（图例、显示模式）、树内容区、状态栏 | ~180 |
| `ObjectCard` | `frontend/src/components/ObjectCard.vue` | 对象节点卡片（MAP/LAYER/CLASS/STYLE/LABEL/WEB/METADATA/CACHE）：展开/折叠、Phase 徽章、子节点递归渲染 | ~140 |
| `FieldEditor` | `frontend/src/components/FieldEditor.vue` | 统一字段编辑器：按 `value_type` 内部分发到对应 Naive UI 控件 | ~290 |

**辅助组件**：

| 组件 | 文件 | 职责 |
|------|------|------|
| `QAPanel` | `frontend/src/components/QAPanel.vue` | 右栏问答面板：历史消息、输入框、轮次计数 |
| `CustomPropModal` | `frontend/src/components/CustomPropModal.vue` | 添加自定义属性模态框 |
| `ws.ts` | `frontend/src/services/ws.ts` | WebSocket 客户端封装 |

**控件映射详情**（`FieldEditor` 内部分发）：

| `value_type` | 控件 | 说明 |
|-------------|------|------|
| `string` | `n-input` | 文本输入 |
| `integer` | `n-input-number` | 整数输入（step=1，带 min/max） |
| `float` | `n-input-number` | 浮点数输入（step=0.1，带 min/max） |
| `boolean` | `n-switch` | 开关 |
| `enum` | `n-select` | 下拉选择（选项来自 `enum` 数组） |
| `array` | 多个 `n-input-number` | 横向排列（extent 4 个、size 2 个） |
| `color` | 3 个 `n-input-number` + 预览块 | RGB 各 0-255，右侧显示颜色预览 |

---

## 10. 导出实现

### 10.1 Mapfile 导出

直接使用 `mappyfile.dumps()` 从 `ConfigTree` 生成：

```python
def export_mapfile(tree: ConfigTree) -> str:
    mf_dict = tree.to_mappyfile_dict()
    text = mappyfile.dumps(mf_dict)
    # 再用 mappyfile 解析校验一次
    mf = mappyfile.loads(text)
    errors = mappyfile.validate(mf, version=8.4)
    if errors:
        raise ValidationError(errors)
    return text
```

### 10.2 MapCache 导出

保持不变，使用 `backend/mapcache/generator.py` + `mapcache.xml.j2`。

---
