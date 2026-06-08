# Proposal-0007: 平台层 — FastAPI WebSocket + ExportService + ImportService

> **类型**: Type-B（设计变更 — 新增组件）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Plan**: `plan-platform` Phase 1, Phase 4
> **影响范围**:
> - `backend/main.py` — FastAPI WebSocket 入口
> - `backend/core/export_service.py` — ExportService
> - `backend/core/import_service.py` — ImportService
> - `tests/unit/test_main.py` — WebSocket 路由测试
> - `tests/unit/test_export_service.py` — 导出测试
> - `tests/unit/test_import_service.py` — 导入测试

---

## 目标

实现后端平台层三个核心模块，使前后端能够通过 WebSocket 进行完整通信。

1. **FastAPI WebSocket (`main.py`)**: 接收前端消息，路由到对应处理器，返回标准响应
2. **ExportService**: 将 ConfigSession 导出为 `.map` 文件内容（+ 可选 `mapcache.xml`）
3. **ImportService**: 将 `.map` 文件文本解析为 ConfigSession

**核心复杂度**：
- WebSocket 消息路由和 session 生命周期管理
- Export 条件链：`validation_state == "pass"` ∧ `no validation errors`
- Import 失败不影响当前会话（原子性）

**原则**：
- TDD 纪律：RED → GREEN → REFACTOR
- WebSocket 测试用 Mock WebSocket 对象
- Export/Import 不依赖真实文件系统（内存操作）

---

## 变更内容

### [ADDED] `backend/main.py`

**FastAPI app** + **WebSocket endpoint**:
- `@app.websocket("/ws")` — 接受连接，接收 JSON 消息，分发处理
- `handle_message(websocket, msg)` — 按 `msg["type"]` 路由
- Session 管理：`sessions: dict[str, ConfigSession]`
- 消息类型处理：`init_session`, `tree_update`, `tree_add_node`, `tree_remove_node`, `focus_change`, `question`, `validate`, `export`, `set_service_types`, `reset_session`, `import_mapfile`
- 响应类型：`tree_state`, `focus_state`, `qa_result`, `validation_result`, `export_result`, `import_result`, `error`

### [ADDED] `backend/core/export_service.py`

**ExportService**:
- `export(session)` → `dict[str, bytes]` — `{"mapfile.map": b"...", "mapcache.xml": b"..."}`
- 使用 `mappyfile.dumps()` + `ConfigTree.to_mappyfile_dict()`
- 条件检查：`can_export` = `validation_state == "pass"` and `len(errors) == 0`

### [ADDED] `backend/core/import_service.py`

**ImportService**:
- `import_mapfile(session_id, content, mapper)` → `(ConfigSession, ValidationResult)`
- 使用 `mappyfile.loads()` 解析文本
- 失败时抛出异常（调用者处理，不影响当前 session）

---

## 测试策略

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-032 | `test_export_service.py` | 导出 .map、校验阻断导出、空 session |
| DC-033 | `test_import_service.py` | 导入成功、导入失败、自定义属性标记 |
| DC-036 | `test_main.py` | Mock WS 消息路由、session 管理、tree_update、question、export、import |

---

## 验收标准

- [x] `pytest tests/unit/test_main.py -v` 全部通过（11 项）
- [x] `pytest tests/unit/test_export_service.py -v` 全部通过（5 项）
- [x] `pytest tests/unit/test_import_service.py -v` 全部通过（4 项）
- [x] WebSocket 消息路由覆盖：init_session, tree_update, tree_add_node, tree_remove_node, focus_change, question, validate, export, set_service_types, reset_session, import_mapfile
- [x] ExportService 校验失败时阻止导出
- [x] ImportService 失败时抛出异常（不污染当前 session）
- [x] 前端 WS 服务集成 stores（tree_state → sessionStore, qa_result → uiStore）
- [x] 前端组件集成：FieldEditor blur/click, ObjectCard focus, QAPanel send, ConfigTreePanel toolbar
- [x] 全部 312 测试通过，零回归

---

## 依赖

- proposal-0003（TemplateMapper）
- proposal-0004（ConfigSession + ConfigTree）
- proposal-0005（ValidationPipeline）
- proposal-0006（QAService + LLM chain）
- FastAPI, uvicorn, mappyfile, jinja2

---

*Approved by: SDD 流程 — plan-platform Phase 1+4 既定任务*
