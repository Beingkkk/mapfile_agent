"""ConfigTree — business isolation layer over mappyfile dict.

DC-005: TreeNode/TreeLeaf  DC-006~011: ConfigTree
plan-config-tree §3.2–§3.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from template_mapper import FieldDescriptor, TemplateMapper


# ────────────────────────────────────────────────────────────────────────────
# Tree model
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class TreeNode:
    """Object node (MAP, LAYER, CLASS, STYLE, LABEL, WEB, METADATA, CACHE)."""

    id: str
    path: str
    object_type: str
    children: list[TreeNode | TreeLeaf] = field(default_factory=list)
    expanded: bool = True

    def leaves(self) -> list[TreeLeaf]:
        return [c for c in self.children if isinstance(c, TreeLeaf)]

    def nodes(self) -> list[TreeNode]:
        return [c for c in self.children if isinstance(c, TreeNode)]


@dataclass
class TreeLeaf:
    """Property leaf."""

    id: str
    path: str
    key: str
    descriptor: FieldDescriptor
    value: Any
    user_modified: bool = False
    errors: list[str] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# ConfigTree
# ────────────────────────────────────────────────────────────────────────────

# Fields that mappyfile requires to be lists.
_ARRAY_FIELDS = {"layers", "classes", "styles", "labels"}

# Fields whose enum representation must be stringified from bool.
_ENUM_BOOL_FIELDS = {"status"}

# Nested object key → mappyfile __type__ value (for dumps() expansion)
_MAPPYFILE_TYPE_MAP = {
    "web": "web",
    "metadata": "metadata",
    "layers": "layer",
    "classes": "class",
    "styles": "style",
    "labels": "label",
}


class ConfigTree:
    """Wrap a mappyfile-compatible dict with a frontend-friendly tree model."""

    def __init__(
        self,
        params: dict[str, Any],
        mapper: TemplateMapper,
        service_types: list[str] | None = None,
        *,
        import_mode: bool = False,
    ) -> None:
        self.params = params
        self.mapper = mapper
        self.service_types = service_types if service_types is not None else ["wms"]
        self.import_mode = import_mode
        self.root = self._build_tree(params, path="map", object_type="MAP")

    # ─────────────────────────────────────────────────────────────────────────
    # Construction
    # ─────────────────────────────────────────────────────────────────────────

    # Nested-object keys that should render as TreeNode, never TreeLeaf.
    _NESTED_KEYS: set[str] = {"layers", "classes", "styles", "labels", "web", "metadata", "cache"}

    def _build_tree(self, obj: dict, path: str, object_type: str) -> TreeNode:
        """Recursively turn a mappyfile dict into TreeNode + TreeLeaf."""
        node = TreeNode(id=self._make_id(path), path=path, object_type=object_type)

        # 1. Pre-defined fields (schema order, with service-type filtering)
        for field in self.mapper.list_all_fields(object_type):
            if object_type == "METADATA" and not self._is_metadata_field_visible(field):
                continue
            if object_type == "LAYER" and not self._is_layer_field_visible(field):
                continue
            # Nested objects render as TreeNode via _build_children, not TreeLeaf
            if field in self._NESTED_KEYS:
                continue
            desc = self.mapper.get_field_descriptor(object_type, field)
            if desc is None:
                desc = FieldDescriptor(key=field, value_type="string")
            # Always render schema fields so the user sees what can be edited.
            # Value = actual if set, otherwise default from rules, else None.
            # Also write defaults back into params so validation passes.
            if field in obj:
                if obj[field] is None and desc.default is not None:
                    obj[field] = desc.default
                value = obj[field]
            else:
                if not self.import_mode and desc.default is not None:
                    obj[field] = desc.default
                value = desc.default if desc.default is not None else None
            leaf = TreeLeaf(
                id=self._make_id(f"{path}.{field}"),
                path=f"{path}.{field}",
                key=field,
                descriptor=desc,
                value=value,
            )
            node.children.append(leaf)

        # 2. Custom properties (expanded from _custom)
        for field, meta in obj.get("_custom", {}).items():
            leaf = TreeLeaf(
                id=self._make_id(f"{path}.{field}"),
                path=f"{path}.{field}",
                key=field,
                descriptor=FieldDescriptor(
                    key=field,
                    value_type=meta["type"],
                    custom=True,
                    custom_desc=meta.get("desc", ""),
                ),
                value=meta["value"],
            )
            node.children.append(leaf)

        # 3. Child objects
        node.children.extend(self._build_children(obj, path, object_type))

        # 4. Unknown fields (present in params but not in schema or _custom).
        # These are usually L4 mappyfile false-positives or bad LLM updates.
        # Render them so the user can see and delete them.
        schema_fields = set(self.mapper.list_all_fields(object_type))
        custom_fields = set(obj.get("_custom", {}).keys())
        for field, value in obj.items():
            if field in schema_fields or field in custom_fields:
                continue
            if field.startswith("__") or field == "_custom":
                continue
            leaf = TreeLeaf(
                id=self._make_id(f"{path}.{field}"),
                path=f"{path}.{field}",
                key=field,
                descriptor=FieldDescriptor(
                    key=field,
                    value_type="string",
                    editable=True,
                ),
                value=value,
            )
            node.children.append(leaf)

        return node

    def _build_children(
        self, obj: dict, parent_path: str, parent_type: str
    ) -> list[TreeNode]:
        """Build child object nodes according to object type."""
        children: list[TreeNode] = []
        if parent_type == "MAP":
            if "web" in obj:
                children.append(
                    self._build_tree(obj["web"], "web", "WEB")
                )
            # Normalise layers to a list (handles transform-3 test data)
            layers = obj.get("layers", [])
            if isinstance(layers, dict):
                layers = [layers]
            for i, layer in enumerate(layers):
                if isinstance(layer, dict):
                    children.append(self._build_tree(layer, f"layers.{i}", "LAYER"))
            if "cache" in obj:
                children.append(self._build_tree(obj["cache"], "cache", "CACHE"))
        elif parent_type == "LAYER":
            if "metadata" in obj:
                children.append(
                    self._build_tree(
                        obj["metadata"], f"{parent_path}.metadata", "METADATA"
                    )
                )
            classes = obj.get("classes", [])
            if isinstance(classes, dict):
                classes = [classes]
            for i, cls in enumerate(classes):
                if isinstance(cls, dict):
                    children.append(
                        self._build_tree(cls, f"{parent_path}.classes.{i}", "CLASS")
                    )
        elif parent_type == "CLASS":
            if "metadata" in obj:
                children.append(
                    self._build_tree(
                        obj["metadata"], f"{parent_path}.metadata", "METADATA"
                    )
                )
            styles = obj.get("styles", [])
            if isinstance(styles, dict):
                styles = [styles]
            for i, style in enumerate(styles):
                if isinstance(style, dict):
                    children.append(
                        self._build_tree(style, f"{parent_path}.styles.{i}", "STYLE")
                    )
            labels = obj.get("labels", [])
            if isinstance(labels, dict):
                labels = [labels]
            for i, label in enumerate(labels):
                if isinstance(label, dict):
                    children.append(
                        self._build_tree(label, f"{parent_path}.labels.{i}", "LABEL")
                    )
        elif parent_type == "WEB":
            if "metadata" in obj:
                children.append(
                    self._build_tree(
                        obj["metadata"], f"{parent_path}.metadata", "METADATA"
                    )
                )
        return children

    def _is_metadata_field_visible(self, field: str) -> bool:
        """Filter METADATA field visibility by service type."""
        if field.startswith("ows_"):
            return True
        if field.startswith("wms_") and "wms" not in self.service_types:
            return False
        if field.startswith("wfs_") and "wfs" not in self.service_types:
            return False
        if field.startswith("wcs_") and "wcs" not in self.service_types:
            return False
        if field.startswith("gml_") and "wfs" not in self.service_types:
            return False
        return True

    def _is_layer_field_visible(self, _field: str) -> bool:
        """Filter LAYER field visibility by service type (no WFS/WCS-specific
        direct LAYER fields at this time)."""
        return True

    def auto_fill_service_defaults(self, services_added: list[str]) -> list[dict]:
        """当新增服务类型时，自动填充该服务的关键默认值。

        仅填充 service-metadata 中定义了 default 且当前 params 中不存在的字段。
        不覆盖用户已填写的值。

        Args:
            services_added: 新勾选的服务类型列表，如 ['wms', 'wfs']。

        Returns:
            实际执行的填充操作列表，每项包含 field/value/path。
        """
        filled: list[dict] = []
        svc_meta = self.mapper.get_service_metadata()
        meta_fields = svc_meta.get("metadata_fields", {})

        # Common suffixes that also have ows_* variants — skip if ows_* exists
        _COMMON_SUFFIXES = {"title", "abstract", "onlineresource",
                            "enable_request", "srs", "extent"}

        # Ensure web.metadata exists
        if "web" not in self.params:
            self.params["web"] = {"__type__": "web"}
        if "metadata" not in self.params["web"]:
            self.params["web"]["metadata"] = {}
        web_meta: dict[str, Any] = self.params["web"]["metadata"]

        for svc in services_added:
            svc_config = meta_fields.get(svc)
            if svc_config is None:
                continue
            for field_suffix, config in svc_config.items():
                if "default" not in config:
                    continue
                full_key = f"{svc}_{field_suffix}"
                # Skip if the service-specific key already exists
                if full_key in web_meta:
                    continue
                # Skip if an ows_* common variant already exists
                if field_suffix in _COMMON_SUFFIXES:
                    ows_key = f"ows_{field_suffix}"
                    if ows_key in web_meta:
                        continue
                # Fill default
                web_meta[full_key] = config["default"]
                filled.append({
                    "field": full_key,
                    "value": config["default"],
                    "path": f"web.metadata.{full_key}",
                })

        return filled

    def _make_id(self, path: str) -> str:
        return path.replace(".", "_").replace("[", "").replace("]", "")

    # ─────────────────────────────────────────────────────────────────────────
    # Serialization for frontend
    # ─────────────────────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        """Serialize the tree root to a JSON-friendly dict for the frontend."""
        return self._serialize_node(self.root)

    def _serialize_node(self, node: TreeNode) -> dict:
        """Recursively serialize a TreeNode."""
        return {
            "id": node.id,
            "path": node.path,
            "object_type": node.object_type,
            "expanded": node.expanded,
            "children": [self._serialize_child(c) for c in node.children],
        }

    def _serialize_child(self, child: TreeNode | TreeLeaf) -> dict:
        if isinstance(child, TreeNode):
            return self._serialize_node(child)
        # TreeLeaf
        desc = child.descriptor
        return {
            "id": child.id,
            "path": child.path,
            "key": child.key,
            "value": child.value,
            "value_type": desc.value_type,
            "phase": desc.phase,
            "required": desc.required,
            "required_when": desc.required_when,
            "derived": desc.derived,
            "default": desc.default,
            "enum": desc.enum,
            "custom": desc.custom,
            "custom_desc": desc.custom_desc,
            "user_modified": child.user_modified,
            "errors": child.errors,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Data access
    # ─────────────────────────────────────────────────────────────────────────

    def get_node(self, path: str) -> TreeNode | TreeLeaf | None:
        """Look up a node by flat path.

        Supports both relative paths (``"name"`` resolves against the MAP
        root) and absolute paths (``"layers.0.name"``).
        """
        # Normalise: strip leading "map." if present
        if path.startswith("map."):
            path = path[4:]
        if path in ("map", ""):
            return self.root

        # Fast path: direct key match against root children
        for child in self.root.children:
            if isinstance(child, TreeLeaf) and child.key == path:
                return child
            if isinstance(child, TreeNode) and child.path == path:
                return child

        # DFS for nested paths
        def _search(node: TreeNode) -> TreeNode | TreeLeaf | None:
            for child in node.children:
                if isinstance(child, TreeLeaf):
                    if child.path == path or child.key == path:
                        return child
                elif isinstance(child, TreeNode):
                    if child.path == path:
                        return child
                    result = _search(child)
                    if result is not None:
                        return result
            return None

        return _search(self.root)

    # ─────────────────────────────────────────────────────────────────────────
    # Data mutation
    # ─────────────────────────────────────────────────────────────────────────

    def update_value(self, path: str, value: Any, user_modified: bool = True) -> None:
        """Update a leaf value and write back to params."""
        node = self.get_node(path)
        if isinstance(node, TreeLeaf):
            node.value = value
            node.user_modified = user_modified
            self._write_to_params(path, value)
        else:
            # Field not yet in tree — write directly to params, rebuild, then flag
            self._write_to_params(path, value)
            self.root = self._build_tree(self.params, "map", "MAP")
            node = self.get_node(path)
            if isinstance(node, TreeLeaf):
                node.user_modified = user_modified

    def add_object(self, parent_path: str, object_type: str) -> TreeNode:
        """Add a new child object under the given parent."""
        parent = self._resolve_dict(parent_path)

        object_type_lower = object_type.lower()

        if object_type == "WEB":
            parent["web"] = {"__type__": object_type_lower}
        elif object_type == "CACHE":
            parent["cache"] = {"__type__": object_type_lower}
        elif object_type == "METADATA":
            parent["metadata"] = {}
        elif object_type in {"LAYER", "CLASS", "STYLE", "LABEL"}:
            list_key = self._PLURALS.get(object_type_lower, f"{object_type_lower}s")
            if list_key not in parent:
                parent[list_key] = []
            new_item: dict[str, Any] = {"__type__": object_type_lower}
            if object_type == "STYLE":
                new_item["color"] = [128, 128, 128]
            # When import_mode is active, _build_tree won't backfill defaults
            # for missing fields — pre-fill them here so new nodes are usable.
            if self.import_mode:
                fields = self.mapper.get_fields(object_type)
                for f_name, f_desc in fields.items():
                    if f_desc.default is not None and f_name not in new_item:
                        new_item[f_name] = f_desc.default
            parent[list_key].append(new_item)
        else:
            raise ValueError(f"Unsupported object type: {object_type}")

        self.root = self._build_tree(self.params, "map", "MAP")
        return self._find_added_node(parent_path, object_type)

    # object_type -> plural key used in params
    _PLURALS = {
        "layer": "layers",
        "class": "classes",
        "style": "styles",
        "label": "labels",
    }

    def _find_added_node(self, parent_path: str, object_type: str) -> TreeNode:
        """Return the last-added node of the given object type."""
        object_type_lower = object_type.lower()

        if object_type in {"WEB", "CACHE", "METADATA"}:
            if object_type == "WEB":
                return self.get_node("web")  # type: ignore[return-value]
            if object_type == "CACHE":
                return self.get_node("cache")  # type: ignore[return-value]
            if object_type == "METADATA":
                return self.get_node(f"{parent_path}.metadata")  # type: ignore[return-value]

        list_key = self._PLURALS.get(object_type_lower, f"{object_type_lower}s")
        parent = self._resolve_dict(parent_path)
        items = parent.get(list_key, [])
        if not items:
            raise RuntimeError(f"Failed to add {object_type}")
        idx = len(items) - 1

        # Build lookup path
        if parent_path in ("map", ""):
            lookup = f"{list_key}.{idx}"
        else:
            lookup = f"{parent_path}.{list_key}.{idx}"
        if lookup.startswith("map."):
            lookup = lookup[4:]

        node = self.get_node(lookup)
        if isinstance(node, TreeNode):
            return node
        raise RuntimeError(f"Cannot find added {object_type} node at {lookup}")

    def remove_object(self, path: str) -> None:
        """Remove an object node from params."""
        parts = path.split(".")
        if len(parts) < 1:
            raise KeyError(f"Cannot remove root or invalid path: {path}")

        # Navigate to the container of the last segment
        current: Any = self.params
        for part in parts[:-1]:
            if isinstance(current, dict):
                current = current[part]
            elif isinstance(current, list):
                current = current[int(part)]
            else:
                raise KeyError(f"Cannot traverse path segment '{part}' in {type(current)}")

        target = parts[-1]

        if isinstance(current, dict):
            if target in current:
                del current[target]
            else:
                raise KeyError(f"Cannot resolve path for removal: {path}")
        elif isinstance(current, list):
            idx = int(target)
            if 0 <= idx < len(current):
                current.pop(idx)
            else:
                raise KeyError(f"Index out of range: {path}")
        else:
            raise KeyError(f"Cannot resolve path for removal: {path}")

        self.root = self._build_tree(self.params, "map", "MAP")

    def add_custom_property(
        self,
        parent_path: str,
        key: str,
        value: Any,
        prop_type: str,
        desc: str = "",
    ) -> None:
        """Add a custom property stored under _custom."""
        parent = self._resolve_dict(parent_path)
        parent.setdefault("_custom", {})[key] = {
            "value": value,
            "type": prop_type,
            "desc": desc,
        }
        self.root = self._build_tree(self.params, "map", "MAP")

    # ─────────────────────────────────────────────────────────────────────────
    # Serialization — 7 mandatory transforms
    # ─────────────────────────────────────────────────────────────────────────

    def to_mappyfile_dict(self) -> dict:
        """Return a dict ready for mappyfile.dumps()."""
        first_pass = self._filter_and_expand(self.params)
        second_pass = self._post_transform(first_pass)
        return self._add_type_tags(second_pass, "")

    def _filter_and_expand(self, obj: Any) -> Any:
        """Recursively apply transforms 1–2."""
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                if v is None:
                    continue  # Transform: skip unset optional fields
                if k == "_custom":
                    for ck, cv in v.items():
                        result[ck] = self._filter_and_expand(cv["value"])
                    continue
                if k == "cache":
                    continue
                result[k] = self._filter_and_expand(v)
            return result
        if isinstance(obj, list):
            return [self._filter_and_expand(i) for i in obj]
        return obj

    def _post_transform(self, obj: Any) -> Any:
        """Second pass: transforms 3–7."""
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            for k, v in obj.items():
                processed = self._post_transform(v)
                # Transform 3: array wrap for layers/classes/styles/labels
                if k in _ARRAY_FIELDS:
                    if isinstance(processed, dict):
                        processed = [processed]
                    elif isinstance(processed, list):
                        # Defensive: filter out non-dict elements that would
                        # crash mappyfile.validate (string indices error)
                        processed = [item for item in processed if isinstance(item, dict)]
                # Transform 4: enum-bool conversion (status)
                if k in _ENUM_BOOL_FIELDS and isinstance(processed, bool):
                    processed = "ON" if processed else "OFF"
                result[k] = processed
            return result
        if isinstance(obj, list):
            return [self._post_transform(i) for i in obj]
        return obj

    # Transform 9: add __type__ to nested objects so mappyfile.dumps()
    # expands them as proper Mapfile blocks (WEB, METADATA, LAYER, etc.)
    def _add_type_tags(self, obj: Any, parent_key: str) -> Any:
        """Recursively add __type__ to nested container dicts."""
        if isinstance(obj, dict):
            result: dict[str, Any] = {}
            container_type = _MAPPYFILE_TYPE_MAP.get(parent_key, "")
            if container_type and "__type__" not in obj:
                result["__type__"] = container_type
            # Defensive: root object must always have __type__ for mappyfile
            if not parent_key and "__type__" not in obj:
                result["__type__"] = "map"
            for k, v in obj.items():
                if k == "__type__":
                    result[k] = v
                    continue
                result[k] = self._add_type_tags(v, k)
            return result
        if isinstance(obj, list):
            return [self._add_type_tags(i, parent_key) for i in obj]
        return obj

    # ─────────────────────────────────────────────────────────────────────────
    # Path helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _write_to_params(self, path: str, value: Any) -> None:
        """Write value back into self.params at the given flat path."""
        # Normalise path
        if path.startswith("map."):
            path = path[4:]

        parts = path.split(".")
        current: Any = self.params

        for i, part in enumerate(parts[:-1]):
            if isinstance(current, dict):
                if part not in current:
                    # Peek ahead: if next part is numeric, create a list
                    next_part = parts[i + 1]
                    if next_part.isdigit():
                        current[part] = []
                    else:
                        current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                idx = int(part)
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
            else:
                raise KeyError(f"Cannot traverse path segment '{part}' in {type(current)}")

        key = parts[-1]
        current[key] = value

    def _resolve_dict(self, path: str) -> dict[str, Any]:
        """Resolve a flat path to the containing dict in self.params."""
        if path in ("map", ""):
            return self.params

        if path.startswith("map."):
            path = path[4:]

        parts = path.split(".")
        current: Any = self.params

        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    # Peek ahead: if next part is numeric, create a list
                    next_idx = parts.index(part) + 1
                    if next_idx < len(parts) and parts[next_idx].isdigit():
                        current[part] = []
                    else:
                        current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                idx = int(part)
                while len(current) <= idx:
                    current.append({})
                current = current[idx]
            else:
                raise KeyError(
                    f"Cannot resolve path segment '{part}' in {type(current)}"
                )

        if not isinstance(current, dict):
            raise KeyError(f"Path '{path}' does not resolve to a dict")
        return current
