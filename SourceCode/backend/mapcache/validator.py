"""MapCacheValidator — basic XML structure validation without MapCache install.

DC-039  plan-platform §3.6
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    state: str = "pass"  # pass | fail
    errors: list[dict] = field(default_factory=list)


class MapCacheValidator:
    """Validate MapCache XML structure."""

    REQUIRED_ELEMENTS = {"source", "cache", "tileset"}
    VALID_SERVICE_TYPES = {"wmts", "tms", "wms", "kml", "gmaps", "ve", "demo"}

    def validate(self, xml_text: str) -> ValidationResult:
        """Validate MapCache XML and return result."""
        if not xml_text.strip():
            return ValidationResult(
                state="fail",
                errors=[{"message": "Empty XML", "level": "error"}],
            )

        try:
            import xml.etree.ElementTree as ET

            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return ValidationResult(
                state="fail",
                errors=[{"message": f"XML parse error: {exc}", "level": "error"}],
            )

        errors: list[dict] = []

        # Check root element
        if root.tag != "mapcache":
            errors.append({
                "message": f"Root element must be 'mapcache', got '{root.tag}'",
                "level": "error",
            })

        # Check required elements
        found_tags = {child.tag for child in root}
        for required in self.REQUIRED_ELEMENTS:
            if required not in found_tags:
                errors.append({
                    "message": f"Missing required element: <{required}>",
                    "level": "error",
                })

        # Validate service types
        for service in root.findall("service"):
            svc_type = service.get("type", "")
            if svc_type and svc_type not in self.VALID_SERVICE_TYPES:
                errors.append({
                    "message": f"Invalid service type: '{svc_type}'",
                    "level": "error",
                })

        if errors:
            return ValidationResult(state="fail", errors=errors)

        return ValidationResult(state="pass", errors=[])
