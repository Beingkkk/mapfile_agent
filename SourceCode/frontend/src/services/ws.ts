import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'

export class WebSocketService {
  private ws: WebSocket | null = null
  private handlers: Map<string, ((payload: any) => void)[]> = new Map()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private _sessionId: string = 'default'

  connect(url: string, sessionId?: string) {
    if (sessionId) this._sessionId = sessionId
    const fullUrl = `${url}?session_id=${this._sessionId}`
    this.ws = new WebSocket(fullUrl)
    this.ws.onopen = () => {
      console.log('[WS] Connected')
      this.startHeartbeat()
      // Init session on connect
      this.send({ type: 'init_session' })
    }
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        this._routeToStores(msg)
        const handlers = this.handlers.get(msg.type) || []
        handlers.forEach((h) => h(msg))
      } catch {
        console.error('[WS] Invalid message:', event.data)
      }
    }
    this.ws.onclose = () => {
      console.log('[WS] Disconnected')
      this.stopHeartbeat()
      this.reconnect()
    }
    this.ws.onerror = (err) => {
      console.error('[WS] Error:', err)
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.stopHeartbeat()
    this.ws?.close()
    this.ws = null
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  send(message: any) {
    if (this.isConnected) {
      this.ws!.send(JSON.stringify(message))
    } else {
      console.warn('[WS] Not connected, message dropped:', message)
    }
  }

  on(type: string, handler: (payload: any) => void): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, [])
    }
    this.handlers.get(type)!.push(handler)
    return () => {
      const list = this.handlers.get(type) || []
      const idx = list.indexOf(handler)
      if (idx >= 0) list.splice(idx, 1)
    }
  }

  private _routeToStores(msg: any) {
    const sessionStore = useSessionStore()
    const uiStore = useUIStore()

    switch (msg.type) {
      case 'tree_state':
        sessionStore.applyTreeState(msg)
        break
      case 'focus_state':
        sessionStore.setFocus(msg.focus_param)
        uiStore.qaFocusParam = msg.focus_param
        break
      case 'qa_result':
        uiStore.addQAMessage({ role: 'bot', text: msg.bot_message })
        if (msg.params_update && msg.params_update.length > 0) {
          sessionStore.applyTreeState({
            params_snapshot: msg.params_snapshot,
            validation_state: msg.validation_state,
            validation_errors: msg.validation_errors,
          })
        }
        break
      case 'validation_result':
        sessionStore.validation_state = msg.validation_state
        sessionStore.validation_errors = msg.validation_errors
        sessionStore.can_export = msg.can_export
        break
      case 'export_result':
        if (msg.success) {
          // TODO: trigger file download via Electron
          console.log('[WS] Export success:', msg.files)
        } else {
          console.error('[WS] Export failed:', msg.error)
        }
        break
      case 'import_result':
        if (!msg.success) {
          console.error('[WS] Import failed:', msg.error)
        }
        break
      case 'error':
        console.error('[WS] Server error:', msg.message)
        break
    }
  }

  private reconnect() {
    this.reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...')
      this.connect('ws://localhost:8765/ws', this._sessionId)
    }, 3000)
  }

  private startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
}

export const ws = new WebSocketService()
