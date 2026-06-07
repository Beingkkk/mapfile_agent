# Plan: Platform

> **模块**：平台层（FastAPI、MapCache、导入导出、Electron、打包）
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M4（导入/导出）
> **对应 design**：`design/core-services.md` §7.6~7.7, `design/conventions.md` §13.3
> **前置依赖**：`plan-config-tree` DC-004~011, `plan-validation` DC-012~016, `plan-backend-llm` DC-017~021

---

## 1. 模块概述

平台层是「胶水层」——它不实现核心业务逻辑，而是将各模块组装为可运行的服务。包括：
- **QAService**：编排 LLM 问答完整流程
- **ExportService / ImportService**：文件导入导出
- **MapCache**：XML 生成与校验
- **FastAPI WebSocket**：前后端通信入口
- **Electron**：桌面壳 + 文件系统交互

**特点**：贯穿项目生命周期，最后收尾，但部分模块可早期并行。

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| FastAPI 仅暴露 WebSocket `/ws`，不暴露 HTTP REST | `constitution.md` §4.1 |
| Electron 主进程启动 Python 子进程 | `conventions.md` §13.3 |
| 后端通过 PyInstaller 打包为 exe | `conventions.md` §14.3 |
| MapCache 1.16.0 规则校验，无需安装 MapCache | `conventions.md` §15.1 |
| 导出前必须校验通过 | `spec.md` §5.1 |
| 导入失败不影响当前会话 | `spec.md` §5.1 |

---

## 3. 接口定义

### 3.1 QAService — 问答编排

```python
# DC-031: backend/core/qa_service.py

@dataclass
class QAResult:
    bot_message: str
    params_update: list[dict]
    validation_state: str
    validation_errors: list[dict]
    can_export: bool
    focus_param: str | None

class QAService:
    def __init__(
        self, mapper: TemplateMapper,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        validator: ValidationPipeline
    ) -> None: ...

    async def answer(self, session: ConfigSession, question: str) -> QAResult: ...
```

### 3.2 ExportService — 导出

```python
# DC-032: backend/core/export_service.py

class ExportService:
    def export(self, session: ConfigSession) -> dict[str, bytes]: ...
    def get_service_summary(self, session: ConfigSession) -> str: ...
```

### 3.3 ImportService — 导入

```python
# DC-033: backend/core/import_service.py

class ImportService:
    def __init__(
        self, mapper: TemplateMapper, validator: ValidationPipeline
    ) -> None: ...

    def import_mapfile(
        self, session_id: str, content: str,
        old_session: ConfigSession | None = None
    ) -> tuple[ConfigSession, ValidationResult]: ...
```

### 3.4 MapCache 生成器/校验器

```python
# DC-034: backend/mapcache/generator.py

class MapCacheGenerator:
    def __init__(self, template_path: str = "mapcache.xml.j2") -> None: ...
    def render(self, params: dict) -> str: ...

# DC-035: backend/mapcache/validator.py

class MapCacheValidator:
    def validate(self, xml_content: str) -> list[dict]: ...
```

### 3.5 FastAPI WebSocket 入口

```python
# DC-036: backend/main.py

from fastapi import FastAPI, WebSocket

app = FastAPI(title="MapGuide Backend")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket): ...

async def handle_message(websocket: WebSocket, msg: dict) -> None: ...

sessions: dict[str, ConfigSession] = {}

def get_or_create_session(session_id: str) -> ConfigSession: ...
def remove_session(session_id: str) -> None: ...
```

### 3.6 Electron 主进程

```javascript
// DC-037: electron/main.js

function createWindow() { ... }
function startPythonBackend() { ... }
function setupIPC() { ... }

// IPC 通道
// - 'dialog:openFile' → 打开文件选择器
// - 'dialog:saveDirectory' → 打开保存目录选择器
// - 'file:write' → 写入文件
```

```javascript
// DC-038: electron/preload.js

contextBridge.exposeInMainWorld('electronAPI', {
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  saveDirectory: () => ipcRenderer.invoke('dialog:saveDirectory'),
  writeFile: (path, content) => ipcRenderer.invoke('file:write', path, content),
});
```

---

## 4. 数据流

### 4.1 完整问答流

```
WS: question { text }
  → handle_message() → QAService.answer()
    ├── DialogueHistory.add_message("user", text)
    ├── PromptBuilder.render(L0-L5)
    ├── LLMClient.chat(prompt)
    ├── LLMOutput.parse(raw)
    ├── UpdateResolver.resolve() x N
    ├── ConfigTree.update_value() x N
    ├── ValidationPipeline.validate_tree()
    └── DialogueHistory.add_message("bot", answer)
  → WS: qa_result { ... }
```

### 4.2 导出流

```
WS: export {}
  → handle_message() → validate_tree()
  → ExportService.export()
    ├── mappyfile.dumps(tree.to_mappyfile_dict())
    └── MapCacheGenerator.render() (if enabled)
  → WS: export_result { files }
  → Electron dialog.showSaveDialog
  → Electron file:write
```

### 4.3 导入流

```
Electron dialog:openFile
  → Electron file:read
  → WS: import_mapfile { content }
  → ImportService.import_mapfile()
    ├── mappyfile.loads(content)
    ├── ConfigSession.from_mapfile_content()
    └── ValidationPipeline.validate_tree()
  → WS: import_result { success }
  → WS: tree_state { ... }
```

---

## 5. 测试策略

### 5.1 单元测试

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-031 | `tests/unit/test_qa_service.py` | Mock LLM 问答、params_update 应用、校验触发 |
| DC-032 | `tests/unit/test_export_service.py` | 导出 .map、导出 mapcache.xml、校验阻断 |
| DC-033 | `tests/unit/test_import_service.py` | 解析成功/失败、自定义属性标记、校验结果 |
| DC-034 | `tests/unit/test_mapcache_generator.py` | Jinja2 渲染、参数注入 |
| DC-035 | `tests/unit/test_mapcache_validator.py` | 结构校验、服务校验、缓存校验 |
| DC-036 | `tests/unit/test_main.py` | Mock WebSocket、消息分发、session 管理 |

### 5.2 集成测试

| 场景 | 测试文件 |
|------|----------|
| 编辑 → 校验 → 导出 闭环 | `tests/integration/test_end_to_end.py` |
| 导入 → 修改 → 导出 闭环 | `tests/integration/test_import_export.py` |
| MapCache 生成 → 校验 闭环 | `tests/integration/test_mapcache_roundtrip.py` |

---

## 6. 任务清单

### Phase 1: 导入导出（TDD）

- [ ] [RED] `test_export_service.py` — 导出 .map、导出阻断、服务摘要
- [ ] [GREEN] `export_service.py` — ExportService
- [ ] [RED] `test_import_service.py` — 导入成功/失败、自定义属性标记
- [ ] [GREEN] `import_service.py` — ImportService
- [ ] [REFACTOR] 服务间依赖注入优化

### Phase 2: MapCache（TDD）

- [ ] [RED] `test_mapcache_generator.py` — Jinja2 模板渲染
- [ ] [GREEN] `mapcache/generator.py` + `mapcache.xml.j2`
- [ ] [RED] `test_mapcache_validator.py` — XML 结构校验
- [ ] [GREEN] `mapcache/validator.py`
- [ ] [REFACTOR] 提取通用 XML 校验工具

### Phase 3: QAService（TDD）

- [ ] [RED] `test_qa_service.py` — Mock LLM 完整问答流
- [ ] [GREEN] `qa_service.py` — QAService
- [ ] [REFACTOR] 六步流水线抽象

### Phase 4: FastAPI + WebSocket（TDD）

- [ ] [RED] `test_main.py` — Mock WebSocket、消息路由
- [ ] [GREEN] `main.py` — FastAPI + WS 入口
- [ ] [REFACTOR] 消息处理器解耦

### Phase 5: Electron（逐步实现）

- [ ] `electron/main.js` — 窗口 + Python 子进程
- [ ] `electron/preload.js` — IPC 桥接
- [ ] `package.json` — electron-builder 配置
- [ ] PyInstaller `build/pyinstaller.spec`

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| `mapcache.xml.j2` | MapCache XML 模板尚未创建 | 中 — Phase 2 处理 |
| PyInstaller spec | 打包配置未创建 | 低 — Phase 5 处理 |
| `tests/` | 测试目录尚未创建 | **高** — 所有 TDD 前提 |
| `backend/`, `frontend/`, `electron/` | 目录待脚手架搭建 | **高** — 阻塞所有开发 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
