<template>
  <div class="tree-obj">
    <div class="tree-obj-header" @click="toggle">
      <span class="tree-toggle">{{ expanded ? '▼' : '▶' }}</span>
      <span class="tree-obj-name" @click.stop="handleFocus">{{ node.object_type }}</span>
      <span v-if="node.object_type === 'LAYER' || node.object_type === 'MAP'" class="add-btn" @click.stop="showAddMenu">
        + 添加
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
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { TreeNode } from '@/types/tree'
import FieldEditor from './FieldEditor.vue'
import { ws } from '@/services/ws'

interface Props {
  node: TreeNode
  depth: number
}

const props = defineProps<Props>()
const expanded = ref(props.node.expanded)

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
.tree-children { padding-left: 20px; border-left: 1.5px solid #e4e7eb; margin-left: 10px; }
</style>
