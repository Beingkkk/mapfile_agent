# Proposal-0013: 必填项语义分层与UI三档筛选

> **类型**: Type-B（设计变更）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Spec**: F-M1.2（配置树字段筛选与图例）
> **影响范围**:
> - `data/templates/required.json` — 三层语义重新划分
> - `scripts/generate_rules.py` — 字段定义输出 `required_when`
> - `backend/core/template_mapper.py` — `FieldDescriptor` 新增 `required_when`
> - `backend/core/config_tree.py` — 序列化传递 `required_when`
> - `frontend/src/types/tree.ts` — `TreeLeaf` 类型扩展
> - `frontend/src/stores/ui.ts` — 三档 `showMode`
> - `frontend/src/components/ObjectCard.vue` — 三档过滤逻辑
> - `frontend/src/components/FieldEditor.vue` — 指示器区分 `*` / `◆`
> - `frontend/src/components/ConfigTreePanel.vue` — 三档按钮 + 六项图例
> - `Document/模板说明.md` — §3.2 / §5.3 / 附录 C 文档化

---

## 背景与动机

### 问题

1. `required` 与 `business_required` 在 `FieldDescriptor.required` 中被合并，UI 上统一渲染为红色 `*`，用户无法区分"不填就报错"和"不填也能跑"。
2. `business_required` 中混入了大量已有默认值的字段（`MAP.imagetype=png`、`LAYER.status=on`、`METADATA.ows_enable_request=*` 等），导致"仅必填"模式下字段过多。
3. 真正"不填就无法工作"的字段（如 `MAP.extent`）未被标记，用户填完"必填"后导出 Mapfile 仍然不可用。

### 调研结论

经 MapServer 8.6.3 源码验证（详见 `Document/模板说明.md` 附录 C）：

- **语法绝对必填**：仅 `LAYER.type`（`mapfile.c:4544` 明确检查 `"Layer type not set."`）
- **服务级必填**：WMS/WFS/WCS 的 `title`（`mapwms.cpp:3697` `"Layer Name is optional but title is mandatory."`）
- **条件必填**：`connection`（`connectiontype in ['postgis','ogr','wms']` 时）、`data`（`connectiontype == 'local'` 时）

---

## 设计变更

### 1. `required.json` 三层语义重新划分

| 层级 | 定义 | 当前内容（变更后） |
|------|------|-------------------|
| `required` | 语法绝对必填，不填则 MapServer `loadXXX()` 返回 `MS_FAILURE` | `LAYER.type`, `CACHE.type` |
| `business_required` | 无默认值且业务上必须用户显式填写 | **全部清空**（原有字段均有默认值） |
| `required_when` | 条件必填，满足特定条件时不填产生 `OWS_WARN` 或阻塞 | `METADATA.ows_title`, `LAYER.connection`, `LAYER.data`, `STYLE.symbol/size/width/outlinecolor` 等 |

**关键修正**：
- 从 `business_required` 中移除所有已有默认值的字段
- `LAYER.name` / `MAP.name` 从 `required` 中移除（不是语法必填）
- `METADATA.ows_title` / `ows_onlineresource` 从 `business_required` 移入 `required_when`

### 2. `required_when` 字段贯通数据流

```
generate_rules.py          template_mapper.py          config_tree.py
    │                           │                            │
    ▼                           ▼                            ▼
字段定义添加               FieldDescriptor 新增         serialize() 输出
"required_when": "..."    required_when: str|None      "required_when": "..."
```

### 3. 前端三档筛选模式

| 模式 | 按钮文字 | 显示条件 | 对应语义 |
|------|---------|---------|---------|
| `all` | 全部 | 所有字段 | — |
| `required` | 建议填 | `required === true` 或 `required_when` 不为空 | 语法必填 + 条件必填（建议用户关注） |
| `strict` | 仅必填 | `required === true` 且 `!required_when` | 语法绝对必填 |

### 4. 图例扩展为六项

```
* 必填（语法绝对必填）  ◆ 条件（满足条件时必填）  D 默认  ○ 可选  → 推导  ✎ 自定义
```

---

## 变更内容

### [MODIFIED] `data/templates/required.json`

**变更前**（问题状态）：
```json
"MAP": { "business_required": ["imagetype", "status"] },
"LAYER": { "required": ["name", "type"], "business_required": ["connectiontype", "projection", "status"] },
"METADATA": { "business_required": ["ows_title", "ows_onlineresource", "ows_enable_request"] }
```

**变更后**（对齐调研结论）：
```json
"MAP": { "required": [], "business_required": [], "required_when": {} },
"LAYER": {
  "required": ["type"],
  "business_required": [],
  "required_when": {
    "connection": "connectiontype in ['postgis', 'ogr', 'wms']",
    "data": "connectiontype == 'local'",
    "name": "len(session.service_types) > 0"
  }
}
```

### [MODIFIED] `scripts/generate_rules.py`

- `build_object_type_rules()`: 字段定义中新增 `"required_when"`
- 调整 `required_cfg` 加载顺序（提前到循环前，供字段定义引用）

### [MODIFIED] `backend/core/template_mapper.py`

- `FieldDescriptor` 新增 `required_when: str | None = None`
- `get_field_descriptor()`: 从字段定义中读取并设置 `required_when`

### [MODIFIED] `backend/core/config_tree.py`

- `_serialize_child()`: 输出 `"required_when": desc.required_when`

### [MODIFIED] `frontend/src/types/tree.ts`

```ts
export interface TreeLeaf {
  // ...existing fields...
  required_when?: string;  // ← 新增
}
```

### [MODIFIED] `frontend/src/stores/ui.ts`

```ts
interface UIState {
  showMode: 'all' | 'required' | 'strict';  // ← 扩展为三档
}
```

### [MODIFIED] `frontend/src/components/ObjectCard.vue`

```ts
// visibleChildren 过滤逻辑
if (uiStore.showMode === 'required') {
  return leaf.required === true || (leaf.required_when && leaf.required_when.length > 0)
}
// strict mode
return leaf.required === true && !leaf.required_when
```

### [MODIFIED] `frontend/src/components/FieldEditor.vue`

指示器逻辑区分 `*`（语法必填）和 `◆`（条件必填）：
```ts
if (props.leaf.required && !props.leaf.required_when) return '*'
if (props.leaf.required_when) return '◆'
```

### [MODIFIED] `frontend/src/components/ConfigTreePanel.vue`

- 三个筛选按钮：全部 / 建议填 / 仅必填
- 图例从五项扩展为六项（新增 `◆ 条件`）

### [MODIFIED] `Document/模板说明.md`

- §3.2 重写为三层语义定义（含源码验证摘录）
- §5.3 更新为正确/错误示例
- 新增附录 C：完整探究结论

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| `generate_rules.py` 输出包含 `required_when` | 单元测试 | `TestBuildObjectTypeRules::test_required_rules_in_output` ✅ |
| `TemplateMapper` 返回 `required_when` | 单元测试 | `test_returns_descriptor_for_known_field` ✅ |
| `ConfigTree.serialize()` 包含 `required_when` | 单元测试 | `TestConfigTreeBuildSimple` ✅ |
| 三档筛选模式切换 | 手动 / 单测 | `all`→`required`→`strict` 字段数量递减 |
| 语法必填字段显示 `*` | 手动 | `LAYER.type` 显示红色 `*` |
| 条件必填字段显示 `◆` | 手动 | `LAYER.connection` 显示橙色 `◆` |
| 图例六项完整 | 手动 | `*必填 ◆条件 D默认 ○可选 →推导 ✎自定义` |
| 回归 | `pytest tests/unit/` | 188 passed |
| 回归 | `npm test -- --run` | 73 passed |

---

## 验收标准

- [x] `required.json` 中 `business_required` 不再包含有默认值的字段
- [x] `LAYER.name` / `MAP.name` 不在 `required` 中
- [x] `mapguide_rules.json` 字段定义包含 `required_when`
- [x] 前端 `TreeLeaf` 类型包含 `required_when`
- [x] UI 支持三档筛选（全部 / 建议填 / 仅必填）
- [x] 图例显示六项（含 `◆ 条件`）
- [x] `FieldEditor` 指示器正确区分 `*` 和 `◆`
- [x] 全部后端测试通过（188/188）
- [x] 全部前端测试通过（73/73）
- [x] 有 `default` 的字段在初始化时自动回填到 `params`
- [x] 非必填字段值为 `None` 时不触发 L2 类型错误
- [x] 导出序列化时过滤 `None` 值，不写入 Mapfile

---

## 追加记录（Amendment）

> **日期**: 2026-06-08
>
> 验收过程中发现：`mappyfile.create("map")` 给大量字段初始化为 `None`，其中部分字段在 `mapguide_rules.json` 中没有 `default` 定义，导致校验仍报错。
>
> 追加修复（Type-C）：
> 1. `generate_rules.py` 字段定义补回 `"required": true/false`，使 `FieldDescriptor.required` 正常工作
> 2. `ValidationPipeline._check_type()` 对非必填字段的 `None` 跳过类型检查
> 3. `ConfigTree._filter_and_expand()` 导出时过滤 `None` 键值对
> 4. `ConfigTree._build_tree()` 对缺失或显式 `None` 的字段回填 `default`
>
> 修复后空 session 校验错误从 33 条降至 0 条。

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `data/templates/required.json` | 三层语义重新划分，清空 `business_required` |
| `scripts/generate_rules.py` | 字段定义输出 `required_when` |
| `backend/core/template_mapper.py` | `FieldDescriptor.required_when` |
| `backend/core/config_tree.py` | 序列化输出 `required_when` |
| `frontend/src/types/tree.ts` | `TreeLeaf.required_when` |
| `frontend/src/stores/ui.ts` | `showMode: 'all' \| 'required' \| 'strict'` |
| `frontend/src/components/ObjectCard.vue` | 三档过滤逻辑 |
| `frontend/src/components/FieldEditor.vue` | `*` / `◆` 指示器区分 |
| `frontend/src/components/ConfigTreePanel.vue` | 三档按钮 + 六项图例 |
| `Document/模板说明.md` | §3.2 / §5.3 / 附录 C 更新 |

---

## 依赖

- proposal-0004（ConfigTree + ConfigSession）
- proposal-0009（Electron 打包 + 前端组件结构）

## 后续可扩展

- `functional_required` 概念：UI 橙色标记（如 `MAP.extent`），表示"不填不会报错但功能不完整"
- `required_when` 运行时条件评估：当前仅静态传递条件表达式，未来可在 L3 验证后将触发的条件必填实时反馈到前端筛选

---

*Proposed: 2026-06-08*  
*Implemented: 2026-06-08*
