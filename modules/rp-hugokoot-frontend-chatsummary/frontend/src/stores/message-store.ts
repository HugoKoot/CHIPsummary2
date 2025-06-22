import { defineStore } from 'pinia';
import type { ChatMessage } from '../components/models';

export const useMessageStore = defineStore('messages', {
  state: () => ({
    messages: [] as ChatMessage[],
  }),
  // getters: {
  //   doubleCount: (state) => state.counter * 2,
  // },
  actions: {
    addMessage(message: ChatMessage) {
      this.messages.push(message);
    },
    clearMessages() {
      this.messages = [];
    }
  },
});
