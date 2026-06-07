<template>
  <div class="tree-prop">
    <span class="req-indicator">{{ indicator }}</span>
    <span class="tree-prop-key">{{ leaf.key }}:</span>
    <span class="tree-prop-value">
      <component :is="controlComponent" v-model="value" />
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TreeLeaf } from '@/types/tree'

interface Props {
  leaf: TreeLeaf
}

const props = defineProps<Props>()
const value = ref(props.leaf.value)

const indicator = computed(() => {
  if (props.leaf.required) return '*'
  if (props.leaf.derived) return '→'
  if (props.leaf.custom) return '✎'
  if (props.leaf.default !== undefined) return 'D'
  return '○'
})

const controlComponent = computed(() => {
  // TODO: implement value_type dispatch
  return 'input'
})
</script>

<style scoped>
.tree-prop {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 6px;
  margin-bottom: 1px;
}
.tree-prop:hover { background: #f7f8fa; }
.req-indicator { width: 16px; text-align: center; font-weight: 700; }
.tree-prop-key { font-family: monospace; font-size: 14px; color: #616e7c; min-width: 90px; }
</style>