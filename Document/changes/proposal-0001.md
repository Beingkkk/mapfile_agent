# Proposal-0001: 项目脚手架搭建

> **类型**: Type-D（技术债重构 — 开发基础设施）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-07
> **对应 Plan**: `plan-template-system` / `plan-config-tree` / `plan-validation` / `plan-backend-llm` / `plan-frontend` / `plan-platform`
> **影响范围**: 全局 — 所有后续开发依赖本 proposal

---

## 目标

创建 MapGuide 项目的完整开发目录结构，使后续 TDD 开发具备基础环境。

**原则**：`spike/` 和 `scripts/` 是既有验证/工具代码，不纳入开发时代码结构。开发时代码独立组织。

---

## 变更内容

### [ADDED] SourceCode/backend/ — Python FastAPI 后端

```
backend/
├── core/                          # 业务核心
│   ├── __init__.py
│   ├── session.py                 # ConfigSession
│   ├── config_tree.py             # ConfigTree, TreeNode, TreeLeaf
│   ├── template_mapper.py         # TemplateMapper, FieldDescriptor
│   ├── validation.py              # ValidationPipeline, ValidationResult
│   ├── qa_service.py              # QAService, QAResult
│   ├── export_service.py          # ExportService
│   ├── import_service.py          # ImportService
│   ├── history.py                 # DialogueHistory
│   └── result_types.py            # 共享结果类型
├── llm/                           # LLM 相关
│   ├── __init__.py
│   ├── prompt_builder.py          # PromptBuilder
│   ├── llm_client.py              # LLMClient
│   ├── llm_output.py              # LLMOutput.parse
│   ├── update_resolver.py         # UpdateResolver
│   └── templates/                 # Jinja2 模板
│       └── _framework.j2          # 系统 Prompt 模板（占位）
├── mapcache/                      # MapCache 生成器/校验器
│   ├── __init__.py
│   ├── generator.py
│   ├── validator.py
│   └── templates/
│       └── mapcache.xml.j2        # MapCache XML 模板（占位）
├── main.py                        # FastAPI 入口 + WebSocket 路由
└── requirements.txt               # Python 依赖
```

### [ADDED] SourceCode/frontend/ — Vue 3 前端

使用 `npm create vue@latest` 初始化，选项：TypeScript + Pinia + Vitest，**不启用** Router（单页面应用）。

```
frontend/
├── src/
│   ├── components/                # Vue 组件
│   │   ├── ConfigTreePanel.vue
│   │   ├── ObjectCard.vue
│   │   ├── FieldEditor.vue
│   │   ├── QAPanel.vue
│   │   └── CustomPropModal.vue
│   ├── stores/                    # Pinia stores
│   │   ├── session.ts
│   │   └── ui.ts
│   ├── services/                  # WebSocket client
│   │   └── ws.ts
│   ├── types/                     # TypeScript 类型
│   │   └── tree.ts
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
├── tsconfig.json
└── vitest.config.ts               # 单元测试配置
```

### [ADDED] SourceCode/electron/ — Electron 桌面壳

```
electron/
├── main.js                        # 主进程
├── preload.js                     # Preload 脚本
└── build/
    └── pyinstaller.spec           # PyInstaller 配置（占位）
```

### [ADDED] SourceCode/tests/ — 测试

```
tests/
├── unit/                          # 单元测试
│   ├── __init__.py
│   ├── test_generate_rules.py     # plan-template-system
│   ├── test_template_mapper.py    # plan-template-system
│   ├── test_session.py            # plan-config-tree
│   ├── test_config_tree.py        # plan-config-tree
│   ├── test_validation.py         # plan-validation
│   ├── test_history.py            # plan-backend-llm
│   ├── test_prompt_builder.py     # plan-backend-llm
│   ├── test_llm_client.py         # plan-backend-llm
│   ├── test_llm_output.py         # plan-backend-llm
│   ├── test_update_resolver.py    # plan-backend-llm
│   ├── test_qa_service.py         # plan-platform
│   ├── test_export_service.py     # plan-platform
│   ├── test_import_service.py     # plan-platform
│   ├── test_mapcache_generator.py # plan-platform
│   ├── test_mapcache_validator.py # plan-platform
│   └── test_main.py               # plan-platform
└── integration/                   # 集成测试
    ├── __init__.py
    ├── test_rules_output.py
    ├── test_end_to_end.py
    ├── test_import_export.py
    └── test_mapcache_roundtrip.py
```

### [ADDED] 根级配置文件

- `SourceCode/pytest.ini` — pytest 配置（测试路径、覆盖率阈值）
- `SourceCode/.gitignore` — 开发时忽略规则（node_modules, __pycache__, dist 等）
- `SourceCode/frontend/.gitignore` — 前端忽略规则

---

## 验收标准

- [ ] `backend/` 目录结构完整，每个模块有 `__init__.py`
- [ ] `frontend/` 目录结构完整，`npm install` 成功
- [ ] `frontend/` Vitest 可运行（空测试通过）
- [ ] `electron/` 目录结构完整
- [ ] `tests/` 目录结构完整，pytest 可运行（空测试通过）
- [ ] `pytest tests/unit/` 从 `SourceCode/` 目录运行成功
- [ ] commit 格式符合规范

---

## 依赖

- Node.js ≥ 18（已验证：v24.13.1）
- npm（已验证：11.7.0）
- Python 3.11 + gis-agent conda 环境

---

*Approved by: 用户确认 Go/No-Go 条件*
