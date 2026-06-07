# 实施进度与工作难度评估

> 更新日期：2026-06-07
> 状态：三个核心难点验证全部完成，设计文档与 V3 实现已对齐

---

## 已完成的工作

| 模块 | 状态 | 说明 |
|------|------|------|
| V1: mappyfile validate 行为摸底 | ✅ | 62 个用例，`to_mappyfile_dict()` 7 条强制变换规则确定 |
| V2: LLM Prompt 输出稳定性 | ✅ | 30 次调用，JSON 可解析率 93.3%，4 层容错解析策略确定 |
| V3: ConfigTree 前端递归渲染 | ✅ | 280 节点、4 层嵌套、7 种控件映射全部覆盖，构建零错误 |
| `generate_rules.py` 规则合并器 | ✅ | 8 个业务覆盖文件合并为单一 `mapguide_rules.json` |
| `mapguide_rules.json` 运行时规则 | ✅ | 8 个 object_types，~400 个字段定义，flat_params 索引 |
| 设计文档对齐 | ✅ | data-structures / conventions / core-services 已同步 V3 结论 |

---

## 剩余工作模块

### 后端（Python）

| 模块 | 文件 | 预估行数 | 难度 | 依赖 | 说明 |
|------|------|---------|------|------|------|
| **TemplateMapper** | `core/template_mapper.py` | ~200 | 低 | 无 | 加载 rules，字段查询，别名解析。规则文件已就绪，纯查表逻辑 |
| **FieldDescriptor** | `core/template_mapper.py` | ~50 | 低 | 无 | Pydantic 模型，字段元数据封装 |
| **ConfigSession** | `core/session.py` | ~150 | 低 | ConfigTree | 会话状态容器，`__post_init__` 初始化空 MAP |
| **ConfigTree** | `core/config_tree.py` | ~300 | 中 | TemplateMapper | `_build_tree` 递归构建、`update_value`、扁平路径查找、`to_mappyfile_dict` 7 条变换 |
| **ValidationPipeline L1-L3** | `core/validation.py` | ~200 | 中 | ConfigTree | 别名解析、类型检查（Pydantic）、语义检查（dependencies.json） |
| **ValidationPipeline L4** | `core/validation.py` | ~100 | 中高 | ConfigTree | mappyfile 语法校验 + false positive 过滤。V1 已摸清边界，但过滤逻辑需仔细 |
| **DialogueHistory** | `core/history.py` | ~100 | 低 | 无 | 精简历史，按 focus_param 分组，最多 6 轮 |
| **QAService** | `core/qa_service.py` | ~150 | 中 | PromptBuilder, LLMClient, ValidationPipeline | 问答主流程，6 步流水线 |
| **ExportService** | `core/export_service.py` | ~100 | 低 | ConfigTree | mappyfile.dumps() + MapCache XML 生成 |
| **ImportService** | `core/import_service.py` | ~100 | 低 | ConfigTree, ValidationPipeline | mappyfile.loads() → ConfigSession |
| **PromptBuilder** | `llm/prompt_builder.py` | ~100 | 中 | Jinja2 | L0-L5 上下文组装，~1500 token 预算控制 |
| **LLMClient** | `llm/llm_client.py` | ~150 | 低 | anthropic SDK | temperature=0.1，指数退避 3 次重试 |
| **LLMOutput** | `llm/llm_output.py` | ~200 | 中 | 无 | 4 层容错解析：`direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback`。V2 已验证策略 |
| **UpdateResolver** | `llm/update_resolver.py` | ~100 | 低 | 无 | 路径解析，宽容格式转换（`layers[0]` → `layers.0`） |
| **MapCacheGenerator** | `mapcache/generator.py` | ~150 | 中 | Jinja2 | `mapcache.xml.j2` + session params 渲染 |
| **MapCacheValidator** | `mapcache/validator.py` | ~150 | 中 | 无 | 自定义 XML 规则校验，无需 MapCache 安装 |
| **FastAPI + WebSocket** | `main.py` | ~200 | 中 | 所有服务 | WS 路由、消息分发、session 管理 |

**后端总计预估：~2550 行 Python**

### 前端（Vue 3）

| 模块 | 文件 | 预估行数 | 难度 | 说明 |
|------|------|---------|------|------|
| **ConfigTreePanel** | `components/ConfigTreePanel.vue` | ~180 | 低 | V3 已实现基础版本，需接入 WebSocket |
| **ObjectCard** | `components/ObjectCard.vue` | ~140 | 低 | V3 已实现，需接入增删节点功能 |
| **FieldEditor** | `components/FieldEditor.vue` | ~290 | 低 | V3 已实现，需接入 WS update 事件 |
| **QAPanel** | `components/QAPanel.vue` | ~200 | 低 | 标准聊天 UI：消息列表、输入框、轮次计数 |
| **CustomPropModal** | `components/CustomPropModal.vue` | ~100 | 低 | 模态框：key + type + desc + value |
| **Pinia Stores** | `stores/` | ~200 | 低 | session state、UI state、WS 连接状态 |
| **WebSocket Service** | `services/ws.ts` | ~150 | 中 | WS 连接、消息序列化、断线重连、心跳 |
| **TypeScript 类型** | `types/` | ~100 | 低 | TreeNode、TreeLeaf、WSMessage、FieldDef |
| **App.vue / 布局** | `App.vue` | ~100 | 低 | 两栏布局（55%/45%） |

**前端总计预估：~1460 行 Vue/TS**

### Electron

| 模块 | 文件 | 预估行数 | 难度 | 说明 |
|------|------|---------|------|------|
| **main.js** | `electron/main.js` | ~200 | 低 | 窗口管理、启动 Python 子进程、IPC |
| **preload.js** | `electron/preload.js` | ~50 | 低 | 安全 IPC 桥接 |
| **打包配置** | `package.json` + `electron-builder` | ~100 | 低 | 标准配置 |

### 测试

| 类型 | 范围 | 预估行数 | 说明 |
|------|------|---------|------|
| 单元测试 | `tests/unit/` | ~1000 | TemplateMapper、ConfigTree、LLMOutput、UpdateResolver、ValidationPipeline |
| 集成测试 | `tests/integration/` | ~500 | generate_rules 输出校验、端到端 LLM mock |

---

## 难度热力图

```
高 ┤                    [L4 false positive过滤]
   │         [WebSocket全双工]  [MapCache校验器]
   │    [ConfigTree序列化]  [LLMOutput解析]
中 ┤ [Validation L1-L3] [PromptBuilder]
   │         [QAService]
   │    [Import/Export]
低 ┤ [TemplateMapper] [FieldDescriptor] [DialogueHistory]
   │ [LLMClient] [UpdateResolver] [Pinia] [QAPanel]
   │ [ObjectCard] [FieldEditor] [Electron]
   └──────────────────────────────────────────────
```

---

## 关键风险点（已降低）

| 原风险 | 验证后状态 | 剩余风险 |
|--------|-----------|---------|
| mappyfile 行为不确定 | V1 ✅ 摸清 62 个用例 | L4 false positive 过滤需编码实现 |
| LLM 输出不稳定 | V2 ✅ 93.3% 可解析 | 只需按既定策略编码容错层 |
| 前端递归渲染性能 | V3 ✅ 280 节点验证通过 | 真实数据规模可能更大，预留虚拟滚动方案 |

---

## 时间预估（单人全栈）

| 阶段 | 内容 | 预估时间 |
|------|------|---------|
| **Phase 1：后端核心** | TemplateMapper → ConfigTree → ValidationPipeline L1-L3 | 1 周 |
| **Phase 2：LLM 链路** | PromptBuilder → LLMClient → LLMOutput → QAService | 1 周 |
| **Phase 3：前后端贯通** | WebSocket 路由 + 前端 WS 服务 + 基础交互 | 1 周 |
| **Phase 4：完善功能** | L4 校验、Import/Export、MapCache、CustomProp | 1 周 |
| **Phase 5：Electron + 测试** | 打包、单元测试、集成测试、端到端 | 1 周 |
| **缓冲** | Bug 修复、文档、性能调优 | 0.5-1 周 |
| **总计** | | **5-6 周** |

---

## 结论

**三个核心难点（V1/V2/V3）全部验证通过，最大技术风险已经消除。**

剩余工作主要是**按设计文档编码实现**，而非技术探索。设计文档已足够详细（类接口、数据流、消息格式、控件映射全部已定义），可以直接进入脚手架搭建和模块实现阶段。

**推荐下一步**：搭建项目脚手架（`backend/`、`frontend/`、`electron/`、`tests/` 目录结构）→ 从 `TemplateMapper` + `ConfigTree` 开始 TDD 开发。
