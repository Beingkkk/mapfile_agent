---
title: LLM 集成
description: 会话历史策略、Prompt 上下文分级、QAService、PromptBuilder、LLMClient、LLMOutput 容错解析
---

## 5. 会话历史策略

### 5.1 不保留全部历史

v2 的会话历史不是无限的。设计原则：

- **主题意图消息**（进入任务开始时用户发送的第一条消息）**永远保留**
- **关注点切换后**，可以选择性清空该关注点之前的问答记录
- 仅保留与**当前关注点**相关的上下文

### 5.2 历史清理触发条件

```python
class DialogueHistory:
    """精简的会话历史管理。"""

    def __init__(self):
        self.intent_message: str | None = None   # 永远保留
        self.messages: list[DialogueMessage] = []  # 当前关注点的上下文
        self.current_focus: str | None = None

    @property
    def round_count(self) -> int:
        """当前关注点的问答轮数（user + bot 为 1 轮）。"""
        return len(self.messages) // 2

    def set_intent(self, text: str):
        """用户进入新任务时发送的主题意图。"""
        self.intent_message = text
        self.messages = []

    def set_focus(self, focus_param: str | None):
        """
        用户切换关注点时触发。
        如果 focus_param 发生变化，清空 messages（保留意图），轮数归零。
        """
        if focus_param != self.current_focus:
            self.messages = []  # 只保留意图，清空之前问答
            self.current_focus = focus_param

    def add_message(self, role: str, content: str):
        self.messages.append(DialogueMessage(role=role, content=content))

    def to_prompt_context(self) -> str:
        """生成给 LLM 的历史上下文。"""
        parts = []
        if self.intent_message:
            parts.append(f"【用户初始意图】{self.intent_message}")
        for msg in self.messages[-6:]:  # 只保留最近 6 轮
            parts.append(f"{msg.role}: {msg.content}")
        return "\n".join(parts)
```

### 5.3 为什么这样设计

- **LLM token 预算有限**：Mapfile 结构上下文 + 模板摘要 + 历史消息，很容易超过 8k
- **用户切换关注点 = 开启新话题**：之前关于 color 的讨论对 projection 问题没有帮助
- **意图必须保留**："我要把 PostGIS buildings 表发布成 WMS" 这条信息决定后续所有回答的上下文

---

## 6. LLM 上下文策略

### 6.1 不发送完整模板

LLM Prompt **不能**把整个 schema 扔进去，因为：

- Mapfile schema 有数百个字段，全量 token 爆炸
- LLM 不需要知道所有字段，只需要知道**当前关注点相关的字段**

**上下文分级**：

| 层级 | 内容 | 长度控制 |
|------|------|---------|
| L0 系统角色 | `_framework.j2` 固定模板 | ~200 tokens |
| L1 用户意图 | 初始意图 + 当前 map 结构快照 | ~300 tokens |
| L2 关注点摘要 | 当前关注对象/参数 + 相关模板字段摘要 | ~400 tokens |
| L3 关注点路径 | `focus_param`（如 `layers.0.name`） | ~30 tokens |
| L4 当前错误 | 校验错误（如果有） | ~200 tokens |
| L5 精简历史 | 最近 4-6 轮对话 | ~400 tokens |
| **总计** | | **~1500 tokens** |

### 6.2 模板摘要生成规则

`TemplateMapper.get_llm_context_summary(object_type)` 的生成规则：

```
LAYER 对象参数摘要：
- name: string, 必填, 图层名称
- type: enum[point,line,polygon,raster], 必填, 几何类型
- connectiontype: enum[local,postgis,ogr,wms], 必填, 数据源连接类型
- connection: string, 条件必填（connectiontype=postgis 时）, 连接字符串
- data: string, 条件必填（非 local 时）, 数据查询
- projection: array, 可选, 坐标参考系统
```

**摘要原则**：
- 只输出字段名 + 类型 + 是否必填 + 一句话说明
- 不输出 min/max/default 等细节（后端处理）
- **`editable=false` 的字段不输出到 LLM Prompt**，避免 LLM 误建议修改不可编辑内容
- 如果用户关注的是**属性节点**，只输出该字段 + 同对象内必填字段
- 如果用户关注的是**对象节点**，输出该对象的所有直接子字段（已过滤 editable=false）

### 6.3 Prompt 组装示例

```jinja2
你是一位专业的 MapServer 配置助手。用户直接在配置树中编辑参数，你的职责是：
1. 回答用户关于参数含义的问题
2. 分析校验错误的原因
3. 建议正确的配置值

【用户初始意图】
{{ intent_message }}

【当前配置快照】
{{ map_structure_yaml }}

【当前关注点】
参数路径：{{ focus_param }}

【相关参数说明】
{{ context_summary }}

{% if validation_errors %}
【当前校验错误】
{{ validation_errors }}
{% endif %}

【最近对话】
{{ recent_messages }}

请用中文回答用户的问题。如果用户询问如何修改参数，请直接给出建议值。
如果需要修改参数，请按以下 JSON 格式返回：
{
  "thought": "简短思考",
  "action": "answer",
  "params_update": [
    {"path": "layers.0.connectiontype", "value": "postgis"}
  ],
  "question": "给用户的自然语言回答"
}
```

---

## 附录：V2 验证结论（LLM Prompt 输出稳定性）

> 验证时间：2026-06-06 | 模型：M3 (minimaxi) | 30 次 API 调用

### V2.1 核心指标

| 指标 | 结果 | 标准 | 状态 |
|------|------|------|------|
| JSON 可解析率 | **93.3%** (28/30) | ≥ 90% | ✅ 通过 |
| action 正确率 | **78.6%** (22/28) | ≥ 80% | ⚠️ 接近 |

### V2.2 action 场景差异（关键发现）

| 场景 | 稳定性 | 失败模式 | 建议 |
|------|--------|---------|------|
| `action=update`（参数修改） | **100%**（9/9） | 无 | 核心场景，极其稳定 |
| `action=answer`（长文本解释） | **86%**（12/14） | content 超长导致 JSON 截断 | prompt 中限制 content≤300 字 |
| `action=question`（反问） | **89%**（8/9） | 同上 | 同上 |

**结论**：参数修改是核心场景，稳定性极高；长文本解释有较低失败风险，需控制 content 长度。

### V2.3 宽容解析策略（已验证有效）

LLM 输出需经过 **4 层容错解析**（借鉴 GISTaskAgent `diagnosis.py` 模式）：

```python
# 解析优先级
direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback
```

| 策略 | 触发率 | 说明 |
|------|--------|------|
| `direct_json` | 70% | 直接解析成功 |
| `strip_codeblock` | **23%** | LLM 经常输出 ` ```json {...} ``` `，即使 prompt 明确禁止 |
| `json5_tolerant` | 0% | 本次未触发，保留作为兜底 |
| `all_failed` | 7% | 两次均发生在 content 超长的 answer/question 场景 |

**关键经验**：`strip_codeblock` 至关重要——即使 prompt 强调"不要 Markdown 代码块"，LLM 仍经常添加。

### V2.4 LLM 值类型常见问题

V2 发现 LLM 在值类型上有两种常见错误，需 `UpdateResolver` 或 L2 强制转换：

| 字段 | LLM 可能输出 | 正确格式 | 转换逻辑 |
|------|-------------|---------|---------|
| `projection` | 字符串 `"init=epsg:4326"` | 数组 `["init=epsg:4326"]` | `isinstance(v, str) → [v]` |
| `status` | JSON 布尔 `false` | 字符串 `"OFF"` | `isinstance(v, bool) → "ON"/"OFF"` |

这与 V1 发现的 mappyfile enum-boolean 混用问题一致。

### V2.5 PromptBuilder 设计修正

基于 V2 验证，`_framework.j2` 需增加以下约束：

1. **明确禁止 Markdown 代码块**：`"不要输出 ```json 代码块标记，直接输出原始 JSON"`
2. **限制 content 长度**：`"content 字段不超过 300 中文字符，避免输出截断"`
3. **action 选择引导**：明确区分 answer/update/question 的适用场景

### V2.6 LLMOutput 错误分类

```python
error_types = {
    "json_parse":       "助手返回的格式无法识别，已转为普通问答模式。",
    "schema_missing":   "助手返回的数据不完整，已记录此问题。",
    "schema_invalid":   "助手返回了意外的操作类型，已按最保守方式处理。",
    "empty_response":   "助手没有返回有效内容，请重试。",
}
```

每种错误类型独立计数，便于后续分析 prompt 效果并迭代优化。
