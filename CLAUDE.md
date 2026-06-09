# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MapGuide** is a Windows desktop application (Electron + Vue 3 + Python) for interactively editing MapServer Mapfile (`.map`) and MapCache XML (`.xml`) configurations. The UX is **config-tree-first**: the left panel is an interactive `ConfigTree` where users add layers, edit parameters inline, and trigger validation; the right panel is a Q&A assistant where an LLM answers questions about parameters, explains errors, and suggests configurations.

**Design constraints**: single-person project, minimal scope, no over-engineering. The MVP targets one flow: **PostGIS/Shapefile → WMS/WFS/WCS → optional MapCache disk cache (WMTS/TMS)**, locked to **MapServer 8.4**.

**⚠️ CLAUDE.md 定位**: 本文档面向开发决策（架构约束、关键规则、实现细节）。架构决策以本文档和 `Document/技术细节.md` 为准。项目根目录暂无 README.md；快速上手指南在 `Document/design/conventions.md` §2。

---

## SDD Workflow

This project uses **Specification-Driven Development (SDD)**. All plans are locked; changes must go through the proposal process.

| Layer | File | Purpose |
|-------|------|---------|
| Constitution | `Document/constitution.md` | Rarely changes |
| Spec | `Document/spec.md` | Source of truth for requirements |
| Plans | `Document/plan-*.md` | Per-module design (locked) |
| Proposals | `Document/changes/proposal-{NNNN}.md` | Active change deltas |

**Rules**:
- Never modify a locked plan or spec directly. Create a `proposal-{NNNN}.md` first.
- Proposal types: Type-A (req change), Type-B (design change), Type-C (bug fix, no proposal needed), Type-D (tech debt).
- TDD discipline: RED → GREEN → REFACTOR. One failing test at a time.
- All proposals are in `Document/changes/`. See `Document/changes/proposal-0001.md` through `proposal-0003.md` for examples.

---

## Current Implementation State

**All 5 phases complete + 14 proposals implemented** — backend Python ~2,700 lines, frontend Vue/TS ~1,100 lines, Electron ~300 lines, **334 Python tests + 79 frontend tests passing**.

| Module | Files | Tests | Proposal |
|--------|-------|-------|----------|
| `generate_rules.py` | `scripts/generate_rules.py` | `tests/unit/test_generate_rules.py` (53), `tests/integration/test_rules_output.py` (17) | #0002 |
| `TemplateMapper` + `FieldDescriptor` | `backend/core/template_mapper.py` | `tests/unit/test_template_mapper.py` (33) | #0003 |
| `ConfigSession` + `ConfigTree` | `backend/core/session.py`, `backend/core/config_tree.py`, `backend/core/history.py` | `tests/unit/test_session.py` (12), `tests/unit/test_config_tree.py` (52) | #0004 |
| `ValidationPipeline` (L1-L4) | `backend/core/validation.py` | `tests/unit/test_validation.py` (45) | #0005 |
| `LLMClient` + `LLMOutput` + `UpdateResolver` | `backend/llm/llm_client.py`, `llm_output.py`, `update_resolver.py` | `tests/unit/test_llm_client.py` (6), `test_llm_output.py` (17), `test_update_resolver.py` (5) | #0006 |
| `PromptBuilder` + `QAService` + `ImportService` + `ExportService` | `backend/llm/prompt_builder.py`, `core/qa_service.py`, `core/import_service.py`, `core/export_service.py` | `tests/unit/test_prompt_builder.py` (5), `test_qa_service.py` (9), `test_import_service.py` (7), `test_export_service.py` (8) | #0007 |
| `MapCacheGenerator` + `MapCacheValidator` | `backend/mapcache/generator.py`, `mapcache/validator.py` | `tests/unit/test_mapcache_generator.py` (8), `test_mapcache_validator.py` (8) | #0008 |
| `CustomPropModal` + Electron config | `frontend/src/components/CustomPropModal.vue`, `electron/main.js`, `electron/preload.js`, `SourceCode/package.json` | `tests/unit/*` (FieldEditor 25, ws 13, ui 11, session 1, ObjectCard 4) | #0009 |
| WebSocket routing | `backend/main.py` | `tests/unit/test_main.py` (12) | #0004, #0007 |
| UI 差距修复 | `frontend/src/components/ConfigTreePanel.vue`, `ObjectCard.vue`, `FieldEditor.vue` | — | #0010 |
| 块提问 UX 修复 | `frontend/src/components/ObjectCard.vue`, `QAPanel.vue` | QAPanel 11 | #0011 |
| QA loading 占位气泡 | `frontend/src/types/tree.ts`, `stores/ui.ts`, `services/ws.ts`, `components/QAPanel.vue` | ui 4, QAPanel 4, ws 4 | #0012 |
| 必填项语义分层 + UI 三档筛选 | `data/templates/required.json`, `generate_rules.py`, `template_mapper.py`, `config_tree.py`, `ObjectCard.vue`, `FieldEditor.vue`, `ConfigTreePanel.vue` | backend 56 + frontend 11 | #0013 |
| **扩展 required_when 覆盖服务发布基本参数** | `data/templates/required.json` | — | **#0014** |
| 导入按钮 + IPC readFile | `frontend/src/components/ConfigTreePanel.vue`, `electron/main.js`, `electron/preload.js` | — | Type-C |
| 导入默认值抑制 (import_mode) | `backend/core/config_tree.py`, `backend/core/session.py`, `backend/core/import_service.py` | — | Type-C |
| 字段搜索（结果列表跳转） | `frontend/src/components/ConfigTreePanel.vue`, `ObjectCard.vue`, `FieldEditor.vue` | ConfigTreePanel 6 | Type-C |

**Spikes** (pre-development validation, not production code):

- V1 (`spike/v1_mappyfile_validate.py`): mappyfile behavior, 62 cases
- V2 (`spike/v2_llm_prompt_stability.py`): LLM JSON stability, 30 calls
- V3 (`spike/v3-config-tree/`): ConfigTree recursive rendering, 280 nodes

See `spike/v1_result.md`, `spike/v2_result.md`, `spike/v3_result.md`, `spike/feasibility_report.md`.

---

## Architecture

### Big Picture

```
Electron Main (Node.js)
  ├─ spawns Python backend subprocess (dev: manual, prod: PyInstaller exe)
  └─ manages window lifecycle

Vue 3 Renderer (Naive UI + Pinia)
  ├─ ConfigTree: left panel, interactive Mapfile hierarchy tree
  └─ QAPanel: right panel, chat history + question input
      ↕ WebSocket (ws://localhost:PORT/ws)  ← ONLY communication channel

Python Backend (FastAPI + uvicorn, gis-agent conda env)
  ├─ WebSocket endpoint: receives tree updates / questions / validate / export / set_service_types
  │     │
  │     ├──▶ ConfigSession holds params (mappyfile dict) + ConfigTree + DialogueHistory + service_types
  │     │
  │     ├──▶ ConfigTree: business view over params, supports custom props,
  │     │              filters METADATA/LAYER fields by service_types (WMS/WFS/WCS)
  │     │
  │     ├──▶ TemplateMapper loads mapguide_rules.json (aliases, types, required, defaults, deps, service_metadata)
  │     │
  │     ├──▶ ValidationPipeline: 4-layer validation (alias → type → semantic → mappyfile)
  │     │
  │     └──▶ QAService.answer(question) ──▶ PromptBuilder + LLMClient + UpdateResolver
  │
  ├─ Mapfile generator: to_mappyfile_dict() → mappyfile.validate() → mappyfile.dumps()
  │   (one .map supports WMS + WFS + WCS simultaneously)
  └─ MapCache generator: backend/mapcache/ (Jinja2 template + MapCacheValidator, WMTS/TMS)
```

### Communication Constraint

**Front-end ↔ back-end uses WebSocket ONLY.** No HTTP REST endpoints for front-end consumption. The only HTTP traffic is back-end → LLM vendor API.

### Data Flows

**User edits a field:**
```
tree_update WS message { updates: [{path, value}] }
    │
    ▼
ConfigTree.update_value()  # 遍历 updates 逐个应用
    │
    ▼
ValidationPipeline.validate_field(path, service_types)  # layers 1-3 only
    │
    ▼
tree_state WS message → frontend
```

**User asks a question:**
```
question WS message
    │
    ▼
QAService.answer(session, text)
    │
    ├──▶ PromptBuilder.render(L0-L5 context)
    ├──▶ LLMClient.chat()
    ├──▶ LLMOutput.parse(raw_json)
    ├──▶ UpdateResolver.resolve() → path
    ├──▶ ConfigTree.apply_updates()
    └──▶ ValidationPipeline.validate_tree()
    │
    ▼
qa_result WS message → frontend (triggers finishQALoading + add bot message)
```

**User clicks manual validate:**
```
validate WS message
    │
    ▼
ValidationPipeline.validate_tree(tree, service_types)
    │
    ▼
validation_result WS message → frontend (QA error summary)
tree_state WS message → frontend (leaf-level error indicators updated)
```

**User imports a mapfile:**
```
import_mapfile WS message { content: "MAP..." }
    │
    ▼
ImportService.import_mapfile() → mappyfile.loads(content)
    │
    ▼
ConfigSession(import_mode=True)  # suppresses default backfill
    │
    ▼
ValidationPipeline.validate_tree()  # full L1-L4
    │
    ▼
import_result + tree_state WS messages → frontend
```

**User edits a field (auto-validate):**
```
tree_update WS message { updates: [{path, value}] }
    │
    ▼
ConfigTree.update_value()
    │
    ▼
ValidationPipeline.validate_field(path, service_types)  # L1–L3 only
    │
    ▼
tree_state WS message → frontend (leaf errors updated inline)
```

---

## Critical Rules

- The LLM **never** generates raw Mapfile/XML text. It outputs structured JSON (`action`, `params_update`, `question`). Backend validates, merges into `ConfigSession.params`, then feeds to `mappyfile` / Jinja2 for deterministic generation.
- **No per-phase prompt, no phase state machine**. Only one `_framework.j2` exists. Backend handles all rules.
- **Service type selection**: UI shows checkboxes for WMS/WFS/WCS + MapCache(WMTS/TMS). METADATA and LAYER fields are filtered by selected services. `ows_*` (general prefix) fields are always visible; `wms_*`/`wfs_*`/`wcs_*` fields appear only when their service is checked. Hidden field values are retained in params.
- The UI is a **two-column layout**: left `ConfigTree` (55%), right `QAPanel` (45%).
- `phase` is a **classification label** (datasource=blue `#2563eb`, style=orange `#ea580c`, service=green `#16a34a`, cache=purple `#9333ea`), not a flow driver.
- **Any parameter modification** (user-edited or LLM-suggested) triggers validation.
- Validation is **layered**: alias → type → semantic → mappyfile syntax. Field blur only runs layers 1-3; add/remove node, manual validate, and export run all 4 layers.
- **Export condition chain** (cannot skip): `validation_state == "pass"` ∧ `no validation errors`.
- **No persistence**: `ConfigSession` is in-memory only. "Reset" destroys and recreates the session.
- **Flat path addressing**: LLM updates use stable paths (e.g. `layers.0.connectiontype`), not line numbers. No line_map or rebuild_line_map needed.
- **Focus can be parameter or node**: Clicking a `FieldEditor` leaf sets focus to the parameter path (e.g. `layers.0.name`); clicking an `ObjectCard` header sets focus to the node path (e.g. `layers.0`). Both are injected into the LLM prompt via `focus_param`.
- **Focus change inserts divider**: Switching focus resets the backend DialogueHistory (preserves intent), and the frontend inserts a visual divider line in the QA panel. Dividers only appear when there was actual user/bot exchange since the last divider; empty history or repeated focus switches without QA do not produce dividers.

---

## Commands

### Python Environment

All Python work **must** use the `gis-agent` conda environment. `conda activate` does not work in this bash shell; always invoke Python by full path.

```bash
# Python executable
"/c/Users/PC/.conda/envs/gis-agent/python" --version   # 3.11.15

# Package installer (when needed)
"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install <pkg>
```

### Tests

**pytest must be run from `SourceCode/`** because tests live under `SourceCode/tests/unit/`:

```bash
cd SourceCode

# All tests
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/ -v

# Single test file
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_template_mapper.py -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_config_tree.py -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_validation.py -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_mapcache_generator.py -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_main.py -v

# Single test class or method
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_template_mapper.py::TestResolveAlias -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_generate_rules.py::TestInferValueType::test_enum_present_returns_enum -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_config_tree.py::TestConfigTreeSerialize::test_transform_1_custom_expansion -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_validation.py::TestValidationPipelineIntegration -v
```

### Rules Generation

```bash
cd SourceCode

# Generate rules (run whenever templates change)
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py

# Verify output
"/c/Users/PC/.conda/envs/gis-agent/python" -c "import json; r=json.load(open('data/mapguide_rules.json', encoding='utf-8')); print(f'Objects: {len(r[\"object_types\"])}, Fields: {sum(len(o[\"fields\"]) for o in r[\"object_types\"].values())}')"

# Run V1 validation spike
"/c/Users/PC/.conda/envs/gis-agent/python" spike/v1_mappyfile_validate.py
```

### Backend (Python)

```bash
cd SourceCode/backend

# Start dev server (Electron uses port 18080; standalone dev can use any port)
"/c/Users/PC/.conda/envs/gis-agent/python" -m uvicorn main:app --port 18080 --reload

# Install dependencies
"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install -r requirements.txt
```

### Frontend (Vue)

```bash
cd SourceCode/frontend

# Dev server
npm run dev

# Tests (vitest + jsdom)
npm test               # interactive watch mode
npm test -- --run      # single run (CI mode)

# Single test file
npm test -- --run src/components/FieldEditor.spec.ts
npm test -- --run src/services/ws.spec.ts

# Production build
npm run build
# Note: vue-tsc has Node v24 compatibility issues; use `npx vite build` as fallback
```

**Path aliases**: Both `vite.config.ts` and `vitest.config.ts` must define `resolve.alias: { '@': path.resolve(__dirname, 'src') }` for `@/` imports to work in dev and test.

### Electron

```bash
cd SourceCode

# Dev mode (auto-starts Python backend from gis-agent conda env)
npm run electron:dev

# Production build
npm run electron:build
# Output: dist/MapGuide-Setup-x.x.x.exe
```

**Electron backend path behavior** (`electron/main.js`):
- **Development**: Uses `C:\Users\PC\.conda\envs\gis-agent\python.exe` (overridable via `PYTHON_PATH` env var) to run `uvicorn backend.main:app --port 18080`. Waits for port 18080 to be ready before loading the window.
- **Production**: Uses `resources\backend\MapGuideBackend.exe` (PyInstaller single-file output from `_entrypoint.py`). The exe is included via `build.extraResources` in `SourceCode/package.json`.
  - **IS_DEV detection**: `!!process.defaultApp` (NOT `app.isPackaged`, which returns `false` in `win-unpacked` mode).
  - **Resources path**: Electron passes `MAPGUIDE_RESOURCES = process.resourcesPath` env var so the backend knows where external `config/` lives.
  - **Entry point**: PyInstaller uses `backend/_entrypoint.py` (not `main.py`) as the entry script. `_entrypoint.py` sets up `sys.path` and calls `uvicorn.run(app)`.
- **Process cleanup**: On Windows, `SIGTERM` does not work on PyInstaller exe. Use `taskkill /pid ${pid} /f /t` (kill process tree, including uvicorn workers). Force-kill after 2s if still running.
- **IPC channels**:
  - `dialog:openFile` — file picker with filter support (used for import)
  - `file:read` — reads file content as UTF-8 string (used for import)
  - `save:exportFiles` — opens directory dialog and writes exported files (`.map`, `.xml`) to disk

### Production Packaging

**推荐方式**：一键 PowerShell 脚本（含全部 5 步：前置检查 → Vite 构建 → PyInstaller → electron-builder → README）

```powershell
cd scripts
.\build-electron.ps1
```

输出到项目根目录 `dist/`，包含 NSIS 安装包和便携版 `win-unpacked/`。

**手动步骤**（调试/排查时使用）：

```bash
# Step 1: Python backend → standalone exe
cd SourceCode/electron/build
"/c/Users/PC/.conda/envs/gis-agent/python" -m PyInstaller pyinstaller.spec --clean --noconfirm --distpath ../../backend/dist --workpath ../../backend/build

# Step 2: Vue frontend → static bundle
cd SourceCode/frontend
npm run build
# ⚠️ 检查 dist/index.html 中 script src 是否为 "./assets/" 开头

# Step 3: Electron → Windows installer
cd SourceCode
npx electron-builder
```

---

## Testing: Importing Non-Package Modules

`backend/core/` modules are not on the default PYTHONPATH during test runs. Each test file that imports them adds the directory via `sys.path.insert`:

```python
import sys
from pathlib import Path

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

from config_tree import ConfigTree, TreeNode, TreeLeaf
```

For `scripts/generate_rules.py` (outside any package), use `importlib.util`:

```python
import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location("generate_rules", SCRIPTS_DIR / "generate_rules.py")
assert _spec is not None and _spec.loader is not None
gr = importlib.util.module_from_spec(_spec)
sys.modules["generate_rules"] = gr
_spec.loader.exec_module(gr)
```

---

## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. Use it for **structural** questions — what calls what, what would break, where is X defined, what is X's signature. Use native grep/read only for **literal text** queries (string contents, comments, log messages) or after you already have a specific file open.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach/become Y?" | `codegraph_trace` |
| "What would changing this break?" | `codegraph_impact` |
| "Show me Y's source / signature" | `codegraph_node` |
| "Give me focused context for a task" | `codegraph_context` |
| "See several related symbols at once" | `codegraph_explore` |
| "What's in directory X?" | `codegraph_files` |

**Rules of thumb**:
- Answer architecture questions **directly** with 2-3 codegraph calls instead of delegating to file-reading sub-agents.
- Don't chain `codegraph_search + codegraph_node` when you just want context — `codegraph_context` is one call.
- Don't loop `codegraph_node` over many symbols — one `codegraph_explore` returns several symbols' source grouped.
- Index lags ~500ms behind writes; don't re-query immediately after editing a file in the same turn.

---

## Key Technical Decisions

### Data Flow: Schema + Templates → Rules

```
mapfile-schema-8-4.json (official MapServer 8.4 schema)
    │
    ├─ aliases.json        → 自然语言/中文 → 参数值映射
    ├─ required.json       → 必填/条件必填规则
    ├─ phase-map.json      → 对象类型 → 阶段归属
    ├─ defaults-override.json → 默认值覆盖
    ├─ dependencies.json   → 跨字段依赖
    ├─ custom-allowed.json → 自定义属性白名单
    ├─ object-fields.json  → 业务补充字段（METADATA、CACHE 等 schema 未枚举的场景）
    └─ service-metadata.json → WMS/WFS/WCS 多服务参数映射
    │
    ▼
generate_rules.py 合并
    │
    ▼
mapguide_rules.json（运行时唯一读取的规则文件）
    │
    ▼
TemplateMapper.__init__() 加载
    │
    ▼
FieldDescriptor
```

**Key merge rules** (implemented in `generate_rules.py`):
- `value_type`: Schema enum → `"enum"`; Schema type → mapped internal type; unknown → `"string"`
- `default`: `defaults-override.json` > schema default > `None`. Example override: `MAP.size` defaults to `[800, 600]` instead of schema's `[-1, -1]`.
- `required` / `required_when` / `business_required`: from `required.json`
- `phase`: from `phase-map.json` (all fields in an object type share the same phase)
- `aliases`: from `aliases.json`
- `dependencies`: from `dependencies.json`
- `custom_allowed`: from `custom-allowed.json`
- Nested objects not in `EXPANDED_NESTED_FIELDS` are marked `editable: false`

**Windows encoding note**: `generate_rules.py` writes UTF-8 correctly. If `python scripts/generate_rules.py` prints garbled Chinese in this bash shell, it is a **terminal display issue** (Windows default code page), not file corruption. Verify with `sys.stdout.reconfigure(encoding='utf-8')` or by inspecting the file bytes.

**Output structure**: `mapguide_rules.json` contains `object_types` (per-type field definitions), `flat_params` (indexed paths for PromptBuilder), `aliases`, `dependencies`, `phase_map`, `custom_allowed`, `service_metadata`.

### LLM Integration (anthropic SDK)

- `LLMClient` wraps `anthropic.Anthropic` with configurable `base_url`.
- `chat()` for structured JSON output (`temperature=0.1`, exponential backoff retry 3×).
- **Single Prompt**: `PromptBuilder` assembles one Jinja2 template (`_framework.j2`) + runtime session context.
- Token budget: ~1500 tokens total (L0-L5), recent QA history capped at 4-6 rounds.
- **LLM boundary**: The LLM only understands natural language and outputs raw parameter values or flat path-based updates (e.g. `layers.0.connectiontype`). All alias conversion, type conversion, validation, and default-filling is handled by backend code.
- **Provider lock**: Only Anthropic Claude is supported. LLMClient encapsulates the SDK; no raw API exposure to upper layers.

**V2 validation findings** (affect LLMOutput / PromptBuilder):
- JSON parse rate **93.3%**; `action=update` is **100%** stable
- 4-layer fallback parsing: `direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback`
- `strip_codeblock` saves **23%** of calls — LLM still wraps in ` ```json ` despite prompt forbidding it
- `action=answer` content truncation risk → prompt limits `content≤300` chars
- Common type errors: `projection` as string instead of array; `status` as JSON bool instead of `"ON"`/`"OFF"`

### Validation Pipeline

Validation happens after every parameter change:

1. **Alias resolution**: `TemplateMapper.resolve_alias()` converts user-friendly terms.
2. **Type conversion**: Pydantic validates types, enums, ranges.
3. **Semantic validation**: `dependencies.json` drives conditional required, mutually exclusive, derived-value, and **validates** rules.

   **Supported relations**:
   - `requires_when`: source 字段满足 condition 时，target 字段必须存在且非空
   - `forbids_when`: source 字段满足 condition 时，target 字段不应存在
   - `derives` / `invalidates`: 信息类，不报错
   - `validates`: source/target 指向同一字段时，对字段值执行业务级校验；condition 支持 `value[0]`, `len(value)`, `min()`, `max()`, `all()`, `any()`, `isinstance()`

   Example (`MAP.size` must be two positive integers):
   ```json
   {
     "source": "MAP.size",
     "target": "MAP.size",
     "relation": "validates",
     "condition": "len(value) == 2 and value[0] > 0 and value[1] > 0",
     "description": "MAP SIZE 必须是两个正整数 [width, height]"
   }
   ```
4. **mappyfile syntax**: `mappyfile.validate(mf, version=8.4)` validates the assembled Mapfile.

Layers 1-3 run on every field blur. Layer 4 only runs on add/remove node, manual validate, and export.

### Mapfile Generation

Use mappyfile's native object flow:

```python
mf_dict = tree.to_mappyfile_dict()  # applies 9 transforms including __type__ tags
errors = mappyfile.validate(mf_dict, version=8.4)  # pass float, not str
output = mappyfile.dumps(mf_dict)
```

**Constraints**: `version` must be `float` (`8.4`), not `str`. `PROJECTION` must be an array `["init=epsg:3857"]`, not a string.

### ConfigTree.to_mappyfile_dict() — Serialization Rules

`ConfigTree.to_mappyfile_dict()` performs 9 mandatory transforms before handing data to mappyfile. These rules come from V1 validation (`spike/v1_result.md`) against `mappyfile==1.1.1`, plus proposal-0013 Amendment and the `__type__` discovery:

| # | Transform | Trigger | Why |
|---|-----------|---------|-----|
| 1 | `_custom` expansion | `"_custom" in dict` | mappyfile rejects unknown keys; custom props must be hoisted |
| 2 | `cache` strip | `key == "cache"` | `cache` is not a Mapfile object; MapCache XML generated separately |
| 3 | Array wrap | `key in {layers,classes,styles,labels}` and `isinstance(v, dict)` | mappyfile requires these to be lists |
| 4 | Enum-bool conversion | `field_key in {"status"}` and `isinstance(v, bool)` | string-enum fields (e.g. `status`) reject Python bool; boolean-type fields (e.g. `LABEL.antialias`) accept it |
| 5 | PROJECTION array guard | `key == "projection"` | must remain a list |
| 6 | Extent array guard | `key == "extent"` | must remain a 4-element list |
| 7 | Color RGB array guard | `value_type == "color"` | must remain `[R, G, B]` |
| 8 | **None filter** | `v is None` | Unset optional fields must not appear in Mapfile; mappyfile treats `None` as invalid |
| 9 | **`__type__` tags** | nested dicts (`web`, `metadata`, `layers`, etc.) | mappyfile `dumps()` requires `__type__` on every nested object to expand them as proper `WEB ... END` blocks instead of Python dict strings. Root object gets `"map"`; `web`→`"web"`, `metadata`→`"metadata"`, `layers[i]`→`"layer"`, etc. |

**ValidationPipeline L2 behavior**: Non-required fields with `None` values are skipped in `_check_type()` (no type error). Only `required=True` fields (e.g. `LAYER.type`) report type errors for `None`. This pairs with transform 8 to ensure unset optional fields neither fail validation nor pollute export.

**Critical validation findings**:
- mappyfile `dumps()` never throws (62/62 test cases); `validate()` is the strict gate
- `validate()` **does NOT check** `MAP.name` or `LAYER.name` as required → must rely on L3 semantic validation
- `validate()` rejects **any** schema-external field with `does not match any of the regexes` → L4 must filter these false positives (custom props + `object-fields.json` fields)
- **Nested objects require `__type__`**: mappyfile `dumps()` treats plain Python dicts as strings. `WEB {'metadata': {...}}` is the failure mode. Every nested object must carry `__type__` (`"web"`, `"metadata"`, `"layer"`, etc.) for mappyfile to emit proper `WEB ... METADATA ... END END` blocks.
- Enum values are **case-insensitive** (`postgis`/`POSTGIS` both pass)

### ConfigTree Design

- `ConfigSession.params` is the **single source of truth**: a mappyfile-compatible dict.
- `ConfigTree` wraps it with `TreeNode`/`TreeLeaf` for UI rendering and custom properties.
- Custom properties are stored under `_custom` per object and expanded during serialization.
- LLM updates use **flat path addressing** (`layers.0.connectiontype`) — stable identifiers that do not change when tree structure changes.

**Default value backfill**: `ConfigTree._build_tree()` writes `desc.default` back into `params` when a field is absent or explicitly `None`. This ensures fields marked with `D` in the UI actually hold their default value and pass validation.

**Import mode (`import_mode=True`)**: When importing an existing `.map` file, `ConfigTree` is constructed with `import_mode=True`. In this mode, missing fields are **not** backfilled with defaults — only fields actually present in the original mapfile are retained. This preserves round-trip fidelity (import → export produces a file structurally identical to the original, minus comments which mappyfile does not preserve). New nodes added via `add_object()` during an import session are pre-filled with defaults so they remain usable.

**Required field semantics (3 layers)**:
- `required` (red `*`): Syntax-absolute required — `mappyfile.loadXXX()` fails if missing. Only `LAYER.type` and `CACHE.type` qualify.
- `required_when` (orange `◆`): Conditionally required / conditionally important based on runtime context. Two sub-categories:
  - **Functional dependency**: parent field values drive requirement, e.g. `LAYER.connection` when `connectiontype in ['postgis','ogr','wms']`
  - **Business importance**: fields that have defaults but are critical for service publishing, e.g. `MAP.extent` (defaults to global `[-180,-90,180,90]`), `MAP.projection`, `LAYER.extent` — marked when `len(session.service_types) > 0`
- `business_required`: Cleared. Rationale: all previously listed fields now have defaults handled by automatic backfill. **Note**: having a default does NOT remove business importance — see `required_when` business-importance category above.

**Service type filtering in ConfigTree**: ConfigTree receives `service_types: list[str]` at construction time. METADATA field visibility follows prefix rules:
- `ows_*` — always visible (general prefix shared by all OGC services)
- `wms_*` / `wfs_*` / `wcs_*` — visible only when their service is in `service_types`
- `gml_*` — lives under **LAYER.METADATA**, visible only when WFS is enabled
- Hidden field values are retained in `params`; filtering is purely a UI concern

**Internal node filtering on export**: `to_mappyfile_dict()` does two critical transforms before handing data to mappyfile:
1. **Skip `cache`** — The `cache` node holds MapCache config (type, base, expires, wmts_enabled, tms_enabled). It is not a Mapfile standard object; MapCache XML is generated separately by `MapCacheGenerator` via Jinja2.
2. **Expand `_custom`** — Custom properties are stored as `_custom: {key: {value, type, desc}}` per object. During serialization the container is removed and inner keys are promoted to the parent dict.

Directly calling `mappyfile.dumps(session.params)` will fail because mappyfile does not recognize the `cache` key. Always go through `tree.to_mappyfile_dict()`.

### Frontend UX Behaviors

**Loading placeholder for LLM processing**: Any `question` WS message sent from anywhere (QAPanel input, quick questions, FieldEditor ? button) automatically triggers a `role: 'loading'` placeholder bubble via `ws.ts send()`. The placeholder is removed by `finishQALoading()` when `qa_result`, `error`, or timeout/clear occurs. See proposal-0012.

**Auto-scroll**: The chat area (`chat-area`) automatically scrolls to bottom whenever `qaMessages.length` changes (`{ immediate: true }`).

### Frontend UI Specification

The UI design is specified in `Document/技术细节.md` §4/§11/§12 and visualized in `Document/UX/ui-prototype-interactive-v2.html`. Key constraints:

- **Two-column layout**: left `ConfigTree` (55%), right `QAPanel` (45%)
- **Inline editing**: each leaf uses a control mapped from `FieldDescriptor.value_type`
- **Focus mechanism**: clicking a tree node sets `focus_param` (flat path like `layers.0.name`), injected into the LLM prompt
- **Phase color badges**: datasource=blue `#2563eb`, style=orange `#ea580c`, service=green `#16a34a`, cache=purple `#9333ea`
- **Show-mode toggle**: Three modes — `all` (全部), `required` (建议填, shows `required=True` OR `required_when` present), `strict` (仅必填, shows only `required=True` without `required_when`)
- **Custom properties**: modal dialog for key + description + type; rendered with `✎` indicator
- **Legend bar**: top of ConfigTree shows `📋 图例：* 必填 · ◆ 条件 · D 默认值 · ○ 可选 · → 推导 · ✎ 自定义`
- **QA round counter**: displayed in QAPanel header; resets to 0 on focus change
- **Reset / New Task** button: confirm dialog, then full session reset
- **No history persistence**: in-memory only
- **Import button**: "📂 导入" pill button in ConfigTreePanel header, left of validate/export. Opens Electron file dialog (`.map` filter), reads file via `readFile` IPC, sends `import_mapfile` WS message.
- **Responsive breakpoints**: ≤900px collapses QAPanel; ≤600px uses bottom input bar

### Electron Production Packaging

The production build bundles the Python backend into a standalone exe via PyInstaller, packages the Vue frontend via Vite, and wraps both in an Electron installer via electron-builder. The packaging flow is: **PyInstaller** (Python → exe) → **Vite build** (Vue → static) → **electron-builder** (exe + static → installer/portable).

**Critical: 7 pitfalls and their solutions** (all discovered and fixed during the initial packaging of this project):

| # | Pitfall | Symptom | Solution |
|---|---------|---------|----------|
| 1 | `app.isPackaged` unreliable | `win-unpacked` exe falsely reports dev mode → "Backend Startup Failed" | Use `const IS_DEV = !!process.defaultApp` in `electron/main.js` |
| 2 | Vite absolute paths | Blank page after launch, JS/CSS 404 under `file://` | `base: './'` in `vite.config.ts`; verify `dist/index.html` uses `./assets/` |
| 3 | PyInstaller path misalignment | "Templates directory not found: `_MEIxxx\llm\templates`" | PyInstaller places entry script at `sys._MEIPASS` root. `datas` target path must NOT include `backend/` prefix (e.g. `('.../llm/templates', 'llm/templates')` NOT `('.../llm/templates', 'backend/llm/templates')`) |
| 4 | Third-party package resources missing | "map.json does not exist" (mappyfile schemas) | PyInstaller does NOT auto-bundle `.json`/`.j2` files from installed packages. Explicitly add them: `(str(site_packages / 'mappyfile' / 'schemas'), 'mappyfile/schemas')` in `datas` |
| 5 | No uvicorn entry point | PyInstaller exe exits immediately, backend health check times out | Create `backend/_entrypoint.py` with `sys.path` setup + `uvicorn.run(app)`. PyInstaller entry must be `_entrypoint.py`, not `main.py` |
| 6 | Windows signal handling broken | Python process survives after closing Electron window | On Windows, `SIGTERM` is ignored by PyInstaller exe. Use `taskkill /pid ${pid} /f /t` in `electron/main.js` `stopPythonBackend()` |
| 7 | Config trapped in asar | Users cannot edit `config.json` after installation | `config/` → `extraResources` (asar-external); `data/` → `datas` (bundled inside exe). Electron passes `MAPGUIDE_RESOURCES=process.resourcesPath` env var so backend finds external config |

**Backend path resolution** (`backend/main.py`) handles both dev and PyInstaller modes:

```python
if hasattr(sys, '_MEIPASS'):
    _BASE_DIR = Path(sys._MEIPASS)           # bundled data/ lives here
    _RESOURCE_DIR = Path(os.environ.get('MAPGUIDE_RESOURCES', sys._MEIPASS))
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent
    _RESOURCE_DIR = _BASE_DIR

RULES_PATH = _BASE_DIR / "data" / "mapguide_rules.json"     # read-only, bundled
CONFIG_PATH = _RESOURCE_DIR / "config" / "config.json"      # user-editable, external
TEMPLATES_DIR = Path(__file__).resolve().parent / "llm" / "templates"
```

**Vite config check** (`frontend/vite.config.ts`): Always verify `base: './'` is present. After `npm run build`, inspect `dist/index.html` — `<script src="./assets/...">` must use `./` prefix. If it shows `src="/assets/..."`, Electron's `file://` protocol resolves `/` to disk root (`C:/assets/...`), causing a blank page.

---

## Documentation References

| File | Purpose |
|------|---------|
| `Document/constitution.md` | SDD constitution — project values, scope boundaries |
| `Document/spec.md` | Requirements spec — MoSCoW, MVP scope, constraints |
| `Document/plan-template-system.md` | Template resources plan — DC-001~DC-003 |
| `Document/plan-config-tree.md` | ConfigSession/ConfigTree plan |
| `Document/plan-validation.md` | ValidationPipeline plan |
| `Document/plan-backend-llm.md` | LLM integration plan |
| `Document/plan-frontend.md` | Frontend component plan |
| `Document/plan-platform.md` | Electron + packaging plan |
| `Document/需求输入.md` | High-level requirements (Chinese) |
| `Document/技术细节.md` | Design overview index (Chinese) |
| `Document/design/template-system.md` | Template resources, generate_rules.py merge logic, TemplateMapper, FieldDescriptor |
| `Document/design/data-structures.md` | ConfigSession, ConfigTree, TreeNode/TreeLeaf, flat path addressing |
| `Document/design/validation.md` | 4-layer validation strategy, mappyfile false-positive filtering |
| `Document/design/core-services.md` | Architecture overview, ValidationPipeline, ExportService, ImportService, class directory |
| `Document/design/llm-integration.md` | DialogueHistory, Prompt L0-L5 context, QAService, LLMClient, LLMOutput parsing |
| `Document/design/interaction-flows.md` | 6 interaction scenario data flows |
| `Document/design/frontend-backend-contract.md` | WebSocket message types, communication constraints |
| `Document/design/conventions.md` | Tech stack, directory structure, dev commands, code constraints, debugging |
| `Document/模板说明.md` | Template resource reference for GIS professionals |
| `Document/UX/ui-prototype-interactive-v2.html` | Interactive UI prototype |
| `spike/v1_result.md` | V1 conclusions: mappyfile validate() behavior, to_mappyfile_dict() 7 transforms |
| `spike/v2_result.md` | V2 conclusions: LLM JSON output stability, graceful degradation patterns |
| `spike/v3_result.md` | V3 conclusions: ConfigTree recursive rendering, 280-node perf, 7 value_type controls |
| `spike/feasibility_report.md` | Go/No-go decision: all 3 spikes passed |
| `Document/design/implementation-progress.md` | Remaining modules, difficulty heatmap, time estimate |

---

## Conventions

- **Backend code** lives in `SourceCode/backend/`. Use absolute Python path from gis-agent conda env for all Python execution.
- **Single LLM**: One System Prompt (`_framework.j2`), no phase state machine. Backend handles all rules.
- **Validate on every change**: Every user edit and every LLM-suggested update triggers validation.
- **No persistence**: `ConfigSession` is in-memory only. "Restart" destroys and recreates the session.
- **Version locked**: MVP targets MapServer 8.4 only.
- **Frontend UI library**: Naive UI (not Element Plus). **Do not use `n-tree`** — use custom layered rendering (ObjectCard + FieldEditor).
- **`config.json` is gitignored**: It contains LLM API credentials. Use `config.json.template` as the reference structure.
- **`mapguide_rules.json` is generated**: Run `scripts/generate_rules.py` after modifying `data/templates/`. The script also loads `service-metadata.json` for multi-service parameter mapping.
- **Multi-service Mapfile**: One `.map` file supports WMS + WFS + WCS simultaneously. Service-specific METADATA params (wms_*, wfs_*, wcs_*) are filtered by UI; `ows_*` general-prefix params are always visible. WMTS/TMS are provided via MapCache (`mapcache.xml`), not Mapfile.
- **Default values are technical fallbacks, not business exemptions**: A field having a default (e.g. `MAP.extent = [-180,-90,180,90]`) does not mean it requires no user attention. Proposal-0014 established that service-critical fields with defaults should still be marked `required_when` under service mode to prompt user review.
- **`data/schemas/` removed**: the root-level `mapfile-schema-8-4.json` and `schemas/` directory were cleaned up; the canonical schema now lives in `data/templates/mapfile-schema-8-4.json`.
- **Color format**: RGB arrays `[0, 0, 255]` everywhere. No hex conversion.
- **Testing approach**: TDD. Unit tests for backend/core/ and backend/llm/. Integration tests for generate_rules.py output + LLM mock end-to-end.
- **QA panel divider behavior**: Visual dividers in the QA panel mark context resets (focus change or manual clear). They use `role: 'divider'` (not `system`) with a minimal 1px gray line. Dividers are only inserted when (a) there is actual user/bot message history, and (b) there has been new QA exchange since the last divider. No double icons: `roleIcon('system')` already shows `⚠️`, so system message text must not include a second `⚠️`.
- **Manual validate sends dual messages**: `_handle_validate` sends both `validation_result` (for QA panel error summary) **and** `tree_state` (for leaf-level error indicators on the ConfigTree). Auto-validate via `tree_update` only sends `tree_state`.
- **Commit format**: `type(scope): proposal-NNNN description`
- **Import round-trip**: `import_mode=True` preserves original fields only; defaults are not backfilled. New nodes added during import session are pre-filled with defaults via `add_object()`.
- **Field search**: ConfigTreePanel has a search box that filters current tree leaves by key/path. Clicking a result expands ancestor nodes, sets focus, and scrolls to the field with a highlight pulse.
- **mappyfile comment loss**: `mappyfile.loads()` does not preserve comments. Import → export will lose all `#` comments; this is an inherent limitation, not a bug.

**Constraints**: `version` must be `float` (`8.4`), not `str`. `PROJECTION` must be an array `["init=epsg:3857"]`, not a string.
