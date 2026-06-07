# MapGuide 宪法文档 (Constitution)

> **效力**：最高约束，变更需通过 ADR 流程（Architecture Decision Record）
> **版本**：v1.0.0（SDD 采纳基线）
> **日期**：2026-06-07

---

## 1. 项目定位与愿景

**MapGuide** 是一款 Windows 桌面应用，用于交互式编辑 MapServer Mapfile（`.map`）与 MapCache XML（`.xml`）配置，并集成 LLM 辅助问答。

**一句话**：让用户通过可视化配置树直接编辑参数，遇到问题时随时向 LLM 提问，后端负责所有校验和转换，最终导出可直接部署的配置文件。

---

## 2. 范围边界

### 2.1 在范围内（Must 做）

| 边界 | 说明 |
|------|------|
| **MapServer 8.4** | 唯一目标版本，锁定 |
| **数据源** | PostGIS / Shapefile（`connectiontype ∈ {local, postgis, ogr}`） |
| **服务类型** | WMS / WFS / WCS（一份 `.map` 同时支持多服务） |
| **缓存** | MapCache 磁盘缓存（WMTS/TMS），通过 `mapcache.xml` 配置 |
| **LLM 辅助** | Anthropic Claude 问答，解释参数、分析错误、建议配置 |
| **导出** | `.map` + `mapcache.xml` |

### 2.2 不在范围内（Must 不做）

| 边界 | 说明 |
|------|------|
| **其他数据源** | Oracle Spatial、SQL Server、MongoDB 等 |
| **其他服务** | WMTS（Mapfile 原生）、GeoRSS、KML 等 |
| **持久化** | 无数据库、无文件保存、无配置历史 |
| **多用户** | 单机单用户，无并发 |
| **地图预览** | 不提供渲染预览，仅文本配置 |
| **版本管理** | 无 diff、无回滚、无分支 |
| **LLM 提供商切换** | MVP 只支持 Anthropic Claude |

---

## 3. 技术栈锁定（不可变更）

以下决策为**架构基石**，未经 ADR 流程不得变更：

| 层级 | 选型 | 版本/约束 | 锁定理由 |
|------|------|-----------|----------|
| 后端运行时 | Python | 3.11（`gis-agent` conda 环境） | 单一环境，避免版本碎片化 |
| Web 框架 | FastAPI + uvicorn | 最新稳定版 | 仅暴露 WebSocket `/ws`，无 HTTP REST |
| Mapfile 操作 | mappyfile | 支持 8.4 | 官方库，已验证 62 个用例 |
| 数据校验 | Pydantic v2 | 最新稳定版 | 类型安全 |
| LLM 客户端 | anthropic SDK | 最新稳定版 | 只支持 Claude |
| Prompt 模板 | Jinja2 | 最新稳定版 | 单一模板 `_framework.j2` |
| 前端框架 | Vue 3 | Composition API | 响应式 + 组件化 |
| 构建工具 | Vite | 最新稳定版 | 开发/生产一致 |
| 状态管理 | Pinia | 最新稳定版 | 全局状态 |
| UI 组件库 | Naive UI | 仅表单控件 | **禁用 `n-tree`**，自定义分层渲染 |
| 桌面壳 | Electron | 最新稳定版 | 主进程 + 渲染进程 |
| 打包 | PyInstaller + electron-builder | — | 后端 exe + 前端 bundle + 安装包 |

---

## 4. 架构铁律（绝对约束）

### 4.1 通信约束

- **前后端唯一通道**：WebSocket（`ws://localhost:8765/ws`）
- **禁止 HTTP REST** 供前端调用
- 后端 → LLM 厂商走 HTTP API（唯一外部 HTTP）

### 4.2 LLM 边界

- **LLM 不生成原始 Mapfile/XML 文本**
- **LLM 不处理规则**：别名、类型转换、依赖校验、默认值、推导参数全部由后端代码处理
- **单 Prompt 架构**：只有 `_framework.j2` 一个系统模板，无阶段切换
- **容错降级**：LLM 输出格式错误时静默忽略 `params_update`，降级为纯文本回答

### 4.3 状态约束

- **无持久化**：`ConfigSession` 完全内存驻留，关闭即丢失
- **无历史保存**：重置 = 销毁并重建 session
- **单会话单后端**：Electron 启动一个 Python 子进程，只服务一个用户会话

### 4.4 数据格式约束

- **颜色**：RGB 数组 `[R, G, B]`，不使用 hex 字符串
- **PROJECTION**：数组 `["init=epsg:3857"]`，不能是字符串
- **Mapfile version**：浮点数 `8.4`，不能是字符串 `"8.4"`

### 4.5 模板资源约束

- `mapguide_rules.json` 是运行时**唯一**读取的规则文件
- 模板资源（`data/templates/*.json`）人工维护，git 跟踪
- 运行 `generate_rules.py` 后必须验证输出结构

---

## 5. 编码规范

### 5.1 Python

- 类型注解强制（`mypy --strict` 目标）
- Docstring 格式：Google style
- 命名：`snake_case` 函数/变量，`PascalCase` 类，`UPPER_SNAKE_CASE` 常量
- 最大行宽：100
- 异常：自定义异常继承自 `MapGuideError`，不裸抛 `Exception`

### 5.2 TypeScript / Vue

- 严格模式开启
- 组件命名：`PascalCase`
- Props 必须类型注解
- 不使用 `any`，使用 `unknown` + 类型守卫

### 5.3 文档规范

- 所有公共函数/类必须有 docstring
- 所有模块 plan 中的接口签名必须与代码一致
- 变更必须通过 `changes/proposal-{NNNN}.md`，禁止直接修改锁定 plan

---

## 6. 版本策略

| 文档 | 版本规则 | 当前版本 |
|------|----------|----------|
| `constitution.md` | 极少变更，Major 升级需 ADR | v1.0.0 |
| `spec.md` | 需求变更时 Minor 升级 | v1.0.0 |
| `plan-{module}.md` | 设计变更时 Minor 升级 | v1.0.0 |
| `proposal-{NNNN}.md` | 单点变更，IMPLEMENTED 后归档 | — |

---

## 7. 红色条款（绝对禁区）

| 编号 | 禁止行为 | 违反后果 |
|:----:|---------|----------|
| **RED-1** | 无 plan 直接编码 | 代码视为技术债，必须补 plan |
| **RED-2** | plan 与代码不一致 | 冻结功能，先对齐再开发 |
| **RED-3** | 未经审阅的 proposal 直接实现 | 回滚实现，重新走 propose → implement |
| **RED-4** | 需求变更不更新 spec | 需求漂移，spec 失去真相源地位 |
| **RED-5** | 直接修改已锁定的 plan 或 spec | 变更追溯链断裂 |
| **RED-6** | 先实现后补测试 | 测试无效，需重写 |

---

*本文档为 SDD 规范驱动开发工作流的最高约束层。任何与本文档冲突的设计或实现，以本文档为准。*
