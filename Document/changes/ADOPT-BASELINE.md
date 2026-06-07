# SDD 采纳基线标记

> **日期**：2026-06-07
> **基线版本**：v1.0.0
> **操作**：/sdd-adopt → 模块重拆（6 plan）

---

## 采纳范围

本项目（MapGuide）从既有设计文档体系迁移到 SDD 规范驱动开发工作流。

### 源文档

| 源文档 | 用途 | 迁移去向 |
|--------|------|----------|
| `Document/需求输入.md` | PRD（626 行） | → `Document/spec.md` |
| `Document/技术细节.md` | 技术总览索引 | → 各 plan 文件 + `Document/constitution.md` |
| `Document/design/*.md`（8 份） | 模块设计 | → 6 个 plan 文件 |
| `Document/UX/ui-prototype-interactive-v2.html` | UI 原型 | → 原型参考（保留，非 plan 内容） |
| `Document/design/implementation-progress.md` | 进度评估 | → 各 plan 任务清单 |

### 已交付代码基线

| 代码 | 状态 | Plan 覆盖 |
|------|------|----------|
| `SourceCode/scripts/generate_rules.py` | 已交付，缺测试 | `plan-template-system.md` DC-001 |
| `SourceCode/data/templates/*.json` | 已交付 | `plan-template-system.md` DC-001 |
| `SourceCode/data/mapguide_rules.json` | 生成产物 | `plan-template-system.md` DC-002 |
| `SourceCode/spike/` | 验证脚本 | 非生产代码，保留为参考 |

---

## 创建的 SDD 文档

### 约束层

- ✅ `Document/constitution.md` — 最高约束（技术栈锁定、架构铁律、红色条款）

### 需求层

- ✅ `Document/spec.md` — 需求真相源（Must/Should/Could/Won't Have、验收标准）

### 设计层（6 个 Plan）

| Plan | DC 编号 | 周期 | 内容 | 前置依赖 |
|------|--------|------|------|----------|
| `plan-template-system` | DC-001~003 | **3-4 天** | 规则生成器 + TemplateMapper + FieldDescriptor | 无（已有代码） |
| `plan-config-tree` | DC-004~011 | **4-5 天** | ConfigSession + ConfigTree + TreeNode/TreeLeaf + 序列化 | plan-template-system |
| `plan-validation` | DC-012~016 | **4-5 天** | 四层校验（L1 别名 → L2 类型 → L3 语义 → L4 mappyfile） | plan-config-tree |
| `plan-backend-llm` | DC-017~021 | **4-5 天** | DialogueHistory + PromptBuilder + LLMClient + LLMOutput + UpdateResolver | plan-config-tree |
| `plan-frontend` | DC-022~030 | **5-7 天** | Vue 3 组件 + Pinia + WebSocket | plan-platform（契约） |
| `plan-platform` | DC-031~038 | **5-7 天** | QAService + Export/Import + MapCache + FastAPI + Electron | plan-config-tree + plan-validation + plan-backend-llm |

### 变更管理

- ✅ `Document/changes/` — 变更提案目录
- ✅ `Document/archive/` — 归档目录
- ✅ `Document/technical-debt.md` — 10 项技术债登记

---

## 重拆理由

**原 4 plan 的问题**：

| 原 Plan | 问题 | 解决方式 |
|---------|------|----------|
| `plan-backend-core` | 9 个类垂直跨度太大（数据→校验→服务） | 拆为 `plan-config-tree` + `plan-validation` + `plan-platform`（QAService/Export/Import） |
| `plan-infrastructure` | 4 个无关领域硬塞一起（规则生成/MapCache/FastAPI/Electron） | 规则生成移入 `plan-template-system`，其余归入 `plan-platform` |

**新 6 plan 的优势**：

- 每个 plan **3-7 天**完成，周期可控
- `plan-template-system` 风险最低先交付，建立 TDD 信心
- `plan-config-tree` 是数据根基，独立后不会被校验复杂度拖累
- `plan-validation` L4 false positive 是高风险点，独立 plan 允许延期不阻塞其他模块

---

## 追溯链索引

| Plan | DC 编号范围 | 对应 Spec 章节 |
|------|------------|---------------|
| `plan-template-system` | DC-001~003 | F-M1（配置树结构）, 可维护性 |
| `plan-config-tree` | DC-004~011 | F-M1（配置树编辑） |
| `plan-validation` | DC-012~016 | F-M3（校验系统） |
| `plan-backend-llm` | DC-017~021 | F-M5（LLM 集成） |
| `plan-frontend` | DC-022~030 | F-M1, F-M2（界面 + 问答） |
| `plan-platform` | DC-031~038 | F-M4（导入/导出） |

---

## 已识别技术债（10 项）

详见 `Document/technical-debt.md`。

**高优先级**：
1. **TD-001~004**: backend/ frontend/ electron/ tests/ 目录缺失
2. **TD-005**: `generate_rules.py` 无单元测试
3. **TD-008**: `_framework.j2` Prompt 模板缺失

---

## 建议的 Proposal 顺序

1. **proposal-0001**: 脚手架搭建（创建所有目录结构）
2. **proposal-0002**: `generate_rules.py` 单元测试（plan-template-system Phase 1）
3. **proposal-0003**: TemplateMapper + FieldDescriptor（plan-template-system Phase 2）
4. **proposal-0004**: ConfigSession + ConfigTree（plan-config-tree Phase 1~2）

---

*基线已锁定（v1.0.0）。任何变更必须通过 `changes/proposal-{NNNN}.md` 流程。*
