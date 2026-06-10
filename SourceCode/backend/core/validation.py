"""ValidationPipeline — 4-layer validation system.

DC-012~016  plan-validation §3
L1: alias resolution | L2: type check | L3: semantic | L4: mappyfile syntax
"""

from __future__ import annotations

import ast
import json
import operator
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config_tree import ConfigTree, TreeLeaf, TreeNode
from template_mapper import FieldDescriptor, TemplateMapper


# ────────────────────────────────────────────────────────────────────────────
# DC-012: ValidationResult
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """Outcome of a validation run."""

    state: str = "pass"  # pass | fail
    errors: list[dict] = field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# DC-013~016: ValidationPipeline
# ────────────────────────────────────────────────────────────────────────────


class ValidationPipeline:
    """4-layer validation: alias → type → semantic → mappyfile."""

    def __init__(self, mapper: TemplateMapper) -> None:
        self.mapper = mapper
        # Load dependencies for L3 semantic checks
        rules_dir = Path(__file__).resolve().parent.parent.parent / "data" / "templates"
        deps_path = rules_dir / "dependencies.json"
        self._dependencies: list[dict] = []
        if deps_path.exists():
            with open(deps_path, encoding="utf-8") as f:
                data = json.load(f)
                self._dependencies = data.get("edges", [])

        # Load custom-allowed for L4 false-positive filtering
        custom_path = rules_dir / "custom-allowed.json"
        self._custom_allowed: dict[str, bool] = {}
        if custom_path.exists():
            with open(custom_path, encoding="utf-8") as f:
                data = json.load(f)
                self._custom_allowed = {
                    k: v for k, v in data.items() if not k.startswith("_")
                }

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def validate_field(
        self,
        tree: ConfigTree,
        path: str,
        service_types: list[str],
        full: bool = False,
    ) -> list[dict]:
        """Validate a single field (L1–L3; full=True adds L4).

        Returns list of error dicts: [{path, message, level}].
        """
        node = tree.get_node(path)
        if not isinstance(node, TreeLeaf):
            return []

        errors: list[dict] = []

        # L1: alias resolution (silent, may mutate leaf.value)
        self._try_resolve_alias(node)

        # L2: type check
        errors.extend(self._check_type(node))

        # L3: semantic check
        errors.extend(self._check_semantic(tree, node, service_types))

        # L4: mappyfile syntax (only when full=True)
        if full:
            errors.extend(self._check_mappyfile(tree))

        # De-duplicate by (path, message)
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for e in errors:
            key = (e.get("path", ""), e.get("message", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        # Attach errors to leaf for UI — only those matching this leaf's path
        # so the user sees errors on the field they actually edited.
        node.errors = [e["message"] for e in deduped if e.get("path") == path]
        return deduped

    def validate_tree(
        self, tree: ConfigTree, service_types: list[str]
    ) -> ValidationResult:
        """Run all 4 layers on every leaf in the tree."""
        all_errors: list[dict] = []

        def _walk(node: TreeNode | TreeLeaf) -> None:
            if isinstance(node, TreeLeaf):
                errs = self.validate_field(
                    tree, node.path, service_types, full=True
                )
                all_errors.extend(errs)
            elif isinstance(node, TreeNode):
                for child in node.children:
                    _walk(child)

        _walk(tree.root)

        # Also run L3 service-type-level checks (requires tree-level context)
        all_errors.extend(self._check_semantic(tree, None, service_types))

        # De-duplicate
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for e in all_errors:
            key = (e.get("path", ""), e.get("message", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(e)

        # Update all leaf error lists
        self._sync_errors_to_tree(tree, deduped)

        state = "fail" if deduped else "pass"
        return ValidationResult(state=state, errors=deduped)

    # ─────────────────────────────────────────────────────────────────────────
    # L1: Alias resolution  (DC-014)
    # ─────────────────────────────────────────────────────────────────────────

    def _try_resolve_alias(self, leaf: TreeLeaf) -> Any:
        """Silently resolve alias via TemplateMapper; mutates leaf.value."""
        # Aliases are string-to-string mappings only
        if not isinstance(leaf.value, str):
            return leaf.value
        # Determine object_type from leaf.path
        object_type = self._infer_object_type(leaf.path)
        resolved = self.mapper.resolve_alias(
            object_type, leaf.key, leaf.value
        )
        if resolved != leaf.value:
            leaf.value = resolved
        return resolved

    # ─────────────────────────────────────────────────────────────────────────
    # L2: Type check  (DC-014)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_type(self, leaf: TreeLeaf) -> list[dict]:
        """Return errors for value_type violations.

        None on non-required fields is treated as "not set yet" and skipped.
        Only syntax-required fields (required=True) are checked for None.
        """
        vt = leaf.descriptor.value_type
        value = leaf.value
        path = leaf.path

        # Skip type check for None on non-required fields
        if value is None and not leaf.descriptor.required:
            return []

        checkers = {
            "enum": self._check_enum,
            "integer": self._check_integer,
            "float": self._check_float,
            "boolean": self._check_boolean,
            "color": self._check_color,
            "array": self._check_array,
            "expression": self._check_expression,
        }

        checker = checkers.get(vt)
        if checker is None:
            return []

        msg = checker(value, leaf.descriptor)
        if msg:
            return [{"path": path, "message": msg, "level": "error"}]
        return []

    def _check_enum(self, value: Any, desc: FieldDescriptor) -> str | None:
        if desc.enum is None:
            return None
        allowed = [str(v).lower() for v in desc.enum]
        if str(value).lower() not in allowed:
            return f"Value '{value}' is not a valid enum. Allowed: {desc.enum}"
        return None

    def _check_integer(self, value: Any, desc: FieldDescriptor) -> str | None:
        if not isinstance(value, int) or isinstance(value, bool):
            return f"Expected integer, got {type(value).__name__}"
        if desc.min is not None and value < desc.min:
            return f"Value {value} is below minimum {desc.min}"
        if desc.max is not None and value > desc.max:
            return f"Value {value} exceeds maximum {desc.max}"
        return None

    def _check_float(self, value: Any, desc: FieldDescriptor) -> str | None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"Expected float, got {type(value).__name__}"
        v = float(value)
        if desc.min is not None and v < float(desc.min):
            return f"Value {v} is below minimum {desc.min}"
        if desc.max is not None and v > float(desc.max):
            return f"Value {v} exceeds maximum {desc.max}"
        return None

    def _check_boolean(self, value: Any, _desc: FieldDescriptor) -> str | None:
        if not isinstance(value, bool):
            return f"Expected boolean, got {type(value).__name__}"
        return None

    def _check_color(self, value: Any, _desc: FieldDescriptor) -> str | None:
        if not isinstance(value, list) or len(value) != 3:
            return "Color must be an RGB array [R, G, B]"
        for c in value:
            if not isinstance(c, int) or isinstance(c, bool):
                return "Color values must be integers"
            if not 0 <= c <= 255:
                return f"Color value {c} out of range [0, 255]"
        return None

    def _check_array(self, value: Any, _desc: FieldDescriptor) -> str | None:
        if not isinstance(value, list):
            return f"Expected array, got {type(value).__name__}"
        return None

    def _check_expression(self, value: Any, _desc: FieldDescriptor) -> str | None:
        if not isinstance(value, str):
            return f"Expected expression string, got {type(value).__name__}"
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # L3: Semantic check  (DC-015)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_semantic(
        self,
        tree: ConfigTree,
        leaf: TreeLeaf | None,
        service_types: list[str],
    ) -> list[dict]:
        """Check dependencies.json rules: requires_when, forbids_when, derives.

        Walks every object node in the tree and evaluates dependency edges
        against the actual node instances (handles multiple LAYERs, CLASSes).
        """
        errors: list[dict] = []

        # Gather all object nodes keyed by type for fast lookup
        nodes_by_type: dict[str, list[TreeNode]] = {}

        def _collect(node: TreeNode | TreeLeaf) -> None:
            if isinstance(node, TreeNode):
                nodes_by_type.setdefault(node.object_type, []).append(node)
                for child in node.children:
                    _collect(child)

        _collect(tree.root)

        for edge in self._dependencies:
            relation = edge.get("relation", "")
            source = edge.get("source", "")
            target = edge.get("target", "")
            condition = edge.get("condition", "")

            if relation == "requires_when":
                errors.extend(
                    self._eval_requires_when_on_nodes(
                        tree, nodes_by_type, source, target, condition, service_types
                    )
                )
            elif relation == "forbids_when":
                errors.extend(
                    self._eval_forbids_when_on_nodes(
                        tree, nodes_by_type, source, target, condition, service_types
                    )
                )
            elif relation == "validates":
                description = edge.get("description", "")
                errors.extend(
                    self._eval_validates_on_nodes(
                        tree, nodes_by_type, source, target, condition, description, service_types
                    )
                )
            # "derives" and "invalidates" are informational, not errors

        return errors

    def _eval_requires_when_on_nodes(
        self,
        tree: ConfigTree,
        nodes_by_type: dict[str, list[TreeNode]],
        source: str,
        target: str,
        condition: str,
        service_types: list[str],
    ) -> list[dict]:
        """Evaluate requires_when against all matching object instances."""
        errors: list[dict] = []
        src_type, src_field = self._parse_edge_path(source)
        tgt_type, tgt_field = self._parse_edge_path(target)

        if src_type == "session":
            # Session-level condition (e.g. session.service_types)
            val = service_types if src_field == "service_types" else None
            if val is not None and self._eval_condition(condition, val, service_types):
                # Target is on every matching object instance
                for node in nodes_by_type.get(tgt_type, []):
                    tgt_leaf = self._find_leaf_in_node(node, tgt_field, tree)
                    if tgt_leaf is None or tgt_leaf.value is None or tgt_leaf.value == "":
                        errors.append({
                            "path": node.path + "." + tgt_field if node.path else tgt_field,
                            "message": f"'{tgt_field}' is required when {source}={val}",
                            "level": "error",
                        })
            return errors

        # Object-level condition
        for node in nodes_by_type.get(src_type, []):
            src_leaf = self._find_leaf_in_node(node, src_field, tree)
            if src_leaf is None:
                continue
            if not self._eval_condition(condition, src_leaf.value, service_types):
                continue

            # Find target — same object type, same instance
            for tgt_node in nodes_by_type.get(tgt_type, []):
                # If target type differs from source type, match by path prefix
                # e.g. LAYER.type → STYLE.symbol: target STYLE under same LAYER path
                if tgt_type != src_type:
                    if not tgt_node.path.startswith(node.path + "."):
                        continue
                else:
                    # Same type — must be same instance
                    if tgt_node.path != node.path:
                        continue

                tgt_leaf = self._find_leaf_in_node(tgt_node, tgt_field, tree)
                if tgt_leaf is None or tgt_leaf.value is None or tgt_leaf.value == "":
                    errors.append({
                        "path": tgt_node.path + "." + tgt_field,
                        "message": f"'{tgt_field}' is required when {source}={src_leaf.value}",
                        "level": "error",
                    })

        return errors

    def _eval_forbids_when_on_nodes(
        self,
        tree: ConfigTree,
        nodes_by_type: dict[str, list[TreeNode]],
        source: str,
        target: str,
        condition: str,
        service_types: list[str],
    ) -> list[dict]:
        """Evaluate forbids_when against all matching object instances."""
        errors: list[dict] = []
        src_type, src_field = self._parse_edge_path(source)
        tgt_type, tgt_field = self._parse_edge_path(target)

        for node in nodes_by_type.get(src_type, []):
            src_leaf = self._find_leaf_in_node(node, src_field, tree)
            if src_leaf is None:
                continue
            if not self._eval_condition(condition, src_leaf.value, service_types):
                continue

            for tgt_node in nodes_by_type.get(tgt_type, []):
                if tgt_type != src_type:
                    if not tgt_node.path.startswith(node.path + "."):
                        continue
                else:
                    if tgt_node.path != node.path:
                        continue

                tgt_leaf = self._find_leaf_in_node(tgt_node, tgt_field, tree)
                if tgt_leaf is not None and tgt_leaf.value is not None and tgt_leaf.value != "":
                    errors.append({
                        "path": tgt_node.path + "." + tgt_field,
                        "message": f"'{tgt_field}' should not be set when {source}={src_leaf.value}",
                        "level": "error",
                    })

        return errors

    def _eval_validates_on_nodes(
        self,
        tree: ConfigTree,
        nodes_by_type: dict[str, list[TreeNode]],
        source: str,
        target: str,
        condition: str,
        description: str,
        service_types: list[str],
    ) -> list[dict]:
        """Evaluate validates edges: when condition fails, report an error on target."""
        errors: list[dict] = []
        src_type, src_field = self._parse_edge_path(source)
        tgt_type, tgt_field = self._parse_edge_path(target)

        for node in nodes_by_type.get(src_type, []):
            src_leaf = self._find_leaf_in_node(node, src_field, tree)
            if src_leaf is None or src_leaf.value is None:
                continue

            if not self._eval_condition(condition, src_leaf.value, service_types):
                # Target field may differ from source; default to source field path
                field_to_report = tgt_field or src_field
                errors.append({
                    "path": node.path + "." + field_to_report if node.path else field_to_report,
                    "message": description or f"'{src_field}' has invalid value {src_leaf.value!r}",
                    "level": "error",
                })

        return errors

    @staticmethod
    def _parse_edge_path(edge_path: str) -> tuple[str, str]:
        """Parse 'LAYER.connectiontype' → ('LAYER', 'connectiontype').

        Special case: 'session.service_types' → ('session', 'service_types').
        """
        parts = edge_path.split(".")
        if len(parts) == 2:
            return parts[0], parts[1]
        return edge_path, ""

    def _find_leaf_in_node(self, node: TreeNode, field: str, tree: ConfigTree | None = None) -> TreeLeaf | None:
        """Find a leaf with the given field name inside a node.

        Falls back to params lookup because hidden fields (filtered by
        service_types) retain their values in params.
        """
        # 1. Search in tree children
        for child in node.children:
            if isinstance(child, TreeLeaf) and child.key == field:
                return child
            if isinstance(child, TreeNode):
                for grandchild in child.children:
                    if isinstance(grandchild, TreeLeaf) and grandchild.key == field:
                        return grandchild

        # 2. Fallback: resolve from params using the node's path
        if tree is not None and node.path:
            try:
                val = self._resolve_value_from_params(tree, node.path, field)
                if val is not None:
                    return TreeLeaf(
                        id=f"{node.path}_{field}",
                        path=f"{node.path}.{field}",
                        key=field,
                        descriptor=FieldDescriptor(key=field, value_type="string"),
                        value=val,
                    )
            except (KeyError, ValueError, TypeError):
                pass
        return None

    @staticmethod
    def _resolve_value_from_params(tree: ConfigTree, node_path: str, field: str) -> Any:
        """Resolve a field value from params via the node's path."""
        path = node_path
        if path.startswith("map."):
            path = path[4:]

        parts = path.split(".")
        current: Any = tree.params
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                idx = int(part)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
            if current is None:
                return None

        if isinstance(current, dict):
            return current.get(field)
        return None

    def _eval_condition(
        self,
        condition: str,
        value: Any,
        service_types: list[str] | None = None,
    ) -> bool:
        """Safely evaluate a dependency condition expression.

        Supported patterns:
        - value == 'x'
        - value in ['a', 'b']
        - 'wfs' in value   (value is a list)
        """
        if not condition:
            return True

        # Build safe evaluation namespace
        safe_ns: dict[str, Any] = {
            "value": value,
            "__builtins__": {},
        }

        # Whitelist operators
        safe_ns.update(
            {
                k: getattr(operator, k)
                for k in ("eq", "ne", "lt", "le", "gt", "ge", "contains")
            }
        )

        # Rewrite common operators to function calls for safety
        expr = condition.replace("==", "__eq__").replace("!=", "__ne__")
        # Actually, let's use a simpler approach: parse with ast and evaluate
        return self._safe_eval(condition, value)

    def _safe_eval(self, expr: str, value: Any) -> bool:
        """Parse and safely evaluate a condition expression."""
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return False

        def _eval_node(node: ast.AST) -> Any:
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            if isinstance(node, ast.Constant):
                return node.value
            if isinstance(node, ast.Str):  # py < 3.8 compat
                return node.s
            if isinstance(node, ast.Num):  # py < 3.8 compat
                return node.n
            if isinstance(node, ast.Name):
                if node.id == "value":
                    return value
                raise NameError(f"Name {node.id} not allowed")
            if isinstance(node, ast.Compare):
                left = _eval_node(node.left)
                if len(node.ops) != 1 or len(node.comparators) != 1:
                    raise ValueError("Only single comparisons supported")
                op = node.ops[0]
                right = _eval_node(node.comparators[0])
                if isinstance(op, ast.Eq):
                    return left == right
                if isinstance(op, ast.NotEq):
                    return left != right
                if isinstance(op, ast.Lt):
                    return left < right
                if isinstance(op, ast.LtE):
                    return left <= right
                if isinstance(op, ast.Gt):
                    return left > right
                if isinstance(op, ast.GtE):
                    return left >= right
                if isinstance(op, ast.In):
                    return left in right
                raise ValueError(f"Unsupported comparison {type(op).__name__}")
            if isinstance(node, ast.List):
                return [_eval_node(elt) for elt in node.elts]
            if isinstance(node, ast.Tuple):
                return tuple(_eval_node(elt) for elt in node.elts)
            if isinstance(node, ast.BoolOp):
                values = [_eval_node(v) for v in node.values]
                if isinstance(node.op, ast.And):
                    return all(values)
                if isinstance(node.op, ast.Or):
                    return any(values)
            if isinstance(node, ast.Subscript):
                container = _eval_node(node.value)
                slice_node = node.slice
                if isinstance(slice_node, ast.Index):  # Python < 3.9
                    idx = _eval_node(slice_node.value)
                elif isinstance(slice_node, ast.Constant):  # Python 3.9+
                    idx = slice_node.value
                else:
                    idx = _eval_node(slice_node)
                return container[idx]
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    allowed_funcs = {
                        "len": len,
                        "min": min,
                        "max": max,
                        "all": all,
                        "any": any,
                        "isinstance": isinstance,
                    }
                    if node.func.id not in allowed_funcs:
                        raise ValueError(f"Function {node.func.id} not allowed")
                    args = [_eval_node(a) for a in node.args]
                    return allowed_funcs[node.func.id](*args)
                raise ValueError("Only simple function calls are supported")
            raise ValueError(f"Unsupported AST node {type(node).__name__}")

        return bool(_eval_node(tree))

    # ─────────────────────────────────────────────────────────────────────────
    # L4: Mappyfile syntax  (DC-016)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_mappyfile(self, tree: ConfigTree) -> list[dict]:
        """Run mappyfile.validate and filter false positives."""
        try:
            import mappyfile
        except ImportError:
            return []

        try:
            mf_dict = tree.to_mappyfile_dict()
            raw = mappyfile.validate(mf_dict, version=8.4)
        except Exception as exc:
            # Defensive: mappyfile.validate may throw on malformed dicts
            # (e.g. string element in an object-array like layers/classes)
            return [
                {
                    "path": "",
                    "message": f"Mapfile syntax validation failed: {exc}",
                    "level": "error",
                }
            ]

        # Defensive: mappyfile.validate may return a non-list in edge cases
        errors: list[Any] = raw if isinstance(raw, list) else []

        filtered: list[dict] = []
        for err in errors:
            if not isinstance(err, dict):
                continue
            if self._is_false_positive(err, tree):
                continue
            filtered.append(self._format_mappyfile_error(err))

        return filtered

    _REGEX_UNKNOWN_KEY = re.compile(
        r"'([^']+)'(?:,\s*'([^']+)')*\s+do not match any of the regexes"
    )
    _REGEX_SINGLE_UNKNOWN = re.compile(
        r"'([^']+)'\s+does not match any of the regexes"
    )

    def _is_false_positive(self, err: dict, tree: ConfigTree) -> bool:
        """Check if a mappyfile error is a known false positive."""
        error_text = err.get("error", "")
        message = err.get("message", "")

        # Extract object type from message: "ERROR: Invalid value in MAP"
        obj_type = self._extract_object_type_from_message(message)

        # Pattern: key does not match any of the regexes
        if "does not match any of the regexes" in error_text:
            keys = self._extract_unknown_keys(error_text)
            for key in keys:
                # Check if this is a known field in our rules
                if obj_type and key in self.mapper.list_all_fields(obj_type):
                    return True
                # Check if this is a custom property
                if self._is_custom_property(tree, key):
                    return True

        return False

    def _extract_object_type_from_message(self, message: str) -> str | None:
        """Extract object type from 'ERROR: Invalid value in LAYER'."""
        m = re.search(r"in\s+([A-Z]+)\s*$", message)
        if m:
            return m.group(1)
        return None

    def _extract_unknown_keys(self, error_text: str) -> list[str]:
        """Extract key names from 'key1', 'key2' do not match... errors."""
        # Try plural form first
        m = self._REGEX_UNKNOWN_KEY.search(error_text)
        if m:
            keys = [m.group(1)]
            # Capture additional quoted keys
            remaining = error_text[m.end() :]
            # Actually, re-search the full text for all quoted strings
            return re.findall(r"'([^']+)'", error_text)
        # Try singular form
        m2 = self._REGEX_SINGLE_UNKNOWN.search(error_text)
        if m2:
            return [m2.group(1)]
        return []

    def _is_custom_property(self, tree: ConfigTree, key: str) -> bool:
        """Check if a key exists as a custom property anywhere in the tree."""

        def _walk(node: TreeNode | TreeLeaf) -> bool:
            if isinstance(node, TreeLeaf):
                return node.key == key and node.descriptor.custom
            for child in node.children:
                if _walk(child):
                    return True
            return False

        return _walk(tree.root)

    def _format_mappyfile_error(self, err: dict) -> dict:
        """Convert mappyfile error to our standard format."""
        error_text = err.get("error", "")
        message = err.get("message", "")
        # Try to extract path from the error text
        path = self._extract_path_from_mappyfile_error(error_text, message)
        return {
            "path": path or "",
            "message": error_text or message,
            "level": "error",
        }

    def _extract_path_from_mappyfile_error(
        self, error_text: str, message: str
    ) -> str | None:
        """Try to build a flat path from mappyfile error.

        mappyfile errors have the format:
        - error: "'key' does not match any of the regexes: ..."
        - message: "ERROR: Invalid value in OBJ_TYPE"

        Returns the best-effort flat path (e.g. "web.metadata.foo",
        "layers", "type").  For indexed objects (LAYER/CLASS/STYLE/LABEL)
        we cannot determine the index from the error, so we return the
        plural key ("layers") which at least highlights the container.
        """
        obj_type = self._extract_object_type_from_message(message)
        if not obj_type:
            return None

        keys = self._extract_unknown_keys(error_text)
        key = keys[0] if keys else None

        # Map mappyfile object type → flat path prefix used by ConfigTree.
        # Indexed containers (layers/classes/styles/labels) use the plural
        # because mappyfile does not include the index in its error.
        TYPE_PATH_MAP: dict[str, str] = {
            "MAP": "map",
            "WEB": "web",
            "LAYER": "layers",
            "CLASS": "classes",
            "STYLE": "styles",
            "LABEL": "labels",
            "METADATA": "web.metadata",
        }

        prefix = TYPE_PATH_MAP.get(obj_type)
        if prefix is None:
            return None

        if key:
            # Errors like "'foo' is a required property" don't have a key
            # in the regex sense, but _extract_unknown_keys may return [].
            # If we do have a key, append it.
            # For required-property errors the key is sometimes in the error
            # text as "'type' is a required property" — the regex extractor
            # already handles quoted strings.
            return f"{prefix}.{key}"

        return prefix

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _infer_object_type(self, path: str) -> str:
        """Infer the object type from a flat path.

        e.g. 'layers.0.classes.0.styles.0.color' → 'STYLE'
        """
        parts = path.split(".")
        # Look for object type indicators in the path
        type_map = {
            "layers": "LAYER",
            "classes": "CLASS",
            "styles": "STYLE",
            "labels": "LABEL",
            "web": "WEB",
            "metadata": "METADATA",
            "cache": "CACHE",
        }
        for part in reversed(parts):
            if part in type_map:
                return type_map[part]
        return "MAP"

    def _sync_errors_to_tree(
        self, tree: ConfigTree, errors: list[dict]
    ) -> None:
        """Update all leaf error lists from the aggregated errors."""
        # Build map: path → list of messages
        msg_map: dict[str, list[str]] = {}
        for e in errors:
            path = e.get("path", "")
            if path:
                msg_map.setdefault(path, []).append(e["message"])

        def _walk(node: TreeNode | TreeLeaf) -> None:
            if isinstance(node, TreeLeaf):
                node.errors = msg_map.get(node.path, [])
            elif isinstance(node, TreeNode):
                for child in node.children:
                    _walk(child)

        _walk(tree.root)
