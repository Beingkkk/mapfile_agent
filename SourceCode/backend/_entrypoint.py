"""PyInstaller entry point for MapGuide backend.

This script is the standalone entry point for the PyInstaller exe.
It sets up sys.path (same logic as main.py) and starts uvicorn.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ─── Path resolution (same as main.py) ─────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_CORE = _HERE / "core"
_LLM = _HERE / "llm"
_MAPCACHE = _HERE / "mapcache"
for p in (str(_HERE), str(_CORE), str(_LLM), str(_MAPCACHE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn  # noqa: E402
from main import app  # noqa: E402

# ─── Constants (mirroring main.py) ─────────────────────────────────────────
BACKEND_PORT = 18080
BACKEND_HOST = "127.0.0.1"

if __name__ == "__main__":
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
