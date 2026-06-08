<template>
  <div class="app">
    <ConfigTreePanel />
    <QAPanel />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import ConfigTreePanel from './components/ConfigTreePanel.vue'
import QAPanel from './components/QAPanel.vue'
import { ws } from './services/ws'

onMounted(() => {
  ws.connect('ws://localhost:8765/ws')
})

onUnmounted(() => {
  ws.disconnect()
})
</script>

<style>
.app {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  height: 100vh;
  width: 100vw;
}
</style>
