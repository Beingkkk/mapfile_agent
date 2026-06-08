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
      // Only count user/bot pairs for round count
      const qaOnly = this.qaMessages.filter(
        (m) => m.role === 'user' || m.role === 'bot',
      )
      this.qaRoundCount = Math.floor(qaOnly.length / 2)
    },
    clearQA() {
      this.qaMessages = []
      this.qaRoundCount = 0
    },
    resetHistoryContext() {
      // 1. Must have at least one user/bot message
      const hasQA = this.qaMessages.some(
        (m) => m.role === 'user' || m.role === 'bot',
      )
      if (!hasQA) {
        this.qaRoundCount = 0
        return
      }
      // 2. Find the last divider; skip if no new QA has happened since then
      let lastDividerIndex = -1
      for (let i = this.qaMessages.length - 1; i >= 0; i--) {
        if (this.qaMessages[i].role === 'divider') {
          lastDividerIndex = i
          break
        }
      }
      const hasNewQA = this.qaMessages.slice(lastDividerIndex + 1).some(
        (m) => m.role === 'user' || m.role === 'bot',
      )
      if (!hasNewQA) return
      this.qaRoundCount = 0
      this.qaMessages.push({
        role: 'divider',
        text: '',
      })
    },
  },
})
