<template>
  <div class="title-bar" @dblclick="toggleMaximize">
    <div class="title-bar-drag">
      <img :src="iconImg" class="title-bar-icon-img" alt="MapGuide" />
      <span class="title-bar-text">MapGuide</span>
      <span class="title-bar-sub">MapServer 8.4 配置编辑器</span>
    </div>
    <div class="title-bar-controls">
      <button class="tb-btn minimize" title="最小化" @click="minimize">
        <svg viewBox="0 0 16 16" width="12" height="12">
          <rect x="1" y="7" width="14" height="2" fill="currentColor" />
        </svg>
      </button>
      <button class="tb-btn maximize" :title="isMaximized ? '还原' : '最大化'" @click="toggleMaximize">
        <svg v-if="!isMaximized" viewBox="0 0 16 16" width="12" height="12">
          <rect x="1" y="1" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" />
        </svg>
        <svg v-else viewBox="0 0 16 16" width="12" height="12">
          <rect x="3" y="5" width="10" height="10" fill="none" stroke="currentColor" stroke-width="1.5" />
          <rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.5" />
        </svg>
      </button>
      <button class="tb-btn close" title="关闭" @click="close">
        <svg viewBox="0 0 16 16" width="12" height="12">
          <line x1="2" y1="2" x2="14" y2="14" stroke="currentColor" stroke-width="1.5" />
          <line x1="14" y1="2" x2="2" y2="14" stroke="currentColor" stroke-width="1.5" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import iconImg from '@/assets/icon.png'

const isMaximized = ref(false)

const isElectron = typeof window !== 'undefined' && !!window.electronAPI

function minimize() {
  if (isElectron) {
    window.electronAPI!.minimizeWindow()
  }
}

function toggleMaximize() {
  if (isElectron) {
    window.electronAPI!.maximizeWindow()
  }
}

function close() {
  if (isElectron) {
    window.electronAPI!.closeWindow()
  }
}

// Track maximized state via resize event
async function updateMaximizedState() {
  if (isElectron) {
    isMaximized.value = await window.electronAPI!.isMaximized()
  }
}

onMounted(() => {
  updateMaximizedState()
  window.addEventListener('resize', updateMaximizedState)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMaximizedState)
})
</script>

<style scoped>
.title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 36px;
  background: #1a1a2e;
  color: #e2e8f0;
  user-select: none;
  -webkit-app-region: drag;
  flex-shrink: 0;
  border-bottom: 1px solid #2d2d44;
}

.title-bar-drag {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 12px;
  flex: 1;
  height: 100%;
}

.title-bar-icon-img {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  object-fit: contain;
}

.title-bar-text {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.title-bar-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-left: 4px;
}

.title-bar-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.tb-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 100%;
  border: none;
  background: transparent;
  color: #e2e8f0;
  cursor: pointer;
  transition: background 0.15s;
}

.tb-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tb-btn.close:hover {
  background: #e11d48;
}

.tb-btn svg {
  pointer-events: none;
}
</style>
