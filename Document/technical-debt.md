# 技术债登记册

> **说明**：SDD 采纳基线（v1.0.0）扫描发现的无 plan 代码和待补全项。
> **更新日期**：2026-06-07（模块重拆后更新）
> **规则**：新增技术债需标注发现日期、来源 plan、预计解决 proposal。

---

## 已锁定 plan 覆盖的代码

以下代码/文件已有对应 plan，非技术债：

| 代码/文件 | Plan | 状态 |
|-----------|------|------|
| `scripts/generate_rules.py` | `plan-template-system.md` DC-001 | 有代码缺测试 |
| `data/templates/*.json` | `plan-template-system.md` DC-001 | 模板资源 |
| `data/mapguide_rules.json` | `plan-template-system.md` DC-002 | 生成产物 |
| V1/V2/V3 spike 结果 | 各 plan「已知技术债」 | 设计参考 |
| UI 原型 | `plan-frontend.md` | 设计参考 |

---

## 当前技术债

### TD-001：backend/ 目录尚未创建

- **发现日期**：2026-06-07
- **说明**：后端 Python 模块目录待脚手架搭建
- **影响**：阻塞 `plan-template-system`、`plan-config-tree`、`plan-validation`、`plan-backend-llm`、`plan-platform` 所有任务
- **解决方式**：`proposal-0001`（脚手架搭建）
- **对应 Plan**：全部后端 plan

### TD-002：frontend/ 目录尚未创建

- **发现日期**：2026-06-07
- **说明**：Vue 3 前端项目待初始化（vite create + Naive UI + Pinia）
- **影响**：阻塞 `plan-frontend` 所有任务
- **解决方式**：`proposal-0001`（脚手架搭建）
- **对应 Plan**：`plan-frontend`

### TD-003：electron/ 目录尚未创建

- **发现日期**：2026-06-07
- **说明**：Electron 主进程和 preload 脚本待创建
- **影响**：阻塞桌面打包和文件系统交互
- **解决方式**：`proposal-0001`（脚手架搭建）→ `plan-platform` Phase 5
- **对应 Plan**：`plan-platform`

### TD-004：tests/ 目录尚未创建

- **发现日期**：2026-06-07
- **说明**：单元测试和集成测试目录待创建
- **影响**：阻塞所有 TDD 任务（RED-GREEN-REFACTOR）
- **解决方式**：`proposal-0001`（脚手架搭建）
- **对应 Plan**：全部 plan

### TD-005：`generate_rules.py` 无单元测试

- **发现日期**：2026-06-07
- **说明**：唯一已交付代码没有测试覆盖
- **影响**：修改模板资源时无法回归验证
- **解决方式**：`plan-template-system` Phase 1
- **对应 Plan**：`plan-template-system`

### TD-006：spike/ 脚本为验证代码，非生产

- **发现日期**：2026-06-07
- **说明**：`spike/v1_mappyfile_validate.py`、`v2_llm_prompt_stability.py`、`v3_config_tree_render.html` 为预开发验证脚本
- **影响**：无直接功能影响
- **决策**：保留为设计决策依据，不删除
- **对应 Plan**：各 plan「已知技术债」

### TD-007：UI 原型图为 HTML 文件，非 Vue 组件

- **发现日期**：2026-06-07
- **说明**：`Document/UX/ui-prototype-interactive-v2.html` 为原生 HTML/JS 原型
- **影响**：需人工迁移到 Vue 3 组件
- **解决方式**：`plan-frontend` Phase 2
- **对应 Plan**：`plan-frontend`

### TD-008：`_framework.j2` Prompt 模板尚未创建

- **发现日期**：2026-06-07
- **说明**：LLM 系统 Prompt 模板文件缺失
- **影响**：阻塞 PromptBuilder 和 LLM 端到端测试
- **解决方式**：`plan-backend-llm` Phase 1
- **对应 Plan**：`plan-backend-llm`

### TD-009：`mapcache.xml.j2` 模板尚未创建

- **发现日期**：2026-06-07
- **说明**：MapCache XML 生成模板缺失
- **影响**：阻塞 MapCache 导出功能
- **解决方式**：`plan-platform` Phase 2
- **对应 Plan**：`plan-platform`

### TD-010：`config.json` 未创建（仅模板存在）

- **发现日期**：2026-06-07
- **说明**：`SourceCode/config/config.json.template` 存在，但真实 `config.json` 需用户创建
- **影响**：首次运行需手动配置 API key
- **解决方式**：文档说明 + 启动时检测
- **对应 Plan**：`plan-platform`

---

## 技术债趋势

```
高优先级  │  TD-001  TD-002  TD-003  TD-004  TD-005
          │
中优先级  │  TD-007  TD-008  TD-009
          │
低优先级  │  TD-006  TD-010
          └─────────────────────────────────────────
```

---

## 已解决技术债（归档）

无。

---

*技术债随 proposal 实现逐步消除。消除后移至「已解决技术债」归档。*
