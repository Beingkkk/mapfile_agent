# Proposal-0003: TemplateMapper + FieldDescriptor

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-07
> **对应 Plan**: `plan-template-system` Phase 2
> **影响范围**: `backend/core/template_mapper.py`、`tests/unit/test_template_mapper.py`

---

## 目标

实现运行时规则查询组件 `TemplateMapper` 和字段元数据描述符 `FieldDescriptor`，为 `ConfigTree` 和 `QAService` 提供规则查询能力。

**原则**：纯数据查询组件，无状态（规则文件在 `__init__` 中一次性加载），覆盖 plan 中 DC-002/DC-003 定义的接口。

---

## 变更内容

### [ADDED] `backend/core/template_mapper.py`

实现两个组件：

**`FieldDescriptor`**（dataclass）：封装单个字段的完整元数据，从 `mapguide_rules.json` 的字段定义映射而来。

**`TemplateMapper`**：运行时唯一规则文件读取入口，接口：
- `__init__(rules_path)` — 加载并解析 `mapguide_rules.json`
- `get_object_type(object_type)` → dict — 返回对象类型规则（含 fields/required/business_required/required_when）
- `get_field_descriptor(object_type, field)` → FieldDescriptor — 从字段定义构建描述符
- `allows_custom_properties(object_type)` → bool — 查询 `custom_allowed`
- `list_all_fields(object_type)` → list[str] — 返回字段名列表
- `resolve_alias(object_type, field, alias)` → Any — 自然语言/中文 → 参数值
- `get_llm_context_summary(object_type)` → str — 为 LLM prompt 生成字段摘要

### [ADDED/MODIFIED] `tests/unit/test_template_mapper.py`

替换占位测试，覆盖：
- `TemplateMapper` 初始化与加载
- `get_object_type` 正常查询与异常处理
- `get_field_descriptor` 属性正确映射
- `allows_custom_properties` 按 `custom_allowed` 判断
- `list_all_fields` 返回完整字段列表
- `resolve_alias` 正向解析与 fallback 行为
- `get_llm_context_summary` 生成非空摘要
- `FieldDescriptor` dataclass 创建与属性访问

---

## 验收标准

- [ ] `pytest tests/unit/test_template_mapper.py -v` 全部通过
- [ ] 测试使用真实 `data/mapguide_rules.json` 验证，不依赖 mock
- [ ] `TemplateMapper` 对缺失 object_type / field 返回 `None`（不抛异常）
- [ ] `resolve_alias` 对未知 alias 返回原值（透传）
- [ ] 代码符合类型注解规范

---

## 依赖

- proposal-0001（目录结构）
- proposal-0002（generate_rules.py 已验证）
- `data/mapguide_rules.json` 已生成

---

*Approved by: SDD 流程 — plan-template-system Phase 2 既定任务*
