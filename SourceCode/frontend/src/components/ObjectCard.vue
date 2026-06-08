<template>
  <div class="tree-obj">
    <!-- Object Header -->
    <div class="tree-obj-header" :class="{ selected: isSelected }" @click="setFocus">
      <span class="tree-toggle" :class="{ collapsed: !expanded }" @click.stop="toggleExpanded">{{ '▼' }}</span>
      <span class="tree-obj-icon" :class="iconClass">{{ iconText }}</span>
      <span class="tree-obj-name">{{ nodeType }}</span>
      <span v-if="nodeIndex" class="tree-obj-index">#{{ nodeIndex }}</span>

      <!-- Hover actions -->
      <span class="tree-obj-actions">
        <button
          v-if="canAddChild"
          class="tree-obj-btn add"
          title="添加子节点"
          @click.stop="showAddMenu"
        >+</button>
        <button
          v-if="canDelete"
          class="tree-obj-btn del"
          title="删除节点"
          @click.stop="deleteNode"
        >×</button>
      </span>
    </div>

    <!-- Children -->
    <div v-if="expanded" class="tree-children">
      <div v-for="child in visibleChildren" :key="child.id || child.path">
        <ObjectCard
          v-if="'children' in child"
          :node="child"
          :depth="depth + 1"
        />
        <FieldEditor
          v-else
          :leaf="child"
        />
      </div>

      <!-- Add child buttons at bottom of children list -->
      <button
        v-for="childType in availableChildTypes"
        :key="childType"
        class="tree-add-btn"
        @click.stop="addChild(childType)"
      >
        + 添加 {{ childType }}
      </button>

      <!-- Add custom prop button at bottom -->
      <button
        v-if="canAddCustom"
        class="tree-add-btn custom"
        @click.stop="openCustomProp"
      >
        ✎ 自定义属性
      </button>
    </div>

    <CustomPropModal
      :parent-path="node.path"
      :visible="showModal"
      @confirm="onCustomConfirm"
      @cancel="showModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TreeNode, TreeLeaf } from '@/types/tree'
import { useUIStore } from '@/stores/ui'
import { useSessionStore } from '@/stores/session'
import FieldEditor from './FieldEditor.vue'
import CustomPropModal from './CustomPropModal.vue'
import { ws } from '@/services/ws'

interface Props {
  node: TreeNode
  depth: number
}

const props = defineProps<Props>()
const uiStore = useUIStore()
const sessionStore = useSessionStore()
const expanded = ref(props.node.expanded ?? true)
const showModal = ref(false)

const nodeType = computed(() => props.node.object_type || 'UNKNOWN')
const nodeIndex = computed(() => {
  const path = props.node?.path
  if (!path) return null
  const m = path.match(/\.(\d+)$/)
  return m ? parseInt(m[1], 10) + 1 : null
})

const isSelected = computed(() => sessionStore.focus_param === props.node.path)

// ── Icon ──
const iconMap: Record<string, string> = {
  MAP: '🗺️',
  LAYER: '📐',
  CLASS: '🎨',
  STYLE: '✏️',
  LABEL: '🏷️',
  WEB: '🌐',
  METADATA: '📋',
  CACHE: '💾',
}
const iconText = computed(() => iconMap[nodeType.value] || '📁')
const iconClass = computed(() => nodeType.value.toLowerCase())

// ── Children filtering by showMode ──
const visibleChildren = computed(() => {
  const children = props.node.children || []
  if (uiStore.showMode === 'all') {
    return children
  }
  // required mode: hide non-required leaves, always show nodes
  return children.filter((child: TreeNode | TreeLeaf) => {
    if ('children' in child) {
      return true // TreeNode always visible
    }
    // TreeLeaf: show only if required
    return (child as TreeLeaf).required === true
  })
})

// ── Node operations ──
const canDelete = computed(() => nodeType.value !== 'MAP')

// ── Add child ──
/** Which child types each parent can create. */
const CHILD_TYPES_MAP: Record<string, string[]> = {
  MAP: ['LAYER', 'WEB'],
  LAYER: ['CLASS', 'METADATA'],
  CLASS: ['STYLE', 'METADATA'],
  WEB: ['METADATA'],
}

/** Child types already present under this node. */
const existingChildTypes = computed(() => {
  return new Set(
    (props.node.children || [])
      .filter((c): c is TreeNode => 'children' in c)
      .map((c) => c.object_type),
  )
})

/** Child types that can still be added. */
const availableChildTypes = computed(() => {
  const types = CHILD_TYPES_MAP[nodeType.value] || []
  return types.filter((t) => !existingChildTypes.value.has(t))
})

const canAddChild = computed(() => availableChildTypes.value.length > 0)

function addChild(childType: string) {
  ws.send({
    type: 'tree_add_node',
    parent_path: props.node.path,
    object_type: childType,
  })
}

function showAddMenu() {
  const first = availableChildTypes.value[0]
  if (first) {
    addChild(first)
  }
}

function deleteNode() {
  ws.send({
    type: 'tree_remove_node',
    path: props.node.path,
  })
}

// ── Custom prop ──
const CUSTOM_ALLOWED = new Set(['MAP', 'WEB', 'METADATA', 'LAYER', 'CLASS', 'CACHE'])
const canAddCustom = computed(() => CUSTOM_ALLOWED.has(nodeType.value))

function openCustomProp() {
  showModal.value = true
}

function onCustomConfirm(key: string, propType: string, value: string, desc: string) {
  showModal.value = false
  let coerced: any = value
  if (propType === 'integer') coerced = parseInt(value, 10) || 0
  else if (propType === 'float') coerced = parseFloat(value) || 0
  else if (propType === 'boolean') coerced = value.toLowerCase() === 'true'
  else if (propType === 'array') {
    try { coerced = JSON.parse(value) } catch { coerced = value.split(',').map(s => s.trim()) }
  }
  else if (propType === 'color') {
    try { coerced = JSON.parse(value) } catch { coerced = [128, 128, 128] }
  }

  ws.send({
    type: 'tree_add_custom_prop',
    parent_path: props.node.path,
    key,
    value: coerced,
    prop_type: propType,
    desc,
  })
}

function toggleExpanded() {
  expanded.value = !expanded.value
  if (props.node.path) {
    uiStore.toggleNode(props.node.path)
  }
}

function setFocus() {
  if (props.node.path) {
    ws.send({
      type: 'focus_change',
      path: props.node.path,
    })
  }
}
</script>

<style scoped>
.tree-obj { margin-bottom: 2px; }

.tree-obj-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.12s;
  user-select: none;
  position: relative;
}
.tree-obj-header:hover { background: #f7f8fa; }
.tree-obj-header.selected {
  background: #f0f4f8;
  box-shadow: inset 3px 0 0 #627d98;
}

/* Toggle button with rotation */
.tree-toggle {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: #9aa5b1;
  flex-shrink: 0;
  transition: transform 0.15s;
}
.tree-toggle.collapsed { transform: rotate(-90deg); }

/* Object type icon */
.tree-obj-icon {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  flex-shrink: 0;
}
.tree-obj-icon.map   { background: rgba(36,59,83,0.08); }
.tree-obj-icon.layer { background: #eff6ff; }
.tree-obj-icon.class { background: #fff7ed; }
.tree-obj-icon.style { background: #fff7ed; }
.tree-obj-icon.label { background: #fff7ed; }
.tree-obj-icon.web   { background: #f0fdf4; }
.tree-obj-icon.cache { background: #faf5ff; }
.tree-obj-icon.meta  { background: #f0fdf4; }

.tree-obj-name {
  font-weight: 600;
  font-size: 14px;
  color: #374151;
}
.tree-obj-index {
  font-size: 13px;
  color: #9aa5b1;
  font-weight: 400;
  margin-left: 2px;
}

/* Hover actions */
.tree-obj-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.15s;
}
.tree-obj-header:hover .tree-obj-actions { opacity: 1; }

.tree-obj-btn {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #9aa5b1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.12s;
}
.tree-obj-btn:hover { background: #f0f2f5; color: #52606d; }
.tree-obj-btn.add:hover { color: #36b37e; }
.tree-obj-btn.del:hover { color: #de350b; }

/* Children area */
.tree-children {
  padding-left: 20px;
  border-left: 1.5px solid #e4e7eb;
  margin-left: 10px;
}

/* Add buttons at bottom of children list */
.tree-add-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  margin: 4px 0;
  border-radius: 6px;
  border: 1.5px dashed #c4cdd5;
  background: transparent;
  color: #7b8794;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s;
}
.tree-add-btn:hover {
  border-color: #829ab1;
  color: #486581;
  background: #f0f4f8;
}
.tree-add-btn.custom {
  border-color: #d9e2ec;
  color: #627d98;
}
.tree-add-btn.custom:hover {
  border-color: #829ab1;
  color: #334e68;
  background: #f0f4f8;
}
</style>
