import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import FieldEditor from './FieldEditor.vue'
import type { TreeLeaf } from '@/types/tree'

// Mock WebSocket service
const mockSend = vi.fn()
vi.mock('@/services/ws', () => ({
  ws: {
    send: (...args: any[]) => mockSend(...args),
  },
}))

function makeLeaf(overrides: Partial<TreeLeaf> = {}): TreeLeaf {
  return {
    id: 'test-id',
    path: 'map.name',
    key: 'name',
    value: 'TestMap',
    value_type: 'string',
    phase: 'service',
    required: false,
    derived: false,
    custom: false,
    user_modified: false,
    errors: [],
    ...overrides,
  }
}

describe('FieldEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockSend.mockClear()
  })

  it('renders string input by default', () => {
    const leaf = makeLeaf({ value_type: 'string', value: 'hello' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const input = wrapper.find('input')
    expect(input.exists()).toBe(true)
    expect(input.element.value).toBe('hello')
  })

  it('renders number input for integer type', () => {
    const leaf = makeLeaf({ value_type: 'integer', value: 42, key: 'size' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const input = wrapper.find('input[type="number"]')
    expect(input.exists()).toBe(true)
  })

  it('renders number input for float type with step', () => {
    const leaf = makeLeaf({ value_type: 'float', value: 3.14, key: 'opacity' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const input = wrapper.find('input[type="number"]')
    expect(input.exists()).toBe(true)
    expect(input.attributes('step')).toBe('0.01')
  })

  it('renders select for enum type', () => {
    const leaf = makeLeaf({
      value_type: 'enum',
      value: 'postgis',
      enum: ['postgis', 'shapefile', 'wms'],
      key: 'connectiontype',
    })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
    const options = select.findAll('option')
    expect(options).toHaveLength(3)
  })

  it('renders checkbox for boolean type', () => {
    const leaf = makeLeaf({ value_type: 'boolean', value: true, key: 'antialias' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    expect((checkbox.element as HTMLInputElement).checked).toBe(true)
  })

  it('renders color preview for color type', () => {
    const leaf = makeLeaf({ value_type: 'color', value: [255, 0, 128], key: 'color' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const preview = wrapper.find('.color-preview')
    expect(preview.exists()).toBe(true)
    expect(preview.text()).toContain('255')
  })

  it('renders array display for array type', () => {
    const leaf = makeLeaf({ value_type: 'array', value: ['a', 'b', 'c'], key: 'projection' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const display = wrapper.find('.array-display')
    expect(display.exists()).toBe(true)
  })

  it('renders expression input with expression class', () => {
    const leaf = makeLeaf({ value_type: 'expression', value: '([area] > 100)', key: 'expression' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const input = wrapper.find('.expression-input')
    expect(input.exists()).toBe(true)
  })

  it('shows required indicator * for required fields', () => {
    const leaf = makeLeaf({ required: true, key: 'name' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.text()).toContain('*')
  })

  it('shows derived indicator → for derived fields', () => {
    const leaf = makeLeaf({ derived: true, required: false })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.text()).toContain('→')
  })

  it('shows custom indicator ✎ for custom fields', () => {
    const leaf = makeLeaf({ custom: true, required: false })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.text()).toContain('✎')
  })

  it('shows error mark when errors exist', () => {
    const leaf = makeLeaf({ errors: ['Invalid value', 'Must not be empty'] })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const errorMark = wrapper.find('.error-mark')
    expect(errorMark.exists()).toBe(true)
    expect(errorMark.attributes('title')).toBe('Invalid value; Must not be empty')
  })

  it('shows custom desc icon when custom field has description', () => {
    const leaf = makeLeaf({ custom: true, custom_desc: 'This is a custom property' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const descIcon = wrapper.find('.custom-desc')
    expect(descIcon.exists()).toBe(true)
    expect(descIcon.attributes('title')).toBe('This is a custom property')
  })

  it('emits focus_change on click', async () => {
    const leaf = makeLeaf({ path: 'map.name' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    await wrapper.trigger('click')
    expect(mockSend).toHaveBeenCalledWith({
      type: 'focus_change',
      path: 'map.name',
    })
  })

  it('emits tree_update on blur for string fields', async () => {
    const leaf = makeLeaf({ value_type: 'string', path: 'map.name', value: 'old' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    const input = wrapper.find('input')
    await input.setValue('new')
    await input.trigger('blur')
    expect(mockSend).toHaveBeenCalledWith({
      type: 'tree_update',
      updates: [{ path: 'map.name', value: 'new' }],
    })
  })

  it('syncs external value changes via watch', async () => {
    const leaf = makeLeaf({ value: 'initial' })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.find('input').element.value).toBe('initial')

    await wrapper.setProps({
      leaf: { ...leaf, value: 'updated' },
    })
    expect(wrapper.find('input').element.value).toBe('updated')
  })

  it('applies has-error class when errors exist', () => {
    const leaf = makeLeaf({ errors: ['bad'] })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.classes()).toContain('has-error')
  })

  it('shows default indicator D for fields with defaults', () => {
    const leaf = makeLeaf({ default: 'default-value', required: false, derived: false, custom: false })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.text()).toContain('D')
  })

  it('shows optional indicator ○ for plain optional fields', () => {
    const leaf = makeLeaf({ required: false, derived: false, custom: false, default: undefined })
    const wrapper = mount(FieldEditor, { props: { leaf } })
    expect(wrapper.text()).toContain('○')
  })
})
