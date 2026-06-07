<template>
  <div v-if="visible" class="modal-overlay" @click.self="cancel">
    <div class="modal-card">
      <div class="modal-title">➕ 添加自定义属性</div>
      <div class="custom-prop-form">
        <label>Key 名称 *</label>
        <input v-model="key" placeholder="例如：transparency" />
        <label>类型 *</label>
        <select v-model="propType">
          <option value="string">string</option>
          <option value="enum">enum</option>
          <option value="integer">integer</option>
          <option value="float">float</option>
          <option value="boolean">boolean</option>
          <option value="color">color</option>
          <option value="array">array</option>
        </select>
        <label>描述</label>
        <textarea v-model="desc" placeholder="用途说明（可选）" />
      </div>
      <div class="modal-actions">
        <button @click="cancel">取消</button>
        <button @click="confirm">添加</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  parentPath: string
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['confirm', 'cancel'])

const key = ref('')
const propType = ref('string')
const desc = ref('')

function confirm() {
  if (!key.value.trim()) return
  emit('confirm', key.value, propType.value, desc.value)
  key.value = ''
  propType.value = 'string'
  desc.value = ''
}

function cancel() {
  emit('cancel')
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 300; }
.modal-card { background: #fff; border-radius: 14px; padding: 24px; max-width: 460px; width: 100%; }
.modal-title { font-size: 17px; font-weight: 700; margin-bottom: 18px; }
.custom-prop-form { display: flex; flex-direction: column; gap: 14px; margin-bottom: 20px; }
.custom-prop-form label { font-size: 13px; font-weight: 600; color: #52606d; }
.custom-prop-form input, .custom-prop-form select, .custom-prop-form textarea { padding: 9px 12px; border: 1.5px solid #d1d5db; border-radius: 8px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>