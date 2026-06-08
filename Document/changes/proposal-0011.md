# Proposal-0011: QAPanel 块提问 UX 修复 + ObjectCard 焦点交互拆分

> **类型**: Type-D（技术债 — 实现与需求体验不一致）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Spec**: F-M2.2（用户可选中属性/对象节点后提问）
> **影响范围**:
> - `frontend/src/components/ObjectCard.vue` — 拆分 toggle 与 focus 交互
> - `frontend/src/components/QAPanel.vue` — 区分对象/属性路径的 UI 文案与快捷问题
> - `frontend/src/components/FieldEditor.vue` — focus 交互一致性（可选，保持现状）

---

## 目标

修复两个 UX 问题，使"块提问"（选中对象节点后提问）的体验与"参数提问"清晰区分：

1. **ObjectCard 交互拆分**：当前点击对象头同时做展开/折叠 + 设焦点，用户只感知到前者。需要将 toggle（折叠状态）与 focus（焦点状态）拆分为两个独立交互区域。
2. **QAPanel 路径类型感知**：当前 focus_param 无论是对象路径（`layers.0`）还是属性路径（`layers.0.name`），UI 文案和快捷问题都按"参数"风格展示。需要区分两者，对象路径展示"块级"文案。

**原则**：
- 纯前端 UX 改动，不修改后端 WS 消息格式
- 不修改后端 prompt 组装逻辑（已有完整 map snapshot + focus_param）
- 全部现有测试零回归

---

## 变更内容

### [MODIFIED] `frontend/src/components/ObjectCard.vue`

**拆分 toggle 与 focus 的触发区域**：

当前实现（问题）：
```
.tree-obj-header (整个头) @click="toggle"
  └── toggle() { expanded = !expanded; send focus_change }
```

目标实现：
```
.tree-obj-header (除 toggle 外的主体区域) @click="setFocus"
  ├── .tree-toggle (18×18 按钮区域) @click.stop="toggleExpanded"
  ├── .tree-obj-icon
  ├── .tree-obj-name / .tree-obj-index
  └── .tree-obj-actions (hover 显示)
```

具体改动：
- 将 `.tree-toggle` 从纯文本装饰改为独立可点击区域，阻止冒泡（`@click.stop`）
- `.tree-obj-header` 的 `@click` 仅发送 `focus_change`，不再切换 `expanded`
- 保持 `selected` 样式（`inset 3px 0 0 #627d98`）作为焦点视觉反馈 —— 当前已有，但需确保对象节点选中态足够明显
- 对象节点的 `selected` 态与属性行的 `focused` 态视觉上需保持一致的语言

### [MODIFIED] `frontend/src/components/QAPanel.vue`

**增加路径类型判断，区分对象路径与属性路径**：

#### 1. 新增辅助函数 `resolveFocusLabel(path)`

```ts
function resolveFocusLabel(path: string | null): { label: string; isObject: boolean } {
  if (!path) return { label: '', isObject: false }
  // 对象路径特征：以对象类型名结尾（如 layers.0, web, map, layers.0.classes.0）
  // 属性路径特征：最后一节是字段名（如 layers.0.name）
  const parts = path.split('.')
  const last = parts[parts.length - 1]
  const isIndex = /^\d+$/.test(last)        // e.g. "0" in "layers.0"
  const isObjectType = ['map', 'web', 'metadata', 'cache'].includes(last.toLowerCase())
  const isObject = isIndex || isObjectType   // 对象节点路径

  if (isObject) {
    // 生成友好标签：layers.0 → "LAYER #1", web → "WEB"
    const typeMap: Record<string, string> = {
      map: 'MAP', layers: 'LAYER', classes: 'CLASS',
      styles: 'STYLE', labels: 'LABEL', web: 'WEB',
      metadata: 'METADATA', cache: 'CACHE',
    }
    for (let i = parts.length - 1; i >= 0; i--) {
      const t = typeMap[parts[i].toLowerCase()]
      if (t) {
        const idx = isIndex ? ` #${parseInt(last, 10) + 1}` : ''
        return { label: `${t}${idx}`, isObject: true }
      }
    }
    return { label: path, isObject: true }
  }

  // 属性路径
  return { label: path, isObject: false }
}
```

#### 2. 焦点条文案适配

| 路径类型 | 当前文案 | 目标文案 |
|---------|---------|---------|
| 对象 (`layers.0`) | `🔍 layers.0` | `🔍 LAYER #1` |
| 属性 (`layers.0.name`) | `🔍 layers.0.name` | `🔍 layers.0.name`（保持）|
| 无焦点 | `💡 点击左侧树节点或参数...` | `💡 点击左侧树节点或参数，可针对该节点/参数提问` |

#### 3. Placeholder 适配

| 路径类型 | 当前 placeholder | 目标 placeholder |
|---------|-----------------|-----------------|
| 对象 | `针对 layers.0 提问...` | `针对 LAYER #1 提问...` |
| 属性 | `针对 layers.0.name 提问...` | 保持 |

#### 4. 快捷问题适配

**对象路径**（当前不合理，需重写）：
```ts
// 当前：name = "0" → 「0」怎么填？ ❌
// 目标：
[
  `「LAYER #1」还需要配置什么？`,
  `「LAYER #1」有哪些必填字段？`,
  `「LAYER #1」的最佳实践是什么？`,
]
```

**属性路径**（当前合理，保持）：
```ts
[
  `「name」怎么填？`,
  `「name」有哪些可选值？`,
  `「name」的最佳实践是什么？`,
]
```

**无焦点**（保持）：
```ts
[
  '帮我检查一下当前配置',
  '导出前还需要配置什么？',
  '当前配置有什么潜在问题？',
]
```

#### 5. 空状态文案适配

| 路径类型 | 当前 | 目标 |
|---------|------|------|
| 对象 | `针对当前焦点参数提问...` | `针对当前 LAYER #1 提问，或输入任意问题` |
| 属性 | `针对当前焦点参数提问...` | 保持 |

### [UNCHANGED] 后端行为

后端以下逻辑**无需修改**，当前已正确支持块提问：
- `_handle_focus_change` 接收任意 path（对象/属性均可）
- `_build_map_snapshot()` 始终输出完整 params，LLM 可看到对象完整内容
- `_build_context_summary()` 根据路径推断对象类型（`layers.0` → `LAYER`），返回该对象字段定义摘要
- `_framework.j2` 注入 `focus_param = "layers.0"`，LLM 明确知晓关注点

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| 点击 toggle 箭头 | 手动 | 仅展开/折叠，不触发 focus_change |
| 点击对象头主体 | 手动 | 发送 focus_change，对象头显示 selected 态 |
| 对象路径焦点条 | 手动 | 显示 `LAYER #1` / `CLASS #1` 等友好标签 |
| 属性路径焦点条 | 手动 | 显示完整路径如 `layers.0.name` |
| 对象路径快捷问题 | 手动 | 显示块级提问（如"还需要配置什么"） |
| 属性路径快捷问题 | 手动 | 显示参数级提问（如"怎么填"） |
| 切换焦点类型 | 手动 | 对象→属性、属性→对象时文案正确切换 |
| 回归 | `npm test` | 43 前端测试全部通过 |

---

## 验收标准

- [x] 点击 `.tree-toggle` 仅切换展开/折叠，不设置焦点
- [x] 点击对象头主体（除 toggle 和操作按钮外）设置焦点，并显示 selected 态
- [x] 对象路径（`layers.0`）在焦点条显示友好标签（`LAYER #1`）
- [x] 属性路径（`layers.0.name`）在焦点条显示完整路径
- [x] 对象路径的快捷问题是块级风格（"还需要配置什么"/"必填字段"/"最佳实践"）
- [x] 属性路径的快捷问题是参数级风格（"怎么填"/"可选值"/"最佳实践"）
- [x] 全部前端测试通过（58/58）

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `ObjectCard.vue` | 拆分 toggle 与 focus 触发区域：`.tree-toggle` 添加 `@click.stop="toggleExpanded"` 仅切换展开/折叠；`.tree-obj-header` 的 `@click` 改为 `setFocus` 仅发送 `focus_change`；提取 `toggleExpanded()` 和 `setFocus()` 两个独立函数 |
| `QAPanel.vue` | 新增 `resolveFocusLabel()` 辅助函数，区分对象路径（`layers.0` → `LAYER #1`）与属性路径（`layers.0.name`）；焦点条、placeholder、快捷问题、空状态文案、bot 消息 focus tag 全部适配路径类型；对象路径显示块级提问，属性路径显示参数级提问 |
| `ObjectCard.spec.ts` | 新增 4 个测试：toggle 箭头不触发 focus_change、header 点击触发 focus_change 且不折叠、selected 态匹配/不匹配验证；修复 mock hoisting 问题（`vi.mock` 工厂内不引用外部变量） |
| `QAPanel.spec.ts` | 新增 11 个测试：对象路径友好标签（LAYER/CLASS/MAP）、块级快捷问题、块级 placeholder；属性路径完整标签、参数级快捷问题、参数级 placeholder；无焦点默认状态 |

## 依赖

- proposal-0004（ConfigSession + focus_change 消息基线）
- proposal-0007（QAPanel + WS 问答链路）
- proposal-0009（ObjectCard 折叠动画 + hover 操作基线）
- proposal-0010（UI 布局/字体/样式基线）

---

*Implemented: 2026-06-08 — TDD 流程（RED → GREEN），58 前端测试全部通过*
