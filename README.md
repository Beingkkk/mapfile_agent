# MapGuide

MapGuide 是一款桌面端对话式配置工具，通过自然语言对话引导用户生成 MapServer `.map` 和 MapCache `.xml` 配置文件。

## 核心特点

- **配置树优先交互**：左侧面板为交互式配置树（ConfigTree），用户可直接编辑参数、添加图层、触发验证；右侧为问答助手，LLM 回答参数含义、解释错误、建议配置
- **确定性生成**：LLM 只输出结构化参数更新，最终 `.map` / `.xml` 由代码（mappyfile + Jinja2）确定性生成，杜绝幻觉
- **即时验证**：每次参数更新后后端立即执行四层验证（别名 → 类型 → 语义 → mappyfile 语法），错误即时反馈修正
- **多服务支持**：同一份 `.map` 配置同时支持 WMS + WFS + WCS；MapCache 可选生成 WMTS/TMS
- **零配置上手**：打开即对话，结束即丢弃，无需手动编写 Mapfile 语法

## 技术栈

| 层级 | 技术 |
|------|------|
| 桌面框架 | Electron 28+ |
| 前端 | Vue 3 + Vite + Naive UI + Pinia |
| 后端 | Python 3.11 + FastAPI + uvicorn |
| Mapfile 生成 | mappyfile（MapServer 8.4） |
| MapCache 生成 | Jinja2 |
| 参数校验 | Pydantic v2 |
| LLM 接入 | anthropic SDK |

## 项目结构

```
SourceCode/
├── scripts/
│   └── generate_rules.py      # 规则生成器：schema + 业务模板 → mapguide_rules.json
├── data/
│   ├── templates/               # 9 个业务覆盖模板 JSON
│   ├── mapguide_rules.json      # 生成的运行时规则文件（运行时唯一读取）
│   └── init_session_intent.json # 默认会话意图
├── config/
│   └── config.json.template     # LLM API 配置模板
├── backend/                     # Python FastAPI 后端（尚未搭建）
│   ├── main.py                  # FastAPI 入口 + WebSocket endpoint
│   ├── core/                    # ConfigSession, ConfigTree, TemplateMapper, ValidationPipeline
│   ├── llm/                     # PromptBuilder, LLMClient, LLMOutput, UpdateResolver
│   └── mapcache/                # MapCacheGenerator, MapCacheValidator
├── frontend/                    # Vue 3 + Vite 前端（尚未搭建）
│   └── src/
│       ├── components/          # ConfigTree, QAPanel, ObjectCard, FieldEditor
│       ├── stores/              # Pinia 状态管理
│       └── api/                 # WebSocket 客户端
├── electron/                    # Electron 主进程（尚未搭建）
└── tests/                       # 单元测试 + 集成测试（尚未搭建）

Document/
├── 需求输入.md                  # 需求规格：MVP 范围、UX 布局、交互场景
├── 技术细节.md                  # 技术设计：类设计、数据流、WebSocket 协议
├── 模板说明.md                  # 模板资源参考（面向 GIS 专业人员）
├── UX/ui-prototype-interactive-v2.html  # 交互式 UI 原型
└── design/                      # 架构图与数据流图
```

## 开发启动

**后端**（端口 8765）：
```bash
cd SourceCode/backend
"/c/Users/PC/.conda/envs/gis-agent/python" -m uvicorn main:app --port 8765 --reload
```

**前端**（开发服务器）：
```bash
cd SourceCode/frontend
npm run dev
```

**Electron**（开发模式，需前后端已启动）：
```bash
cd SourceCode
npm run electron:dev
```

**运行测试**：
```bash
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/ -v
```

**生成规则**（修改 `data/templates/*.json` 后执行）：
```bash
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py
```

## 生产打包

```bash
# 1. Python 后端 → standalone exe
cd SourceCode/backend
"/c/Users/PC/.conda/envs/gis-agent/python" -m PyInstaller build/pyinstaller.spec

# 2. Vue 前端 → 静态资源
cd SourceCode/frontend
npm run build

# 3. Electron → Windows 安装程序
cd SourceCode
npm run electron:build
# 输出: dist/MapGuide-Setup-x.x.x.exe
```

## 设计约束

- **单 Agent 架构**：一个 LLM 调用处理全部对话逻辑
- **无阶段状态机**：一个 System Prompt（`_framework.j2`），Backend 处理所有规则
- **MVP 范围**：PostGIS / Shapefile → WMS/WFS/WCS → 可选 MapCache 磁盘缓存（锁定 MapServer 8.4）
- **无持久化**：会话纯内存存储，"重新开始"即丢弃

> **详细架构与开发规范请参见 [CLAUDE.md](CLAUDE.md)。**
