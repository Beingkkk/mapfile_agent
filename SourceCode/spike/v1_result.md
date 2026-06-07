# V1 验证结论：mappyfile `validate()` 行为摸底

> 验证时间：2026-06-06
> mappyfile 版本：1.1.1
> 测试用例：62 个，覆盖 10 个维度

---

## 一、核心结论（TL;DR）

| 维度 | 结论 | 对 `to_mappyfile_dict()` 的影响 |
|------|------|--------------------------------|
| 布尔值 | **视字段而定**：string-enum（如 `status`）拒绝 Python bool；boolean 类型（如 `LABEL.antialias`）接受 | ⚠️ L2 自动转换 enum bool → `"ON"`/`"OFF"` |
| Enum 大小写 | **不敏感**：`postgis`/`POSTGIS` 都通过 | ✅ 无需强制大写，mappyfile 自动规范化 |
| 颜色 | **RGB 数组** `[R,G,B]` ✓；hex 字符串 ✓；空格分隔字符串 ✗ | ✅ 按设计文档用 RGB 数组 |
| 投影 | **必须是数组** `["init=epsg:3857"]`，字符串 ✗ | ✅ 按设计文档用数组 |
| Extent | **必须是 4 元素数组**，字符串/3元素/5元素 ✗ | ✅ 按设计文档用数组 |
| 数组字段 | `layers`/`classes`/`styles` **必须是列表**，单元素 dict ✗ | ⚠️ **必须包装为列表** |
| METADATA | 完全自由，整数自动转字符串，自定义属性通过 | ✅ 无需特殊处理 |
| 缺字段 | **极宽松**：MAP 缺 name、LAYER 缺 name 都通过 | ⚠️ 不能依赖 validate 做必填检查 |
| 自定义字段 | **零容忍**：任何 schema 外字段都被 validate 拒绝 | 🔴 **重大发现，需重新设计** |
| dumps 稳定性 | **62/62 全部成功**，dumps() 从不抛异常 | ✅ 极为可靠 |

**总体评价**：`dumps()` 非常可靠，但 `validate()` 的边界与直觉差异较大——它**严格到拒绝合法字段**（如 `DUMP`），又**宽松到放过缺 name**，不可作为唯一质量门。

---

## 二、详细发现

### 2.1 布尔值：视 schema 类型而定（⚠️ 高优先级）

```python
# ❌ validate 失败（string-enum 字段）
{"status": True}   # 错误：True is not of type 'string'

# ✅ validate 通过（string-enum 字段）
{"status": "ON"}   # dumps → STATUS ON
{"status": "OFF"}  # dumps → STATUS OFF

# ✅ validate 通过（boolean 类型字段）
{"antialias": True}   # LABEL.antialias 的 schema 类型是 boolean
{"partials": False}   # LABEL.partials 的 schema 类型是 boolean
```

**关键结论**：mappyfile schema 中同时存在两种布尔表示：
1. **string-enum**（如 `status`）：enum 为 `["on", "off"]`，`value_type="enum"` → **不接受 Python bool**
2. **boolean**（如 `LABEL.antialias`）：`type="boolean"`，`value_type="boolean"` → **接受 Python bool**

**对策**：
- L2 Type 校验：enum 字段收到 `bool` 时自动转 `"ON"`/`"OFF"`
- `to_mappyfile_dict()`：硬编码兜底集合 `_BOOLEAN_STRING_FIELDS = {"status"}`，防御旁路输入

---

### 2.2 Enum 大小写：实际上不敏感（✅ 好消息）

| 输入 | validate 结果 | dumps 输出 |
|------|--------------|-----------|
| `connectiontype: "POSTGIS"` | ✓ 通过 | `CONNECTIONTYPE POSTGIS` |
| `connectiontype: "postgis"` | ✓ 通过 | `CONNECTIONTYPE POSTGIS` |
| `type: "POLYGON"` | ✓ 通过 | `TYPE POLYGON` |
| `type: "polygon"` | ✓ 通过 | `TYPE POLYGON` |

**结论**：mappyfile 内部会把 enum 值规范化为大写。前端/LLM 可以传任意大小写，序列化层无需强制转换。

---

### 2.3 颜色：RGB 数组是唯一安全格式（✅ 符合设计）

| 输入 | validate 结果 | dumps 输出 |
|------|--------------|-----------|
| `[255, 0, 0]` | ✓ | `IMAGECOLOR 255 0 0` |
| `"255 0 0"` | ✗ | `IMAGECOLOR "255 0 0"`（带引号，错误） |
| `"#FF0000"` | ✓ | `IMAGECOLOR "#FF0000"`（带引号） |

**注意**：hex 字符串虽然通过 validate，但 dumps 输出会带引号（`"#FF0000"`），这在 Mapfile 语法中可能不被接受。设计文档要求统一使用 RGB 数组 `[R, G, B]` 是完全正确的决定。

**`to_mappyfile_dict()` 规则**：颜色字段统一输出为 `[R, G, B]` 整数数组。

---

### 2.4 投影：必须是数组（✅ 符合设计）

| 输入 | validate 结果 | dumps 输出 |
|------|--------------|-----------|
| `["init=epsg:3857"]` | ✓ | `PROJECTION "init=epsg:3857" END` |
| `"init=epsg:3857"` | ✗ | 同上（但 validate 报错） |
| `["proj=merc", "datum=WGS84"]` | ✓ | 多行 PROJECTION 块 |

**`to_mappyfile_dict()` 规则**：`projection` 字段必须保持数组格式，不可转为字符串。

---

### 2.5 Extent：必须是 4 元素数组（✅ 符合设计）

| 输入 | validate 结果 | 说明 |
|------|--------------|------|
| `[-180, -90, 180, 90]` | ✓ | 正确 |
| `"-180 -90 180 90"` | ✗ | 不接受字符串 |
| `[-180, -90, 180]` | ✗ | 太短（3元素）|
| `[-180, -90, 180, 90, 0]` | ✗ | 太长（5元素）|

**`to_mappyfile_dict()` 规则**：`extent` 字段必须保持 `[minx, miny, maxx, maxy]` 4 元素数组。

---

### 2.6 数组字段：必须是列表，不可省略（⚠️ 中等优先级）

| 字段 | 列表 ✓ | 单元素 dict ✗ | 错误信息 |
|------|--------|--------------|---------|
| `layers` | ✓ | ✗ | `is not of type 'array'` |
| `classes` | ✓ | ✗ | 同上 |
| `styles` | ✓ | ✗ | 同上 |
| `labels`（推断）| ✓ | ✗ | 同上 |

**关键场景**：用户添加第一个 LAYER 时，前端如果传 `layers: {...}` 而不是 `layers: [{...}]`，validate 会失败。

**`to_mappyfile_dict()` 规则**：序列化前检查 `layers`/`classes`/`styles`/`labels`，如果是 dict 则包装为 `[dict]`。

---

### 2.7 METADATA：完全自由，最宽容的区域（✅ 无需处理）

| 测试 | validate 结果 | 说明 |
|------|--------------|------|
| `metadata: {"wms_title": "My Map"}` | ✓ | 标准用法 |
| `metadata: {}` | ✓ | 空对象通过 |
| `metadata: {"wms_max_width": 4096}` | ✓ | 整数自动转字符串 |
| `metadata: {"my_custom_key": "value"}` | ✓ | 自定义属性通过 |

**结论**：METADATA 是 mappyfile schema 中的"自由区域"，任何键值对都被接受，值类型不限（会被自动 stringify）。这与自定义字段的严格形成鲜明对比。

**`to_mappyfile_dict()` 规则**：METADATA 无需特殊转换，直接透传。

---

### 2.8 缺字段检查：极宽松，不可依赖（⚠️ 重要发现）

| 场景 | validate 结果 | 说明 |
|------|--------------|------|
| MAP 缺 `name` | **✓ 通过** | ❗schema 未标记 required |
| LAYER 缺 `name` | **✓ 通过** | ❗同上 |
| LAYER 缺 `type` | ✗ 失败 | `'type' is a required property` |
| CLASS 缺 `name` | ✓ 通过 | 可选字段 |
| STYLE 空对象 `{}` | ✓ 通过 | 无必填检查 |
| LABEL 缺 `text` | ✓ 通过 | 无必填检查 |

**重大发现**：`mappyfile.validate()` **不检查 MAP.name 和 LAYER.name 的缺失**。这意味着第4层验证无法替代前3层的必填校验。我们的 `required.json` 和 `required_when` 规则仍然是必需的。

**设计影响**：`ValidationPipeline` 的前3层（alias → type → semantic）必须承担所有必填检查，不能把希望寄托在第4层 mappyfile validate。

---

### 2.9 自定义字段：零容忍（🔴 重大发现）

| 场景 | validate 结果 | 错误信息 |
|------|--------------|---------|
| MAP 加 `my_unknown_field` | ✗ | `does not match any of the regexes: '^__[a-z]+__$'` |
| LAYER 加 `my_custom` | ✗ | 同上 |
| MAP 加 `_custom` | ✗ | 同上（`_custom` 也不被接受）|
| LAYER 加 `dump` | ✗ | 同上（`DUMP` 是合法 MapServer 属性！）|

**矛盾点**：`mappyfile.dumps()` 能够正确输出未知字段（如 `DUMP TRUE`），但 `mappyfile.validate()` 会报错。

这意味着：
1. `dumps()` 比 `validate()` 更宽容
2. 如果我们让 `to_mappyfile_dict()` 展开 `_custom` 到父对象，第4层 validate 会对这些字段报错
3. 某些 MapServer 合法字段（如 `DUMP`）不在 mappyfile schema 中，会被误报

**解决方案**（需在 `ValidationPipeline` 第4层实现）：

```python
# 伪代码：第4层 validate 的错误过滤
mappyfile_errors = mappyfile.validate(mf_dict, version=8.4)
# 过滤 "未知字段" 类型的假阳性
filtered = [
    e for e in mappyfile_errors
    if not (
        "does not match any of the regexes" in str(e)
        and field_in_custom_allowed_or_object_fields(e.field)
    )
]
```

**`to_mappyfile_dict()` 规则**：
1. 展开 `_custom`：把 `{_custom: {key: {value, ...}}}` 提升为 `{key: value, ...}`，删除 `_custom` 容器
2. 保留 `custom_allowed.json` 和 `object-fields.json` 中列出的字段（dumps 能处理）
3. 但需在第4层 validate 时过滤这些字段导致的 regex 错误

---

### 2.10 dumps() 稳定性：100% 成功

62 个测试用例中，`mappyfile.dumps()` **从未抛出异常**，即使输入是 validate 明确拒绝的格式（如字符串 projection、布尔 status、dict 形式的 layers）。

| 输入 | dumps 结果 | 是否可用 |
|------|-----------|---------|
| `status: True` | `STATUS TRUE` | MapServer 可能接受，但非标准 |
| `projection: "init=epsg:3857"` | `PROJECTION "init=epsg:3857" END` | 结构正确，但语法可能有问题 |
| `layers: {...}` | 正常展开为 LAYER | 与列表形式输出完全一致 |

**结论**：`dumps()` 的容错能力极强，但输出不一定符合 MapServer 语法要求。**不能**因为 dumps 成功就认为配置正确。

---

## 三、`to_mappyfile_dict()` 强制变换规则清单

基于以上发现，`ConfigTree.to_mappyfile_dict()` 在把 `session.params` 交给 `mappyfile` 之前，必须执行以下变换：

| # | 变换 | 触发条件 | 目标 |
|---|------|---------|------|
| 1 | enum 布尔兜底 | `field_key in {"status"}` and `isinstance(value, bool)` | `"ON"` / `"OFF"` |
| 2 | 数组字段包装 | `key in ("layers","classes","styles","labels")` and `isinstance(value, dict)` | 包装为 `[value]` |
| 3 | PROJECTION 保持数组 | `key == "projection"` | 确保是 `list` |
| 4 | Extent 保持数组 | `key == "extent"` | 确保是 4 元素 `list` |
| 5 | 颜色保持 RGB 数组 | `value_type == "color"` | 确保是 `[R, G, B]` |
| 6 | `_custom` 展开 | `"_custom" in obj` | 提升子键到父对象，删除 `_custom` 容器 |
| 7 | `cache` 节点剥离 | `key == "cache"` | 不输出给 mappyfile（MapCache 单独生成）|

---

## 四、对 `ValidationPipeline` 的设计修正

### 4.1 第4层 `mappyfile.validate()` 的错误过滤策略

由于 mappyfile 对未知字段零容忍，但 dumps 能正常处理这些字段，第4层需要过滤以下**假阳性错误**：

| 错误模式 | 原因 | 处理方式 |
|----------|------|----------|
| `does not match any of the regexes: '^__[a-z]+__$'` | 字段不在 mappyfile schema 中 | 检查该字段是否在 `custom_allowed` 或 `object_fields` 中，是则忽略 |
| `'type' is a required property`（LAYER） | LAYER 缺 type | ✅ **保留**，这是真正的错误 |
| `is too short` / `is too long`（EXTENT） | 元素数量不对 | ✅ **保留** |
| `is not of type 'array'`（PROJECTION/SIZE/EXTENT） | 类型错误 | ✅ **保留** |
| `is not of type 'string'`（STATUS 等布尔） | 布尔值未转换 | ✅ **保留**（应在第2层就拦截）|

### 4.2 必填校验不可下放

`mappyfile.validate()` **不检查**以下字段的缺失：
- MAP 的 `name`
- LAYER 的 `name`
- CLASS 的 `name`
- STYLE 的任何字段
- LABEL 的 `text`

因此，所有必填/条件必填规则必须在 `ValidationPipeline` 的第3层（semantic）完成，**不能**指望第4层兜底。

### 4.3 层级分工调整建议

| 层级 | 负责内容 | 不变 / 需调整 |
|------|---------|--------------|
| L1 Alias 解析 | 自然语言 → 参数值 | 不变 |
| L2 Type 校验 | Pydantic 类型、enum、范围 | **增加**：boolean 预检（True/False → ON/OFF） |
| L3 Semantic | `required.json` + `dependencies.json` | **强化**：补充 MAP.name、LAYER.name 的必填校验 |
| L4 mappyfile | `mappyfile.validate()` + 错误过滤 | **新增**：过滤 `custom_allowed` 导致的 regex 错误 |

---

## 五、对 `generate_rules.py` / 模板文件的修正建议

### 5.1 `object-fields.json` 补充

测试发现 `DUMP` 是 MapServer 合法属性但不在 mappyfile schema 中。需要审计 `object-fields.json`，确保常见 MapServer 属性已被覆盖。

已知缺失（待补充）：
- LAYER: `dump`
- 其他待审计...

### 5.2 `custom-allowed.json` 的用途澄清

`custom-allowed.json` 当前用于 `generate_rules.py` 生成规则时的白名单。但 mappyfile validate 不读我们的规则，所以该白名单的实际作用是：
1. 告诉前端这些字段可以显示在 UI 中
2. 告诉 `ValidationPipeline` 第4层：这些字段导致的 regex 错误是假阳性，应过滤

### 5.3 `defaults-override.json` — 无需修改

验证确认现有默认值全部正确：
- `status: "on"` → 小写通过 validate，dumps 输出大写 `STATUS ON`
- `antialias: true` / `partials: false` → JSON boolean 对应 Python `True`/`False`，schema 类型为 `boolean`，validate 通过

---

## 六、验证脚本与原始数据

- **测试脚本**：`SourceCode/spike/v1_mappyfile_validate.py`（62 个用例）
- **机器可读结果**：`SourceCode/spike/v1_result.json`
- **本报告**：`SourceCode/spike/v1_result.md`

---

## 七、Go / No-go 判定

| 条件 | 状态 | 说明 |
|------|------|------|
| mappyfile 可用 | ✅ **Go** | `dumps()` 100% 可靠，输出格式正确 |
| `validate()` 可用 | ⚠️ **Go with caution** | 可用，但必须配合错误过滤 + 前3层必填校验 |
| 需要架构调整 | 🔴 **是** | `to_mappyfile_dict()` 需增加6条强制变换规则；`ValidationPipeline` 第4层需增加假阳性过滤 |

**结论**：V1 验证通过，但需要在正式编码前把本报告的变换规则和错误过滤策略落实到 `Document/技术细节.md` 和代码实现中。
