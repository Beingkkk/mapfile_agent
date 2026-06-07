# Plan: Backend LLM Integration

> **模块**：后端 LLM 链路
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M5
> **对应 design**：`design/llm-integration.md`
> **前置依赖**：`plan-config-tree` DC-004（ConfigSession）

---

## 1. 模块概述

LLM 集成模块负责与 Anthropic Claude API 通信，包括会话历史管理、Prompt 组装、API 调用、响应容错解析、参数更新应用。核心目标是让 LLM 输出稳定可解析的 JSON，同时保持对用户友好的自然语言回答。

**本模块相对独立**：除 DialogueHistory 外，其他子模块只依赖 ConfigSession（获取当前 map 状态和焦点）。可用 Mock 测试完全闭环。

**包含内容**：
- `backend/core/history.py` — DialogueHistory
- `backend/llm/prompt_builder.py` — PromptBuilder
- `backend/llm/llm_client.py` — LLMClient
- `backend/llm/llm_output.py` — LLMOutput
- `backend/llm/update_resolver.py` — UpdateResolver

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| 单 Prompt 架构，只有 `_framework.j2` | `constitution.md` §4.2 |
| Token 预算 ~1500 tokens（L0-L5） | `conventions.md` §15.5 |
| temperature=0.1 | `conventions.md` §15.5 |
| 指数退避 3 次重试，总超时 ≤30s | `conventions.md` §15.5 |
| 四层容错解析，失败降级为纯文本 | `llm-integration.md` §V2.3 |
| content ≤ 300 中文字符 | `llm-integration.md` §V2.5 |
| 最近 6 轮 QA 历史注入 Prompt | `llm-integration.md` §5.2 |
| LLM 返回 JSON 格式：`{thought, action, params_update, question}` | `spec.md` §3.1 F-M5 |

---

## 3. 接口定义

### 3.1 DialogueHistory — 精简会话历史

```python
# DC-017: backend/core/history.py

@dataclass
class DialogueMessage:
    role: str  # user | bot
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

class DialogueHistory:
    def __init__(self) -> None: ...

    def set_intent(self, text: str) -> None: ...
    def set_focus(self, focus_param: str | None) -> None: ...
    def add_message(self, role: str, content: str) -> None: ...
    def to_prompt_context(self) -> str: ...

    @property
    def round_count(self) -> int: ...
```

### 3.2 PromptBuilder — Prompt 组装

```python
# DC-018: backend/llm/prompt_builder.py

class PromptBuilder:
    def __init__(self, templates_dir: str) -> None: ...

    def render(
        self,
        intent: str,
        map_snapshot: str,
        focus_param: str | None,
        context_summary: str,
        validation_errors: list[dict],
        recent_messages: str = "",
    ) -> str: ...
```

### 3.3 LLMClient — API 调用

```python
# DC-019: backend/llm/llm_client.py

class LLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        base_url: str | None = None,
        temperature: float = 0.1,
        max_retries: int = 3,
    ) -> None: ...

    async def chat(self, prompt: str) -> str: ...

    @property
    def last_usage(self) -> dict: ...
```

### 3.4 LLMOutput — 响应解析

```python
# DC-020: backend/llm/llm_output.py

@dataclass
class ParsedOutput:
    thought: str
    action: str  # answer | update | question
    params_update: list[dict]  # [{path, value}]
    question: str  # 给用户的自然语言回答

class LLMOutput:
    @classmethod
    def parse(cls, raw: str) -> ParsedOutput: ...

    # 内部解析策略
    @classmethod
    def _try_direct_json(cls, raw: str) -> dict | None: ...
    @classmethod
    def _try_strip_codeblock(cls, raw: str) -> dict | None: ...
    @classmethod
    def _try_brace_extract(cls, raw: str) -> dict | None: ...
    @classmethod
    def _try_json5_tolerant(cls, raw: str) -> dict | None: ...
    @classmethod
    def _fallback(cls, raw: str) -> ParsedOutput: ...
```

### 3.5 UpdateResolver — 路径解析与值转换

```python
# DC-021: backend/llm/update_resolver.py

class UpdateResolver:
    def resolve(self, update: dict) -> str: ...

    @staticmethod
    def _normalize_path(path: str) -> str: ...
    @staticmethod
    def _coerce_value(path: str, value: Any, mapper: TemplateMapper) -> Any: ...
```

---

## 4. 数据流

### 4.1 用户提问 → LLM 回答

```
WS: question { text }
  → QAService.answer() (in plan-platform DC-053)
    ├── DialogueHistory.add_message("user", text)
    ├── PromptBuilder.render(L0-L5)
    ├── LLMClient.chat(prompt)
    ├── LLMOutput.parse(raw)
    ├── UpdateResolver.resolve() x N
    ├── ConfigTree.update_value() x N
    ├── ValidationPipeline.validate_tree()
    └── DialogueHistory.add_message("bot", answer)
  → WS: qa_result { ... }
```

### 4.2 L0-L5 Prompt 上下文

| 层级 | 内容 | 来源 | 长度控制 |
|------|------|------|----------|
| L0 | 系统角色 + JSON 输出格式要求 | `_framework.j2` | ~200 tokens |
| L1 | 用户初始意图 + 当前 map 结构快照 | DialogueHistory + ConfigTree | ~300 tokens |
| L2 | 关注点参数摘要 | TemplateMapper | ~400 tokens |
| L3 | focus_param 路径 | ConfigSession | ~30 tokens |
| L4 | 当前校验错误 | ValidationPipeline | ~200 tokens |
| L5 | 最近 4-6 轮对话 | DialogueHistory | ~400 tokens |

---

## 5. 测试策略

### 5.1 单元测试

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-017 | `tests/unit/test_history.py` | set_intent、set_focus 清空、to_prompt_context 6 轮限制 |
| DC-018 | `tests/unit/test_prompt_builder.py` | L0-L5 组装、变量注入、模板渲染 |
| DC-019 | `tests/unit/test_llm_client.py` | Mock API 调用、重试逻辑、超时处理 |
| DC-020 | `tests/unit/test_llm_output.py` | 四层解析各层触发、fallback、常见错误模式 |
| DC-021 | `tests/unit/test_update_resolver.py` | 路径规范化、值强制转换 |

### 5.2 关键测试数据（来自 V2 spike）

```python
# 测试用例：strip_codeblock 触发（23% 概率）
raw_codeblock = '```json\n{"thought": "...", "action": "answer"}\n```'

# 测试用例：content 超长截断
raw_truncated = '{"thought": "...", "action": "answer", "question": "' + "x" * 5000

# 测试用例：projection 字符串而非数组
update_projection_str = {"path": "layers.0.projection", "value": "init=epsg:3857"}

# 测试用例：status JSON 布尔而非字符串
update_status_bool = {"path": "layers.0.status", "value": False}
```

---

## 6. 任务清单

### Phase 1: 历史与 Prompt（TDD）

- [ ] [RED] `test_history.py` — 意图设置、focus 切换清空、6 轮限制
- [ ] [GREEN] `history.py` — DialogueHistory
- [ ] [RED] `test_prompt_builder.py` — L0-L5 组装、变量注入
- [ ] [GREEN] `prompt_builder.py` — PromptBuilder + `_framework.j2`
- [ ] [REFACTOR] 模板缓存优化

### Phase 2: LLM 客户端（TDD）

- [ ] [RED] `test_llm_client.py` — Mock 调用、重试、超时
- [ ] [GREEN] `llm_client.py` — LLMClient（anthropic SDK 封装）
- [ ] [REFACTOR] 提取重试装饰器

### Phase 3: 解析与更新（TDD）

- [ ] [RED] `test_llm_output.py` — direct_json、strip_codeblock、brace_extract、json5_tolerant、fallback
- [ ] [GREEN] `llm_output.py` — LLMOutput.parse()
- [ ] [RED] `test_update_resolver.py` — 路径规范化、值强制转换
- [ ] [GREEN] `update_resolver.py` — UpdateResolver
- [ ] [REFACTOR] 错误分类统计

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| `_framework.j2` | Prompt 模板尚未创建 | **高** — Phase 1 阻塞项 |
| `spike/v2_result.md` | V2 验证结论需转换为生产测试用例 | 高 — Phase 3 必须覆盖 |
| 模型名称硬编码 | `claude-3-sonnet-20240229` 需可配置 | 低 — MVP 后处理 |
| `plan-platform` DC-053 | QAService 依赖本模块全部组件 | — 依赖关系，非技术债 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
