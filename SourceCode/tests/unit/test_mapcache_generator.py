"""Tests for MapCacheGenerator.

DC-038  plan-platform §5.3
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
def generator():
    return MapCacheGenerator(str(TEMPLATES_DIR))


class TestMapCacheGeneratorBasics:
    def test_init_loads_template(self, generator):
        assert generator.template is not None

    def test_generate_no_cache_returns_none(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={"__type__": "map", "name": "test_map"},
        )
        result = generator.generate(session)
        assert result is None


class TestMapCacheGeneratorWithCache:
    def test_generate_with_defaults(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "cache": {
                    "type": "disk",
                    "base": "/tmp/mapcache",
                },
                "layers": [
                    {"__type__": "layer", "name": "roads"},
                ],
            },
        )
        xml = generator.generate(session)
        assert xml is not None
        assert "<mapcache>" in xml
        assert '<cache name="' in xml
        assert "disk" in xml
        assert "<source" in xml
        assert "<tileset" in xml

    def test_generate_with_full_params(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "web": {
                    "metadata": {
                        "ows_onlineresource": "http://localhost/cgi-bin/mapserv",
                    }
                },
                "cache": {
                    "type": "disk",
                    "base": "/data/mapcache",
                    "expires": 3600,
                    "wmts_enabled": True,
                    "tms_enabled": True,
                    "grid": "EPSG:3857",
                    "format": "PNG",
                    "metatile": 4,
                    "minzoom": 0,
                    "maxzoom": 18,
                },
                "layers": [
                    {"__type__": "layer", "name": "roads"},
                    {"__type__": "layer", "name": "rivers"},
                ],
            },
        )
        xml = generator.generate(session)
        assert xml is not None
        assert "<mapcache>" in xml
        assert "/data/mapcache" in xml
        assert "3600" in xml
        assert 'service type="wmts"' in xml
        assert 'service type="tms"' in xml
        assert "EPSG:3857" in xml
        assert "PNG" in xml

    def test_generate_wmts_disabled(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "cache": {
                    "type": "disk",
                    "wmts_enabled": False,
                },
                "layers": [
                    {"__type__": "layer", "name": "roads"},
                ],
            },
        )
        xml = generator.generate(session)
        assert xml is not None
        assert 'service type="wmts"' not in xml

    def test_generate_uses_layer_names(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "cache": {
                    "type": "disk",
                    "base": "/tmp/mc",
                },
                "layers": [
                    {"__type__": "layer", "name": "roads"},
                    {"__type__": "layer", "name": "rivers"},
                ],
            },
        )
        xml = generator.generate(session)
        assert xml is not None
        # Should include layer names in source params
        assert "roads" in xml
        assert "rivers" in xml

    def test_generate_uses_onlineresource(self, generator, mapper):
        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "web": {
                    "metadata": {
                        "ows_onlineresource": "http://example.com/wms",
                    }
                },
                "cache": {
                    "type": "disk",
                },
                "layers": [
                    {"__type__": "layer", "name": "layer1"},
                ],
            },
        )
        xml = generator.generate(session)
        assert xml is not None
        assert "http://example.com/wms" in xml

    def test_generate_xml_is_well_formed(self, generator, mapper):
        import xml.etree.ElementTree as ET

        session = ConfigSession(
            session_id="test",
            mapper=mapper,
            params={
                "__type__": "map",
                "name": "test_map",
                "cache": {
                    "type": "disk",
                },
                "layers": [
                    {"__type__": "layer", "name": "layer1"},
                ],
            },
        )
        xml = generator.generate(session)
        # Should be valid XML
        root = ET.fromstring(xml)
        assert root.tag == "mapcache"
