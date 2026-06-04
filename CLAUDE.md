# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MapGuide** is a Windows desktop application (Electron + Vue 3 + Python) that guides users through natural language conversation to generate MapServer Mapfile (`.map`) and MapCache XML (`.xml`) configurations. It uses a single-agent LLM architecture: the LLM understands user intent and fills structured parameter tables, while deterministic Python code (via `mappyfile` + Jinja2) generates the final configuration files.

**Design constraints**: single-person project, minimal scope, no over-engineering. The MVP targets one flow only: **PostGIS/Shapefile → WMS → optional MapCache disk cache**, locked to **MapServer 8.0**.

**Current implementation state**: The project is in early scaffolding phase. Only `SourceCode/config/` exists with JSON config files. The `backend/`, `frontend/`, `electron/`, and `tests/` directories are planned per the architecture docs but not yet created. The UI design reference is `Document/UX/ui-prototype-interactive.html`.

## Architecture

```
Electron Main (Node.js)
  ├─ spawns Python backend subprocess (dev: manual, prod: PyInstaller exe)
  └─ manages window lifecycle

Vue 3 Renderer (Naive UI + Pinia)
  ├─ ChatPanel: conversation with MapGuide agent
  ├─ ConfigTree: Mapfile hierarchy tree + phase color badges (MAP → LAYER → CLASS → STYLE / WEB → METADATA / MapCache)
  └─ PhaseIndicator: current config phase
      ↕ WebSocket (ws://localhost:PORT/ws)

Python Backend (FastAPI + uvicorn, gis-agent conda env)
  ├─ WebSocket endpoint: receives user messages, drives dialogue
  ├─ ConfigSession: in-memory state machine (greeting → datasource → style → service → cache → review → done)
  ├─ PromptBuilder: assembles phase-specific System Prompt from module-level constants
  ├─ LLMClient: anthropic SDK wrapper with retry, token truncation, streaming
  ├─ Validator: Pydantic semantic validation (e.g. PostGIS requires both CONNECTION and DATA)
  ├─ Mapfile generator: mappyfile.dumps() from collected params dict
  └─ MapCache generator: Jinja2 template, WMS URL/grid auto-derived from Mapfile params
```

**Critical rules**:
- The LLM never generates raw Mapfile/XML text. It outputs structured JSON (`action`, `params_update`, `question`, `next_phase`), which the backend validates, merges into `ConfigSession.params`, and feeds to `mappyfile` / Jinja2 for deterministic text generation.
- The right panel (`ConfigTree`) renders parameters as a **Mapfile hierarchy tree** with **phase color badges** (datasource=blue, style=orange, service=green, cache=purple), showing both structural归属 and collection timing.

## Project Structure

- `SourceCode/backend/` — Python FastAPI backend (planned, not yet scaffolded)
- `SourceCode/frontend/` — Vue 3 + Vite + Naive UI frontend (planned, not yet scaffolded)
- `SourceCode/electron/` — Electron main process (planned, not yet scaffolded)
- `SourceCode/config/` — LLM configuration (`config.json` gitignored, `config.json.template` is the template)
- `SourceCode/tests/` — Unit and integration tests (planned, not yet scaffolded)
- `Document/UX/ui-prototype-interactive.html` — Interactive UI prototype defining the visual design (three-column layout: left nav flow | chat dialog | right config tree)
- `Document/Resources/` — Requirements docs (`需求分析2.md`, `技术路径.md`), research materials (`mappyfile-master/`, `mapserver-8.6.3/`, `mapcache-1.16.0/`)
- `CLAUDE.local.md` — conda environment configuration

The `SourceCode/` directory is the active development workspace. There is no code at the repository root.

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

**pytest 必须从 `SourceCode/` 目录运行**（test 文件在 `SourceCode/tests/unit/` 下）：

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
pyinstaller build/pyinstaller.spec

# Step 2: Vue frontend → static bundle
cd SourceCode/frontend
npm run build

# Step 3: Electron → Windows installer
cd SourceCode
npm run electron:build
# Output: dist/MapGuide-Setup-x.x.x.exe
```

## Key Technical Decisions

### LLM Integration (anthropic SDK)

The LLM module (`SourceCode/backend/llm/`) follows the design in `F:\Developer\GISTaskAgent\Document\plan-llm.md`:
- `LLMClient` wraps `anthropic.Anthropic` with configurable `base_url` (compatible with Claude API and compatible endpoints).
- `chat()` for structured JSON output (temperature=0.1, exponential backoff retry 3×).
- `chat_stream()` for natural language streaming (no retry).
- Token budget: 8000 total, system prompt reserved 2000, FIFO truncation of old history messages.
- Prompts are **module-level string constants**, scene-isolated. Code selects the prompt by current phase; the LLM does not guess the scene.

### Phase-State Machine

`ConfigSession` is an in-memory state machine. A WebSocket connection binds to one session. Phases advance as required parameters are collected:

```
greeting → datasource → style → service → cache(optional) → review → done
```

**Phases are information-gathering topics, not Mapfile configuration order.** The Mapfile is a declarative object tree with no mandatory sequence. Each phase's collected parameters are merged into the same `session.params` dict and ultimately fed to `mappyfile.dumps()`:

| Phase | Writes to Mapfile | Skip behavior |
|-------|-------------------|---------------|
| datasource | `LAYER` (connectiontype, connection, data, type, name, projection) | **Cannot skip** |
| style | `CLASS` + `STYLE` (color, width, symbol, size...) | **Use defaults** (`DEFAULT_STYLES[type]`) |
| service | `WEB.METADATA` + `MAP.imagetype` + `OUTPUTFORMAT` | **Use defaults** (`DEFAULT_SERVICE`) |
| cache | Generates separate `mapcache.xml` | **Skip** (no XML output) |

Each phase has a dedicated System Prompt constant (`_GREETING_PROMPT`, `_DATASOURCE_PROMPT`, etc.) that only exposes parameters relevant to that phase. This minimizes LLM hallucination and context bloat.

### Validation Strategy

Validation happens **after every `params_update`** from the LLM, not at the end:
1. **Structural**: Pydantic model validation (`MapConfig`, `LayerConfig`, etc. derived from mappyfile Schema).
2. **Semantic**: cross-field rules (e.g. `connectiontype == "postgis"` requires both `connection` and `data`; point layers need `symbol` not `width`).
3. **Versional**: parameter existence check against MapServer 8.0 Schema.

Errors are injected back into the conversation history as `system` role messages, prompting the LLM to self-correct on the next turn.

### MapCache Auto-Derivation

MapCache XML parameters are **derived**, not LLM-generated:
- `wms_onlineresource` is assembled from `WEB.METADATA`
- `<grid>` is mapped from `LAYER.PROJECTION` (EPSG:3857 → GoogleMapsCompatible, EPSG:4326 → WGS84)
- The LLM only decides: cache type (disk), storage path, and optional expiry.

## Documentation References

| File | Purpose |
|------|---------|
| `Document/Resources/需求分析2.md` | V2 requirements: single-agent, guided dialogue, minimal scope |
| `Document/Resources/技术路径.md` | Architecture, technology choices, communication protocol, LLM module design |
| `Document/Resources/初步调研.md` | mappyfile research: multi-version Mapfile parsing/validation/generation |
| `Document/UX/ui-prototype-interactive.html` | Interactive UI prototype — visual design reference for the three-column layout |
| `F:\Developer\GISTaskAgent\Document\plan-llm.md` | LLM module design pattern (anthropic SDK adapter, prompt scene isolation, token management) |

## Conventions

- **Backend code** lives in `SourceCode/backend/`. Use absolute Python path from gis-agent conda env for all Python execution.
- **No persistence**: `ConfigSession` is in-memory only. "Restart" destroys and recreates the session.
- **Version locked**: MVP targets MapServer 8.0 only. Future version support is delegated to mappyfile's Schema mechanism, not custom business logic.
- **Frontend UI library**: Naive UI (not Element Plus).
- **`config.json` is gitignored**: It contains LLM API credentials. Use `config.json.template` as the reference structure.
