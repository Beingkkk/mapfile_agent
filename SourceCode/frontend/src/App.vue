<template>
  <div class="app">
    <ConfigTreePanel />
    <QAPanel />
  </div>
</template>

<script setup lang="ts">
import ConfigTreePanel from './components/ConfigTreePanel.vue'
import QAPanel from './components/QAPanel.vue'
</script>

<style>
.app {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  height: 100vh;
  width: 100vw;
}
</style>
