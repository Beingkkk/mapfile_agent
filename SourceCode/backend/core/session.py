"""ConfigSession — session root container.

DC-004: ConfigSession
plan-config-tree §3.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config_tree import ConfigTree
from history import DialogueHistory
from template_mapper import TemplateMapper


@dataclass
class ConfigSession:
    """Complete state container for one configuration task.  In-memory only;
    resetting destroys and recreates the session."""

    session_id: str
    mapper: TemplateMapper
    intent_message: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    tree: ConfigTree | None = None
    history: DialogueHistory = field(default_factory=DialogueHistory)
    validation_state: str = "idle"  # idle | checking | pass | fail
    validation_errors: list[dict] = field(default_factory=list)
    focus_param: str | None = None
    service_types: list[str] = field(default_factory=lambda: ["wms"])
    mapcache_enabled: bool = False
    import_mode: bool = False

    def __post_init__(self) -> None:
        if not self.params:
            # Initialise with a minimal MAP dict
            self.params = {"__type__": "map"}
        if self.tree is None:
            self.tree = ConfigTree(
                self.params, self.mapper, self.service_types,
                import_mode=self.import_mode,
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Focus management
    # ─────────────────────────────────────────────────────────────────────────

    def set_focus(self, path: str | None) -> None:
        """Switch focus parameter; resets QA round counter."""
        self.focus_param = path
        self.history.reset_on_focus_change()

    # ─────────────────────────────────────────────────────────────────────────
    # LLM updates
    # ─────────────────────────────────────────────────────────────────────────

    def apply_llm_updates(self, updates: list[dict]) -> None:
        """Apply a batch of LLM-suggested updates and rebuild the tree."""
        assert self.tree is not None
        for update in updates:
            path = update.get("path")
            value = update.get("value")
            if path is not None:
                self.tree.update_value(path, value, user_modified=False)
        # Rebuild tree so new nodes are reflected
        self.tree = ConfigTree(
            self.params, self.mapper, self.service_types,
            import_mode=self.import_mode,
        )
