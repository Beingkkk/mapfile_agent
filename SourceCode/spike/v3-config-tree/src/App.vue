<template>
  <div class="app">
    <ConfigTree :tree="mockTree" />
  </div>
</template>

<script setup>
import ConfigTree from './components/ConfigTree.vue'
import { mockTree, stats } from './data/mock_tree.js'

console.log('[V3 Spike] Mock tree loaded:', stats)
</script>

<style>
.app {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}
</style>
