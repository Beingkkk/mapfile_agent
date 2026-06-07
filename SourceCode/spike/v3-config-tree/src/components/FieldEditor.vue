<template>
  <div class="field-row" :class="{ focused: isFocused }" @click="handleFocus">
    <!-- 字段标签 -->
    <div class="field-label">
      <span class="phase-dot" :style="{ backgroundColor: phaseColorMap[field.phaseColor] }"></span>
      <span class="field-name" :class="{ required: field.required }">{{ field.name }}</span>
      <span v-if="field.required" class="required-mark">*</span>
      <span v-if="hasDefault" class="default-mark" title="有默认值">D</span>
      <span v-if="field.description" class="desc-hint" :title="field.description">?</span>
    </div>

    <!-- 编辑器 -->
    <div class="field-editor">
      <!-- 字符串 -->
      <template v-if="field.valueType === 'string'">
        <n-input
          v-model:value="strValue"
          size="small"
          placeholder="请输入"
          @blur="handleBlur"
          @focus="handleFocus"
        />
      </template>

      <!-- 整数 -->
      <template v-else-if="field.valueType === 'integer'">
        <n-input-number
          v-model:value="numValue"
          size="small"
          :min="field.min"
          :max="field.max"
          :step="1"
          placeholder="整数"
          @blur="handleBlur"
          @focus="handleFocus"
        />
      </template>

      <!-- 浮点数 -->
      <template v-else-if="field.valueType === 'float'">
        <n-input-number
          v-model:value="numValue"
          size="small"
          :min="field.min"
          :max="field.max"
          :step="0.1"
          placeholder="数值"
          @blur="handleBlur"
          @focus="handleFocus"
        />
      </template>

      <!-- 布尔 -->
      <template v-else-if="field.valueType === 'boolean'">
        <n-switch v-model:value="boolValue" size="small" @update:value="handleChange" />
      </template>

      <!-- 枚举 -->
      <template v-else-if="field.valueType === 'enum'">
        <n-select
          v-model:value="strValue"
          size="small"
          :options="enumOptions"
          placeholder="选择"
          @update:value="handleChange"
        />
      </template>

      <!-- 数组 (extent, size 等) -->
      <template v-else-if="field.valueType === 'array'">
        <div class="array-inputs">
          <n-input-number
            v-for="(v, i) in arrayValue"
            :key="i"
            v-model:value="arrayValue[i]"
            size="small"
            style="width: 70px;"
            @blur="handleBlur"
            @focus="handleFocus"
          />
        </div>
      </template>

      <!-- 颜色 RGB -->
      <template v-else-if="field.valueType === 'color'">
        <div class="color-inputs">
          <n-input-number
            v-for="(v, i) in colorValue"
            :key="i"
            v-model:value="colorValue[i]"
            size="small"
            :min="0"
            :max="255"
            :step="1"
            style="width: 55px;"
            @blur="handleBlur"
            @focus="handleFocus"
          />
          <div class="color-preview" :style="{ backgroundColor: cssColor }"></div>
        </div>
      </template>

      <!-- 未知类型回退 -->
      <template v-else>
        <n-input v-model:value="strValue" size="small" @blur="handleBlur" @focus="handleFocus" />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { NInput, NInputNumber, NSwitch, NSelect } from 'naive-ui'

const props = defineProps({
  field: { type: Object, required: true },
  focusedPath: { type: String, default: '' }
})
const emit = defineEmits(['update', 'focus'])

const phaseColorMap = {
  blue: '#2563eb',
  orange: '#ea580c',
  green: '#16a34a',
  purple: '#9333ea',
  gray: '#9ca3af',
}

const isFocused = computed(() => props.focusedPath === props.field.path)
const hasDefault = computed(() => props.field.default !== undefined && props.field.default !== null)

// 枚举选项
const enumOptions = computed(() => {
  if (!props.field.enum) return []
  return props.field.enum.map(v => ({ label: String(v), value: String(v) }))
})

// 颜色CSS
const cssColor = computed(() => {
  const c = colorValue.value || [0, 0, 0]
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
})

// 各种值的本地状态
const strValue = ref(String(props.field.value ?? ''))
const numValue = ref(Number(props.field.value) || 0)
const boolValue = ref(Boolean(props.field.value))
const arrayValue = ref(Array.isArray(props.field.value) ? [...props.field.value] : [])
const colorValue = ref(Array.isArray(props.field.value) && props.field.value.length === 3
  ? [...props.field.value]
  : [0, 0, 0])

// 监听外部值变化
watch(() => props.field.value, (newVal) => {
  if (props.field.valueType === 'string' || props.field.valueType === 'enum') {
    strValue.value = String(newVal ?? '')
  } else if (['integer', 'float'].includes(props.field.valueType)) {
    numValue.value = Number(newVal) || 0
  } else if (props.field.valueType === 'boolean') {
    boolValue.value = Boolean(newVal)
  } else if (props.field.valueType === 'array') {
    arrayValue.value = Array.isArray(newVal) ? [...newVal] : []
  } else if (props.field.valueType === 'color') {
    colorValue.value = Array.isArray(newVal) && newVal.length === 3 ? [...newVal] : [0, 0, 0]
  }
})

function handleFocus() {
  emit('focus', props.field.path)
}

function handleBlur() {
  let newVal
  switch (props.field.valueType) {
    case 'string':
      newVal = strValue.value
      break
    case 'integer':
      newVal = Math.round(numValue.value)
      break
    case 'float':
      newVal = numValue.value
      break
    case 'boolean':
      newVal = boolValue.value
      break
    case 'enum':
      newVal = strValue.value
      break
    case 'array':
      newVal = [...arrayValue.value]
      break
    case 'color':
      newVal = [...colorValue.value]
      break
    default:
      newVal = strValue.value
  }
  emit('update', { path: props.field.path, value: newVal })
}

function handleChange() {
  handleBlur()
}
</script>

<style scoped>
.field-row {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  gap: 8px;
  transition: background-color 0.15s;
  min-height: 36px;
}
.field-row:hover {
  background-color: #f3f4f6;
}
.field-row.focused {
  background-color: #eff6ff;
  outline: 1px solid #3b82f6;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 160px;
  flex-shrink: 0;
  font-size: 13px;
}
.phase-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.field-name {
  color: #374151;
  font-weight: 500;
}
.field-name.required {
  font-weight: 600;
}
.required-mark {
  color: #ef4444;
  font-size: 12px;
}
.default-mark {
  font-size: 10px;
  color: #6b7280;
  background: #e5e7eb;
  padding: 0 3px;
  border-radius: 2px;
}
.desc-hint {
  font-size: 10px;
  color: #9ca3af;
  cursor: help;
}

.field-editor {
  flex: 1;
  min-width: 0;
}
.field-editor :deep(.n-input__input) {
  font-size: 13px;
}
.field-editor :deep(.n-input-number-input) {
  font-size: 13px;
}

.array-inputs,
.color-inputs {
  display: flex;
  gap: 4px;
  align-items: center;
}
.color-preview {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  border: 1px solid #d1d5db;
  flex-shrink: 0;
}
</style>
