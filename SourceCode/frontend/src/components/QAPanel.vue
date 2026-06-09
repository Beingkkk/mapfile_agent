<template>
  <section class="right-panel">
    <!-- QA Header -->
    <div class="qa-header">
      <div class="qa-header-title">
        💬 问答助手
        <span v-if="uiStore.qaRoundCount > 0" class="round-count">轮次: {{ uiStore.qaRoundCount }}</span>
      </div>
      <button
        v-if="messages.length > 0"
        class="btn-clear"
        title="重置上下文"
        @click="clearHistory"
      >
        🗑️
      </button>
    </div>

    <!-- Chat area -->
    <div ref="chatAreaRef" class="chat-area">
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="chat-empty-icon">💬</div>
        <div class="chat-empty-title">问答助手</div>
        <div class="chat-empty-desc">
          {{ focusParam ? `针对当前 ${focusInfo.label} 提问，或输入任意问题` : '选中左侧树节点或参数，可针对该节点/参数提问' }}
        </div>
      </div>
      <div v-else class="chat-inner">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="['msg', msg.role]"
        >
          <template v-if="msg.role === 'divider'">
            <div class="divider-line" />
          </template>
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
          <template v-else>
            <div class="msg-role">{{ roleIcon(msg.role) }}</div>
            <div class="msg-content">
              <div v-if="msg.role === 'bot'" class="msg-text markdown-body" v-html="renderMarkdown(msg.text)" />
              <div v-else class="msg-text">{{ msg.text }}</div>
              <div v-if="msg.role === 'bot' && msg.focus_param" class="msg-focus-tag">
                <span class="focus-label">🔍</span>
                <span class="focus-value">{{ resolveFocusLabel(msg.focus_param).label }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Focus indicator + Input area -->
    <div class="input-section">
      <div v-if="focusParam" class="qa-focus-bar">
        <span class="focus-icon">🔍</span>
        <span class="focus-path">{{ focusInfo.label }}</span>
        <button class="btn-unfocus" title="取消焦点" @click="clearFocus">×</button>
      </div>
      <div v-else class="qa-focus-bar hint">
        <span class="focus-icon">💡</span>
        <span class="focus-path">点击左侧树节点或参数，可针对该参数提问</span>
      </div>

      <!-- Quick questions -->
      <div class="quick-questions">
        <div v-for="q in quickQuestions" :key="q" class="quick-q-chip" @click="sendQuickQuestion(q)">
          {{ q }}
        </div>
      </div>

      <div class="input-area">
        <textarea
          v-model="inputText"
          :disabled="isSending"
          :placeholder="inputPlaceholder"
          rows="2"
          @keydown.enter.exact.prevent="send"
        />
        <button :disabled="isSending || !inputText.trim()" @click="send">
          {{ isSending ? '⏳' : '发送' }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { marked } from 'marked'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'
import { ws } from '@/services/ws'

const sessionStore = useSessionStore()
const uiStore = useUIStore()
const inputText = ref('')
const isSending = ref(false)
const chatAreaRef = ref<HTMLDivElement | null>(null)

const messages = computed(() => uiStore.qaMessages)

/** Auto-scroll chat area to bottom whenever messages change. */
function scrollToBottom() {
  nextTick(() => {
    const el = chatAreaRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

watch(
  () => uiStore.qaMessages.length,
  () => scrollToBottom(),
  { immediate: true },
)
const focusParam = computed(() => sessionStore.focus_param)

/**
 * Resolve a flat path to a user-friendly label and detect if it's an object path.
 * Object paths end with an index (e.g. "layers.0") or a root object type ("map", "web").
 * Attribute paths end with a field name (e.g. "layers.0.name").
 */
function resolveFocusLabel(path: string | null): { label: string; isObject: boolean } {
  if (!path) return { label: '', isObject: false }
  const parts = path.split('.')
  const last = parts[parts.length - 1]
  const isIndex = /^\d+$/.test(last)
  const isObjectType = ['map', 'web', 'metadata', 'cache'].includes(last.toLowerCase())
  const isObject = isIndex || isObjectType

  if (isObject) {
    const typeMap: Record<string, string> = {
      map: 'MAP',
      layers: 'LAYER',
      classes: 'CLASS',
      styles: 'STYLE',
      labels: 'LABEL',
      web: 'WEB',
      metadata: 'METADATA',
      cache: 'CACHE',
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

  return { label: path, isObject: false }
}

const focusInfo = computed(() => resolveFocusLabel(focusParam.value))

const inputPlaceholder = computed(() => {
  if (focusParam.value) {
    return `针对 ${focusInfo.value.label} 提问...`
  }
  return '输入问题...'
})

const quickQuestions = computed(() => {
  if (!focusParam.value) {
    return [
      '帮我检查一下当前配置',
      '导出前还需要配置什么？',
      '当前配置有什么潜在问题？',
    ]
  }

  const { label, isObject } = focusInfo.value

  if (isObject) {
    return [
      `「${label}」还需要配置什么？`,
      `「${label}」有哪些必填字段？`,
      `「${label}」的最佳实践是什么？`,
    ]
  }

  const name = focusParam.value.split('.').pop() || focusParam.value
  return [
    `「${name}」怎么填？`,
    `「${name}」有哪些可选值？`,
    `「${name}」的最佳实践是什么？`,
  ]
})

function roleIcon(role: string): string {
  switch (role) {
    case 'user': return '👤'
    case 'bot': return '🤖'
    case 'system': return '⚠️'
    case 'loading': return '⏳'
    default: return '•'
  }
}

function renderMarkdown(text: string): string {
  return marked.parse(text, { async: false }) as string
}

function send() {
  const text = inputText.value.trim()
  if (!text || isSending.value) return
  doSend(text)
}

function sendQuickQuestion(text: string) {
  if (isSending.value) return
  doSend(text)
}

function doSend(text: string) {
  isSending.value = true
  uiStore.addQAMessage({ role: 'user', text })
  ws.send({ type: 'question', text })
  inputText.value = ''
  // Reset sending state after timeout (in case response never arrives)
  setTimeout(() => {
    if (isSending.value) {
      isSending.value = false
      uiStore.finishQALoading({
        error: '响应超时，请稍后重试或重新提问。',
      })
    }
  }, 30000)
}

function clearFocus() {
  ws.send({ type: 'focus_change', path: null })
}

function clearHistory() {
  ws.send({ type: 'clear_history' })
  uiStore.finishQALoading()
}

// Listen for qa_result to reset sending state
ws.on('qa_result', () => {
  isSending.value = false
})

// Listen for history_cleared to insert divider visually
ws.on('history_cleared', () => {
  uiStore.resetHistoryContext()
})
</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  overflow: hidden;
}

/* Header */
.qa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.qa-header-title {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.round-count {
  font-size: 12px;
  color: #6b7280;
  font-weight: 400;
  padding: 2px 8px;
  background: #f0f2f5;
  border-radius: 999px;
}
.btn-clear {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #9aa5b1;
  transition: all 0.15s;
}
.btn-clear:hover {
  background: #fee2e2;
  color: #991b1b;
}

/* Input section: focus bar + input */
.input-section {
  border-top: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.qa-focus-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f0f4f8;
  border-bottom: 1px solid #d9e2ec;
}
.qa-focus-bar.hint {
  background: #f7f8fa;
  border-bottom: 1px solid #e4e7eb;
}
.focus-icon {
  font-size: 13px;
  flex-shrink: 0;
}
.focus-path {
  font-family: monospace;
  font-size: 13px;
  color: #334e68;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.qa-focus-bar.hint .focus-path {
  font-family: inherit;
  color: #7b8794;
  font-size: 12px;
}
.btn-unfocus {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: none;
  background: #d9e2ec;
  color: #486581;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.12s;
}
.btn-unfocus:hover {
  background: #bf2600;
  color: #fff;
}

/* Chat area */
.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
}
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 8px;
}
.chat-empty-icon {
  font-size: 32px;
  opacity: 0.5;
}
.chat-empty-title {
  font-size: 14px;
  font-weight: 600;
  color: #9aa5b1;
}
.chat-empty-desc {
  font-size: 13px;
  color: #9aa5b1;
  text-align: center;
}
.chat-inner {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.msg.user { flex-direction: row-reverse; }
.msg.system {
  justify-content: center;
}
.msg.divider {
  justify-content: center;
  padding: 6px 0;
  gap: 0;
}
.divider-line {
  width: 70%;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, #d1d5db 40%, #d1d5db 60%, transparent 100%);
}
.msg-text {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}
.msg.user .msg-text {
  background: #2563eb;
  color: #fff;
}
.msg.bot .msg-text {
  background: #fff;
  color: #1f2937;
  border: 1px solid #e5e7eb;
}
.msg.system .msg-text {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
  font-size: 13px;
  max-width: 90%;
}
.msg-role {
  font-size: 16px;
  flex-shrink: 0;
}
.msg.system .msg-role {
  font-size: 14px;
}

.msg-content {
  max-width: 80%;
  display: flex;
  flex-direction: column;
}
.msg-content .msg-text {
  max-width: 100%;
}

/* Focus tag on bot messages */
.msg-focus-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 8px;
  background: #f0f4f8;
  border-radius: 999px;
  font-size: 12px;
  color: #627d98;
  align-self: flex-start;
  max-width: 100%;
}
.msg-focus-tag .focus-label {
  font-size: 11px;
}
.msg-focus-tag .focus-value {
  font-family: monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Markdown rendering styles (deep selector for v-html content) */
:deep(.markdown-body) {
  line-height: 1.6;
}
:deep(.markdown-body p) {
  margin: 0 0 8px 0;
}
:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}
:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  margin: 0 0 8px 0;
  padding-left: 20px;
}
:deep(.markdown-body li) {
  margin-bottom: 4px;
}
:deep(.markdown-body li:last-child) {
  margin-bottom: 0;
}
:deep(.markdown-body strong) {
  font-weight: 600;
  color: #111827;
}
:deep(.markdown-body code) {
  background: #f3f4f6;
  padding: 2px 5px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 13px;
  color: #374151;
}
:deep(.markdown-body pre) {
  background: #1f2937;
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 0 0 8px 0;
}
:deep(.markdown-body pre code) {
  background: transparent;
  padding: 0;
  color: #e5e7eb;
  font-size: 13px;
}
:deep(.markdown-body blockquote) {
  margin: 0 0 8px 0;
  padding-left: 12px;
  border-left: 3px solid #d1d5db;
  color: #6b7280;
}
:deep(.markdown-body a) {
  color: #2563eb;
  text-decoration: none;
}
:deep(.markdown-body a:hover) {
  text-decoration: underline;
}
:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3),
:deep(.markdown-body h4) {
  margin: 12px 0 6px 0;
  font-weight: 600;
  color: #111827;
}
:deep(.markdown-body h1) { font-size: 16px; }
:deep(.markdown-body h2) { font-size: 15px; }
:deep(.markdown-body h3) { font-size: 14px; }
:deep(.markdown-body h4) { font-size: 14px; }
:deep(.markdown-body hr) {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 8px 0;
}

/* Quick questions */
.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 16px;
  border-bottom: 1px solid #e4e7eb;
}
.quick-q-chip {
  padding: 4px 10px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  font-size: 12px;
  color: #4b5563;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.12s;
}
.quick-q-chip:hover {
  background: #f0f4f8;
  border-color: #829ab1;
  color: #1f2937;
}

/* Loading bubble */
.msg.loading .msg-text {
  background: #fff;
  color: #6b7280;
  border: 1px solid #e5e7eb;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.loading-text {
  font-size: 14px;
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

/* Input area */
.input-area {
  padding: 10px 16px;
  border-top: 1px solid #e4e7eb;
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.input-area textarea {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.5;
  outline: none;
  transition: border-color 0.15s;
  resize: none;
  font-family: inherit;
}
.input-area textarea:focus {
  border-color: #2563eb;
}
.input-area textarea:disabled {
  background: #f3f4f6;
  color: #9aa5b1;
}
.input-area button {
  padding: 8px 16px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s;
}
.input-area button:hover:not(:disabled) {
  background: #1d4ed8;
}
.input-area button:disabled {
  background: #9aa5b1;
  cursor: not-allowed;
}
</style>
