# Proposal-0015: 服务类型勾选联动自动配置（自动填充 + 条件必填扩展）

> **类型**: Type-A（需求变更）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-10
> **对应 Spec**: F-M1.2（配置树字段筛选与图例）
> **影响范围**:
> - `data/templates/required.json` — 补充 WFS/WCS 业务关键字段的 required_when
> - `data/templates/defaults-override.json` — 补充服务专用字段默认值
> - `backend/core/config_tree.py` — 新增 `auto_fill_service_defaults()` 方法
> - `backend/core/session.py` — `set_service_types` 处理时触发自动填充
> - `backend/main.py` — `_handle_set_service_types` 传递新增服务列表
> - `data/mapguide_rules.json` — 重新生成

---

## 背景与动机

### 问题

当前勾选 WMS/WFS/WCS 仅控制 METADATA 字段的**显示/隐藏**，不会自动填充默认值，也不会将部分业务关键字段标记为条件必填。

用户勾选 WMS 后，看到 `wms_enable_request`、`wms_srs` 等字段显示出来但都是空的，需要手动逐个填写。而 `service-metadata.json` 中已经定义了这些字段的业务默认值（如 `wms_enable_request="*"`、`wms_srs="EPSG:3857 EPSG:4326"`），系统应当自动帮用户填上。

### 核心原则

> **有默认值的服务字段应在勾选时自动填充，无默认值但业务关键的字段应标记为条件必填（◆）。**

---

## 专业资源调研结论

基于 `模板说明.md` 附录 B（MapServer 8.6.3 源码参数提取）和附录 C（必填项语义探究）的已有结论：

### WMS 业务关键字段（已覆盖）

| 字段 | 状态 | 说明 |
|------|------|------|
| `wms_title` | ✅ 已有 required_when | 无 `ows_title` 时 WMS 专用标题必填（mapwms.cpp:3422） |
| `wms_srs` | ✅ 已有 required_when | 无 `MAP.projection` 时 WMS 专用 SRS 提示 |
| `wms_enable_request` | ✅ 自动回填 | `defaults-override.json` 默认 `"*"` |

### WFS 业务关键字段（需补充）

| 字段 | 状态 | 说明 |
|------|------|------|
| `wfs_title` | ✅ 已有 required_when | 无 `ows_title` 时 WFS 专用标题 |
| `wfs_srs` | ✅ 已有 required_when | 无 `MAP.projection` 时 WFS 专用 SRS |
| `wfs_enable_request` | ✅ 自动回填 | `defaults-override.json` 默认 `"*"` |
| `wfs_namespace_uri` | ⬜ **需新增** required_when | WFS GetCapabilities 输出 `targetNamespace`，无则客户端常出问题（mapwfs.cpp:1425） |
| `wfs_namespace_prefix` | ⬜ **需新增** required_when | 配套 namespace_uri |
| `gml_featureid` | ✅ 已有 dependencies | `dependencies.json` 已有 `requires_when`（WFS 时建议设置） |

### WCS 业务关键字段（需补充）

| 字段 | 状态 | 说明 |
|------|------|------|
| `wcs_title` | ✅ 已有 required_when | 无 `ows_title` 时 WCS 专用标题 |
| `wcs_srs` | ✅ 已有 required_when | 无 `MAP.projection` 时 WCS 专用 SRS |
| `wcs_extent` | ✅ 已有 required_when | WCS 专用范围 |
| `wcs_enable_request` | ✅ 自动回填 | `defaults-override.json` 默认 `"*"` |
| `wcs_imagemode` | ⬜ **需新增** required_when | 决定栅格数据解释方式（BYTE/FLOAT/INT16），无默认值，WCS 必须（mapwcs.cpp） |

---

## 设计变更

### 方案 A：勾选服务时自动填充关键默认值

#### 触发时机

用户在前端勾选某个服务类型（如 WMS）时，`toggleService()` 发送 `set_service_types` WS 消息。后端对比**新增**的服务类型，仅对新勾选的服务执行自动填充。

**不触发的情况**：
- 取消勾选服务（不删除已有字段，保留用户数据）
- 已勾选的服务重新勾选（避免覆盖用户修改）
- 导入模式（`import_mode=True`）

#### 自动填充字段清单

从 `service-metadata.json` 中提取有 `default` 定义的字段：

| 服务 | 字段 | 默认值 | 来源 |
|------|------|--------|------|
| WMS | `wms_enable_request` | `"*"` | defaults-override.json |
| WMS | `wms_srs` | `"EPSG:3857 EPSG:4326"` | service-metadata.json |
| WMS | `wms_include_items` | `"all"` | service-metadata.json |
| WFS | `wfs_enable_request` | `"*"` | defaults-override.json |
| WFS | `wfs_srs` | `"EPSG:4326"` | service-metadata.json |
| WCS | `wcs_enable_request` | `"*"` | defaults-override.json |
| WCS | `wcs_srs` | `"EPSG:3857"` | service-metadata.json |

**填充规则**：
1. 仅当字段在 `params` 中**不存在**时才创建
2. 字段创建在 `MAP.WEB.METADATA` 路径下
3. 填充后触发 `ValidationPipeline.validate_field()` 进行 L1-L3 验证
4. 最后发送 `tree_state` WS 消息更新前端

#### 实现位置

新增 `ConfigTree.auto_fill_service_defaults(services_added: list[str])` 方法：

```python
def auto_fill_service_defaults(self, services_added: list[str]) -> list[dict]:
    """当新增服务类型时，自动填充该服务的关键默认值。

    Returns:
        实际执行的填充操作列表，用于日志/调试。
    """
    # 读取 self.mapper.rules["service_metadata"] 中的默认值定义
    # 对于每个新增服务，找到 metadata_fields 中有 default 的字段
    # 检查 params 中是否已存在，不存在则创建
    # 返回 [{"field": "wms_enable_request", "value": "*", "path": "web.metadata.wms_enable_request"}]
```

在 `ConfigSession._handle_set_service_types()` 中调用：

```python
old_services = set(session.service_types)
new_services = set(msg["services"])
added = list(new_services - old_services)

session.service_types = msg["services"]
session.mapcache_enabled = msg.get("mapcache_enabled", False)
session.tree = ConfigTree(session.params, session.mapper,
                          service_types=session.service_types)

# 自动填充新增服务的默认值
if added and not session.tree.import_mode:
    filled = session.tree.auto_fill_service_defaults(added)
    # filled 结果可记入日志
```

### 方案 B：补充业务关键字段的 required_when

#### required.json 变更

**METADATA 变更后：**

```json
"METADATA": {
  "required": [],
  "business_required": [],
  "required_when": {
    "ows_title": "len(session.service_types) > 0",
    "ows_onlineresource": "len(session.service_types) > 0",
    "ows_srs": "len(session.service_types) > 0 and not map.get('projection')",
    "wms_title": "'wms' in session.service_types and not map.web.metadata.get('ows_title')",
    "wfs_title": "'wfs' in session.service_types and not map.web.metadata.get('ows_title')",
    "wcs_title": "'wcs' in session.service_types and not map.web.metadata.get('ows_title')",
    "wms_srs": "'wms' in session.service_types and not map.get('projection')",
    "wfs_srs": "'wfs' in session.service_types and not map.get('projection')",
    "wcs_srs": "'wcs' in session.service_types and not map.get('projection')",
    "wcs_extent": "'wcs' in session.service_types",
    "wfs_namespace_uri": "'wfs' in session.service_types",
    "wfs_namespace_prefix": "'wfs' in session.service_types",
    "wcs_imagemode": "'wcs' in session.service_types"
  }
}
```

**新增字段说明：**

| 字段 | 条件 | 理由 |
|------|------|------|
| `wfs_namespace_uri` | `'wfs' in session.service_types` | WFS GetCapabilities 需输出 `targetNamespace`，为空时客户端可能拒绝解析 |
| `wfs_namespace_prefix` | `'wfs' in session.service_types` | 配套 `namespace_uri`，构成完整命名空间声明 |
| `wcs_imagemode` | `'wcs' in session.service_types` | 栅格数据类型解释（BYTE/FLOAT/INT16），无默认值，直接影响 Coverage 数据读取 |

#### 语义说明

- `wfs_namespace_uri` / `wfs_namespace_prefix`：WFS 服务不填 namespace 时，GetCapabilities 输出空的 `targetNamespace=""`，部分严格客户端（如 QGIS、GeoServer）会报解析错误。
- `wcs_imagemode`：MapServer WCS 实现中，`imagemode` 决定栅格波段如何解释（如 BYTE 是 0-255，FLOAT 是浮点）。不填时 MapServer 会尝试推断，但推断失败则服务异常。

---

## 变更内容

### [MODIFIED] `data/templates/required.json`

在 METADATA 的 `required_when` 中新增 3 个条目（见上文）。

### [MODIFIED] `data/templates/defaults-override.json`

确认以下默认值已存在（如缺失则补充）：

```json
"METADATA": {
  "ows_enable_request": "*",
  "wms_enable_request": "*",
  "wfs_enable_request": "*",
  "wcs_enable_request": "*"
}
```

### [NEW] `backend/core/config_tree.py` — `auto_fill_service_defaults()`

```python
def auto_fill_service_defaults(self, services_added: list[str]) -> list[dict]:
    """当新增服务类型时，自动填充该服务的关键默认值。

    仅填充 service-metadata 中定义了 default 且当前 params 中不存在的字段。
    不覆盖用户已填写的值。
    """
    filled: list[dict] = []
    svc_meta = self.mapper.rules.get("service_metadata", {})
    meta_fields = svc_meta.get("metadata_fields", {})

    for svc in services_added:
        if svc not in meta_fields:
            continue
        for field, config in meta_fields[svc].items():
            if "default" not in config:
                continue
            full_key = f"{svc}_{field}"
            # 检查 web.metadata 中是否已存在
            web_meta = self.params.get("web", {}).get("metadata", {})
            if full_key in web_meta:
                continue
            # 同时检查 ows_ 通用版本是否已存在（避免重复）
            if field in ["title", "abstract", "onlineresource", "enable_request", "srs"]:
                ows_key = f"ows_{field}"
                if ows_key in web_meta:
                    continue
            # 填入默认值
            if "web" not in self.params:
                self.params["web"] = {}
            if "metadata" not in self.params["web"]:
                self.params["web"]["metadata"] = {}
            self.params["web"]["metadata"][full_key] = config["default"]
            filled.append({
                "field": full_key,
                "value": config["default"],
                "path": f"web.metadata.{full_key}",
            })

    return filled
```

### [MODIFIED] `backend/core/session.py` — `_handle_set_service_types()`

```python
def _handle_set_service_types(self, msg: dict[str, Any], session: ConfigSession) -> None:
    """Handle set_service_types message."""
    old_services = set(session.service_types)
    new_services = set(msg.get("services", []))
    added = list(new_services - old_services)

    session.service_types = msg.get("services", [])
    session.mapcache_enabled = msg.get("mapcache_enabled", False)
    session.tree = ConfigTree(
        session.params, session.mapper,
        service_types=session.service_types
    )

    # 自动填充新增服务的默认值
    if added and not getattr(session.tree, "import_mode", False):
        filled = session.tree.auto_fill_service_defaults(added)
        if filled:
            # 重新序列化以反映填充后的状态
            pass  # tree_state 会在下方发送
```

### [MODIFIED] `backend/main.py` — `_handle_set_service_types()`

无需修改接口，只需确保 `session` 对象在更新 `service_types` 后正确传递。

### [REGENERATED] `data/mapguide_rules.json`

通过 `scripts/generate_rules.py` 重新生成。

---

## 数据流

```
用户勾选 WMS
    │
    ▼
toggleService('wms', true)
    │
    ▼
WS: set_service_types { services: ['wms'], mapcache_enabled: false }
    │
    ▼
_handle_set_service_types()
    ├── 计算 added = ['wms']
    ├── 重建 ConfigTree(service_types=['wms'])
    ├── auto_fill_service_defaults(['wms'])
    │       ├── 读取 service_metadata.metadata_fields.wms
    │       ├── wms_enable_request default="*" → 填入 web.metadata
    │       ├── wms_srs default="EPSG:3857 EPSG:4326" → 填入 web.metadata
    │       ├── wms_include_items default="all" → 填入 web.metadata
    │       └── 返回 filled 列表
    ├── validate_tree()  # 触发 required_when 更新
    │       └── wms_title 显示 ◆（因为 ows_title 不存在）
    └── WS: tree_state → 前端（字段可见 + 默认值已填充 + ◆ 标记更新）
```

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| 新增服务时自动填充默认值 | 单元测试 | `test_auto_fill_wms_defaults`：勾选 WMS 后 `web.metadata.wms_enable_request == "*"` |
| 不覆盖已有值 | 单元测试 | `test_auto_fill_no_override`：已有值不被覆盖 |
| 取消勾选不删除字段 | 单元测试 | `test_uncheck_keeps_values`：取消 WMS 后 `wms_enable_request` 仍在 params 中 |
| 导入模式不触发 | 单元测试 | `test_import_no_auto_fill`：`import_mode=True` 时不自动填充 |
| 新增 required_when 生效 | 单元测试 | `test_wfs_namespace_required_when`：WFS 时 `wfs_namespace_uri` 有 required_when |
| 新增 required_when 验证 | 单元测试 | `test_wcs_imagemode_required_when`：WCS 时 `wcs_imagemode` 有 required_when |
| generate_rules.py 输出 | 集成测试 | `test_rules_output` 包含新增 required_when |
| 后端全部回归测试 | pytest | 全部通过 |
| 前端全部回归测试 | vitest | 全部通过 |

---

## 验收标准

- [ ] 勾选 WMS 时，`wms_enable_request`、`wms_srs`、`wms_include_items` 自动填入默认值
- [ ] 勾选 WFS 时，`wfs_enable_request`、`wfs_srs` 自动填入默认值
- [ ] 勾选 WCS 时，`wcs_enable_request`、`wcs_srs` 自动填入默认值
- [ ] 已存在的字段值不被覆盖
- [ ] 取消勾选不删除已有字段
- [ ] 导入模式不触发自动填充
- [ ] 勾选 WFS 时，`wfs_namespace_uri`、`wfs_namespace_prefix` 显示 ◆
- [ ] 勾选 WCS 时，`wcs_imagemode` 显示 ◆
- [ ] 不勾选对应服务时，上述 ◆ 标记不显示
- [ ] 全部后端测试通过
- [ ] 全部前端测试通过

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `data/templates/required.json` | 新增 METADATA `wfs_namespace_uri`、`wfs_namespace_prefix`、`wcs_imagemode` 的 required_when |
| `data/mapguide_rules.json` | 重新生成，METADATA required_when 从 10 条变为 13 条 |
| `backend/core/template_mapper.py` | 新增 `get_service_metadata()` 公共方法 |
| `backend/core/config_tree.py` | 新增 `auto_fill_service_defaults()` 方法 |
| `backend/main.py` | `_handle_set_service_types` 中计算新增服务并触发自动填充 |
| `tests/unit/test_config_tree.py` | 新增 `TestAutoFillServiceDefaults`（7 个测试用例） |
| `tests/unit/test_main.py` | 新增 3 个 WebSocket 集成测试 |
| `tests/unit/test_template_mapper.py` | 新增 `TestGetServiceMetadata`（3 个测试）+ `TestRequiredWhenProposal0015`（3 个测试） |

**测试统计**：
- 后端单元测试：333 passed（新增 16 个）
- 前端单元测试：79 passed

---

## 依赖

- proposal-0013（必填项语义分层与 UI 三档筛选）
- proposal-0014（扩展 required_when 覆盖服务发布基本参数）

---

*Proposed: 2026-06-10 | Implemented: 2026-06-10*
