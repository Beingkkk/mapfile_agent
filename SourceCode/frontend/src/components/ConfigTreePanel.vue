<template>
  <section class="left-panel">
    <div class="panel-header">
      <div class="panel-header-title">
        🌲 配置树
        <span class="panel-header-sub">MapServer 8.4</span>
      </div>
      <div class="toolbar">
        <button class="tool-btn" :class="{ active: uiStore.showMode === 'all' }" @click="uiStore.setShowMode('all')">全部</button>
        <button class="tool-btn" :class="{ active: uiStore.showMode === 'required' }" @click="uiStore.setShowMode('required')">仅必填</button>
        <button class="tool-btn validate" @click="validate">🔍 校验</button>
        <button class="tool-btn export" :disabled="!sessionStore.can_export" @click="exportMapfile">📥 导出</button>
      </div>
    </div>
    <div class="legend">
      📋 图例：* 必填 · D 默认值 · ○ 可选 · → 推导 · ✎ 自定义
      <span v-if="sessionStore.validation_state === 'fail'" class="status-badge fail">校验失败</span>
      <span v-else-if="sessionStore.validation_state === 'pass'" class="status-badge pass">校验通过</span>
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
import { useUIStore } from '@/stores/ui'
import ObjectCard from './ObjectCard.vue'
import { ws } from '@/services/ws'

const sessionStore = useSessionStore()
const uiStore = useUIStore()
const tree = computed(() => sessionStore.params)

function validate() {
  ws.send({ type: 'validate' })
}

function exportMapfile() {
  ws.send({ type: 'export' })
}
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
  margin-bottom: 8px;
}
.panel-header-sub {
  font-size: 13px;
  color: #7b8794;
  margin-left: 8px;
}
.toolbar {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.tool-btn {
  padding: 4px 10px;
  font-size: 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}
.tool-btn.active {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}
.tool-btn.validate { color: #2563eb; }
.tool-btn.export { color: #16a34a; }
.tool-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.legend {
  padding: 8px 18px;
  font-size: 12px;
  color: #6b7280;
  border-bottom: 1px solid #f3f4f6;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.status-badge.pass { background: #dcfce7; color: #166534; }
.status-badge.fail { background: #fee2e2; color: #991b1b; }
.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
}
</style>
