"""ImportService — parse Mapfile text into ConfigSession.

DC-033  plan-platform §3.3
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from config_tree import ConfigTree
from session import ConfigSession
from validation import ValidationPipeline, ValidationResult

if TYPE_CHECKING:
    from template_mapper import TemplateMapper


class ImportService:
    """Parse a Mapfile (.map) text into a fresh ConfigSession."""

    def __init__(self, mapper: "TemplateMapper") -> None:
        self.mapper = mapper
        self.validator = ValidationPipeline(mapper)

    def import_mapfile(
        self, session_id: str, content: str
    ) -> tuple[ConfigSession, ValidationResult]:
        """Parse Mapfile text and return a new validated session.

        Args:
            session_id: New session identifier.
            content: Raw Mapfile text (UTF-8).

        Returns:
            (ConfigSession, ValidationResult) — the new session and its
            full 4-layer validation outcome.

        Raises:
            Exception: if ``mappyfile.loads()`` fails to parse.
        """
        import mappyfile

        parsed = mappyfile.loads(content)
        # Ensure __type__ marker exists
        if isinstance(parsed, dict):
            parsed["__type__"] = parsed.get("__type__", "map")

        session = ConfigSession(
            session_id=session_id,
            mapper=self.mapper,
            params=parsed,
            import_mode=True,
        )

        # Run full validation
        result = self.validator.validate_tree(session.tree, session.service_types)
        session.validation_state = result.state
        session.validation_errors = result.errors

        return session, result
