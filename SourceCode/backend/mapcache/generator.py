"""MapCacheGenerator — produce mapcache.xml from session params.

DC-038  plan-platform §3.6
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from session import ConfigSession


class MapCacheGenerator:
    """Generate MapCache XML configuration from session state."""

    def __init__(self, templates_dir: str) -> None:
        self.templates_dir = Path(templates_dir)
        self.template = self._load_template()

    def _load_template(self):
        """Load the Jinja2 mapcache template."""
        try:
            from jinja2 import Environment, FileSystemLoader
        except ImportError:
            return None

        env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        return env.get_template("mapcache.xml.j2")

    def generate(self, session: "ConfigSession") -> str | None:
        """Generate mapcache.xml text from session.

        Returns None if session has no cache node.
        """
        cache = session.params.get("cache")
        if not cache:
            return None

        layers = session.params.get("layers", [])
        if isinstance(layers, dict):
            layers = [layers]
        layer_names = [l.get("name", "layer") for l in layers if isinstance(l, dict)]
        layers_str = ",".join(layer_names) if layer_names else "all"

        # Derive WMS URL from WEB.METADATA.ows_onlineresource
        wms_url = self._derive_wms_url(session.params)
        mapfile_path = "/path/to/mapfile.map"  # Placeholder; real path unknown at generation time

        ctx = {
            "source_name": session.params.get("name", "mapsource"),
            "wms_url": wms_url,
            "mapfile_path": mapfile_path,
            "layers": layers_str,
            "cache_name": "tilecache",
            "cache_type": cache.get("type", "disk"),
            "cache_base": cache.get("base", "/tmp/mapcache"),
            "tileset_name": session.params.get("name", "tileset"),
            "grid": cache.get("grid", "EPSG:3857"),
            "format": cache.get("format", "PNG"),
            "metatile": cache.get("metatile", 4),
            "expires": cache.get("expires", 3600),
            "minzoom": cache.get("minzoom", 0),
            "maxzoom": cache.get("maxzoom", 18),
            "wmts_enabled": cache.get("wmts_enabled", False),
            "tms_enabled": cache.get("tms_enabled", False),
        }

        return self.template.render(**ctx)

    @staticmethod
    def _derive_wms_url(params: dict[str, Any]) -> str:
        """Extract WMS endpoint URL from params."""
        web = params.get("web")
        if isinstance(web, dict):
            meta = web.get("metadata")
            if isinstance(meta, dict):
                url = meta.get("ows_onlineresource")
                if url:
                    return str(url)
        # Default placeholder
        return "http://localhost/cgi-bin/mapserv"
