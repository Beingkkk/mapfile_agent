# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MapGuide** is a Windows desktop application (Electron + Vue 3 + Python) for interactively editing MapServer Mapfile (`.map`) and MapCache XML (`.xml`) configurations. The UX is **config-tree-first**: the left panel is an interactive `ConfigTree` where users add layers, edit parameters inline, and trigger validation; the right panel is a Q&A assistant where an LLM answers questions about parameters, explains errors, and suggests configurations.

**Design constraints**: single-person project, minimal scope, no over-engineering. The MVP targets one flow: **PostGIS/Shapefile → WMS/WFS/WCS → optional MapCache disk cache (WMTS/TMS)**, locked to **MapServer 8.4**.

**⚠️ README.md vs CLAUDE.md 分工**: README.md 面向快速上手（技术栈、启动命令、项目结构）；CLAUDE.md 面向开发决策（架构约束、关键规则、实现细节）。两者互补，但架构决策以本文档和 `Document/技术细节.md` 为准。

**⚠️ Current implementation state**: `generate_rules.py` 和 `data/templates/*.json` 是主要已交付代码。`spike/` 目录存放预开发可行性验证脚本：

- **V1**（mappyfile 行为摸底，62 个用例，结论见 `spike/v1_result.md`）✅
- **V2**（LLM Prompt 稳定性，30 次 API 调用，结论见 `spike/v2_result.md`）✅
- **V3**（ConfigTree 前端递归渲染，280 节点、4 层嵌套、7 种控件映射，结论见 `spike/v3_result.md`）✅

三个验证全部通过 → **Go 决策**（`spike/feasibility_report.md`）。`backend/`, `frontend/`, `electron/`, `tests/` 目录待脚手架搭建。

**V2 关键结论**（影响 LLMOutput / PromptBuilder 实现）：
- JSON 可解析率 **93.3%**（≥90% 通过）；`action=update`（参数修改）场景 **100%** 稳定
- LLM 输出需经 **4 层容错解析**：`direct_json → strip_codeblock → brace_extract → json5_tolerant → fallback`
- `strip_codeblock` 挽救了 **23%** 的调用——即使 prompt 禁止，LLM 仍经常输出 ` ```json {...} ``` `
- `action=answer`（长文本解释）有 content 超长导致 JSON 截断的风险，prompt 中需限制 `content≤300` 字
- LLM 值类型常见错误：`projection` 有时输出字符串而非数组；`status` 有时输出 JSON 布尔而非 `"ON"`/`"OFF"`

详细结论记录在 [`design/llm-integration.md`](Document/design/llm-integration.md) §附录 V2。

**V3 关键结论**（影响前端组件实现）：
- 自定义递归组件（ObjectCard + FieldEditor）验证通过，280 节点、4 层嵌套无卡顿
- `FieldEditor` 内部分发 7 种 `value_type` 到对应 Naive UI 控件，无需拆分为独立原子编辑器
- STYLE/LABEL 作为独立 ObjectCard 节点渲染（非内联），验证中表现更清晰
- 详细结论记录在 [`design/data-structures.md`](Document/design/data-structures.md) §4.2 和 [`spike/v3_result.md`](SourceCode/spike/v3_result.md)

## Current Code

The only executable code in this repo is `SourceCode/scripts/generate_rules.py` — a deterministic rule merger that combines the official mappyfile JSON Schema with business overrides into a single runtime rule file.

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
```

**Key merge rules** (implemented in `generate_rules.py`):
- `value_type`: Schema enum → `"enum"`; Schema type → mapped internal type; unknown → `"string"`
- `default`: `defaults-override.json` > schema default > `None`
- `required` / `required_when` / `business_required`: from `required.json`
- `phase`: from `phase-map.json` (all fields in an object type share the same phase)
- `aliases`: from `aliases.json`
- `dependencies`: from `dependencies.json`
- `custom_allowed`: from `custom-allowed.json`
- Nested objects not in `EXPANDED_NESTED_FIELDS` are marked `editable: false`

**Schema extraction paths** (`SCHEMA_LOCATIONS` in the script): MAP → `properties`; LAYER → `properties.layers.items.properties`; CLASS → `...classes.items.properties`; STYLE → `...styles.items.properties`; LABEL → `...labels.items.properties`; WEB → `properties.web.properties`; METADATA → `properties.web.properties.metadata.properties`.

**Output structure**: `mapguide_rules.json` contains `object_types` (per-type field definitions), `flat_params` (indexed paths for PromptBuilder), `aliases`, `dependencies`, `phase_map`, `custom_allowed`, `service_metadata`.

### Available Commands

```bash
# Generate rules (run whenever templates change)
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py

# Verify output (check field counts and structure)
"/c/Users/PC/.conda/envs/gis-agent/python" -c "import json; r=json.load(open('SourceCode/data/mapguide_rules.json')); print(f'Objects: {len(r[\"object_types\"])}, Fields: {sum(len(o[\"fields\"]) for o in r[\"object_types\"].values())}')"

# Run V1 validation spike
"/c/Users/PC/.conda/envs/gis-agent/python" SourceCode/spike/v1_mappyfile_validate.py
```

Commands for pytest, uvicorn, npm, and PyInstaller are in the Planned Commands section below.

## Python Environment

All Python work **must** use the `gis-agent` conda environment. `conda activate` does not work in this bash shell; always invoke Python by full path.

```bash
# Python executable
"/c/Users/PC/.conda/envs/gis-agent/python" --version   # 3.11.15

# Package installer (when needed)
"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install <pkg>
```

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

## Design Blueprint

The architecture and class interfaces for the full application are fully specified in `Document/技术细节.md` §2–§7. Use that as the implementation blueprint. Below is a high-level summary of the target architecture.

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
  ├─ Mapfile generator: mappyfile.create() → fill → validate → dumps()
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
qa_result WS message → frontend
```

### Critical Rules

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
- **Focus change clears QA**: Switching focus parameter resets the QA message history (but preserves initial intent). Round counter shown in UI resets to 0.

## Available Commands

### Now (generate_rules + spikes)

```bash
cd SourceCode

# Generate rules (run whenever templates change)
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py

# Verify output
"/c/Users/PC/.conda/envs/gis-agent/python" -c "import json; r=json.load(open('data/mapguide_rules.json')); print(f'Objects: {len(r[\"object_types\"])}, Fields: {sum(len(o[\"fields\"]) for o in r[\"object_types\"].values())}')"

# Run V1 validation spike
"/c/Users/PC/.conda/envs/gis-agent/python" spike/v1_mappyfile_validate.py

# Run V2 LLM stability spike (requires config/config.json with API key)
"/c/Users/PC/.conda/envs/gis-agent/python" spike/v2_llm_prompt_stability.py
```

### After scaffolding (backend/frontend/electron)

### Backend (Python)

```bash
cd SourceCode/backend

# Start dev server
"/c/Users/PC/.conda/envs/gis-agent/python" -m uvicorn main:app --port 8765 --reload

# Install dependencies
"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install -r requirements.txt
```

**pytest must be run from `SourceCode/`** because tests live under `SourceCode/tests/unit/`:

```bash
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/unit/test_xxx.py -v
"/c/Users/PC/.conda/envs/gis-agent/python" -m pytest tests/ -v
```

### Frontend (Vue)

```bash
cd SourceCode/frontend

# Dev server
npm run dev

# Production build
npm run build
```

### Electron (Development Mode)

```bash
cd SourceCode

# Requires backend (port 8765) and frontend dev server already running
npm run electron:dev
```

### Production Packaging

```bash
# Step 1: Python backend → standalone exe
cd SourceCode/backend
"/c/Users/PC/.conda/envs/gis-agent/python" -m PyInstaller build/pyinstaller.spec

# Step 2: Vue frontend → static bundle
cd SourceCode/frontend
npm run build

# Step 3: Electron → Windows installer
cd SourceCode
npm run electron:build
# Output: dist/MapGuide-Setup-x.x.x.exe
```

## Key Technical Decisions

### Template Resources

Rules come from two layers:
1. `mapfile-schema-8-4.json` — official mappyfile schema (types, enums, defaults)
2. `data/templates/*.json` — business overrides (aliases, required, phase map, defaults, dependencies, custom-property whitelist, object field supplements)

`generate_rules.py` deterministically merges these into `data/mapguide_rules.json`. At runtime, `TemplateMapper` only loads `mapguide_rules.json`.

Supported object types: MAP, LAYER, CLASS, STYLE, **LABEL**, WEB, METADATA, CACHE. LABEL is nested under CLASS (sibling to STYLE) and uses the style phase color.

### LLM Integration (anthropic SDK)

- `LLMClient` wraps `anthropic.Anthropic` with configurable `base_url`.
- `chat()` for structured JSON output (`temperature=0.1`, exponential backoff retry 3×).
- **Single Prompt**: `PromptBuilder` assembles one Jinja2 template (`_framework.j2`) + runtime session context.
- Token budget: ~1500 tokens total (L0-L5), recent QA history capped at 4-6 rounds.
- **LLM boundary**: The LLM only understands natural language and outputs raw parameter values or flat path-based updates (e.g. `layers.0.connectiontype`). All alias conversion, type conversion, validation, and default-filling is handled by backend code.
- **Provider lock**: Only Anthropic Claude is supported. LLMClient encapsulates the SDK; no raw API exposure to upper layers.

### Validation Pipeline

Validation happens after every parameter change:

1. **Alias resolution**: `TemplateMapper.resolve_alias()` converts user-friendly terms.
2. **Type conversion**: Pydantic validates types, enums, ranges.
3. **Semantic validation**: `dependencies.json` drives conditional required, mutually exclusive, and derived-value rules.
4. **mappyfile syntax**: `mappyfile.validate(mf, version=8.4)` validates the assembled Mapfile.

Layers 1-3 run on every field blur. Layer 4 only runs on add/remove node, manual validate, and export.

### MapCache Generator/Validator

`backend/mapcache/` will contain two self-built components that are **peers to `mappyfile`**:
- `MapCacheGenerator` — renders `mapcache.xml` from `mapcache.xml.j2` + session params
- `MapCacheValidator` — validates generated XML against MapCache 1.16.0 rules without requiring MapCache installation

Both are core infrastructure and need unit test coverage.

### Mapfile Generation

Use mappyfile's native object flow:

```python
mf = mappyfile.create("map")
# fill from session.params
errors = mappyfile.validate(mf, version=8.4)  # pass float, not str
output = mappyfile.dumps(mf)
```

**Constraints**: `version` must be `float` (`8.4`), not `str`. `PROJECTION` must be an array `["init=epsg:3857"]`, not a string.

### ConfigTree.to_mappyfile_dict() — Serialization Rules

`ConfigTree.to_mappyfile_dict()` performs 7 mandatory transforms before handing data to mappyfile. These rules come from V1 validation (`spike/v1_result.md`) against `mappyfile==1.1.1`:

| # | Transform | Trigger | Why |
|---|-----------|---------|-----|
| 1 | `_custom` expansion | `"_custom" in dict` | mappyfile rejects unknown keys; custom props must be hoisted |
| 2 | `cache` strip | `key == "cache"` | `cache` is not a Mapfile object; MapCache XML generated separately |
| 3 | Array wrap | `key in {layers,classes,styles,labels}` and `isinstance(v, dict)` | mappyfile requires these to be lists |
| 4 | Enum-bool conversion | `field_key in {"status"}` and `isinstance(v, bool)` | string-enum fields (e.g. `status`) reject Python bool; boolean-type fields (e.g. `LABEL.antialias`) accept it |
| 5 | PROJECTION array guard | `key == "projection"` | must remain a list |
| 6 | Extent array guard | `key == "extent"` | must remain a 4-element list |
| 7 | Color RGB array guard | `value_type == "color"` | must remain `[R, G, B]` |

**Critical V1 findings**:
- mappyfile `dumps()` never throws (62/62 test cases); `validate()` is the strict gate
- `validate()` **does NOT check** `MAP.name` or `LAYER.name` as required → must rely on L3 semantic validation
- `validate()` rejects **any** schema-external field with `does not match any of the regexes` → L4 must filter these false positives (custom props + `object-fields.json` fields)
- Enum values are **case-insensitive** (`postgis`/`POSTGIS` both pass)

### ConfigTree Design

- `ConfigSession.params` is the **single source of truth**: a mappyfile-compatible dict.
- `ConfigTree` wraps it with `TreeNode`/`TreeLeaf` for UI rendering and custom properties.
- Custom properties are stored under `_custom` per object and expanded during serialization.
- LLM updates use **flat path addressing** (`layers.0.connectiontype`) — stable identifiers that do not change when tree structure changes.

**Service type filtering in ConfigTree**: ConfigTree receives `service_types: list[str]` at construction time. METADATA field visibility follows prefix rules:
- `ows_*` — always visible (general prefix shared by all OGC services)
- `wms_*` / `wfs_*` / `wcs_*` — visible only when their service is in `service_types`
- `gml_*` — lives under **LAYER.METADATA**, visible only when WFS is enabled
- Hidden field values are retained in `params`; filtering is purely a UI concern

**Internal node filtering on export**: `to_mappyfile_dict()` does two critical transforms before handing data to mappyfile:
1. **Skip `cache`** — The `cache` node holds MapCache config (type, base, expires, wmts_enabled, tms_enabled). It is not a Mapfile standard object; MapCache XML is generated separately by `MapCacheGenerator` via Jinja2.
2. **Expand `_custom`** — Custom properties are stored as `_custom: {key: {value, type, desc}}` per object. During serialization the container is removed and inner keys are promoted to the parent dict.

Directly calling `mappyfile.dumps(session.params)` will fail because mappyfile does not recognize the `cache` key. Always go through `tree.to_mappyfile_dict()`.

### Frontend UI Specification

The v2 UI design is specified in `Document/技术细节.md` §4/§11/§12 and visualized in `Document/UX/ui-prototype-interactive-v2.html`. Key constraints:

- **Two-column layout**: left `ConfigTree` (55%), right `QAPanel` (45%)
- **Inline editing**: each leaf uses a control mapped from `FieldDescriptor.value_type`
- **Focus mechanism**: clicking a tree node sets `focus_param` (flat path like `layers.0.name`), injected into the LLM prompt
- **Phase color badges**: datasource=blue `#2563eb`, style=orange `#ea580c`, service=green `#16a34a`, cache=purple `#9333ea`
- **Show-mode toggle**: "全部 / 仅必填" filters optional/default fields
- **Custom properties**: modal dialog for key + description + type; rendered with `✎` indicator
- **Legend bar**: top of ConfigTree shows `📋 图例：* 必填 · D 默认值 · ○ 可选 · → 推导 · ✎ 自定义`
- **QA round counter**: displayed in QAPanel header; resets to 0 on focus change
- **Reset / New Task** button: confirm dialog, then full session reset
- **No history persistence**: in-memory only
- **Responsive breakpoints**: ≤900px collapses QAPanel; ≤600px uses bottom input bar

## Documentation References

| File | Purpose |
|------|---------|
| `Document/需求输入.md` | High-level requirements: MVP scope, UX layout, interaction scenarios, validation/export rules |
| `Document/技术细节.md` | **总览索引**（已拆分）。设计前提 + 模块文档索引 |
| `Document/design/template-system.md` | Template resources, generate_rules.py merge logic, TemplateMapper, FieldDescriptor |
| `Document/design/data-structures.md` | ConfigSession, ConfigTree, TreeNode/TreeLeaf, flat path addressing |
| `Document/design/validation.md` | 4-layer validation strategy, mappyfile false-positive filtering |
| `Document/design/core-services.md` | Architecture overview, ValidationPipeline, ExportService, ImportService, class directory |
| `Document/design/llm-integration.md` | DialogueHistory, Prompt L0-L5 context, QAService, LLMClient, LLMOutput parsing, **V2 spike conclusions** |
| `Document/design/interaction-flows.md` | 6 interaction scenario data flows |
| `Document/design/frontend-backend-contract.md` | WebSocket message types, communication constraints |
| `Document/design/conventions.md` | Tech stack, directory structure, dev commands, code constraints, debugging |
| `Document/模板说明.md` | Template resource reference for GIS professionals: how to modify `data/templates/*.json` |
| `Document/UX/ui-prototype-interactive-v2.html` | Interactive v2 UI prototype |
| `Document/design/architecture.html` | Module architecture diagram (6 views) |
| `Document/design/dataflow-6-scenes.html` | Interactive data flow diagrams |
| `Document/核心难点验证计划.md` | Pre-development feasibility spikes (V1/V2/V3) |
| `spike/v1_result.md` | V1 conclusions: mappyfile validate() behavior, to_mappyfile_dict() 7 mandatory transforms |
| `spike/v2_result.md` | V2 conclusions: LLM JSON output stability, graceful degradation patterns |
| `spike/v3_result.md` | V3 conclusions: ConfigTree recursive rendering, 280-node perf, 7 value_type controls |
| `spike/feasibility_report.md` | Go/No-go decision: all 3 spikes passed |
| `Document/design/implementation-progress.md` | Remaining modules, difficulty heatmap, time estimate (5-6 weeks) |

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
- **`data/schemas/` removed**: the root-level `mapfile-schema-8-4.json` and `schemas/` directory were cleaned up; the canonical schema now lives in `data/templates/mapfile-schema-8-4.json`.
- **Color format**: RGB arrays `[0, 0, 255]` everywhere. No hex conversion.
- **Testing approach**: TDD. Unit tests for backend/core/ and backend/llm/. Integration tests for generate_rules.py output + LLM mock end-to-end.

**Constraints**: `version` must be `float` (`8.4`), not `str`. `PROJECTION` must be an array `["init=epsg:3857"]`, not a string.
