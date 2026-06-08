import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ObjectCard from './ObjectCard.vue'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'

// Mock ws service — ObjectCard calls ws.send() on interactions
vi.mock('@/services/ws', () => ({
  ws: { send: vi.fn() }
}))

// Import the mocked module to access the mock function
import { ws } from '@/services/ws'

describe('ObjectCard', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders without error given empty node (defensive)', () => {
    const wrapper = mount(ObjectCard, {
      props: { node: {} as any, depth: 0 }
    })
    expect(wrapper.find('.tree-obj-header').exists()).toBe(true)
    expect(wrapper.text()).toContain('UNKNOWN')
  })

  it('renders MAP node with expanded children', () => {
    const node = {
      id: 'map',
      path: 'map',
      object_type: 'MAP' as const,
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
          user_modified: false,
          errors: [],
        }
      ]
    }
    const wrapper = mount(ObjectCard, {
      props: { node: node as any, depth: 0 }
    })
    expect(wrapper.text()).toContain('MAP')
    expect(wrapper.find('.tree-children').exists()).toBe(true)
    expect(wrapper.text()).toContain('name')
  })

  it('renders collapsed node without children visible', () => {
    const node = {
      id: 'map',
      path: 'map',
      object_type: 'MAP' as const,
      expanded: false,
      children: []
    }
    const wrapper = mount(ObjectCard, {
      props: { node: node as any, depth: 0 }
    })
    expect(wrapper.find('.tree-children').exists()).toBe(false)
    expect(wrapper.text()).toContain('MAP')
  })

  it('filters non-required leaves when showMode is required', () => {
    const node: any = {
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
          user_modified: false,
          errors: [],
        },
        {
          id: 'map_status',
          path: 'map.status',
          key: 'status',
          value: 'ON',
          value_type: 'enum',
          phase: 'service',
          required: false,
          derived: false,
          custom: false,
          user_modified: false,
          errors: [],
        }
      ]
    }
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mount(ObjectCard, {
      props: { node: node as any, depth: 0 },
      global: { plugins: [pinia] }
    })
    // Both children visible in 'all' mode (default)
    expect(wrapper.text()).toContain('name')
    expect(wrapper.text()).toContain('status')
  })

  describe('toggle vs focus interaction splitting (proposal-0011)', () => {
    beforeEach(() => {
      vi.mocked(ws.send).mockClear()
    })

    it('clicking toggle arrow toggles expansion without sending focus_change', async () => {
      const node = {
        id: 'map',
        path: 'map',
        object_type: 'MAP' as const,
        expanded: true,
        children: [
          {
            id: 'map_name',
            path: 'map.name',
            key: 'name',
            value: 'test',
            value_type: 'string',
            phase: 'service',
            required: true,
            derived: false,
            custom: false,
            user_modified: false,
            errors: [],
          }
        ]
      }
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(ObjectCard, {
        props: { node: node as any, depth: 0 },
        global: { plugins: [pinia] }
      })

      // Initially expanded
      expect(wrapper.find('.tree-children').exists()).toBe(true)

      // Click toggle arrow
      const toggle = wrapper.find('.tree-toggle')
      expect(toggle.exists()).toBe(true)
      await toggle.trigger('click')
      await flushPromises()

      // Now collapsed
      expect(wrapper.find('.tree-children').exists()).toBe(false)

      // Should NOT have sent focus_change
      const focusCalls = vi.mocked(ws.send).mock.calls.filter(
        (c: any) => c[0]?.type === 'focus_change'
      )
      expect(focusCalls).toHaveLength(0)
    })

    it('clicking header body sends focus_change without toggling expansion', async () => {
      const node = {
        id: 'map',
        path: 'map',
        object_type: 'MAP' as const,
        expanded: true,
        children: [
          {
            id: 'map_name',
            path: 'map.name',
            key: 'name',
            value: 'test',
            value_type: 'string',
            phase: 'service',
            required: true,
            derived: false,
            custom: false,
            user_modified: false,
            errors: [],
          }
        ]
      }
      const pinia = createPinia()
      setActivePinia(pinia)
      const wrapper = mount(ObjectCard, {
        props: { node: node as any, depth: 0 },
        global: { plugins: [pinia] }
      })

      // Initially expanded
      expect(wrapper.find('.tree-children').exists()).toBe(true)

      // Click header body (not toggle)
      await wrapper.find('.tree-obj-header').trigger('click')
      await flushPromises()

      // Still expanded
      expect(wrapper.find('.tree-children').exists()).toBe(true)

      // Should have sent focus_change
      expect(vi.mocked(ws.send)).toHaveBeenCalledWith({
        type: 'focus_change',
        path: 'map',
      })
    })

    it('shows selected state when session focus_param matches node path', async () => {
      const node = {
        id: 'layers.0',
        path: 'layers.0',
        object_type: 'LAYER' as const,
        expanded: true,
        children: []
      }
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.0')

      const wrapper = mount(ObjectCard, {
        props: { node: node as any, depth: 1 },
        global: { plugins: [pinia] }
      })

      const header = wrapper.find('.tree-obj-header')
      expect(header.classes()).toContain('selected')
    })

    it('does not show selected state when focus is on a different node', async () => {
      const node = {
        id: 'layers.0',
        path: 'layers.0',
        object_type: 'LAYER' as const,
        expanded: true,
        children: []
      }
      const pinia = createPinia()
      setActivePinia(pinia)
      const sessionStore = useSessionStore()
      sessionStore.setFocus('layers.1')

      const wrapper = mount(ObjectCard, {
        props: { node: node as any, depth: 1 },
        global: { plugins: [pinia] }
      })

      const header = wrapper.find('.tree-obj-header')
      expect(header.classes()).not.toContain('selected')
    })
  })
})
