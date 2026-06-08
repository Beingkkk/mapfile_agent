<template>
  <div class="app">
    <TitleBar />
    <div class="app-body">
      <ConfigTreePanel />
      <QAPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import TitleBar from './components/TitleBar.vue'
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
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.app-body {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  flex: 1;
  overflow: hidden;
}
</style>
