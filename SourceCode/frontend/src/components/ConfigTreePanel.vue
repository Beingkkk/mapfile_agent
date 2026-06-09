<template>
  <section class="left-panel">
    <!-- Panel Header: title left, actions right -->
    <div class="panel-header">
      <div class="panel-header-title">
        🌲 配置树
        <span class="panel-header-sub">MapServer 8.4</span>
      </div>
      <div class="panel-header-actions">
        <button class="btn-pill import" title="导入" @click="importMapfile">
          <span class="btn-pill-icon">📂</span>
          <span class="btn-pill-text">导入</span>
        </button>
        <span class="action-divider" />
        <button class="btn-pill validate" title="校验" @click="validate">
          <span class="btn-pill-icon">✅</span>
          <span class="btn-pill-text">校验</span>
        </button>
        <button
          class="btn-pill export"
          title="导出"
          :disabled="!sessionStore.can_export"
          @click="exportMapfile"
        >
          <span class="btn-pill-icon">📥</span>
          <span class="btn-pill-text">导出</span>
        </button>
      </div>
    </div>

    <!-- Service Type Bar -->
    <div class="service-type-bar">
      <span class="service-type-label">服务类型</span>
      <div class="service-type-group">
        <label class="svc-checkbox">
          <input
            type="checkbox"
            :checked="sessionStore.service_types.includes('wms')"
            @change="toggleService('wms', ($event.target as HTMLInputElement).checked)"
          />
          <span>WMS</span>
        </label>
        <label class="svc-checkbox">
          <input
            type="checkbox"
            :checked="sessionStore.service_types.includes('wfs')"
            @change="toggleService('wfs', ($event.target as HTMLInputElement).checked)"
          />
          <span>WFS</span>
        </label>
        <label class="svc-checkbox">
          <input
            type="checkbox"
            :checked="sessionStore.service_types.includes('wcs')"
            @change="toggleService('wcs', ($event.target as HTMLInputElement).checked)"
          />
          <span>WCS</span>
        </label>
        <span class="service-divider" />
        <label class="svc-checkbox mapcache">
          <input
            type="checkbox"
            :checked="sessionStore.mapcache_enabled"
            @change="toggleMapcache(($event.target as HTMLInputElement).checked)"
          />
          <span>MapCache</span>
        </label>
      </div>
    </div>

    <!-- Search Bar -->
    <div class="search-bar">
      <span class="search-icon">🔍</span>
      <input
        ref="searchInputRef"
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索字段..."
        @focus="isSearchFocused = true"
        @keydown.esc="clearSearch"
      />
      <button
        v-if="searchQuery"
        class="search-clear"
        title="清除"
        @click="clearSearch"
      >
        ×
      </button>
      <!-- Search Results Dropdown -->
      <div
        v-if="searchResults.length > 0 && isSearchFocused"
        class="search-dropdown"
      >
        <div
          v-for="result in searchResults"
          :key="result.path"
          class="search-result-item"
          @mousedown.prevent="onResultClick(result)"
        >
          <span class="search-result-key">{{ result.key }}</span>
          <span class="search-result-meta">
            <span class="search-result-type">[{{ result.value_type }}]</span>
            <span class="search-result-path">{{ result.parentPath }}</span>
          </span>
        </div>
      </div>
      <div
        v-else-if="searchQuery && isSearchFocused && searchResults.length === 0"
        class="search-dropdown empty"
      >
        <span class="search-empty">无匹配字段</span>
      </div>
    </div>

    <!-- Legend Bar: showmode toggle + legend text + status -->
    <div class="legend-bar">
      <div class="showmode-toggle">
        <button
          class="showmode-btn"
          :class="{ active: uiStore.showMode === 'all' }"
          @click="uiStore.setShowMode('all')"
        >
          全部
        </button>
        <button
          class="showmode-btn"
          :class="{ active: uiStore.showMode === 'required' }"
          @click="uiStore.setShowMode('required')"
        >
          建议填
        </button>
        <button
          class="showmode-btn"
          :class="{ active: uiStore.showMode === 'strict' }"
          @click="uiStore.setShowMode('strict')"
        >
          仅必填
        </button>
      </div>
      <div class="legend-items">
        <span class="legend-item"><span class="req-dot required">*</span>必填</span>
        <span class="legend-item"><span class="req-dot required-when">◆</span>条件</span>
        <span class="legend-item"><span class="req-dot default">D</span>默认</span>
        <span class="legend-item"><span class="req-dot optional">○</span>可选</span>
        <span class="legend-item"><span class="req-dot derived">→</span>推导</span>
        <span class="legend-item"><span class="req-dot custom">✎</span>自定义</span>
      </div>
      <div class="legend-status">
        <span v-if="sessionStore.validation_state === 'fail'" class="status-badge fail">校验失败</span>
        <span v-else-if="sessionStore.validation_state === 'pass'" class="status-badge pass">校验通过</span>
      </div>
    </div>

    <!-- Tree Scroll Area -->
    <div class="tree-scroll">
      <div v-if="!isTreeReady" class="tree-loading">
        <div class="tree-loading-spinner">⏳</div>
        <div class="tree-loading-text">正在加载配置...</div>
        <div class="tree-loading-hint">请确保后端服务已启动</div>
      </div>
      <div v-else class="tree">
        <ObjectCard :node="tree" :depth="0" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, nextTick } from 'vue'
import type { TreeNode, TreeLeaf } from '@/types/tree'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'
import ObjectCard from './ObjectCard.vue'
import { ws } from '@/services/ws'

const sessionStore = useSessionStore()
const uiStore = useUIStore()
const tree = computed(() => sessionStore.params)

// ── Search ──
const searchQuery = ref('')
const isSearchFocused = ref(false)
const searchInputRef = ref<HTMLInputElement | null>(null)

interface SearchResult {
  key: string
  path: string
  value_type: string
  parentPath: string
}

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []

  const results: SearchResult[] = []

  function traverse(node: TreeNode) {
    for (const child of node.children || []) {
      if ('children' in child) {
        traverse(child)
      } else {
        const leaf = child as TreeLeaf
        if (
          leaf.key.toLowerCase().includes(q) ||
          leaf.path.toLowerCase().includes(q)
        ) {
          const parts = leaf.path.split('.')
          parts.pop()
          const parentPath = parts.join('.') || 'map'
          results.push({
            key: leaf.key,
            path: leaf.path,
            value_type: leaf.value_type,
            parentPath,
          })
        }
      }
    }
  }

  const root = tree.value as unknown as TreeNode
  if (root?.children) {
    traverse(root)
  }

  return results.slice(0, 10)
})

function clearSearch() {
  searchQuery.value = ''
  isSearchFocused.value = false
  searchInputRef.value?.blur()
}

function getAncestorPaths(path: string): string[] {
  const parts = path.split('.')
  const ancestors: string[] = []
  let current = ''
  for (let i = 0; i < parts.length; i++) {
    current = current ? `${current}.${parts[i]}` : parts[i]
    ancestors.push(current)
  }
  return ancestors
}

function onResultClick(result: SearchResult) {
  searchQuery.value = ''
  isSearchFocused.value = false

  // Expand all ancestor nodes
  const ancestors = getAncestorPaths(result.parentPath)
  uiStore.expandPaths(ancestors)

  // Also set focus to the field
  ws.send({ type: 'focus_change', path: result.path })

  // Scroll to element after DOM update
  nextTick(() => {
    const el = document.querySelector(`[data-path="${result.path}"]`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('search-highlight')
      setTimeout(() => el.classList.remove('search-highlight'), 2000)
    }
  })
}

/** Tree is ready when params has a valid object_type (from backend tree_state).
 *  Note: children may be empty for a freshly-created MAP node. */
const isTreeReady = computed(() => {
  const p = sessionStore.params
  return p && typeof p === 'object' && p.object_type === 'MAP'
})

function validate() {
  ws.send({ type: 'validate' })
}

function exportMapfile() {
  ws.send({ type: 'export' })
}

async function importMapfile() {
  if (!window.electronAPI) {
    console.warn('[Import] Browser mode not supported for import')
    return
  }
  const result = await window.electronAPI.openFile({
    filters: [{ name: 'Mapfile', extensions: ['map'] }],
  })
  if (result.canceled || result.filePaths.length === 0) return

  const filePath = result.filePaths[0]
  const readResult = await window.electronAPI.readFile(filePath)
  if (!readResult.success || readResult.content === undefined) {
    console.error('[Import] Failed to read file:', readResult.error)
    return
  }

  ws.send({ type: 'import_mapfile', content: readResult.content })
}

function toggleService(service: string, enabled: boolean) {
  const current = new Set(sessionStore.service_types)
  if (enabled) {
    current.add(service)
  } else {
    current.delete(service)
  }
  // At least one service must be selected
  if (current.size === 0) {
    current.add('wms')
  }
  const services = Array.from(current)
  sessionStore.setServiceTypes(services, sessionStore.mapcache_enabled)
  ws.send({
    type: 'set_service_types',
    services,
    mapcache_enabled: sessionStore.mapcache_enabled,
  })
}

function toggleMapcache(enabled: boolean) {
  sessionStore.setServiceTypes(sessionStore.service_types, enabled)
  ws.send({
    type: 'set_service_types',
    services: sessionStore.service_types,
    mapcache_enabled: enabled,
  })
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

/* ── Panel Header ── */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  background: #fff;
  border-bottom: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.panel-header-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2933;
  letter-spacing: -0.2px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-header-sub {
  font-size: 13px;
  color: #7b8794;
}
.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Pill buttons */
.btn-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #4b5563;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn-pill:hover {
  background: #f7f8fa;
  border-color: #9aa5b1;
  color: #1f2937;
}
.btn-pill.import:hover { color: #9333ea; border-color: #9333ea; }
.btn-pill.validate:hover { color: #2563eb; border-color: #2563eb; }
.btn-pill.export:hover { color: #16a34a; border-color: #16a34a; }

.action-divider {
  width: 1px;
  height: 18px;
  background: #d1d5db;
  margin: 0 2px;
}
.btn-pill:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.btn-pill-icon {
  font-size: 14px;
  line-height: 1;
}
.btn-pill-text {
  line-height: 1;
}

/* ── Service Type Bar ── */
.service-type-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 18px;
  background: #fff;
  border-bottom: 1px solid #e4e7eb;
  font-size: 13px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.service-type-label {
  font-weight: 600;
  color: #52606d;
  font-size: 13px;
  white-space: nowrap;
}
.service-type-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.svc-checkbox {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  user-select: none;
  color: #4b5563;
  font-size: 13px;
  transition: color 0.15s;
}
.svc-checkbox:hover { color: #1f2933; }
.svc-checkbox input {
  width: 14px;
  height: 14px;
  accent-color: #486581;
  cursor: pointer;
}
.svc-checkbox.mapcache span {
  color: #9333ea;
  font-weight: 600;
}
.service-divider {
  width: 1px;
  height: 16px;
  background: #d1d5db;
  margin: 0 2px;
}

/* ── Search Bar ── */
.search-bar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  background: #fff;
  border-bottom: 1px solid #e4e7eb;
  flex-shrink: 0;
}
.search-icon {
  font-size: 13px;
  color: #9aa5b1;
  flex-shrink: 0;
}
.search-input {
  flex: 1;
  padding: 5px 9px;
  border: 1.5px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  color: #374151;
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-input:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
}
.search-input::placeholder {
  color: #9aa5b1;
}
.search-clear {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #9aa5b1;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.search-clear:hover {
  background: #f0f2f5;
  color: #52606d;
}

/* Search dropdown */
.search-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 18px;
  right: 18px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  z-index: 100;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}
.search-dropdown.empty {
  padding: 12px;
  text-align: center;
}
.search-empty {
  font-size: 13px;
  color: #9aa5b1;
}
.search-result-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s;
}
.search-result-item:hover {
  background: #f0f4f8;
}
.search-result-key {
  font-family: monospace;
  font-size: 13px;
  color: #374151;
  font-weight: 600;
  flex-shrink: 0;
}
.search-result-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
}
.search-result-type {
  font-size: 11px;
  color: #7b8794;
  background: #f0f2f5;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: monospace;
  flex-shrink: 0;
}
.search-result-path {
  font-size: 12px;
  color: #9aa5b1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Search highlight on target element */
:deep(.search-highlight) {
  animation: search-highlight-pulse 2s ease-out;
}
@keyframes search-highlight-pulse {
  0% { background-color: #fef3c7; }
  100% { background-color: transparent; }
}

/* ── Legend Bar ── */
.legend-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 18px;
  background: #f7f8fa;
  border-bottom: 1px solid #e4e7eb;
  font-size: 13px;
  color: #616e7c;
  flex-shrink: 0;
  flex-wrap: wrap;
}

/* Show mode toggle */
.showmode-toggle {
  display: flex;
  align-items: center;
  background: #f0f2f5;
  border-radius: 8px;
  padding: 2px;
  border: 1px solid #d1d5db;
}
.showmode-btn {
  padding: 5px 10px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #616e7c;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.showmode-btn:hover { color: #3e4c59; }
.showmode-btn.active {
  background: #fff;
  color: #1f2933;
  box-shadow: 0 1px 2px 0 rgb(31 41 51 / 0.04);
  font-weight: 600;
}

/* Legend items */
.legend-items {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 3px;
}
.req-dot {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  flex-shrink: 0;
}
.req-dot.required { color: #de350b; font-size: 13px; }
.req-dot.required-when { color: #ea580c; font-size: 12px; }
.req-dot.default { color: #7b8794; font-size: 10px; background: #f0f2f5; }
.req-dot.optional { color: #9aa5b1; font-size: 11px; }
.req-dot.derived { color: #7b8794; font-size: 11px; }
.req-dot.custom { color: #486581; font-size: 11px; background: #f0f4f8; }

/* Legend status */
.legend-status {
  margin-left: auto;
}
.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.status-badge.pass { background: #dcfce7; color: #166534; }
.status-badge.fail { background: #fee2e2; color: #991b1b; }

/* ── Tree Scroll Area ── */
.tree-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px 18px;
}

.tree-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: #6b7280;
}
.tree-loading-spinner {
  font-size: 32px;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
.tree-loading-text {
  font-size: 14px;
  font-weight: 500;
  color: #374151;
}
.tree-loading-hint {
  font-size: 12px;
  color: #9aa5b1;
}
</style>
