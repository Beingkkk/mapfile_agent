import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useUIStore } from './ui'

describe('UIStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default state', () => {
    const store = useUIStore()
    expect(store.showMode).toBe('all')
    expect(store.qaRoundCount).toBe(0)
    expect(store.qaMessages).toEqual([])
    expect(store.qaFocusParam).toBeNull()
    expect(store.expandedNodes).toContain('map')
    expect(store.expandedNodes).toContain('web')
  })

  it('toggles show mode', () => {
    const store = useUIStore()
    expect(store.showMode).toBe('all')
    store.setShowMode('required')
    expect(store.showMode).toBe('required')
    store.setShowMode('all')
    expect(store.showMode).toBe('all')
  })

  it('toggles node expansion', () => {
    const store = useUIStore()
    const nodeId = 'test-node'
    expect(store.expandedNodes.has(nodeId)).toBe(false)
    store.toggleNode(nodeId)
    expect(store.expandedNodes.has(nodeId)).toBe(true)
    store.toggleNode(nodeId)
    expect(store.expandedNodes.has(nodeId)).toBe(false)
  })

  it('adds QA messages and tracks round count', () => {
    const store = useUIStore()
    expect(store.qaMessages).toHaveLength(0)
    expect(store.qaRoundCount).toBe(0)

    store.addQAMessage({ role: 'user', text: 'Hello' })
    expect(store.qaMessages).toHaveLength(1)
    expect(store.qaRoundCount).toBe(0)

    store.addQAMessage({ role: 'bot', text: 'Hi!' })
    expect(store.qaMessages).toHaveLength(2)
    expect(store.qaRoundCount).toBe(1)

    store.addQAMessage({ role: 'user', text: 'Q2' })
    store.addQAMessage({ role: 'bot', text: 'A2' })
    expect(store.qaMessages).toHaveLength(4)
    expect(store.qaRoundCount).toBe(2)
  })

  it('preserves message roles and text', () => {
    const store = useUIStore()
    store.addQAMessage({ role: 'user', text: 'question' })
    store.addQAMessage({ role: 'bot', text: 'answer' })
    expect(store.qaMessages[0].role).toBe('user')
    expect(store.qaMessages[0].text).toBe('question')
    expect(store.qaMessages[1].role).toBe('bot')
    expect(store.qaMessages[1].text).toBe('answer')
  })

  it('clears QA state', () => {
    const store = useUIStore()
    store.addQAMessage({ role: 'user', text: 'Q' })
    store.addQAMessage({ role: 'bot', text: 'A' })
    expect(store.qaMessages.length).toBeGreaterThan(0)

    store.clearQA()
    expect(store.qaMessages).toEqual([])
    expect(store.qaRoundCount).toBe(0)
  })

  describe('QA loading placeholder', () => {
    it('adds loading message on startQALoading', () => {
      const store = useUIStore()
      store.addQAMessage({ role: 'user', text: 'Q' })
      store.startQALoading()
      expect(store.qaMessages).toHaveLength(2)
      expect(store.qaMessages[1].role).toBe('loading')
      expect(store.qaMessages[1].text).toBe('思考中…')
    })

    it('removes loading message on finishQALoading', () => {
      const store = useUIStore()
      store.addQAMessage({ role: 'user', text: 'Q' })
      store.startQALoading()
      store.finishQALoading()
      expect(store.qaMessages).toHaveLength(1)
      expect(store.qaMessages.some((m) => m.role === 'loading')).toBe(false)
    })

    it('replaces stale loading message when startQALoading called twice', () => {
      const store = useUIStore()
      store.startQALoading()
      store.startQALoading()
      expect(store.qaMessages.filter((m) => m.role === 'loading')).toHaveLength(1)
    })

    it('adds system error when finishQALoading receives error', () => {
      const store = useUIStore()
      store.startQALoading()
      store.finishQALoading({ error: 'Timeout' })
      expect(store.qaMessages.some((m) => m.role === 'loading')).toBe(false)
      expect(store.qaMessages.some((m) => m.role === 'system' && m.text === 'Timeout')).toBe(true)
    })

    it('excludes loading messages from round count', () => {
      const store = useUIStore()
      store.addQAMessage({ role: 'user', text: 'Q' })
      store.startQALoading()
      store.finishQALoading()
      store.addQAMessage({ role: 'bot', text: 'A' })
      expect(store.qaRoundCount).toBe(1)
    })
  })
})
