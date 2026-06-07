# Plan: Frontend (Vue 3)

> **模块**：前端用户界面
> **版本**：v1.0.0（SDD 采纳基线）
> **状态**：LOCKED — 变更需通过 proposal 流程
> **对应 spec**：`spec.md` §3.1 F-M1, F-M2
> **对应 design**：`design/frontend-backend-contract.md`, `design/conventions.md` §13.2
> **对应原型**：`Document/UX/ui-prototype-interactive-v2.html`
> **前置依赖**：`plan-platform` DC-062~064（WebSocket 契约定义）

---

## 1. 模块概述

前端采用 Vue 3 + Naive UI + Pinia，提供两栏布局：左侧配置树（55%）+ 右侧问答面板（45%）。通过 WebSocket 与后端保持实时同步。

**核心设计**：自定义分层渲染，不使用 Naive UI 的 `n-tree`。对象节点用 `ObjectCard` 递归渲染，属性叶子用 `FieldEditor` 按 `value_type` 分发控件。

**V3 已验证**：280 节点、4 层嵌套、7 种 `value_type` 控件映射全部通过。

**包含内容**：
- `frontend/src/components/` — Vue 组件
- `frontend/src/stores/` — Pinia stores
- `frontend/src/services/ws.ts` — WebSocket client
- `frontend/src/types/` — TypeScript 类型

---

## 2. 设计约束

| 约束 | 来源 |
|------|------|
| **禁用 `n-tree`**，自定义分层渲染 | `constitution.md` §3 技术栈锁定 |
| Naive UI 仅提供表单控件 | `conventions.md` §13.2 |
| 两栏布局：左 55% / 右 45% | `spec.md` §2 |
| WebSocket 是唯一通信通道 | `constitution.md` §4.1 |
| 颜色格式：RGB 数组，无 hex | `constitution.md` §4.4 |
| V3 验证：280 节点 4 层嵌套无卡顿 | `spike/v3_result.md` |
| 响应式：≤900px 收起 QAPanel，≤600px 底部输入 | `spec.md` §3.2 F-S2 |

---

## 3. 接口定义

### 3.1 TypeScript 类型

```typescript
// DC-022: types/tree.ts

interface TreeNode {
  id: string;
  path: string;
  object_type: 'MAP' | 'LAYER' | 'CLASS' | 'STYLE' | 'LABEL' | 'WEB' | 'METADATA' | 'CACHE';
  children: (TreeNode | TreeLeaf)[];
  expanded: boolean;
}

interface TreeLeaf {
  id: string;
  path: string;
  key: string;
  value: any;
  value_type: 'string' | 'enum' | 'integer' | 'float' | 'boolean' | 'color' | 'array' | 'expression';
  phase: 'datasource' | 'style' | 'service' | 'cache';
  required: boolean;
  derived: boolean;
  default?: any;
  enum?: any[];
  custom: boolean;
  custom_desc?: string;
  user_modified: boolean;
  errors: string[];
}

interface WSMessage {
  type: string;
  [key: string]: any;
}

interface ValidationError {
  path: string;
  message: string;
}
```

### 3.2 Pinia Stores

```typescript
// DC-023: stores/session.ts

interface SessionState {
  params: any;
  validation_state: 'idle' | 'checking' | 'pass' | 'fail';
  validation_errors: ValidationError[];
  focus_param: string | null;
  service_types: string[];
  mapcache_enabled: boolean;
  can_export: boolean;
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({...}),
  actions: {
    applyTreeState(payload: any): void;
    setFocus(path: string | null): void;
    setServiceTypes(services: string[], mapcache: boolean): void;
  }
});

// DC-024: stores/ui.ts

interface UIState {
  showMode: 'all' | 'required';
  expandedNodes: Set<string>;
  qaMessages: QAMessage[];
  qaRoundCount: number;
  qaFocusParam: string | null;
}

export const useUIStore = defineStore('ui', {
  state: (): UIState => ({...}),
  actions: {
    setShowMode(mode: 'all' | 'required'): void;
    toggleNode(id: string): void;
    addQAMessage(msg: QAMessage): void;
    clearQA(): void;
  }
});
```

### 3.3 WebSocket Service

```typescript
// DC-025: services/ws.ts

class WebSocketService {
  connect(url: string): void;
  disconnect(): void;
  get isConnected(): boolean;
  send(message: WSMessage): void;
  on(type: string, handler: (payload: any) => void): () => void;
  private reconnect(): void;
  private startHeartbeat(): void;
  private stopHeartbeat(): void;
}

export const ws = new WebSocketService();
```

### 3.4 组件

```typescript
// DC-026: components/ConfigTreePanel.vue
// 职责：左栏容器（工具栏 + 图例 + 树内容 + 状态栏）

// DC-027: components/ObjectCard.vue
interface ObjectCardProps {
  node: TreeNode;
  depth: number;
}

// DC-028: components/FieldEditor.vue
interface FieldEditorProps {
  leaf: TreeLeaf;
}

// DC-029: components/QAPanel.vue
// 职责：右栏问答面板

// DC-030: components/CustomPropModal.vue
interface CustomPropModalProps {
  parentPath: string;
  visible: boolean;
}
```

---

## 4. 数据流

### 4.1 用户编辑字段

```
FieldEditor onBlur
  → emit('update', { path, value })
  → ws.send({ type: 'tree_update', updates: [{path, value}] })
  → 后端处理
  → WS: tree_state { params_snapshot, validation_state, errors }
  → sessionStore.applyTreeState()
  → 组件重新渲染
```

### 4.2 用户提问

```
QAPanel 输入框 onSubmit
  → ws.send({ type: 'question', text })
  → 后端处理
  → WS: qa_result { bot_message, params_update, ... }
  → uiStore.addQAMessage({ role: 'bot', text })
  → 如果有 params_update → sessionStore.applyTreeState()
```

### 4.3 切换关注点

```
FieldEditor / ObjectCard onClick
  → ws.send({ type: 'focus_change', path })
  → 后端处理
  → WS: focus_state { focus_param }
  → uiStore.clearQA()
  → uiStore.qaRoundCount = 0
```

---

## 5. 测试策略

### 5.1 单元测试（Vitest）

| DC 编号 | 测试文件 | 关键用例 |
|---------|----------|----------|
| DC-022 | `types/tree.spec.ts` | TreeNode/TreeLeaf 类型校验 |
| DC-023 | `stores/session.spec.ts` | applyTreeState、setFocus、setServiceTypes |
| DC-024 | `stores/ui.spec.ts` | showMode 切换、节点展开、QA 消息管理 |
| DC-025 | `services/ws.spec.ts` | Mock WebSocket、消息收发、断线重连 |
| DC-026 | `components/ConfigTreePanel.spec.ts` | 渲染、模式切换 |
| DC-027 | `components/ObjectCard.spec.ts` | 递归渲染、展开折叠 |
| DC-028 | `components/FieldEditor.spec.ts` | 7 种 value_type 控件渲染、事件触发 |
| DC-029 | `components/QAPanel.spec.ts` | 消息列表、输入提交、轮次计数 |
| DC-030 | `components/CustomPropModal.spec.ts` | 模态框交互、表单验证 |

### 5.2 E2E 测试（Playwright，可选）

| 场景 | 说明 |
|------|------|
| 完整编辑流 | 打开 → 填参 → 校验 → 导出 |
| LLM 问答流 | 提问 → 收到回答 → 参数更新 |
| 导入导出流 | 导入 .map → 修改 → 导出 |

---

## 6. 任务清单

### Phase 1: 骨架（TDD）

- [ ] [RED] `types/tree.spec.ts` — TreeNode/TreeLeaf 类型校验
- [ ] [GREEN] `types/tree.ts` — 类型定义
- [ ] [RED] `stores/session.spec.ts` — applyTreeState、setFocus
- [ ] [GREEN] `stores/session.ts` — SessionStore
- [ ] [RED] `stores/ui.spec.ts` — showMode、expandedNodes
- [ ] [GREEN] `stores/ui.ts` — UIStore
- [ ] [RED] `services/ws.spec.ts` — Mock WS 连接、消息收发
- [ ] [GREEN] `services/ws.ts` — WebSocketService
- [ ] [REFACTOR] Store 间解耦

### Phase 2: 核心组件（TDD）

- [ ] [RED] `FieldEditor.spec.ts` — 各 value_type 渲染 + 事件
- [ ] [GREEN] `FieldEditor.vue` — 7 种控件分发
- [ ] [RED] `ObjectCard.spec.ts` — 递归渲染、展开折叠
- [ ] [GREEN] `ObjectCard.vue` — 对象节点卡片
- [ ] [RED] `ConfigTreePanel.spec.ts` — 整合渲染
- [ ] [GREEN] `ConfigTreePanel.vue` — 左栏容器
- [ ] [REFACTOR] 提取通用样式变量

### Phase 3: 辅助组件（TDD）

- [ ] [RED] `QAPanel.spec.ts` — 消息列表、输入提交
- [ ] [GREEN] `QAPanel.vue` — 问答面板
- [ ] [RED] `CustomPropModal.spec.ts` — 模态框交互
- [ ] [GREEN] `CustomPropModal.vue` — 自定义属性模态框
- [ ] [REFACTOR] 组件间 props 优化

### Phase 4: 前后端贯通

- [ ] [RED] 集成测试 — 完整 WS 消息流
- [ ] [GREEN] App.vue 两栏布局 + WS 初始化
- [ ] [GREEN] 响应式断点适配（≤900px / ≤600px）
- [ ] [REFACTOR] 性能优化（大节点虚拟滚动预留）

---

## 7. 已知技术债

| 位置 | 说明 | 优先级 |
|------|------|--------|
| `spike/v3_result.md` | V3 为原生 HTML/JS 原型，非 Vue 组件 | 中 — Phase 2 需迁移 |
| `Document/UX/ui-prototype-interactive-v2.html` | 原型图为设计参考 | 低 — 保留为视觉参考 |
| 响应式布局 | ≤900px/≤600px 断点尚未实现 | 中 — Phase 4 处理 |
| E2E 测试 | Playwright 未配置 | 低 — MVP 后补充 |

---

*锁定日期：2026-06-07。变更请提交 `changes/proposal-{NNNN}.md`。*
