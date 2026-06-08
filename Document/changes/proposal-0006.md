# Proposal-0006: LLM 链路完整实现

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Plan**: `plan-backend-llm` Phase 1-3
> **影响范围**:
> - `backend/llm/prompt_builder.py` — PromptBuilder
> - `backend/llm/llm_client.py` — LLMClient
> - `backend/llm/llm_output.py` — LLMOutput
> - `backend/llm/update_resolver.py` — UpdateResolver
> - `backend/core/qa_service.py` — QAService 组装层
> - `backend/llm/templates/_framework.j2` — Prompt 模板
> - `tests/unit/test_prompt_builder.py` — PromptBuilder 测试
> - `tests/unit/test_llm_client.py` — LLMClient 测试
> - `tests/unit/test_llm_output.py` — LLMOutput 测试
> - `tests/unit/test_update_resolver.py` — UpdateResolver 测试
> - `tests/unit/test_qa_service.py` — QAService 测试

---

## 目标

实现 LLM 链路全部组件（PromptBuilder → LLMClient → LLMOutput → UpdateResolver → QAService），使后端能够接收用户问题、组装 Prompt、调用 LLM、解析响应、应用更新、校验结果，并返回前端。

**核心复杂度**：
1. LLMOutput 四层容错解析（direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback）
2. UpdateResolver 的值强制转换（projection 字符串→数组、status 布尔→字符串）
3. PromptBuilder L0-L5 上下文组装 + ~1500 token 预算

**原则**：
- TDD 纪律：RED → GREEN → REFACTOR
- LLMClient 用 Mock 测试（无需真实 API 调用）
- 所有组件可独立测试

---

## 变更内容

### [ADDED] `backend/llm/prompt_builder.py`

**PromptBuilder**：
- `__init__(templates_dir)` — 加载 `_framework.j2` 模板
- `render(intent, map_snapshot, focus_param, context_summary, validation_errors, recent_messages)` → `str`

### [ADDED] `backend/llm/llm_client.py`

**LLMClient**（Anthropic SDK 封装）：
- `__init__(api_key, model, base_url, temperature, max_retries)`
- `chat(prompt)` → `str` — 同步调用，指数退避 3 次重试
- `last_usage` — property，返回 token 使用量

### [ADDED] `backend/llm/llm_output.py`

**ParsedOutput**（dataclass）：`thought`, `action`, `params_update`, `question`

**LLMOutput**：
- `parse(raw)` → `ParsedOutput` — 四层容错解析
- `_try_direct_json(raw)` → `dict | None`
- `_try_strip_codeblock(raw)` → `dict | None`
- `_try_brace_extract(raw)` → `dict | None`
- `_try_json5_tolerant(raw)` → `dict | None`
- `_fallback(raw)` → `ParsedOutput`

### [ADDED] `backend/llm/update_resolver.py`

**UpdateResolver**：
- `resolve(update, mapper)` → `dict` — `{path, value}` 规范化 + 强制转换
- `_normalize_path(path)` — `layers[0]` → `layers.0`
- `_coerce_value(path, value, mapper)` — 按 value_type 转换

### [ADDED] `backend/core/qa_service.py`

**QAService**（组装层）：
- `__init__(session, pipeline, mapper, client, builder)`
- `answer(question)` → `dict` — 完整 6 步流水线
  1. `history.add_message("user", question)`
  2. `builder.render(L0-L5)`
  3. `client.chat(prompt)`
  4. `LLMOutput.parse(raw)`
  5. `UpdateResolver.resolve() × N` + `tree.update_value()` + `validate_tree()`
  6. `history.add_message("bot", answer)`
- 返回 `dict`：`{action, updates, answer, validation_state, errors}`

### [ADDED] `backend/llm/templates/_framework.j2`

系统角色 + JSON 输出格式要求的 Jinja2 模板。

---

## 测试策略

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-018 | `test_prompt_builder.py` | 模板加载、变量注入、L0-L5 组装 |
| DC-019 | `test_llm_client.py` | Mock API 调用、重试逻辑、超时处理 |
| DC-020 | `test_llm_output.py` | 四层解析各层触发、fallback、常见错误模式 |
| DC-021 | `test_update_resolver.py` | 路径规范化、值强制转换 |
| DC-053 | `test_qa_service.py` | Mock 端到端流水线、update/answer/question action |

---

## 验收标准

- [x] `pytest tests/unit/test_prompt_builder.py -v` 全部通过（12 项）
- [x] `pytest tests/unit/test_llm_client.py -v` 全部通过（8 项）
- [x] `pytest tests/unit/test_llm_output.py -v` 全部通过（19 项）
- [x] `pytest tests/unit/test_update_resolver.py -v` 全部通过（22 项）
- [x] `pytest tests/unit/test_qa_service.py -v` 全部通过（8 项）
- [x] LLMOutput 四层解析：direct_json、strip_codeblock、brace_extract、json5_tolerant 各覆盖
- [x] LLMOutput fallback：无法解析时返回 `action=answer` 的纯文本
- [x] UpdateResolver 强制转换：projection→array、status→ON/OFF、颜色别名、整数/浮点字符串
- [x] QAService `answer()` 返回 `{action, updates, answer, validation_state, errors}`
- [x] 全部 295 个测试通过，零回归

---

## 依赖

- proposal-0003（TemplateMapper + FieldDescriptor，resolve_alias / get_llm_context_summary 接口）
- proposal-0004（ConfigSession + ConfigTree，update_value / to_mappyfile_dict）
- proposal-0005（ValidationPipeline + DialogueHistory，validate_tree / add_message）

---

*Approved by: SDD 流程 — plan-backend-llm Phase 1-3 既定任务*
