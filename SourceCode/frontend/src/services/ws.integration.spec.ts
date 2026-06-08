import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'
import { WebSocketService } from './ws'

describe('WebSocket Integration — end-to-end message flow', () => {
  let ws: WebSocketService
  let mockWsInstance: any

  beforeEach(() => {
    // Real Pinia stores — no mocks
    setActivePinia(createPinia())
    vi.useFakeTimers({ shouldAdvanceTime: true })

    // Mock WebSocket constructor
    mockWsInstance = {
      readyState: 0, // CONNECTING
      send: vi.fn(),
      close: vi.fn(),
      onopen: null as ((e?: any) => void) | null,
      onmessage: null as ((e?: any) => void) | null,
      onclose: null as (() => void) | null,
      onerror: null as ((e?: any) => void) | null,
    }
    // @ts-ignore
    global.WebSocket = function () { return mockWsInstance }

    ws = new WebSocketService()
  })

  afterEach(() => {
    ws.disconnect()
    vi.useRealTimers()
  })

  it('receives tree_state and populates store with TreeNode structure', () => {
    ws.connect('ws://localhost:8765/ws')

    // Simulate WebSocket open — set readyState BEFORE calling onopen
    // because ws.send() checks isConnected which reads readyState
    mockWsInstance.readyState = 1 // OPEN
    mockWsInstance.onopen?.()

    // Simulate backend response: tree_state with real TreeNode format
    const treeStateMsg = {
      type: 'tree_state',
      params_snapshot: {
        id: 'map',
        path: 'map',
        object_type: 'MAP',
        expanded: true,
        children: [
          {
            id: 'map_name',
            path: 'map.name',
            key: 'name',
            value: 'test_map',
            value_type: 'string',
            phase: 'service',
            required: true,
            derived: false,
            custom: false,
            custom_desc: '',
            user_modified: false,
            errors: [],
          },
          {
            id: 'map_web',
            path: 'web',
            object_type: 'WEB',
            expanded: true,
            children: [],
          }
        ]
      },
      validation_state: 'idle',
      validation_errors: [],
      can_export: false,
      service_types: ['wms'],
      mapcache_enabled: false,
    }

    mockWsInstance.onmessage?.({ data: JSON.stringify(treeStateMsg) })

    // Verify session store received the data
    const sessionStore = useSessionStore()
    expect(sessionStore.params).toEqual(treeStateMsg.params_snapshot)

    // Verify TreeNode structure: must have children array
    expect(sessionStore.params.children).toBeDefined()
    expect(Array.isArray(sessionStore.params.children)).toBe(true)
    expect(sessionStore.params.children.length).toBe(2)

    // First child is TreeLeaf
    const leaf = sessionStore.params.children[0]
    expect(leaf.key).toBe('name')
    expect(leaf.value_type).toBe('string')

    // Second child is TreeNode
    const node = sessionStore.params.children[1]
    expect(node.object_type).toBe('WEB')
    expect(Array.isArray(node.children)).toBe(true)

    // Verify session metadata
    expect(sessionStore.validation_state).toBe('idle')
    expect(sessionStore.service_types).toEqual(['wms'])
  })

  it('receives qa_result and adds message to UI store', () => {
    ws.connect('ws://localhost:8765/ws')
    mockWsInstance.readyState = 1
    mockWsInstance.onopen?.()

    const qaMsg = {
      type: 'qa_result',
      bot_message: 'Here is the answer',
      params_update: [],
      validation_state: 'pass',
      validation_errors: [],
      can_export: true,
    }

    mockWsInstance.onmessage?.({ data: JSON.stringify(qaMsg) })

    const uiStore = useUIStore()
    expect(uiStore.qaMessages).toHaveLength(1)
    expect(uiStore.qaMessages[0].role).toBe('bot')
    expect(uiStore.qaMessages[0].text).toBe('Here is the answer')
    expect(uiStore.qaRoundCount).toBe(0)
  })
})
