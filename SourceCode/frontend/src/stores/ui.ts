import { defineStore } from 'pinia'
import type { QAMessage } from '@/types/tree'

interface UIState {
  showMode: 'all' | 'required';
  expandedNodes: Set<string>;
  qaMessages: QAMessage[];
  qaRoundCount: number;
  qaFocusParam: string | null;
}

export const useUIStore = defineStore('ui', {
  state: (): UIState => ({
    showMode: 'all',
    expandedNodes: new Set(['map', 'web']),
    qaMessages: [],
    qaRoundCount: 0,
    qaFocusParam: null,
  }),
  actions: {
    setShowMode(mode: 'all' | 'required') {
      this.showMode = mode
    },
    toggleNode(id: string) {
      if (this.expandedNodes.has(id)) {
        this.expandedNodes.delete(id)
      } else {
        this.expandedNodes.add(id)
      }
    },
    addQAMessage(msg: QAMessage) {
      this.qaMessages.push(msg)
      this.qaRoundCount = Math.floor(this.qaMessages.length / 2)
    },
    clearQA() {
      this.qaMessages = []
      this.qaRoundCount = 0
    },
  },
})
