"""Tests for MapCacheValidator.

DC-039  plan-platform §5.3
"""

from __future__ import annotations

import sys
from pathlib import Path

_MAPCACHE = Path(__file__).resolve().parent.parent.parent / "backend" / "mapcache"
if str(_MAPCACHE) not in sys.path:
    sys.path.insert(0, str(_MAPCACHE))

from validator import MapCacheValidator

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mapcache>
  <source name="test" type="wms">
    <http><url>http://localhost/wms</url></http>
    <getmap><params><map>/path.map</map><layers>all</layers></params></getmap>
  </source>
  <cache name="tilecache" type="disk">
    <base>/tmp/mapcache</base>
  </cache>
  <tileset name="test">
    <source>test</source>
    <cache>tilecache</cache>
    <grid>EPSG:3857</grid>
    <format>PNG</format>
    <metatile>4</metatile>
    <expires>3600</expires>
  </tileset>
  <service type="wmts" enabled="true" />
</mapcache>
"""


class TestMapCacheValidator:
    def test_valid_xml_passes(self):
        v = MapCacheValidator()
        result = v.validate(VALID_XML)
        assert result.state == "pass"
        assert result.errors == []

    def test_malformed_xml_fails(self):
        v = MapCacheValidator()
        result = v.validate("<mapcache><unclosed>")
        assert result.state == "fail"
        assert any("xml" in e["message"].lower() for e in result.errors)

    def test_missing_source_fails(self):
        v = MapCacheValidator()
        xml = """<?xml version="1.0"?>
<mapcache>
  <cache name="c" type="disk"><base>/tmp</base></cache>
  <tileset name="t"><source>s</source><cache>c</cache></tileset>
</mapcache>
"""
        result = v.validate(xml)
        assert result.state == "fail"
        assert any("source" in e["message"].lower() for e in result.errors)

    def test_missing_cache_fails(self):
        v = MapCacheValidator()
        xml = """<?xml version="1.0"?>
<mapcache>
  <source name="s" type="wms"><http><url>http://x</url></http></source>
  <tileset name="t"><source>s</source><cache>c</cache></tileset>
</mapcache>
"""
        result = v.validate(xml)
        assert result.state == "fail"
        assert any("cache" in e["message"].lower() for e in result.errors)

    def test_missing_tileset_fails(self):
        v = MapCacheValidator()
        xml = """<?xml version="1.0"?>
<mapcache>
  <source name="s" type="wms"><http><url>http://x</url></http></source>
  <cache name="c" type="disk"><base>/tmp</base></cache>
</mapcache>
"""
        result = v.validate(xml)
        assert result.state == "fail"
        assert any("tileset" in e["message"].lower() for e in result.errors)

    def test_empty_string_fails(self):
        v = MapCacheValidator()
        result = v.validate("")
        assert result.state == "fail"

    def test_service_type_valid(self):
        v = MapCacheValidator()
        xml = VALID_XML.replace('type="wmts"', 'type="tms"')
        result = v.validate(xml)
        assert result.state == "pass"

    def test_invalid_service_type_fails(self):
        v = MapCacheValidator()
        xml = VALID_XML.replace('type="wmts"', 'type="invalid"')
        result = v.validate(xml)
        assert result.state == "fail"
        assert any("service" in e["message"].lower() for e in result.errors)
