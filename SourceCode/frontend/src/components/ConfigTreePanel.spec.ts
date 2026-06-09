import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfigTreePanel from './ConfigTreePanel.vue'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'

// Mock ws service
vi.mock('@/services/ws', () => ({
  ws: { send: vi.fn() },
}))

import { ws } from '@/services/ws'

function createMockTree() {
  return {
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
      },
      {
        id: 'web',
        path: 'web',
        object_type: 'WEB',
        expanded: true,
        children: [
          {
            id: 'web_metadata',
            path: 'web.metadata',
            object_type: 'METADATA',
            expanded: true,
            children: [
              {
                id: 'web_metadata_ows_title',
                path: 'web.metadata.ows_title',
                key: 'ows_title',
                value: 'My Map',
                value_type: 'string',
                phase: 'service',
                required: false,
                derived: false,
                custom: false,
                user_modified: false,
                errors: [],
              },
            ],
          },
        ],
      },
    ],
  }
}

describe('ConfigTreePanel — Search', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(ws.send).mockClear()
  })

  function mountWithTree() {
    const pinia = createPinia()
    setActivePinia(pinia)
    const sessionStore = useSessionStore()
    sessionStore.applyTreeState({
      params_snapshot: createMockTree(),
      validation_state: 'idle',
      validation_errors: [],
      can_export: false,
    })
    return mount(ConfigTreePanel, {
      global: { plugins: [pinia] },
    })
  }

  it('renders search input', () => {
    const wrapper = mountWithTree()
    expect(wrapper.find('.search-input').exists()).toBe(true)
    expect(wrapper.find('.search-icon').exists()).toBe(true)
  })

  it('shows matching fields when typing search query', async () => {
    const wrapper = mountWithTree()
    const input = wrapper.find('.search-input')

    await input.setValue('name')
    await input.trigger('focus')
    await flushPromises()

    const dropdown = wrapper.find('.search-dropdown')
    expect(dropdown.exists()).toBe(true)
    expect(dropdown.text()).toContain('name')
    expect(dropdown.text()).toContain('[string]')
    expect(dropdown.text()).toContain('map')
  })

  it('shows "no match" when query has no matches', async () => {
    const wrapper = mountWithTree()
    const input = wrapper.find('.search-input')

    await input.setValue('xyznonexistent')
    await input.trigger('focus')
    await flushPromises()

    expect(wrapper.find('.search-empty').exists()).toBe(true)
    expect(wrapper.find('.search-empty').text()).toBe('无匹配字段')
  })

  it('hides dropdown when query is empty', async () => {
    const wrapper = mountWithTree()
    const input = wrapper.find('.search-input')

    await input.setValue('name')
    await input.trigger('focus')
    await flushPromises()
    expect(wrapper.find('.search-dropdown').exists()).toBe(true)

    await input.setValue('')
    await flushPromises()
    expect(wrapper.find('.search-dropdown').exists()).toBe(false)
  })

  it('clicking a result expands ancestors and sends focus_change', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const sessionStore = useSessionStore()
    const uiStore = useUIStore()
    sessionStore.applyTreeState({
      params_snapshot: createMockTree(),
      validation_state: 'idle',
      validation_errors: [],
      can_export: false,
    })

    const wrapper = mount(ConfigTreePanel, {
      global: { plugins: [pinia] },
    })

    const input = wrapper.find('.search-input')
    await input.setValue('ows')
    await input.trigger('focus')
    await flushPromises()

    // Find and click the ows_title result
    const results = wrapper.findAll('.search-result-item')
    const owsResult = results.find((r) => r.text().includes('ows_title'))
    expect(owsResult).toBeDefined()

    await owsResult!.trigger('mousedown')
    await flushPromises()

    // Should have expanded ancestor paths
    expect(uiStore.expandedNodes.has('web')).toBe(true)
    expect(uiStore.expandedNodes.has('web.metadata')).toBe(true)

    // Should have sent focus_change
    expect(vi.mocked(ws.send)).toHaveBeenCalledWith({
      type: 'focus_change',
      path: 'web.metadata.ows_title',
    })
  })

  it('clear button resets search', async () => {
    const wrapper = mountWithTree()
    const input = wrapper.find('.search-input')

    await input.setValue('name')
    await input.trigger('focus')
    await flushPromises()

    const clearBtn = wrapper.find('.search-clear')
    expect(clearBtn.exists()).toBe(true)

    await clearBtn.trigger('click')
    await flushPromises()

    expect((input.element as HTMLInputElement).value).toBe('')
  })
})
