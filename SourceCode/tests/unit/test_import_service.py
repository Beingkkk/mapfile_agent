"""Tests for ImportService.

DC-033  plan-platform §5.1
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_CORE = Path(__file__).resolve().parent.parent.parent / "backend" / "core"
if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

import pytest

from import_service import ImportService
from template_mapper import TemplateMapper

RULES_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mapguide_rules.json"


@pytest.fixture
def mapper():
    return TemplateMapper(str(RULES_PATH))


@pytest.fixture
def valid_mapfile():
    return '''MAP
        NAME "test_map"
        STATUS ON
        EXTENT -180 -90 180 90
        PROJECTION
            "init=epsg:4326"
        END
        LAYER
            NAME "layer1"
            STATUS ON
            TYPE POLYGON
        END
    END'''


class TestImportService:
    def test_import_valid_mapfile(self, mapper, valid_mapfile):
        svc = ImportService(mapper)
        session, result = svc.import_mapfile("import-1", valid_mapfile)

        assert session.session_id == "import-1"
        assert session.params["__type__"] == "map"
        assert session.params["name"] == "test_map"
        assert "layers" in session.params
        assert len(session.params["layers"]) == 1
        assert session.tree is not None

    def test_import_invalid_mapfile_raises(self, mapper):
        svc = ImportService(mapper)
        bad_content = "THIS IS NOT A MAPFILE"

        with pytest.raises((Exception, ValueError)):
            svc.import_mapfile("import-2", bad_content)

    def test_import_preserves_unknown_fields(self, mapper):
        mapfile = '''MAP
            NAME "test"
            STATUS ON
            EXTENT -180 -90 180 90
            my_custom_key "custom_value"
            LAYER
                NAME "l1"
                STATUS ON
                TYPE POLYGON
            END
        END'''
        svc = ImportService(mapper)
        session, _ = svc.import_mapfile("import-3", mapfile)

        # Unknown fields should be preserved in params
        assert "my_custom_key" in session.params
        assert session.params["my_custom_key"] == "custom_value"

    def test_import_returns_validation_result(self, mapper, valid_mapfile):
        svc = ImportService(mapper)
        session, result = svc.import_mapfile("import-4", valid_mapfile)

        from validation import ValidationResult
        assert isinstance(result, ValidationResult)
