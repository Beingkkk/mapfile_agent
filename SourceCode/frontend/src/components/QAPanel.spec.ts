import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QAPanel from './QAPanel.vue'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'

// Mock ws service
vi.mock('@/services/ws', () => ({
  ws: {
    send: vi.fn(),
    on: vi.fn(),
  }
}))

import { ws } from '@/services/ws'

// Mock marked
vi.mock('marked', () => ({
  marked: {
    parse: vi.fn((text: string) => text)
  }
}))

describe('QAPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(ws.send).mockClear()
    vi.mocked(ws.on).mockClear()
    // Simulate ws.ts send() behavior: start loading for question messages
    vi.mocked(ws.send).mockImplementation((msg: any) => {
      if (msg?.type === 'question') {
        useUIStore().startQALoading()
      }
    })
  })

  it('renders empty state when no messages and no focus', () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(QAPanel, {
      global: { plugins: [pinia] }
    })

    expect(wrapper.find('.chat-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('选中左侧树节点或参数')
  })

  describe('object path focus (proposal-0011)', () => {
    it('shows friendly block label for LAYER path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const focusBar = wrapper.find('.qa-focus-bar')
      expect(focusBar.exists()).toBe(true)
      expect(focusBar.text()).toContain('LAYER #1')
    })

    it('shows friendly block label for CLASS path with index', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0.classes.1')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const focusBar = wrapper.find('.qa-focus-bar')
      expect(focusBar.text()).toContain('CLASS #2')
    })

    it('shows friendly block label for MAP path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('map')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const focusBar = wrapper.find('.qa-focus-bar')
      expect(focusBar.text()).toContain('MAP')
    })

    it('shows block-level quick questions for object path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const quickQuestions = wrapper.findAll('.quick-q-chip')
      expect(quickQuestions.length).toBe(3)

      const texts = quickQuestions.map(q => q.text())
      expect(texts[0]).toContain('还需要配置什么')
      expect(texts[1]).toContain('必填字段')
      expect(texts[2]).toContain('最佳实践')
    })

    it('shows block-level placeholder for object path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const input = wrapper.find('.input-area textarea')
      expect(input.attributes('placeholder')).toContain('LAYER #1')
    })
  })

  describe('attribute path focus', () => {
    it('shows full path for attribute path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0.name')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const focusBar = wrapper.find('.qa-focus-bar')
      expect(focusBar.exists()).toBe(true)
      expect(focusBar.text()).toContain('layers.0.name')
    })

    it('shows param-level quick questions for attribute path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0.name')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const quickQuestions = wrapper.findAll('.quick-q-chip')
      expect(quickQuestions.length).toBe(3)

      const texts = quickQuestions.map(q => q.text())
      expect(texts[0]).toContain('怎么填')
      expect(texts[1]).toContain('可选值')
      expect(texts[2]).toContain('最佳实践')
    })

    it('shows param-level placeholder for attribute path', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0.name')

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const input = wrapper.find('.input-area textarea')
      expect(input.attributes('placeholder')).toContain('layers.0.name')
    })
  })

  describe('no focus state', () => {
    it('shows default quick questions when no focus', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const quickQuestions = wrapper.findAll('.quick-q-chip')
      expect(quickQuestions.length).toBe(3)

      const texts = quickQuestions.map(q => q.text())
      expect(texts[0]).toContain('检查')
      expect(texts[1]).toContain('导出')
      expect(texts[2]).toContain('潜在问题')
    })

    it('shows hint text in focus bar when no focus', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)

      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })
      await flushPromises()

      const focusBar = wrapper.find('.qa-focus-bar')
      expect(focusBar.classes()).toContain('hint')
      expect(focusBar.text()).toContain('点击左侧树节点或参数')
    })
  })

  describe('loading placeholder (proposal-0012)', () => {
    it('shows loading bubble after sending question', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })

      const input = wrapper.find('.input-area textarea')
      await input.setValue('hello')
      await input.trigger('keydown.enter')
      await flushPromises()

      expect(wrapper.find('.loading-bubble').exists()).toBe(true)
      expect(wrapper.text()).toContain('思考中')
      expect(wrapper.text()).toContain('⏳')
    })

    it('removes loading bubble when qa_result arrives', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const uiStore = useUIStore()
      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })

      await wrapper.find('.input-area textarea').setValue('q')
      await wrapper.find('.input-area textarea').trigger('keydown.enter')
      await flushPromises()
      expect(wrapper.find('.loading-bubble').exists()).toBe(true)

      // Simulate what ws.ts does when qa_result arrives
      uiStore.finishQALoading()
      uiStore.addQAMessage({ role: 'bot', text: 'answer' })
      await flushPromises()

      expect(wrapper.find('.loading-bubble').exists()).toBe(false)
      expect(wrapper.text()).toContain('answer')
    })

    it('shows system error on 30s timeout', async () => {
      vi.useFakeTimers()
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })

      await wrapper.find('.input-area textarea').setValue('q')
      await wrapper.find('.input-area textarea').trigger('keydown.enter')
      await flushPromises()
      expect(wrapper.find('.loading-bubble').exists()).toBe(true)

      vi.advanceTimersByTime(30000)
      await flushPromises()

      expect(wrapper.find('.loading-bubble').exists()).toBe(false)
      expect(wrapper.text()).toContain('响应超时')
      vi.useRealTimers()
    })

    it('prevents sending while already in loading state', async () => {
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(QAPanel, {
        global: { plugins: [pinia] }
      })

      const input = wrapper.find('.input-area textarea')
      await input.setValue('first')
      await input.trigger('keydown.enter')
      await flushPromises()

      // Try sending a second message while loading
      await input.setValue('second')
      await input.trigger('keydown.enter')
      await flushPromises()

      // Only one user message and one loading bubble should exist
      const uiStore = useUIStore()
      expect(uiStore.qaMessages.filter((m) => m.role === 'user').length).toBe(1)
      expect(uiStore.qaMessages.filter((m) => m.role === 'loading').length).toBe(1)
    })
  })
})
