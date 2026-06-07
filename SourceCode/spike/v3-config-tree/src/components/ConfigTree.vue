<template>
  <div class="config-tree">
    <!-- 顶部工具栏 -->
    <div class="tree-toolbar">
      <div class="legend-bar">
        <span class="legend-title">📋 图例：</span>
        <span class="legend-item"><span class="mark">*</span> 必填</span>
        <span class="legend-item"><span class="mark">D</span> 默认值</span>
        <span class="legend-item"><span class="mark">○</span> 可选</span>
        <span class="legend-item"><span class="mark">→</span> 推导</span>
        <span class="legend-item"><span class="mark">✎</span> 自定义</span>
      </div>
      <div class="toolbar-actions">
        <n-radio-group v-model:value="showMode" size="small">
          <n-radio-button value="all">全部</n-radio-button>
          <n-radio-button value="required">仅必填</n-radio-button>
        </n-radio-group>
        <n-button size="small" @click="expandAll">全部展开</n-button>
        <n-button size="small" @click="collapseAll">全部折叠</n-button>
      </div>
    </div>

    <!-- 树内容 -->
    <div class="tree-content" ref="treeContent">
      <ObjectCard
        :node="filteredTree"
        :focused-path="focusedPath"
        @update="handleUpdate"
        @focus="handleFocus"
      />
    </div>

    <!-- 状态栏 -->
    <div class="tree-status">
      <span>节点: {{ totalNodes }}</span>
      <span>字段: {{ totalFields }}</span>
      <span>焦点: {{ focusedPath || '无' }}</span>
      <span>编辑次数: {{ editCount }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, provide } from 'vue'
import { NRadioGroup, NRadioButton, NButton } from 'naive-ui'
import ObjectCard from './ObjectCard.vue'

const props = defineProps({
  tree: { type: Object, required: true }
})

const showMode = ref('all')
const focusedPath = ref('')
const editCount = ref(0)
const treeContent = ref(null)

// 过滤树：根据showMode过滤
const filteredTree = computed(() => {
  if (showMode.value === 'all') {
    return props.tree
  }
  // 仅必填模式：过滤掉非必填字段
  return filterRequired(props.tree)
})

function filterRequired(node) {
  if (node.type === 'field') {
    return node.required ? node : null
  }
  if (node.type === 'object') {
    const filteredChildren = []
    for (const child of node.children || []) {
      const filtered = filterRequired(child)
      if (filtered) {
        filteredChildren.push(filtered)
      }
    }
    // 对象节点如果没有子节点也保留（结构完整性）
    return {
      ...node,
      children: filteredChildren
    }
  }
  return node
}

// 统计（基于原始树）
const totalNodes = computed(() => countNodes(props.tree))
const totalFields = computed(() => countFields(props.tree))

function countNodes(node) {
  if (node.type === 'field') return 1
  let count = 1
  for (const c of node.children || []) count += countNodes(c)
  return count
}

function countFields(node) {
  if (node.type === 'field') return 1
  let count = 0
  for (const c of node.children || []) count += countFields(c)
  return count
}

// 展开/折叠全部
const expandAllTrigger = ref(0)
const collapseAllTrigger = ref(0)

provide('expandAll', expandAllTrigger)
provide('collapseAll', collapseAllTrigger)

function expandAll() {
  expandAllTrigger.value++
}
function collapseAll() {
  collapseAllTrigger.value++
}

// 处理更新
function handleUpdate(event) {
  editCount.value++
  console.log('[Field Update]', event.path, '=>', event.value)
}

// 处理焦点
function handleFocus(path) {
  focusedPath.value = path
}
</script>

<style scoped>
.config-tree {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #fff;
}

.tree-toolbar {
  padding: 10px 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-bar {
  font-size: 12px;
  color: #4b5563;
}
.legend-title {
  font-weight: 600;
}
.legend-item {
  margin-right: 10px;
}
.legend-item .mark {
  font-weight: 600;
  color: #2563eb;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tree-status {
  padding: 6px 12px;
  border-top: 1px solid #e5e7eb;
  background: #f9fafb;
  font-size: 11px;
  color: #6b7280;
  display: flex;
  gap: 16px;
}
</style>
