# MapGuide

MapGuide 是一款桌面端对话式配置工具，通过自然语言对话引导用户生成 MapServer `.map` 和 MapCache `.xml` 配置文件。

## 核心特点

- **对话引导**：LLM 作为向导，分阶段收集数据源、样式、服务、缓存等配置参数
- **确定性生成**：LLM 只输出结构化参数，最终 `.map` / `.xml` 由代码（mappyfile + Jinja2）确定性生成，杜绝幻觉
- **即时验证**：每次参数更新后后端立即执行结构 + 语义 + 版本三层验证，错误即时反馈修正
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
├── backend/          # Python FastAPI 后端
│   ├── main.py       # FastAPI 入口 + WebSocket endpoint
│   ├── core/         # 会话状态、Prompt 构建、验证、状态机
│   ├── llm/          # LLMClient（anthropic SDK 封装）
│   ├── generator/    # mappyfile / Jinja2 配置生成
│   └── models/       # Pydantic 参数模型
├── frontend/         # Vue 3 + Vite 前端
│   └── src/
│       ├── components/   # ChatPanel、ConfigTree、PhaseIndicator
│       ├── stores/       # Pinia 状态管理
│       └── api/          # WebSocket 客户端
├── electron/         # Electron 主进程
└── tests/            # 单元测试
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

## 生产打包

```bash
# 1. Python 后端 → standalone exe
cd SourceCode/backend
pyinstaller build/pyinstaller.spec

# 2. Vue 前端 → 静态资源
cd SourceCode/frontend
npm run build

# 3. Electron → Windows 安装程序
cd SourceCode
npm run electron:build
# 输出: dist/MapGuide-Setup-x.x.x.exe
```

## 配置阶段

对话按以下阶段引导用户完成配置：

```
greeting → datasource → style → service → cache(可选) → review → done
```

| 阶段 | 收集内容 | 生成目标 |
|------|---------|---------|
| greeting | 服务类型意图 | 决定后续分支 |
| datasource | 数据源类型、连接信息、图层名 | `LAYER` |
| style | 几何类型、颜色、线宽/符号 | `CLASS` + `STYLE` |
| service | WMS 参数、extent、输出格式 | `WEB.METADATA` |
| cache | 缓存类型、存储路径 | `mapcache.xml`（可选） |
| review | 确认所有参数 | 生成最终文件 |
| done | 输出 `.map` + `.xml` | 下载 |

## 设计约束

- **单 Agent 架构**：一个 LLM 调用处理全部对话逻辑
- **场景隔离 Prompt**：代码根据当前阶段选择对应 System Prompt，LLM 不猜场景
- **MVP 范围**：PostGIS / Shapefile → WMS → 可选 MapCache 磁盘缓存（锁定 MapServer 8.4）
- **无持久化**：会话纯内存存储，"重新开始"即丢弃
