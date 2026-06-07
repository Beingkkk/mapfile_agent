---
title: 校验体系
description: 四层校验策略、校验触发时机、mappyfile 校验能力边界与假阳性过滤
---

## 8. 校验策略

### 9.1 四层校验

| 层级 | 执行者 | 校验内容 |
|------|--------|----------|
| 别名解析 | `AliasResolver` | "红色" → `[255,0,0]` |
| 类型校验 | `FieldDescriptor` + Pydantic | 类型、枚举、范围 |
| 语义校验 | `SemanticValidator` | 条件必填、互斥、依赖、**服务类型条件** |
| 语法校验 | `mappyfile.validate(version=8.4)` | Mapfile 结构合法性 |

**mappyfile 校验能力边界**：

`mappyfile.validate(version=8.4)` 只管 Mapfile **语法层**校验：
- 对象/关键词是否合法（如 `LAYER`、`CLASS`、`STYLE`）
- 值类型是否匹配 schema 定义
- 必需字段是否缺失
- 枚举值是否在允许范围内

**它不管的事**（由语义层自行实现）：
- OGC 服务业务规则：如"WFS 需要 `gml_include_items`"、"WCS 的 `LAYER.type` 必须是 raster"
- METADATA 语义：mappyfile 把 `METADATA` 视为通用 key-value 块，不校验 `wms_title` 等参数的存在性
- 服务类型间的依赖关系：如同时启用 WMS+WFS 时 `ows_title` 可替代各自前缀
- MapCache 配置合法性：`mapcache.xml` 的校验由独立的 `MapCacheValidator` 负责

因此，服务类型相关的必填、互斥、条件推导等规则，全部放在第 3 层（语义校验）实现。

### 9.2 校验触发时机

- **字段失焦**：只执行 alias + type + semantic（不执行 mappyfile，因为不完整）
- **添加/删除节点后**：执行全部四层
- **点击「校验全部」**：执行全部四层
- **导出前**：执行全部四层

---
