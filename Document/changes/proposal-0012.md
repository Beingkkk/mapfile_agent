# Proposal-0012: QA 面板 LLM 处理中占位气泡

> **类型**: Type-B（设计变更 — 新增 UI 状态角色与交互）
> **状态**: IMPLEMENTED
> **日期**: 2026-06-08
> **对应 Spec**: F-M2.3（问答助手应提供清晰的状态反馈）
> **影响范围**:
> - `frontend/src/types/tree.ts` — 新增 `loading` 消息角色
> - `frontend/src/stores/ui.ts` — 新增 `startQALoading` / `finishQALoading` action
> - `frontend/src/services/ws.ts` — `qa_result` / `error` 分支管理 loading 状态
> - `frontend/src/components/QAPanel.vue` — 渲染 loading 气泡与超时处理

---

## 目标

解决用户发送问题后 LLM 处理期间的"黑箱"问题：
1. 用户发送问题后，QA 面板立即出现 LLM 占位气泡，明确告知"正在处理"。
2. 响应到达后，占位气泡平滑替换为真实回答。
3. 超时 / 错误 / 清空历史时安全移除占位，避免孤儿气泡。

**原则**：
- 纯前端设计变更，不修改后端 WS 消息格式，也不引入后端 LLM 流式输出。
- `loading` 角色为后续流式输出（`qa_stream_chunk`）预留扩展接口。
- 全部现有测试零回归。

---

## 变更内容

### [MODIFIED] `frontend/src/types/tree.ts`

扩展 `QAMessage.role`：

```ts
export interface QAMessage {
  role: 'user' | 'bot' | 'system' | 'divider' | 'loading';
  text: string;
  time?: string;
  focus_param?: string | null;
}
```

### [MODIFIED] `frontend/src/stores/ui.ts`

新增两个 action：

```ts
startQALoading() {
  // 防御重入：先移除已有 loading 气泡
  this.qaMessages = this.qaMessages.filter((m) => m.role !== 'loading')
  this.qaMessages.push({
    role: 'loading',
    text: '思考中…',
  })
},
finishQALoading(options?: { error?: string }) {
  this.qaMessages = this.qaMessages.filter((m) => m.role !== 'loading')
  if (options?.error) {
    this.qaMessages.push({
      role: 'system',
      text: options.error,
    })
  }
},
```

`addQAMessage` 的轮次计数仅统计 `user/bot`，`loading` 自动被排除，无需修改。

### [MODIFIED] `frontend/src/services/ws.ts`

`qa_result` 分支：
```ts
case 'qa_result':
  uiStore.finishQALoading()
  uiStore.addQAMessage({
    role: 'bot',
    text: msg.bot_message,
    focus_param: msg.focus_param ?? null,
  })
  // ...existing params_update handling
  break
```

`error` 分支（当前只有 `console.error`，补齐用户可见反馈）：
```ts
case 'error':
  console.error('[WS] Server error:', msg.message)
  uiStore.finishQALoading()
  uiStore.addQAMessage({
    role: 'system',
    text: `服务错误: ${msg.message}`,
  })
  break
```

### [MODIFIED] `frontend/src/components/QAPanel.vue`

#### 1. 模板增加 loading 分支

```vue
<template v-else-if="msg.role === 'loading'">
  <div class="msg-role">{{ roleIcon(msg.role) }}</div>
  <div class="msg-content">
    <div class="msg-text loading-bubble">
      <span class="loading-text">思考中</span>
      <span class="loading-dot" />
      <span class="loading-dot" />
      <span class="loading-dot" />
    </div>
  </div>
</template>
```

#### 2. `roleIcon` 增加 loading

```ts
function roleIcon(role: string): string {
  switch (role) {
    case 'user': return '👤'
    case 'bot': return '🤖'
    case 'system': return '⚠️'
    case 'loading': return '⏳'
    default: return '•'
  }
}
```

#### 3. `doSend` 启动 loading

```ts
function doSend(text: string) {
  isSending.value = true
  uiStore.addQAMessage({ role: 'user', text })
  uiStore.startQALoading()
  ws.send({ type: 'question', text })
  inputText.value = ''
}
```

#### 4. 超时处理

```ts
setTimeout(() => {
  if (isSending.value) {
    isSending.value = false
    uiStore.finishQALoading({
      error: '响应超时，请稍后重试或重新提问。',
    })
  }
}, 30000)
```

#### 5. 清空历史时清理 loading

```ts
function clearHistory() {
  ws.send({ type: 'clear_history' })
  uiStore.finishQALoading()
}
```

#### 6. 样式

新增 `.loading-bubble` 与跳动圆点动画：

```css
.msg.loading .msg-text {
  background: #fff;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.loading-dot {
  width: 6px;
  height: 6px;
  background: #9ca3af;
  border-radius: 50%;
  animation: loading-bounce 1.4s infinite ease-in-out both;
}
.loading-dot:nth-child(1) { animation-delay: -0.32s; }
.loading-dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes loading-bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
```

---

## 测试策略

| 检查项 | 方式 | 预期结果 |
|--------|------|---------|
| 发送问题后显示占位 | 手动 / 单测 | QA 面板出现 ⏳ + 跳动圆点 |
| `qa_result` 到达后替换 | 手动 / 单测 | loading 气泡消失，bot 回答出现 |
| 30s 超时未响应 | 手动 / 单测 | loading 消失，出现 system 超时提示 |
| 后端返回 `error` 消息 | 手动 / 单测 | loading 消失，出现 system 错误提示 |
| 清空历史时 loading 存在 | 手动 / 单测 | loading 立即消失 |
| 重复发送被阻止 | 手动 | `isSending` 为 true 时输入框与按钮禁用 |
| loading 不影响轮次计数 | 单测 | `qaRoundCount` 只统计 user/bot 对 |
| 回归 | `npm test` | 全部前端测试通过 |

---

## 验收标准

- [x] 用户发送问题后 100ms 内出现 loading 占位气泡
- [x] LLM 响应到达后占位气泡被真实回答替换
- [x] 30s 未响应时占位气泡被移除并显示超时 system 消息
- [x] 后端 `error` 消息到达时占位气泡被移除并显示错误 system 消息
- [x] loading 期间清空历史不会留下孤儿气泡
- [x] `qaRoundCount` 不受 loading 消息影响
- [x] 全部前端测试通过（73/73）

---

## 实施记录

| 文件 | 变更摘要 |
|------|---------|
| `types/tree.ts` | `QAMessage.role` 增加 `'loading'` |
| `stores/ui.ts` | 新增 `startQALoading` / `finishQALoading` action |
| `services/ws.ts` | `qa_result` / `error` 分支调用 `finishQALoading` |
| `components/QAPanel.vue` | 渲染 loading 气泡、启动/清理逻辑、跳动动画、超时处理 |
| `stores/ui.spec.ts` | loading 生命周期、重入去重、错误回退、轮次计数 |
| `components/QAPanel.spec.ts` | 发送后显示 loading、`qa_result` 替换、超时错误 |
| `services/ws.spec.ts` | `qa_result` / `error` 触发 `finishQALoading` |

---

## 依赖

- proposal-0007（QAPanel + WS 问答链路）
- proposal-0011（QAPanel 块提问 UX）

## 后续可扩展

- proposal-0013（可选）：后端 LLM 流式输出 + `qa_stream_chunk` 消息类型，将 loading 气泡升级为增量填充的 bot 消息。

---

*Proposed: 2026-06-08*
