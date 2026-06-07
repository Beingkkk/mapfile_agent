# Proposal-0002: generate_rules.py 单元测试补充

> **类型**: Type-D（技术债重构 — 为既有代码补测试）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-07
> **对应 Plan**: `plan-template-system` Phase 1
> **影响范围**: `tests/unit/test_generate_rules.py`、`tests/integration/test_rules_output.py`

---

## 目标

为已交付的 `scripts/generate_rules.py` 补充单元测试与集成测试，建立 TDD 信心，确保规则合并逻辑的正确性。

**原则**：不修改 `scripts/generate_rules.py` 的行为，只通过测试覆盖已有函数；集成测试验证生成产物结构完整。

---

## 变更内容

### [MODIFIED] `tests/unit/test_generate_rules.py`

将占位测试替换为完整单元测试，覆盖以下函数：

| 函数 | 测试重点 |
|------|----------|
| `load_json` | 正常加载、文件不存在返回 `{}` |
| `resolve_schema_path` | 按 key 链正确解析、路径中断返回 `{}` |
| `infer_value_type` | enum → "enum"、类型映射、未知 fallback、oneOf 处理、颜色/表达式推断 |
| `is_nested_object` | object + properties、array + items 检测 |
| `extract_field_info` | schema 字段提取、object-fields 简化格式、oneOf enum 合并 |
| `build_object_type_rules` | 字段合并、默认值优先级、phase 应用、editable 标记、object_fields 补充 |
| `build_flat_params` | 各对象类型扁平路径生成、METADATA 双路径（map.web + layers.N）|
| `inject_derived_params` | dependencies 中 derives 关系正确标记 derived |

### [MODIFIED] `tests/integration/test_rules_output.py`

端到端验证 `generate_rules.main()` 的输出结构：

- 产物包含 `version`、`mapserver_version`、`object_types`、`flat_params`、`aliases`、`dependencies`、`phase_map`、`custom_allowed`、`service_metadata`
- 所有 object_types 的 `fields` 非空
- `flat_params` 包含预期的占位符路径（`layers.N.*`、`layers.N.classes.M.*` 等）
- `CACHE` 对象类型存在（纯 object-fields 提供）

---

## 验收标准

- [ ] `pytest tests/unit/test_generate_rules.py -v` 全部通过
- [ ] `pytest tests/integration/test_rules_output.py -v` 全部通过
- [ ] 重新运行 `scripts/generate_rules.py` 后产物不变（回归验证）
- [ ] 测试覆盖率针对 `generate_rules.py` 函数级 ≥85%

---

## 依赖

- proposal-0001 已提交（测试目录已创建）
- `scripts/generate_rules.py` 已完整交付
- `data/templates/*.json` 已存在

---

*Approved by: SDD 流程 — plan-template-system Phase 1 既定任务*
