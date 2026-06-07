import { describe, it, expect } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from './session'

describe('SessionStore', () => {
  it('initializes with default state', () => {
    setActivePinia(createPinia())
    const store = useSessionStore()
    expect(store.validation_state).toBe('idle')
    expect(store.service_types).toEqual(['wms'])
    expect(store.mapcache_enabled).toBe(false)
  })
})
