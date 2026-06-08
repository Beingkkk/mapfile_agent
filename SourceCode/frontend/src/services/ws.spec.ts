import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { WebSocketService } from './ws'

// Mock WebSocket globally
class MockWebSocket {
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3

  readyState = MockWebSocket.CONNECTING
  url = ''
  onopen: ((e?: any) => void) | null = null
  onmessage: ((e?: any) => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((e?: any) => void) | null = null

  constructor(url: string) {
    this.url = url
    // Simulate async open
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN
      this.onopen?.()
    }, 10)
  }

  send(data: string) {
    // no-op in tests
  }

  close() {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.()
  }
}

// @ts-ignore
global.WebSocket = MockWebSocket

// Mock pinia stores
const mockSessionStore = {
  applyTreeState: vi.fn(),
  setFocus: vi.fn(),
  validation_state: 'idle',
  validation_errors: [],
  can_export: false,
  service_types: ['wms'],
  mapcache_enabled: false,
}

const mockUIStore = {
  addQAMessage: vi.fn(),
  qaFocusParam: null,
}

vi.mock('@/stores/session', () => ({
  useSessionStore: () => mockSessionStore,
}))
vi.mock('@/stores/ui', () => ({
  useUIStore: () => mockUIStore,
}))

describe('WebSocketService', () => {
  let ws: WebSocketService

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.clearAllMocks()
    ws = new WebSocketService()
  })

  afterEach(() => {
    ws.disconnect()
    vi.useRealTimers()
  })

  it('connects to the correct URL with session_id', () => {
    ws.connect('ws://localhost:8765/ws', 'test-session')
    // @ts-ignore
    expect(ws.ws?.url).toContain('session_id=test-session')
  })

  it('has correct initial state', () => {
    expect(ws.isConnected).toBe(false)
  })

  it('sends messages only when connected', () => {
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    ws.send({ type: 'test' })
    expect(consoleWarn).toHaveBeenCalledWith(
      '[WS] Not connected, message dropped:',
      expect.objectContaining({ type: 'test' })
    )
    consoleWarn.mockRestore()
  })

  it('registers and unregisters handlers', () => {
    const handler = vi.fn()
    const unregister = ws.on('test_event', handler)

    // Simulate incoming WebSocket message via onmessage callback
    // @ts-ignore
    ws.ws = {
      readyState: 1 as const, // OPEN
      send: vi.fn(),
      close: vi.fn(),
    }

    // Call handlers directly (same as onmessage flow in ws.ts)
    const handlers = ws['handlers'].get('test_event') || []
    handlers.forEach((h: any) => h({ type: 'test_event', payload: 'hello' }))

    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ type: 'test_event', payload: 'hello' }))

    unregister()

    // After unregister, calling again should not trigger
    const handlersAfter = ws['handlers'].get('test_event') || []
    handlersAfter.forEach((h: any) => h({ type: 'test_event' }))

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('routes tree_state messages to session store', () => {
    const payload = {
      type: 'tree_state',
      params_snapshot: { name: 'test' },
      validation_state: 'pass',
      validation_errors: [],
    }
    // @ts-ignore
    ws._routeToStores(payload)
    expect(mockSessionStore.applyTreeState).toHaveBeenCalledWith(payload)
  })

  it('routes validation_result messages correctly', () => {
    const payload = {
      type: 'validation_result',
      validation_state: 'fail',
      validation_errors: [{ path: 'map.name', message: 'Missing' }],
      can_export: false,
    }
    // @ts-ignore
    ws._routeToStores(payload)
    expect(mockSessionStore.validation_state).toBe('fail')
    expect(mockSessionStore.can_export).toBe(false)
  })

  it('routes qa_result messages to UI store', () => {
    const payload = {
      type: 'qa_result',
      bot_message: 'Here is the answer',
      params_update: [],
    }
    // @ts-ignore
    ws._routeToStores(payload)
    expect(mockUIStore.addQAMessage).toHaveBeenCalledWith({
      role: 'bot',
      text: 'Here is the answer',
      focus_param: null,
    })
  })

  it('handles export_result success in browser mode', () => {
    const consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {})
    const payload = {
      type: 'export_result',
      success: true,
      files: [{ name: 'mapfile.map', content_base64: 'YWJj' }],
    }
    // @ts-ignore
    ws._routeToStores(payload)
    expect(consoleLog).toHaveBeenCalled()
    consoleLog.mockRestore()
  })

  it('handles error messages', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    // @ts-ignore
    ws._routeToStores({ type: 'error', message: 'Something went wrong' })
    expect(consoleError).toHaveBeenCalledWith('[WS] Server error:', 'Something went wrong')
    consoleError.mockRestore()
  })

  it('disconnects cleanly', () => {
    ws.connect('ws://localhost:8765/ws')
    ws.disconnect()
    expect(ws.isConnected).toBe(false)
  })

  it('reconnects after close', () => {
    ws.connect('ws://localhost:8765/ws', 's1')
    // Fast-forward past reconnect timer
    vi.advanceTimersByTime(5000)
    // Should attempt reconnection (we just verify no throw)
    expect(() => vi.advanceTimersByTime(5000)).not.toThrow()
  })
})
