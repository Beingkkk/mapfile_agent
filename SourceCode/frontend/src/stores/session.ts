import { defineStore } from 'pinia'
import type { ValidationError } from '@/types/tree'

interface SessionState {
  params: any;
  validation_state: 'idle' | 'checking' | 'pass' | 'fail';
  validation_errors: ValidationError[];
  focus_param: string | null;
  service_types: string[];
  mapcache_enabled: boolean;
  can_export: boolean;
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    params: {},
    validation_state: 'idle',
    validation_errors: [],
    focus_param: null,
    service_types: ['wms'],
    mapcache_enabled: false,
    can_export: false,
  }),
  actions: {
    applyTreeState(payload: any) {
      this.params = payload.params_snapshot ?? this.params
      this.validation_state = payload.validation_state ?? this.validation_state
      this.validation_errors = payload.validation_errors ?? []
      this.can_export = payload.can_export ?? false
    },
    setFocus(path: string | null) {
      this.focus_param = path
    },
    setServiceTypes(services: string[], mapcache: boolean) {
      this.service_types = services
      this.mapcache_enabled = mapcache
    },
  },
})
