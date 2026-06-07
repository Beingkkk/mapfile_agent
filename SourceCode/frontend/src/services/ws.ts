export class WebSocketService {
  private ws: WebSocket | null = null
  private handlers: Map<string, ((payload: any) => void)[]> = new Map()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null

  connect(url: string) {
    this.ws = new WebSocket(url)
    this.ws.onopen = () => {
      console.log('[WS] Connected')
      this.startHeartbeat()
    }
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
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

  private reconnect() {
    this.reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...')
      this.connect('ws://localhost:8765/ws')
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
