<template>
  <section class="right-panel">
    <div class="qa-header">
      <div class="qa-header-title">
        💬 问答助手
        <span v-if="uiStore.qaRoundCount > 0" class="round-count">轮次: {{ uiStore.qaRoundCount }}</span>
      </div>
    </div>
    <div class="chat-area">
      <div v-if="messages.length === 0" class="chat-empty">
        选中左侧参数或节点提问
      </div>
      <div v-else class="chat-inner">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['msg', msg.role]">
          <div class="msg-role">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
          <div class="msg-text">{{ msg.text }}</div>
        </div>
      </div>
    </div>
    <div class="input-area">
      <input v-model="inputText" @keydown.enter="send" placeholder="输入问题..." />
      <button @click="send">发送</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import { ws } from '@/services/ws'

const uiStore = useUIStore()
const inputText = ref('')
const messages = computed(() => uiStore.qaMessages)

function send() {
  const text = inputText.value.trim()
  if (!text) return
  uiStore.addQAMessage({ role: 'user', text })
  ws.send({ type: 'question', text })
  inputText.value = ''
}
</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
  overflow: hidden;
}
.qa-header {
  padding: 12px 18px;
  border-bottom: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.qa-header-title { font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.round-count { font-size: 12px; color: #6b7280; font-weight: 400; }
.chat-area { flex: 1; overflow-y: auto; padding: 16px 18px; }
.chat-empty { text-align: center; color: #9aa5b1; padding: 60px 20px; }
.chat-inner { display: flex; flex-direction: column; gap: 12px; }
.msg { display: flex; gap: 8px; align-items: flex-start; }
.msg.user { flex-direction: row-reverse; }
.msg-text {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
}
.msg.user .msg-text { background: #2563eb; color: #fff; }
.msg.bot .msg-text { background: #fff; color: #1f2937; border: 1px solid #e5e7eb; }
.msg-role { font-size: 16px; }
.input-area { padding: 10px 16px; border-top: 1px solid #e4e7eb; display: flex; gap: 8px; }
.input-area input { flex: 1; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; }
.input-area button { padding: 8px 16px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.input-area button:hover { background: #1d4ed8; }
</style>
