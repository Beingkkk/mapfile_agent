# Proposal-0010: 前端 UI 与原型差距修复

> **类型**: Type-D（技术债 — 实现与原型不一致）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Plan**: `plan-frontend`
> **影响范围**:
> - `frontend/src/components/ConfigTreePanel.vue` — 布局重构、字体调整
> - `frontend/src/components/ObjectCard.vue` — 折叠动画、添加按钮位置、hover 操作
> - `frontend/src/components/FieldEditor.vue` — 字体调整
> - `frontend/src/stores/ui.ts` — showMode 状态消费（已有，需连接渲染层）

---

## 目标

修复前端实现与 `Document/UX/ui-prototype-interactive-v2.html` 原型的 5 项差距：

1. **字体偏小**：输入框/图例/服务类型/工具栏统一放大到原型规格
2. **导出/校验按钮位置**：从 toolbar 内混排改为 header 右侧独立 actions 区域
3. **折叠/展开按钮动画**：纯文本切换改为带 rotate 动画的按钮区域
4. **showMode 过滤不生效**：`uiStore.showMode` 已存储但未在渲染层消费
5. **添加/自定义按钮位置模糊**：从 header 行内移到子列表底部，hover 显示节点操作

**原则**：
- 纯 UI 层改动，不修改后端数据流
- 保持现有 WS 消息格式不变
- 全部现有测试零回归

---

## 变更内容

### [MODIFIED] `frontend/src/components/ConfigTreePanel.vue`

**布局重构**（参考原型 `.panel-header` + `.legend-bar` 分层）：
- `panel-header` 改为 `justify-content: space-between`：左侧标题，右侧 actions（校验/导出 icon 按钮）
- 抽出 `service-type-bar` 作为 header 下方**独立一行**（原型结构）
- 抽出 `showmode-toggle` + `legend` 合并为**图例栏**（原型 `.legend-bar`）
- 导出/校验按钮从 12px 文本改为 14px 主操作按钮样式

**字体调整**：
- 输入框/选择框 13px → 14px
- 图例 12px → 13px
- 服务类型 checkbox 12px → 13px
- 工具栏按钮 12px → 13px

### [MODIFIED] `frontend/src/components/ObjectCard.vue`

**折叠按钮**：
- `.tree-toggle` 增加按钮区域样式（18×18）
- 增加 `transition: transform 0.15s`
- collapsed 时 `rotate(-90deg)` 动画

**showMode 过滤**：
- 注入 `uiStore`，`nodeChildren` 按 `showMode` + `leaf.required` 过滤
- `showMode === 'required'` 时隐藏 `required === false` 的叶子节点
- 节点（TreeNode）始终显示，不受 showMode 影响

**添加/自定义按钮位置**：
- "+ 添加" 从 header 行内移到**子节点列表底部**（有缩进）
- 文字明确化："+ 添加 LAYER"/"+ 添加 CLASS"/"+ 添加 STYLE" 等
- 使用虚线边框样式（原型 `.tree-add-btn`）
- 节点操作按钮（添加/删除）改为 **hover 时显示**（原型 `.tree-obj-actions` opacity 切换）
- "✎ 自定义" 按钮移到属性列表底部

### [MODIFIED] `frontend/src/components/FieldEditor.vue`

**字体调整**：
- input/select 13px → 14px
- req-indicator 13px → 原规格（required 14px，其余保持）

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| showMode=all | 手动 | 所有字段可见 |
| showMode=required | 手动 | 仅 `required=true` 的 leaf 可见，TreeNode 始终可见 |
| 折叠/展开 | 手动 | 点击 toggle 有旋转动画，子节点显示/隐藏 |
| 添加按钮 | 手动 | 仅 LAYER/CLASS/MAP 节点底部显示，文字明确 |
| 节点操作 | 手动 | hover header 时显示添加/删除 icon |
| 布局 | 手动 | header 标题左、actions 右；service-type 独立一行 |
| 回归 | `npm test` | 37 前端测试全部通过 |

---

## 验收标准

- [x] 字体大小与原型一致（输入框 14px、图例 13px 等）
- [x] 导出/校验按钮位于 panel-header 右侧独立区域
- [x] 折叠按钮有 rotate 旋转动画
- [x] "全部/仅必填" 切换有效，树结构按 required 过滤
- [x] 添加/自定义按钮位于子列表底部，hover 显示节点操作
- [x] 全部现有前端测试通过（43/43）

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `ObjectCard.vue` | 注入 `uiStore`/`sessionStore`；`visibleChildren` 按 `showMode` 过滤；折叠按钮加 `rotate` 动画；添加/自定义按钮移到子列表底部；节点操作（+ / ×）改为 hover 显示；增加 `nodeIndex`、`icon` 显示；增加 `canDelete` 逻辑 |
| `ConfigTreePanel.vue` | `panel-header` 改为 `space-between`（标题左、actions 右）；`service-type-bar` 独立一行；`legend-bar` 合并 showmode-toggle + 图例 + 状态 badge；字体统一 13px→14px（输入）、12px→13px（图例/服务类型） |
| `FieldEditor.vue` | 输入框/选择框 13px → 14px；增加 focus border/shadow transition |
| `ObjectCard.spec.ts` | 新增 Pinia 初始化（`beforeEach` + `setActivePinia`）；新增 showMode 过滤测试用例 |

---

## 依赖

- proposal-0009（Electron + ConfigTreePanel 基线）
- `ui-prototype-interactive-v2.html`（设计原型）

---

*Implemented by: SDD 流程 — proposal-0010 实施完成*
