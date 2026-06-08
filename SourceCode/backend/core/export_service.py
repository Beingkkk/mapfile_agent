"""ExportService — generate Mapfile (.map) and optional MapCache XML.

DC-032  plan-platform §3.2
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from session import ConfigSession


class ExportService:
    """Export session state to Mapfile and MapCache XML."""

    def export(self, session: "ConfigSession") -> dict[str, bytes]:
        """Export session to downloadable files.

        Returns:
            {"mapfile.map": b"...", "mapcache.xml": b"..."} (mapcache optional)

        Raises:
            ValueError: if validation does not pass.
        """
        if session.validation_state != "pass" or session.validation_errors:
            raise ValueError(
                f"Cannot export: validation_state={session.validation_state}, "
                f"errors={len(session.validation_errors)}"
            )

        import mappyfile

        tree = session.tree
        assert tree is not None

        mf_dict = tree.to_mappyfile_dict()
        mapfile_text = mappyfile.dumps(mf_dict)

        result: dict[str, bytes] = {
            "mapfile.map": mapfile_text.encode("utf-8"),
        }

        # TODO: MapCache XML generation (Phase 4)
        # if session.mapcache_enabled:
        #     xml = self._generate_mapcache(session)
        #     result["mapcache.xml"] = xml.encode("utf-8")

        return result
