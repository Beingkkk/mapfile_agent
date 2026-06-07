<template>
  <section class="right-panel">
    <div class="qa-header">
      <div class="qa-header-title">
        💬 问答助手
      </div>
    </div>
    <div class="chat-area">
      <div v-if="messages.length === 0" class="chat-empty">
        选中左侧参数或节点提问
      </div>
      <div v-else class="chat-inner">
        <div v-for="msg in messages" :key="msg.text" :class="['msg', msg.role]">
          {{ msg.text }}
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
import { ref } from 'vue'
import { useUIStore } from '@/stores/ui'

const uiStore = useUIStore()
const inputText = ref('')
const messages = ref(uiStore.qaMessages)

function send() {
  if (!inputText.value.trim()) return
  uiStore.addQAMessage({ role: 'user', text: inputText.value })
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
.qa-header-title { font-size: 16px; font-weight: 700; }
.chat-area { flex: 1; overflow-y: auto; padding: 16px 18px; }
.chat-empty { text-align: center; color: #9aa5b1; padding: 60px 20px; }
.input-area { padding: 10px 16px; border-top: 1px solid #e4e7eb; display: flex; gap: 8px; }
.input-area input { flex: 1; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; }
</style>