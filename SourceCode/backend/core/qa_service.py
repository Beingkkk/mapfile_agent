"""QAService — orchestrate the LLM question-answering pipeline.

DC-053  plan-platform §3

6-step pipeline:
    1. Record user message in DialogueHistory
    2. Build prompt via PromptBuilder (L0–L5)
    3. Call LLM via LLMClient
    4. Parse response via LLMOutput
    5. Apply updates via UpdateResolver + ConfigTree + ValidationPipeline
    6. Record bot message in DialogueHistory
"""

from __future__ import annotations

from typing import Any

from config_tree import ConfigTree
from history import DialogueHistory
from template_mapper import TemplateMapper
from validation import ValidationPipeline, ValidationResult

# LLM modules (imported at runtime to avoid circular deps in tests)
from prompt_builder import PromptBuilder
from llm_client import LLMClient
from llm_output import LLMOutput, ParsedOutput
from update_resolver import UpdateResolver


class QAService:
    """Glue layer: assembles LLM chain with session state and validation."""

    def __init__(
        self,
        session,  # ConfigSession (loosely typed to avoid circular import)
        pipeline: ValidationPipeline,
        mapper: TemplateMapper,
        client: LLMClient,
        builder: PromptBuilder,
    ) -> None:
        self.session = session
        self.pipeline = pipeline
        self.mapper = mapper
        self.client = client
        self.builder = builder
        self.resolver = UpdateResolver()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def answer(self, question: str) -> dict[str, Any]:
        """Run the full 6-step QA pipeline.

        Returns:
            {
                "action": str,           # answer | update | question
                "updates": list[dict],   # applied parameter updates
                "answer": str,           # natural language response
                "validation_state": str, # idle | checking | pass | fail
                "errors": list[dict],    # validation errors (if any)
            }
        """
        # 1. Record user message
        self.session.history.add_message("user", question)

        # 2. Build prompt
        prompt = self._build_prompt()

        # 3. Call LLM
        raw = self.client.chat(prompt)

        # 4. Parse response
        parsed: ParsedOutput = LLMOutput.parse(raw)

        # 5. Apply updates (if action == "update")
        applied_updates: list[dict] = []
        if parsed.action == "update" and parsed.params_update:
            for update in parsed.params_update:
                resolved = self.resolver.resolve(update, self.mapper)
                applied_updates.append(resolved)

            # Batch apply all updates at once (avoid redundant tree rebuilds)
            self.session.apply_llm_updates(applied_updates)

            # Validate after updates
            result = self.pipeline.validate_tree(
                self.session.tree, self.session.service_types
            )
            self.session.validation_state = result.state
            self.session.validation_errors = result.errors

        # 6. Record bot message
        self.session.history.add_message("bot", parsed.question)

        return {
            "action": parsed.action,
            "updates": applied_updates,
            "answer": parsed.question,
            "validation_state": self.session.validation_state,
            "errors": self.session.validation_errors,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Prompt construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_prompt(self) -> str:
        """Assemble L0–L5 context for the LLM prompt."""
        intent = getattr(self.session.history, "_initial_intent", None) or ""
        focus = self.session.focus_param

        # Map snapshot: lightweight YAML-like dump of params
        map_snapshot = self._build_map_snapshot()

        # Context summary: focused on current object type
        context_summary = self._build_context_summary(focus)

        # Recent messages from history
        recent = self.session.history.to_prompt_context()

        return self.builder.render(
            intent=intent,
            map_snapshot=map_snapshot,
            focus_param=focus,
            context_summary=context_summary,
            validation_errors=self.session.validation_errors,
            recent_messages=recent,
        )

    def _build_map_snapshot(self) -> str:
        """Generate a concise text snapshot of current map params."""
        params = self.session.params
        lines: list[str] = []

        def _dump(obj: Any, indent: int = 0) -> None:
            prefix = "  " * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.startswith("_") or k == "__type__":
                        continue
                    if v is None:
                        continue
                    if isinstance(v, (dict, list)):
                        lines.append(f"{prefix}{k}:")
                        _dump(v, indent + 1)
                    else:
                        lines.append(f"{prefix}{k}: {v}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        lines.append(f"{prefix}[{i}]:")
                        _dump(item, indent + 1)
                    else:
                        lines.append(f"{prefix}[{i}]: {item}")

        _dump(params)
        return "\n".join(lines) if lines else "(empty map)"

    def _build_context_summary(self, focus_param: str | None) -> str:
        """Generate a focused context summary for the LLM."""
        if focus_param is None:
            # No focus — return MAP-level summary
            return self.mapper.get_llm_context_summary("MAP")

        # Infer object type from focus path
        object_type = self._infer_object_type_from_path(focus_param)
        return self.mapper.get_llm_context_summary(object_type)

    @staticmethod
    def _infer_object_type_from_path(path: str) -> str:
        """Infer object type from a flat path."""
        type_map = {
            "layers": "LAYER",
            "classes": "CLASS",
            "styles": "STYLE",
            "labels": "LABEL",
            "web": "WEB",
            "metadata": "METADATA",
            "cache": "CACHE",
        }
        parts = path.split(".")
        for part in reversed(parts):
            if part in type_map:
                return type_map[part]
        return "MAP"
