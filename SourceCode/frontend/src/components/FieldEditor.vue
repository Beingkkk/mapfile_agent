<template>
  <div class="tree-prop" @click="handleClick">
    <span class="req-indicator">{{ indicator }}</span>
    <span class="tree-prop-key">{{ leaf.key }}:</span>
    <span class="tree-prop-value">
      <input
        v-if="leaf.value_type === 'string' || leaf.value_type === 'expression'"
        v-model="value"
        @blur="handleBlur"
        @keydown.enter="handleBlur"
      />
      <input
        v-else-if="leaf.value_type === 'integer' || leaf.value_type === 'float'"
        v-model.number="value"
        type="number"
        @blur="handleBlur"
        @keydown.enter="handleBlur"
      />
      <select v-else-if="leaf.value_type === 'enum'" v-model="value" @change="handleBlur">
        <option v-for="opt in leaf.enum" :key="opt" :value="opt">{{ opt }}</option>
      </select>
      <input v-else-if="leaf.value_type === 'boolean'" v-model="value" type="checkbox" @change="handleBlur" />
      <span v-else-if="leaf.value_type === 'color'" class="color-preview" :style="colorStyle" @click="editColor">
        {{ colorString }}
      </span>
      <span v-else-if="leaf.value_type === 'array'" class="array-value">
        {{ JSON.stringify(value) }}
      </span>
      <input v-else v-model="value" @blur="handleBlur" />
    </span>
    <span v-if="leaf.errors.length > 0" class="error-mark" title="leaf.errors.join('; ')">⚠️</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TreeLeaf } from '@/types/tree'
import { ws } from '@/services/ws'

interface Props {
  leaf: TreeLeaf
}

const props = defineProps<Props>()
const value = ref(props.leaf.value)

watch(() => props.leaf.value, (newVal) => {
  value.value = newVal
})

const indicator = computed(() => {
  if (props.leaf.required) return '*'
  if (props.leaf.derived) return '→'
  if (props.leaf.custom) return '✎'
  if (props.leaf.default !== undefined) return 'D'
  return '○'
})

const colorStyle = computed(() => {
  if (props.leaf.value_type === 'color' && Array.isArray(value.value)) {
    const [r, g, b] = value.value
    return { backgroundColor: `rgb(${r}, ${g}, ${b})` }
  }
  return {}
})

const colorString = computed(() => {
  if (props.leaf.value_type === 'color' && Array.isArray(value.value)) {
    return `[${value.value.join(', ')}]`
  }
  return String(value.value)
})

function handleBlur() {
  ws.send({
    type: 'tree_update',
    updates: [{ path: props.leaf.path, value: value.value }],
  })
}

function handleClick() {
  ws.send({
    type: 'focus_change',
    path: props.leaf.path,
  })
}

function editColor() {
  // TODO: open color picker modal
}
</script>

<style scoped>
.tree-prop {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  margin-bottom: 1px;
  cursor: pointer;
}
.tree-prop:hover { background: #f7f8fa; }
.req-indicator { width: 16px; text-align: center; font-weight: 700; }
.tree-prop-key { font-family: monospace; font-size: 14px; color: #616e7c; min-width: 90px; }
.tree-prop-value input, .tree-prop-value select {
  padding: 3px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 13px;
}
.error-mark { color: #ef4444; margin-left: 4px; }
.color-preview {
  display: inline-block;
  width: 60px;
  height: 20px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 11px;
  text-align: center;
  line-height: 20px;
}
.array-value {
  font-family: monospace;
  font-size: 12px;
  color: #6b7280;
}
</style>
