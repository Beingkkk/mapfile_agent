<template>
  <div class="object-card" :class="{ expanded: isExpanded }">
    <!-- 对象头部 -->
    <div class="object-header" @click="toggleExpand">
      <span class="expand-icon" :class="{ expanded: isExpanded }">▶</span>
      <span
        class="object-badge"
        :style="{ backgroundColor: phaseColorMap[node.phaseColor], color: '#fff' }"
      >
        {{ node.objectType }}
      </span>
      <span class="object-name">{{ node.name }}</span>
      <span class="object-count">({{ childCount }})</span>
    </div>

    <!-- 子节点（递归渲染） -->
    <div v-if="isExpanded" class="object-children">
      <template v-for="child in node.children" :key="child.path || child.name">
        <!-- 叶子字段 -->
        <FieldEditor
          v-if="child.type === 'field'"
          :field="child"
          :focused-path="focusedPath"
          @update="$emit('update', $event)"
          @focus="$emit('focus', $event)"
        />
        <!-- 嵌套对象（递归） -->
        <ObjectCard
          v-else-if="child.type === 'object'"
          :node="child"
          :focused-path="focusedPath"
          @update="$emit('update', $event)"
          @focus="$emit('focus', $event)"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, ref, watch } from 'vue'
import FieldEditor from './FieldEditor.vue'

const props = defineProps({
  node: { type: Object, required: true },
  focusedPath: { type: String, default: '' }
})
defineEmits(['update', 'focus'])

const phaseColorMap = {
  blue: '#2563eb',
  orange: '#ea580c',
  green: '#16a34a',
  purple: '#9333ea',
  gray: '#9ca3af',
}

const isExpanded = ref(true)

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

// 响应全局展开/折叠
const expandAll = inject('expandAll', ref(0))
const collapseAll = inject('collapseAll', ref(0))

watch(expandAll, () => { isExpanded.value = true })
watch(collapseAll, () => { isExpanded.value = false })

const childCount = computed(() => {
  if (!props.node.children) return 0
  let count = 0
  function countAll(nodes) {
    for (const n of nodes) {
      count++
      if (n.children) countAll(n.children)
    }
  }
  countAll(props.node.children)
  return count
})
</script>

<style scoped>
.object-card {
  border-left: 2px solid transparent;
  transition: border-color 0.15s;
}
.object-card:hover {
  border-left-color: #e5e7eb;
}

.object-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  cursor: pointer;
  user-select: none;
  border-radius: 4px;
  transition: background-color 0.15s;
}
.object-header:hover {
  background-color: #f9fafb;
}

.expand-icon {
  font-size: 10px;
  color: #9ca3af;
  transition: transform 0.2s;
  display: inline-block;
  width: 12px;
  text-align: center;
}
.expand-icon.expanded {
  transform: rotate(90deg);
}

.object-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}
.object-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}
.object-count {
  font-size: 11px;
  color: #9ca3af;
}

.object-children {
  padding-left: 20px;
}
</style>
