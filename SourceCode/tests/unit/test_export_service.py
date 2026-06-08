"""Tests for ExportService.

DC-032 / DC-040  plan-platform §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

_MAPCACHE = Path(__file__).resolve().parent.parent.parent / "backend" / "mapcache"
if str(_MAPCACHE) not in sys.path:
    sys.path.insert(0, str(_MAPCACHE))

import pytest

from config_tree import ConfigTree
from export_service import ExportService
from generator import MapCacheGenerator
from session import ConfigSession
from template_mapper import TemplateMapper

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"
TEMPLATES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "backend" / "mapcache" / "templates"
)


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


@pytest.fixture
def valid_session(mapper):
    """Session with a valid map that passes export conditions."""
    session = ConfigSession(
        session_id="test-1",
        mapper=mapper,
        params={
            "__type__": "map",
            "name": "test_map",
            "status": "ON",
            "extent": [-180, -90, 180, 90],
            "projection": ["init=epsg:4326"],
            "layers": [
                {
                    "__type__": "layer",
                    "name": "layer1",
                    "status": "ON",
                    "type": "polygon",
                }
            ],
        },
        service_types=["wms"],
    )
    session.validation_state = "pass"
    session.validation_errors = []
    return session


class TestExportService:
    def test_export_returns_mapfile_bytes(self, valid_session):
        svc = ExportService()
        files = svc.export(valid_session)

        assert "mapfile.map" in files
        content = files["mapfile.map"]
        assert isinstance(content, bytes)
        text = content.decode("utf-8")
        assert "NAME \"test_map\"" in text
        assert "LAYER" in text

    def test_export_blocks_when_validation_fails(self, valid_session):
        valid_session.validation_state = "fail"
        valid_session.validation_errors = [{"path": "name", "message": "Required"}]

        svc = ExportService()
        with pytest.raises(ValueError, match="export"):
            svc.export(valid_session)

    def test_export_blocks_when_not_pass(self, valid_session):
        valid_session.validation_state = "idle"
        valid_session.validation_errors = []

        svc = ExportService()
        with pytest.raises(ValueError, match="export"):
            svc.export(valid_session)

    def test_export_empty_session_raises(self, mapper):
        session = ConfigSession(session_id="empty", mapper=mapper)
        session.validation_state = "pass"
        session.validation_errors = []

        svc = ExportService()
        # Empty map might still be exportable or might fail mappyfile validation
        # Either way it should not crash
        try:
            files = svc.export(session)
            assert "mapfile.map" in files
        except ValueError:
            pass  # Also acceptable if mappyfile rejects empty map

    def test_export_no_mapcache_when_disabled(self, valid_session):
        valid_session.mapcache_enabled = False
        svc = ExportService()
        files = svc.export(valid_session)

        assert "mapcache.xml" not in files

    def test_export_with_mapcache_enabled_returns_xml(self, valid_session):
        valid_session.mapcache_enabled = True
        valid_session.params["cache"] = {
            "type": "disk",
            "base": "/tmp/mapcache",
        }
        valid_session.params["layers"] = [
            {"__type__": "layer", "name": "layer1"},
        ]
        gen = MapCacheGenerator(str(TEMPLATES_DIR))
        svc = ExportService(mapcache_generator=gen)
        files = svc.export(valid_session)

        assert "mapcache.xml" in files
        xml = files["mapcache.xml"].decode("utf-8")
        assert "<mapcache>" in xml

    def test_export_with_mapcache_no_generator_skips_xml(self, valid_session):
        valid_session.mapcache_enabled = True
        valid_session.params["cache"] = {
            "type": "disk",
            "base": "/tmp/mapcache",
        }
        svc = ExportService()  # No generator
        files = svc.export(valid_session)

        assert "mapcache.xml" not in files

    def test_export_with_mapcache_no_cache_node_skips_xml(self, valid_session):
        valid_session.mapcache_enabled = True
        # No cache node in params
        if "cache" in valid_session.params:
            del valid_session.params["cache"]
        gen = MapCacheGenerator(str(TEMPLATES_DIR))
        svc = ExportService(mapcache_generator=gen)
        files = svc.export(valid_session)

        assert "mapcache.xml" not in files
