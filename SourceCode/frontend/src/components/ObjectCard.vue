<template>
  <div class="tree-obj">
    <div class="tree-obj-header" @click="toggle">
      <span class="tree-toggle">{{ expanded ? '▼' : '▶' }}</span>
      <span class="tree-obj-name">{{ node.object_type }}</span>
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
import type { TreeNode, TreeLeaf } from '@/types/tree'
import FieldEditor from './FieldEditor.vue'

interface Props {
  node: TreeNode
  depth: number
}

const props = defineProps<Props>()
const expanded = ref(props.node.expanded)

function toggle() {
  expanded.value = !expanded.value
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
.tree-children { padding-left: 20px; border-left: 1.5px solid #e4e7eb; margin-left: 10px; }
</style>