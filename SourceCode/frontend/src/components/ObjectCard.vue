<template>
  <div class="tree-obj">
    <div class="tree-obj-header" @click="toggle">
      <span class="tree-toggle">{{ expanded ? '▼' : '▶' }}</span>
      <span class="tree-obj-name" @click.stop="handleFocus">{{ node.object_type }}</span>
      <span v-if="node.object_type === 'LAYER' || node.object_type === 'MAP'" class="add-btn" @click.stop="showAddMenu">
        + 添加
      </span>
      <span v-if="canAddCustom" class="add-btn custom" @click.stop="openCustomProp">
        ✎ 自定义
      </span>
    </div>
    <div v-if="expanded" class="tree-children">
      <div v-for="child in node.children" :key="child.id">
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
import { ref } from 'vue'
import type { TreeNode } from '@/types/tree'
import FieldEditor from './FieldEditor.vue'
import CustomPropModal from './CustomPropModal.vue'
import { ws } from '@/services/ws'

interface Props {
  node: TreeNode
  depth: number
}

const props = defineProps<Props>()
const expanded = ref(props.node.expanded)
const showModal = ref(false)

const CUSTOM_ALLOWED = new Set(['MAP', 'WEB', 'METADATA', 'LAYER', 'CLASS', 'CACHE'])
const canAddCustom = CUSTOM_ALLOWED.has(props.node.object_type)

function toggle() {
  expanded.value = !expanded.value
}

function handleFocus() {
  ws.send({
    type: 'focus_change',
    path: props.node.path,
  })
}

function showAddMenu() {
  // TODO: show context menu for adding child nodes
  // For now, just add a LAYER to MAP or CLASS to LAYER
  const parentType = props.node.object_type
  let childType = ''
  if (parentType === 'MAP') childType = 'LAYER'
  else if (parentType === 'LAYER') childType = 'CLASS'
  else if (parentType === 'CLASS') childType = 'STYLE'
  if (childType) {
    ws.send({
      type: 'tree_add_node',
      parent_path: props.node.path,
      object_type: childType,
    })
  }
}

function openCustomProp() {
  showModal.value = true
}

function onCustomConfirm(key: string, propType: string, value: string, desc: string) {
  showModal.value = false
  // Coerce value by type
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
}
.tree-obj-header:hover { background: #f7f8fa; }
.tree-toggle { font-size: 13px; color: #9aa5b1; }
.tree-obj-name { font-weight: 600; font-size: 14px; }
.add-btn {
  margin-left: auto;
  font-size: 12px;
  color: #2563eb;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
}
.add-btn:hover { background: #dbeafe; }
.add-btn.custom { color: #9333ea; }
.add-btn.custom:hover { background: #f3e8ff; }
.tree-children { padding-left: 20px; border-left: 1.5px solid #e4e7eb; margin-left: 10px; }
</style>
