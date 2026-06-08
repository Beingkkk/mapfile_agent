# Proposal-0005: ValidationPipeline L1-L4 + DialogueHistory 完整实现

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Plan**: `plan-validation` Phase 1-5, `plan-backend-llm` Phase 1
> **影响范围**:
> - `backend/core/validation.py` — ValidationPipeline, ValidationResult
> - `backend/core/history.py` — DialogueHistory 完整实现
> - `tests/unit/test_validation.py` — 取代占位测试
> - `tests/unit/test_history.py` — 取代占位测试

---

## 目标

实现四层校验体系（ValidationPipeline L1-L4），使 ConfigTree 的每次字段变更和 LLM 更新都能经过完整的校验流程。同时补齐 DialogueHistory 的最小占位实现，为后续 LLM 链路做准备。

**核心复杂度**：L4 mappyfile 语法校验的 false positive 过滤——mappyfile 会拒绝 schema 外部字段（自定义属性 + object-fields.json 补充字段），但业务允许这些字段存在。

**原则**：
- 字段失焦只跑 L1-L3；添加/删除节点、手动校验、导出跑全部四层
- 校验错误统一格式 `{path, message, level}`
- 别名解析是静默替换，不报错
- DialogueHistory 按 focus_param 分组，保留初始 intent，最多 6 轮

---

## 变更内容

### [ADDED] `backend/core/validation.py`

实现两个组件：

**`ValidationResult`**（dataclass）：`state: str` (pass|fail), `errors: list[dict]`

**`ValidationPipeline`**：
- `__init__(mapper)` — 加载 `dependencies.json` 作为 L3 规则源
- `validate_field(tree, path, service_types, full=False)` → `list[dict]` — 字段级校验（L1-L3，full=True 时加 L4）
- `validate_tree(tree, service_types)` → `ValidationResult` — 完整树校验（全部四层）
- `_try_resolve_alias(leaf)` → `Any` — L1：通过 `TemplateMapper.resolve_alias` 静默替换别名
- `_check_type(leaf)` → `list[dict]` — L2：按 `value_type` 校验（enum/integer/float/boolean/color/array/expression）
- `_check_semantic(tree, leaf, service_types)` → `list[dict]` — L3：`dependencies.json` 驱动条件必填/互斥/推导
- `_check_mappyfile(tree)` → `list[dict]` — L4：`mappyfile.validate()` + false positive 过滤

**L3 依赖表达式安全求值**：使用受限求值（`ast.literal_eval` + 白名单运算符），避免 `eval()` 安全风险。

**L4 false positive 过滤**：
- 白名单来源：`custom-allowed.json` 中的对象类型允许自定义属性；`object-fields.json` 中的字段
- 过滤策略：对 mappyfile 返回的错误，如果错误路径对应的字段在允许列表中，则忽略该错误
- mappyfile 错误格式：`"does not match any of the regexes"` → 检查对应 key 是否在白名单中

### [MODIFIED] `backend/core/history.py`

从最小占位升级为完整实现：

**`DialogueMessage`**（dataclass）：`role`, `content`, `timestamp`, `intent`, `focus_param`

**`DialogueHistory`**：
- `set_intent(text)` — 设置初始用户意图，保存为 system 消息
- `set_focus(focus_param)` — 设置当前焦点参数
- `add_message(role, content)` — 添加消息，自动递增 round_count
- `to_prompt_context()` — 返回最近最多 6 轮对话的格式化字符串
- `round_count` — property，当前焦点下的对话轮次
- `reset_on_focus_change()` — focus 切换时重置 round counter，保留 system/intent 消息

### [MODIFIED] `tests/unit/test_validation.py`

取代占位测试，覆盖 plan-validation 全部测试策略：

| DC | 测试类 | 用例 |
|---|---|---|
| DC-012 | `TestValidationResult` | 创建、状态判断 |
| DC-014 | `TestL1AliasResolution` | 别名命中、别名不存在（透传）、颜色别名 |
| DC-014 | `TestL2TypeCheck` | enum/integer/float/boolean/color/array/expression 各类型边界 |
| DC-015 | `TestL3SemanticCheck` | 条件必填触发/不触发、互斥、服务类型条件 |
| DC-016 | `TestL4MappyfileSyntax` | 合法 mapfile 通过、自定义属性不报错、object-fields 不报错 |
| DC-015 | `TestValidationPipelineIntegration` | validate_field、validate_tree、错误去重 |

### [MODIFIED] `tests/unit/test_history.py`

取代占位测试：

| DC | 测试类 | 用例 |
|---|---|---|
| DC-017 | `TestDialogueHistory` | set_intent、add_message、round_count、6轮限制、focus切换重置 |

---

## 验收标准

- [x] `pytest tests/unit/test_validation.py -v` 全部通过（38 项）
- [x] `pytest tests/unit/test_history.py -v` 全部通过（12 项）
- [x] L1 别名解析：对已知别名正确替换，未知别名透传原值
- [x] L2 类型检查：覆盖全部 8 种 value_type，enum 大小写不敏感
- [x] L3 语义检查：`requires_when` 条件必填触发/不触发、`forbids_when` 互斥检测
- [x] L4 mappyfile：合法 mapfile 通过校验，自定义属性不报错（false positive 过滤）
- [x] `validate_field` 失焦模式只跑 L1-L3，`validate_tree` 跑全部四层
- [x] DialogueHistory 保留初始 intent，focus 切换后 round_count 重置为 0
- [x] DialogueHistory `to_prompt_context` 最多返回 6 轮对话
- [x] 全部 214 个单元测试通过，17 个集成测试通过，零回归

---

## 依赖

- proposal-0003（TemplateMapper + FieldDescriptor，resolve_alias 接口）
- proposal-0004（ConfigSession + ConfigTree，get_node / update_value / to_mappyfile_dict）
- `data/templates/dependencies.json` 已存在
- `data/templates/custom-allowed.json` 已存在
- mappyfile==1.1.1（已验证）

---

*Approved by: SDD 流程 — plan-validation Phase 1-5 既定任务*
