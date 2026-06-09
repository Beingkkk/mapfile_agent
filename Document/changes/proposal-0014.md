# Proposal-0014: 扩展 required_when 覆盖服务发布基本参数

> **类型**: Type-B（设计变更）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-09
> **对应 Spec**: F-M1.2（配置树字段筛选与图例）
> **影响范围**:
> - `data/templates/required.json` — 新增 MAP/LAYER 级 required_when 规则
> - `data/mapguide_rules.json` — 重新生成

---

## 背景与动机

### 问题

proposal-0013 将 `business_required` 全部清空，理由是"所有字段均有默认值，由自动回填处理"。但这产生了一个误导：**有默认值 != 业务上不需要关注**。

典型例子是 `MAP.extent`，其默认值为 `[-180, -90, 180, 90]`（全球范围）。用户如果填完"必填"和"建议填"后直接导出，服务会拥有一个不切实际的全球范围，导致：
- WMS GetCapabilities 返回错误的 BoundingBox
- 客户端初始视图异常
- 查询和缩放行为不符合预期

用户反馈："我要发布一个服务，难道 extent 就不是关注对象吗？"

### 核心原则

> **默认值是技术兜底，不是业务豁免。**
>
> 一个字段有默认值，只意味着"不填不会让 MapServer 解析报错"，不意味着"这个默认值适合你的场景"。

### 调研结论

从 OGC 服务（WMS/WFS/WCS）发布的实际业务需求出发，以下参数即使有默认值，在发布服务时也属于"基本条件"，需要用户显式配置：

| 字段 | 默认值 | 不关注的后果 |
|------|--------|-------------|
| `MAP.extent` | `[-180, -90, 180, 90]` | 全球范围 != 数据范围，影响 BoundingBox 和初始视图 |
| `MAP.name` | 无 | WMS GetCapabilities 服务标识不明确 |
| `MAP.projection` | `["init=epsg:3857"]` | Web Mercator 不一定匹配数据源坐标系 |
| `LAYER.extent` | 无（自动计算）| 自动计算可能耗时、失败或结果不准 |
| `LAYER.projection` | `["init=epsg:3857"]` | 应与数据源坐标系一致，跨投影时易出错 |

同时补充 `METADATA.ows_srs` 的 required_when，作为 projection 的 metadata 级 fallback 提醒。

---

## 设计变更

### 1. required.json 扩展

在 `required_when` 中新增以下条目：

**MAP:**
- `extent`: `len(session.service_types) > 0`
- `name`: `len(session.service_types) > 0`
- `projection`: `len(session.service_types) > 0`

**LAYER:**
- `extent`: `len(session.service_types) > 0`
- `projection`: `len(session.service_types) > 0`

**METADATA:**
- `ows_srs`: `len(session.service_types) > 0 and not map.get('projection')`

### 2. 语义说明

这些新增的 `required_when` 条件是 `len(session.service_types) > 0`，即：**只要用户勾选了任意服务类型（WMS/WFS/WCS），这些字段就会在"建议填"筛选模式下显示为 `◆`，提醒用户检查/配置。**

如果不发布服务（未勾选任何服务类型），这些字段保持为 `○ 可选`，不打扰纯制图场景。

### 3. UI 行为不变

- `◆` 标记的含义保持不变："条件关注"，不等于"不填就报错"
- "建议填"筛选模式逻辑不变：`required === true` OR `required_when` 不为空
- 图例六项不变

---

## 变更内容

### [MODIFIED] `data/templates/required.json`

**MAP 变更前:**
```json
"MAP": {
  "required": [],
  "business_required": [],
  "required_when": {}
}
```

**MAP 变更后:**
```json
"MAP": {
  "required": [],
  "business_required": [],
  "required_when": {
    "extent": "len(session.service_types) > 0",
    "name": "len(session.service_types) > 0",
    "projection": "len(session.service_types) > 0"
  }
}
```

**LAYER 变更后:**
```json
"LAYER": {
  "required": ["type"],
  "business_required": [],
  "required_when": {
    "extent": "len(session.service_types) > 0",
    "projection": "len(session.service_types) > 0",
    "connection": "connectiontype in ['postgis', 'ogr', 'wms']",
    "data": "connectiontype == 'local'",
    "name": "len(session.service_types) > 0"
  }
}
```

**METADATA 变更后:**
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
    "wcs_extent": "'wcs' in session.service_types"
  }
}
```

### [REGENERATED] `data/mapguide_rules.json`

通过 `scripts/generate_rules.py` 重新生成。

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| `generate_rules.py` 输出包含新增 required_when | 单元测试 | `test_required_rules_in_output` 仍通过（mock 数据独立） |
| `TemplateMapper` 返回新增字段的 required_when | 单元测试 | `test_returns_rules_for_known_type` 仍通过 |
| `ConfigTree.serialize()` 包含 required_when | 单元测试 | 现有测试通过 |
| 后端全部回归测试 | pytest | 全部通过 |
| 前端全部回归测试 | vitest | 全部通过 |

---

## 验收标准

- [ ] `required.json` 中 MAP/LAYER/METADATA 包含新增的 required_when 规则
- [ ] `mapguide_rules.json` 字段定义包含新增 required_when
- [ ] 勾选服务类型后，MAP.extent / MAP.name / MAP.projection 显示为 `◆`
- [ ] 勾选服务类型后，LAYER.extent / LAYER.projection 显示为 `◆`
- [ ] 不勾选服务类型时，上述字段显示为 `○`
- [ ] 全部后端测试通过
- [ ] 全部前端测试通过

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `data/templates/required.json` | 新增 MAP/LAYER extent、projection、name 的 required_when；新增 METADATA.ows_srs required_when |
| `data/mapguide_rules.json` | 重新生成 |

---

## 依赖

- proposal-0013（必填项语义分层与 UI 三档筛选）

*Proposed: 2026-06-09*
