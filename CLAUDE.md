# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MapGuide** is a Windows desktop application (Electron + Vue 3 + Python) for interactively editing MapServer Mapfile (`.map`) and MapCache XML (`.xml`) configurations. The UX is **config-tree-first**: the left panel is an interactive `ConfigTree` where users add layers, edit parameters inline, and trigger validation; the right panel is a Q&A assistant where an LLM answers questions about parameters, explains errors, and suggests configurations.

**Design constraints**: single-person project, minimal scope, no over-engineering. The MVP targets one flow: **PostGIS/Shapefile → WMS/WFS/WCS → optional MapCache disk cache (WMTS/TMS)**, locked to **MapServer 8.4**.

**⚠️ README.md is outdated** — it describes an older phase-state-machine architecture that has been abandoned. The current design is documented in this file and in `Document/技术细节.md`. Do not rely on README.md for architecture decisions.

## Current Implementation State

**Pre-built and working:**
- `SourceCode/scripts/generate_rules.py` — deterministic rule merger (schema + templates → mapguide_rules.json)
- `SourceCode/data/templates/*.json` — 9 template resource files (including `service-metadata.json` for WMS/WFS/WCS parameter filtering)
- `SourceCode/data/mapguide_rules.json` — generated runtime rule file
- `SourceCode/data/init_session_intent.json` — default user intent with 3 scenarios
- `SourceCode/config/config.json.template` — LLM API config template

**Not yet scaffolded:**
- `SourceCode/backend/core/` (ConfigSession, ConfigTree, TemplateMapper, ValidationPipeline, QAService, ExportService)
- `SourceCode/backend/llm/` (PromptBuilder, LLMClient, LLMOutput, UpdateResolver)
- `SourceCode/backend/main.py` (FastAPI + WebSocket routes)
- `SourceCode/backend/mapcache/` — directory planned but empty; generator/validator code not yet written
- `SourceCode/frontend/` (Vue 3 + Vite + Naive UI)
- `SourceCode/electron/` (Electron main process)
- `SourceCode/tests/` (unit + integration tests)

The architecture and class interfaces are fully specified in `Document/技术细节.md` §2–§7. Use that as the implementation blueprint.

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
  │     ├──▶ ConfigTree: business view over params, computes line numbers, supports custom props,
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
ConfigTree.rebuild_line_map()
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
    ├──▶ UpdateResolver: line → path
    ├──▶ ConfigTree.apply_updates()
    ├──▶ ValidationPipeline.validate_tree()
    └──▶ ConfigTree.rebuild_line_map()
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
- **Line numbers**: Computed internally by `preview_mapfile()` for LLM positioning; never displayed in UI. Front-end shows flat paths (e.g. `LAYER[0].connectiontype`).
- **Focus change clears QA**: Switching focus parameter resets the QA message history (but preserves initial intent). Round counter shown in UI resets to 0.

## Python Environment

All Python work **must** use the `gis-agent` conda environment. `conda activate` does not work in this bash shell; always invoke Python by full path.

```bash
# Python executable
"/c/Users/PC/.conda/envs/gis-agent/python" --version   # 3.11.15

# Package installer (when needed)
"/c/Users/PC/.conda/envs/gis-agent/python" -m pip install <pkg>
```

## Development Commands

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

### Generate Rules

```bash
cd SourceCode
"/c/Users/PC/.conda/envs/gis-agent/python" scripts/generate_rules.py
```

Run this whenever you modify files in `data/templates/`.

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
- **LLM boundary**: The LLM only understands natural language and outputs raw parameter values or `line`-based updates. All alias conversion, type conversion, validation, and default-filling is handled by backend code.
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

### ConfigTree Design

- `ConfigSession.params` is the **single source of truth**: a mappyfile-compatible dict.
- `ConfigTree` wraps it with `TreeNode`/`TreeLeaf` for UI rendering, line numbers, and custom properties.
- Custom properties are stored under `_custom` per object and expanded during serialization.
- Line numbers are computed by `ConfigTree.rebuild_line_map()` and must match the final `.map` output.

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
- **Focus mechanism**: clicking a tree node sets `focus_param` + `focus_lines`, injected into the LLM prompt
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
| `Document/技术细节.md` | **Primary technical design**: template resources, class design, ConfigTree, QAService, ValidationPipeline, interaction flows, WebSocket contracts, tech stack, conventions |
| `Document/模板说明.md` | Template resource reference for GIS professionals: how to modify `data/templates/*.json`, parameter lists verified against MapServer 8.6.3 source code |
| `Document/UX/ui-prototype-interactive-v2.html` | Interactive v2 UI prototype — open in browser to see target design |
| `Document/design/architecture.html` | Module architecture diagram with 6 views (runtime, class relations, component tree, data flows, dependencies, decision cheat-sheet) |

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
