<template>
  <div class="tree-prop" :class="{ 'has-error': leaf.errors.length > 0, focused: isFocused }" @click="handleClick">
    <span class="req-indicator" :title="indicatorTitle">{{ indicator }}</span>
    <span class="tree-prop-key" :title="leaf.path">{{ leaf.key }}:</span>
    <span class="tree-prop-value">
      <!-- string / expression -->
      <input
        v-if="leaf.value_type === 'string'"
        v-model="value"
        :placeholder="placeholder"
        @blur="handleBlur"
        @keydown.enter="handleBlur"
      />
      <input
        v-else-if="leaf.value_type === 'expression'"
        v-model="value"
        :placeholder="placeholder"
        class="expression-input"
        @blur="handleBlur"
        @keydown.enter="handleBlur"
      />
      <!-- number -->
      <input
        v-else-if="leaf.value_type === 'integer' || leaf.value_type === 'float'"
        v-model.number="value"
        :step="leaf.value_type === 'float' ? 0.01 : 1"
        type="number"
        @blur="handleBlur"
        @keydown.enter="handleBlur"
      />
      <!-- enum -->
      <select v-else-if="leaf.value_type === 'enum'" v-model="value" @change="handleBlur">
        <option v-for="opt in leaf.enum" :key="opt" :value="opt">{{ opt }}</option>
      </select>
      <!-- boolean -->
      <input v-else-if="leaf.value_type === 'boolean'" v-model="value" type="checkbox" @change="handleBlur" />
      <!-- color -->
      <span v-else-if="leaf.value_type === 'color'" class="color-editor">
        <span class="color-preview" :style="colorStyle" @click.stop="toggleColorEdit">
          {{ colorString }}
        </span>
        <span v-if="showColorEdit" class="color-inputs" @click.stop>
          <input
            v-for="(ch, idx) in ['R', 'G', 'B']"
            :key="ch"
            v-model.number="rgbValues[idx]"
            type="number"
            min="0"
            max="255"
            :placeholder="ch"
            class="rgb-input"
            @blur="commitColor"
            @keydown.enter="commitColor"
          />
        </span>
      </span>
      <!-- array -->
      <span v-else-if="leaf.value_type === 'array'" class="array-editor">
        <span v-if="!showArrayEdit" class="array-display" @click.stop="toggleArrayEdit">
          {{ arrayDisplay }}
        </span>
        <span v-else class="array-input-wrap" @click.stop>
          <input
            ref="arrayInputRef"
            v-model="arrayText"
            :placeholder="arrayPlaceholder"
            @blur="commitArray"
            @keydown.enter="commitArray"
          />
        </span>
      </span>
      <!-- fallback -->
      <input v-else v-model="value" @blur="handleBlur" />
    </span>
    <span v-if="leaf.errors.length > 0" class="prop-actions">
      <span class="error-mark" :title="leaf.errors.join('; ')">⚠️</span>
      <button class="help-btn" title="向LLM提问此参数怎么填" @click.stop="askHelp">?</button>
    </span>
    <span v-else-if="leaf.custom && leaf.custom_desc" class="custom-desc" :title="leaf.custom_desc">ℹ️</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { TreeLeaf } from '@/types/tree'
import { ws } from '@/services/ws'

interface Props {
  leaf: TreeLeaf
}

const props = defineProps<Props>()
const value = ref(props.leaf.value)

// Sync external value changes
watch(() => props.leaf.value, (newVal) => {
  value.value = newVal
})

// ── Indicator ──
const indicator = computed(() => {
  if (props.leaf.required) return '*'
  if (props.leaf.derived) return '→'
  if (props.leaf.custom) return '✎'
  if (props.leaf.default !== undefined) return 'D'
  return '○'
})

const indicatorTitle = computed(() => {
  if (props.leaf.required) return '必填字段'
  if (props.leaf.derived) return '推导字段'
  if (props.leaf.custom) return '自定义属性'
  if (props.leaf.default !== undefined) return '有默认值'
  return '可选字段'
})

// ── Focus tracking ──
const isFocused = computed(() => {
  // Simple heuristic: leaf.path ends with focus_param
  return false // Set by parent if needed
})

// ── Placeholder ──
const placeholder = computed(() => {
  if (props.leaf.value_type === 'expression') {
    return '表达式，例如: ([area] > 1000)'
  }
  if (props.leaf.default !== undefined) {
    return String(props.leaf.default)
  }
  return ''
})

// ── Color editor ──
const showColorEdit = ref(false)

const rgbValues = ref([0, 0, 0])
watch(() => props.leaf.value, (v) => {
  if (props.leaf.value_type === 'color' && Array.isArray(v) && v.length >= 3) {
    rgbValues.value = [v[0] ?? 0, v[1] ?? 0, v[2] ?? 0]
  }
}, { immediate: true })

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

function toggleColorEdit() {
  showColorEdit.value = !showColorEdit.value
}

function commitColor() {
  // Clamp 0-255
  const clamped = rgbValues.value.map(v => Math.max(0, Math.min(255, Math.round(Number(v) || 0))))
  value.value = clamped
  showColorEdit.value = false
  ws.send({
    type: 'tree_update',
    updates: [{ path: props.leaf.path, value: clamped }],
  })
}

// ── Array editor ──
const showArrayEdit = ref(false)
const arrayText = ref('')
const arrayInputRef = ref<HTMLInputElement | null>(null)

const arrayDisplay = computed(() => {
  if (Array.isArray(value.value)) {
    const preview = value.value.slice(0, 3).map(String).join(', ')
    return value.value.length > 3 ? `[${preview}, ...]` : `[${preview}]`
  }
  return String(value.value)
})

const arrayPlaceholder = computed(() => {
  return '逗号分隔，例如: item1, item2, item3'
})

function toggleArrayEdit() {
  showArrayEdit.value = true
  if (Array.isArray(value.value)) {
    arrayText.value = value.value.join(', ')
  } else {
    arrayText.value = String(value.value)
  }
  nextTick(() => arrayInputRef.value?.focus())
}

function commitArray() {
  showArrayEdit.value = false
  let parsed: any
  // Try JSON parse first
  try {
    parsed = JSON.parse(arrayText.value)
    if (!Array.isArray(parsed)) {
      // If not array, try comma split
      parsed = arrayText.value.split(',').map(s => s.trim()).filter(Boolean)
    }
  } catch {
    // Comma-separated fallback
    parsed = arrayText.value.split(',').map(s => s.trim()).filter(Boolean)
  }
  value.value = parsed
  ws.send({
    type: 'tree_update',
    updates: [{ path: props.leaf.path, value: parsed }],
  })
}

// ── Standard update ──
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

// ── Ask LLM for help on this field ──
function askHelp() {
  const leaf = props.leaf
  let question = `参数 \`${leaf.path}\`（${leaf.key}）怎么填？`
  if (leaf.value_type === 'enum' && leaf.enum && leaf.enum.length > 0) {
    question += ` 可选值：${leaf.enum.join('、')}，分别是什么意思？`
  } else if (leaf.value_type === 'boolean') {
    question += ' true / false 分别代表什么含义？'
  } else if (leaf.value_type === 'color') {
    question += ' RGB 颜色值应该怎么设置？'
  } else if (leaf.value_type === 'expression') {
    question += ' 表达式语法是什么？'
  }
  ws.send({ type: 'question', text: question })
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
  transition: background 0.15s;
}
.tree-prop:hover { background: #f7f8fa; }
.tree-prop.has-error { background: #fef2f2; }
.tree-prop.has-error:hover { background: #fee2e2; }

.req-indicator {
  width: 16px;
  text-align: center;
  font-weight: 700;
  font-size: 13px;
  cursor: help;
}
.tree-prop-key {
  font-family: monospace;
  font-size: 14px;
  color: #616e7c;
  min-width: 90px;
}
.tree-prop-value input,
.tree-prop-value select {
  padding: 5px 9px;
  border: 1.5px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  min-width: 60px;
  color: #374151;
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.tree-prop-value input:focus,
.tree-prop-value select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}

.expression-input {
  font-family: monospace;
  min-width: 180px;
}

.prop-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 4px;
}
.error-mark {
  color: #ef4444;
  cursor: help;
  font-size: 14px;
}
.help-btn {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: none;
  background: #dbeafe;
  color: #2563eb;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: all 0.12s;
}
.help-btn:hover {
  background: #2563eb;
  color: #fff;
}
.custom-desc {
  color: #6b7280;
  margin-left: 4px;
  cursor: help;
  font-size: 12px;
}

/* Color editor */
.color-editor {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.color-preview {
  display: inline-block;
  width: 60px;
  height: 20px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 11px;
  text-align: center;
  line-height: 20px;
  cursor: pointer;
  user-select: none;
}
.color-inputs {
  display: inline-flex;
  gap: 4px;
}
.rgb-input {
  width: 44px !important;
  text-align: center;
  padding: 2px 4px !important;
}

/* Array editor */
.array-editor {
  display: inline-flex;
  align-items: center;
}
.array-display {
  font-family: monospace;
  font-size: 12px;
  color: #374151;
  padding: 3px 8px;
  border: 1px dashed #d1d5db;
  border-radius: 4px;
  cursor: pointer;
  min-width: 60px;
}
.array-display:hover {
  border-color: #2563eb;
  background: #eff6ff;
}
.array-input-wrap input {
  font-family: monospace;
  min-width: 200px;
}
</style>
