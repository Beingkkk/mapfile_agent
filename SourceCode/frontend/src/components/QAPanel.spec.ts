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

      const input = wrapper.find('.input-area input')
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

      const input = wrapper.find('.input-area input')
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
})
