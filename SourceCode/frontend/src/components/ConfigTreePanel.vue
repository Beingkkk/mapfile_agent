<template>
  <section class="left-panel">
    <div class="panel-header">
      <div class="panel-header-title">
        🌲 配置树
        <span class="panel-header-sub">MapServer 8.4</span>
      </div>
    </div>
    <div class="tree-scroll">
      <div class="tree">
        <ObjectCard v-if="tree" :node="tree" :depth="0" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import ObjectCard from './ObjectCard.vue'

const sessionStore = useSessionStore()
const tree = computed(() => sessionStore.params)
</script>

<style scoped>
.left-panel {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #e4e7eb;
  overflow: hidden;
}
.panel-header {
  padding: 12px 18px;
  border-bottom: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.panel-header-title {
  font-size: 16px;
  font-weight: 700;
}
.panel-header-sub {
  font-size: 13px;
  color: #7b8794;
  margin-left: 8px;
}
.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
}
</style>