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
      // Auto-start loading placeholder for all question messages
      // (covers QAPanel input, FieldEditor ? button, quick questions, etc.)
      if (message.type === 'question') {
        const uiStore = useUIStore()
        uiStore.startQALoading()
      }
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
        // Insert visual divider only when there was an actual QA exchange
        uiStore.resetHistoryContext()
        break
      case 'qa_result':
        uiStore.finishQALoading()
        uiStore.addQAMessage({
          role: 'bot',
          text: msg.bot_message,
          focus_param: msg.focus_param ?? null,
        })
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
        // Auto-show error summary in QA panel when validation fails
        if (msg.validation_state === 'fail' && msg.validation_errors?.length > 0) {
          const errors = msg.validation_errors as Array<{ path: string; message: string }>
          const errorLines = errors.map((e) => `• \`${e.path}\`: ${e.message}`).join('\n')
          uiStore.addQAMessage({
            role: 'system',
            text: `📋 校验发现 ${errors.length} 处错误：\n${errorLines}\n\n💡 可点击错误字段旁的 ? 按钮向 LLM 求助，或直接在输入框提问。`,
          })
        }
        break
      case 'export_result':
        if (msg.success) {
          const files = msg.files as Array<{ name: string; content_base64: string }>
          if (window.electronAPI) {
            // Electron environment: open save dialog
            window.electronAPI.saveExportFiles(files).then((result) => {
              if (result.success) {
                console.log('[WS] Files saved:', result.saved, 'to', result.directory)
              } else if (result.error) {
                console.error('[WS] Save cancelled or failed:', result.error)
              } else if (result.errors && result.errors.length > 0) {
                console.error('[WS] Some files failed to save:', result.errors)
              }
            })
          } else {
            // Browser environment: log only
            console.log('[WS] Export success (browser mode):', files.map((f: any) => f.name))
          }
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
        uiStore.finishQALoading()
        uiStore.addQAMessage({ role: 'system', text: `服务错误: ${msg.message}` })
        break
    }
  }

  private reconnect() {
    this.reconnectTimer = setTimeout(() => {
      console.log('[WS] Reconnecting...')
      this.connect('ws://localhost:18091/ws', this._sessionId)
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
