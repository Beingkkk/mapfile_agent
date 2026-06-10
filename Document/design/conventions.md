---
title: 开发规范与约束
description: 技术栈选型、目录结构、开发命令、代码约束、调试排错
---

## 13. 技术栈与选型

### 13.1 后端技术栈

| 组件 | 选型 | 版本约束 | 说明 |
|------|------|---------|------|
| 运行环境 | Python 3.11 | 锁定 | 通过 `gis-agent` conda 环境运行 |
| Web 框架 | FastAPI | 最新稳定版 | 提供 WebSocket 入口（前后端唯一通信通道） |
| ASGI 服务器 | uvicorn | 最新稳定版 | 开发模式带 `--reload` |
| Mapfile 操作 | mappyfile | 支持 MapServer 8.4 | 创建/校验/序列化 Mapfile |
| 数据校验 | Pydantic v2 | 最新稳定版 | `FieldDescriptor` + 运行时校验模型 |
| Prompt 模板 | Jinja2 | 最新稳定版 | `_framework.j2` 渲染 |
| LLM 客户端 | anthropic SDK | 最新稳定版 | Claude API 调用，支持自定义 `base_url` |
| 重试/退避 | 自带 `tenacity` 或手写指数退避 | — | LLM 调用 3 次重试 |
| JSON 解析 | `json` + Pydantic | 标准库 | LLM 输出严格按 schema 解析 |
| 日志 | Python `logging` | 标准库 | 统一格式，不引入第三方日志库 |

**不使用的技术**（避免过度设计）：
- 不引入数据库（SQLite/PostgreSQL）—— `ConfigSession` 纯内存
- 不引入 Redis/Memcached —— 无共享状态需求
- 不引入 Celery/RQ —— LLM 调用同步即可
- 不引入 SQLAlchemy/ORM —— 无持久化模型

### 13.2 前端技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | Vue 3 | Composition API |
| 构建工具 | Vite | 开发服务器 + 生产构建 |
| 状态管理 | Pinia | 全局 UI 状态、会话状态 |
| UI 组件库 | Naive UI | **仅使用表单控件**（`n-input`/`n-select`/`n-color-picker`/`n-switch` 等），**不使用 `n-tree`** |
| 样式 | CSS Variables + scoped style | 不使用 Tailwind/SCSS（减少依赖） |
| 通信 | WebSocket (browser native) | 与后端保持一条长连接 |

**渲染方案**：自定义分层渲染（§4.2）。对象节点用自研 `ObjectCard` 组件递归渲染，属性叶子用 `FieldEditor` 统一按 `value_type` 内部分发到对应控件（string/integer/float/boolean/enum/array/color）。Naive UI 只提供底层表单控件（`n-input`、`n-input-number`、`n-switch`、`n-select`），不介入树结构渲染。

> **V3 验证结论**：`FieldEditor` 内部分发方案（单组件 287 行）在 280 节点规模下验证通过，无需拆分为独立原子编辑器组件。如需进一步拆分，可后期从 `FieldEditor` 中提取。

### 13.3 桌面技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 桌面壳 | Electron | 主进程负责窗口 + 启动后端子进程 |
| 打包 | electron-builder | 输出 Windows `.exe` 安装包 |
| 后端分发 | PyInstaller | 生产环境把 Python 后端打包为独立 exe |

### 13.4 Python 依赖清单（requirements.txt）

```text
# Web 服务
fastapi>=0.110
uvicorn[standard]>=0.27
websockets>=12.0

# 数据校验
pydantic>=2.5

# Mapfile
mappyfile>=1.0

# LLM
anthropic>=0.21

# 模板
jinja2>=3.1

# 工具
python-dotenv>=1.0
```

### 13.5 Node 依赖清单

前端：

```json
{
  "vue": "^3.4",
  "pinia": "^2.1",
  "naive-ui": "^2.38",
  "vite": "^5.0"
}
```

Electron：

```json
{
  "electron": "^29.0",
  "electron-builder": "^24.0"
}
```

---

## 14. 开发规范

### 14.1 目录结构

```
SourceCode/
├── backend/                           # Python FastAPI 后端
│   ├── core/                          # 业务核心
│   │   ├── session.py                 # ConfigSession
│   │   ├── config_tree.py             # ConfigTree, TreeNode, TreeLeaf
│   │   ├── template_mapper.py         # TemplateMapper, FieldDescriptor
│   │   ├── validation.py              # ValidationPipeline, ValidationResult
│   │   ├── qa_service.py              # QAService, QAResult
│   │   ├── export_service.py          # ExportService
│   │   ├── import_service.py          # ImportService
│   │   ├── history.py                 # DialogueHistory
│   │   └── result_types.py            # 共享结果类型
│   ├── llm/                           # LLM 相关
│   │   ├── prompt_builder.py          # PromptBuilder
│   │   ├── llm_client.py              # LLMClient
│   │   ├── llm_output.py              # LLMOutput.parse
│   │   └── update_resolver.py         # UpdateResolver
│   ├── mapcache/                      # MapCache 生成器/校验器
│   │   ├── generator.py
│   │   └── validator.py
│   ├── main.py                        # FastAPI 入口 + WebSocket 路由
│   └── requirements.txt
├── frontend/                          # Vue 3 前端
│   ├── src/
│   │   ├── components/                # 页面级组件
│   │   │   ├── ConfigTreePanel.vue    # 左栏配置树面板（含工具栏、图例、状态栏）
│   │   │   ├── ObjectCard.vue         # 对象节点卡片（递归渲染 MAP/LAYER/CLASS/STYLE/LABEL/WEB/METADATA/CACHE）
│   │   │   ├── FieldEditor.vue        # 统一字段编辑器（按 value_type 内部分发到 7 种控件）
│   │   │   ├── QAPanel.vue            # 右栏问答面板
│   │   │   └── CustomPropModal.vue    # 添加自定义属性模态框
│   │   ├── stores/                    # Pinia stores
│   │   ├── services/                  # WebSocket client
│   │   └── types/                     # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
├── electron/                          # Electron 主进程
├── data/                              # 运行时产物 + 模板资源
│   ├── mapguide_rules.json            # 运行时规则（生成产物）
│   └── templates/                     # 模板资源（git 跟踪）
├── scripts/                           # 生成/维护工具
│   └── generate_rules.py
├── tests/                             # 测试
│   ├── unit/                          # 单元测试
│   └── integration/                   # 集成测试
└── config/                            # 配置
    ├── config.json.template           # 模板（git 跟踪）
    └── config.json                    # 真实配置（gitignored）
```

### 14.2 Python 环境约定

**必须使用 `gis-agent` conda 环境**。在 bash 中不能 `conda activate`，所以所有 Python 命令使用完整路径：

```bash
# 检查环境
"/c/Users/PC/.conda/envs/gis-agent/python" --version   # 3.11.15

# 运行后端
cd SourceCode/backend
"/c/Users/PC/.conda/envs/gis-agent/python" -m uvicorn main:app --port 18091 --reload

# 运行测试
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/ -v

# 生成规则
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py
```

### 14.3 开发命令速查

| 任务 | 命令 |
|------|------|
| 安装后端依赖 | `"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install -r SourceCode/backend/requirements.txt` |
| 启动后端开发服务器 | `cd SourceCode/backend && "/c/Users/PC/.conda/envs/gis-agent/python" -m uvicorn main:app --port 18091 --reload` |
| 启动前端开发服务器 | `cd SourceCode/frontend && npm run dev` |
| 启动 Electron 开发 | `cd SourceCode && npm run electron:dev`（需先启动前后端） |
| 运行单元测试 | `cd SourceCode && "/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/ -v` |
| 生成 mapguide_rules.json | `cd SourceCode && "/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py` |
| 构建前端生产包 | `cd SourceCode/frontend && npm run build` |
| 后端打包 exe | `cd SourceCode/backend && "/c/Users/PC/.conda/envs/gis-agent/python" -m PyInstaller build/pyinstaller.spec` |
| Electron 打包 | `cd SourceCode && npm run electron:build` |

### 14.4 测试策略

| 类型 | 范围 | 目标 |
|------|------|------|
| 单元测试 | `tests/unit/` | TemplateMapper、ConfigTree、UpdateResolver、ValidationPipeline |
| 集成测试 | `tests/integration/` | `generate_rules.py` 输出、端到端 LLM mock 问答 |
| 手动测试 | UI 原型 | 两栏布局、关注点切换、导出流程 |

---

## 15. 设计与代码约束

### 15.1 版本锁定与格式约束

- **MapServer 8.4 唯一目标**：`mappyfile.validate(mf, version=8.4)` 中的 `version` 必须是 `float`（`8.4`），不能是字符串
- **MapCache 1.16.0**：`backend/mapcache/` 按此版本规则校验
- **Python 3.11**：不使用 3.12+ 特有语法，保证 conda 环境一致
- **Vue 3 + Naive UI**：不使用 Element Plus 或其他 UI 库
- **颜色格式**：RGB 数组 `[R, G, B]`，不使用 hex 字符串
- **PROJECTION 格式**：必须为数组 `["init=epsg:3857"]`，不能是字符串

### 15.2 LLM 边界约束

- **LLM 不生成原始 Mapfile/XML 文本**。LLM 只输出自然语言回答和 `params_update`
- **所有规则后端处理**：别名、类型转换、依赖校验、默认值、推导参数一律不交给 LLM
- **单 Prompt 架构**：只有 `_framework.j2` 一个系统模板，没有按阶段切换
- **容错降级**：LLM 输出格式错误时，静默忽略 `params_update`，降级为纯文本回答
- **LLM 提供商锁定**：MVP 只支持 Anthropic Claude。`LLMClient` 封装 Anthropic SDK，向上层暴露统一 `chat()` 接口

### 15.3 状态与持久化约束

- **无持久化**：`ConfigSession` 完全在内存中，关闭应用即丢失
- **无历史保存**：重置 = 销毁 session 重新创建
- **单会话单后端**：Electron 主进程启动一个 Python 子进程，只服务一个用户会话
- **WebSocket 长连接**：前后端通过单一 WS 连接通信

### 15.4 安全约束

- `SourceCode/config/config.json` **必须 gitignored**
- LLM API key 不进入前端代码，仅后端 `LLMClient` 读取

### 15.5 性能约束

- **Prompt token 预算 ~1500 tokens**：L0-L5 总和控制在此范围内
- **LLM 调用温度**：`temperature=0.1`
- **重试策略**：指数退避，最多 3 次，总超时 ≤30s
- **字段失焦校验**：只执行 alias/type/semantic，不做 mappyfile
- **历史保留**：每个关注点下最多保留最近 6 轮 QA

### 15.6 错误处理策略

| 场景 | 行为 |
|------|------|
| 字段类型错误 | 字段标红，错误信息发送到前端 |
| 条件依赖错误 | 依赖字段同时标红，错误说明包含触发条件 |
| mappyfile 语法错误 | 全局错误面板显示，阻断导出 |
| LLM 返回非 JSON | 优雅降级为纯文本回答 |
| WebSocket 断线 | 前端显示"连接已断开"，保留树状态 |
| 导入 Mapfile 解析失败 | 前端弹窗显示错误；当前会话不受影响 |
| 导入 Mapfile 校验失败 | 允许导入，错误标红 |

### 15.7 扩展性预留

- 新增对象类型：在 `object-fields.json` 中定义字段，在 `phase-map.json` 中分配阶段
- 新增必填规则：修改 `required.json`
- 新增别名：修改 `aliases.json`
- 新增条件依赖：修改 `dependencies.json`
- 支持新的 LLM 提供商：替换 `LLMClient` 实现即可

---

## 16. 调试与排错

### 16.1 常见开发问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `pytest tests/unit/` 找不到文件 | 没有从 `SourceCode/` 目录运行 | `cd SourceCode` 后再运行 |
| `mappyfile.validate()` 报错 `version` 类型 | 传了字符串 `"8.4"` | 改为浮点数 `8.4` |
| PROJECTION 序列化失败 | 传了字符串而不是数组 | 用 `["init=epsg:3857"]` |
| 前端收不到 WebSocket 消息 | 后端端口/路由不对 | 检查 `ws://localhost:18091/ws` |
| LLM 返回 JSON 解析失败 | 温度太高或 prompt 不清晰 | 检查 prompt 中的 JSON 示例 |

### 16.2 日志级别

- `INFO`：用户操作（更新参数、切换关注点、提问、导出）
- `DEBUG`：Prompt 内容、LLM 原始响应、参数更新详情
- `WARNING`：LLM 输出解析异常、行号解析失败
- `ERROR`：后端异常、校验器崩溃、导出失败
