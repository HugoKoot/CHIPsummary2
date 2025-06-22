import { defineStore } from 'pinia';
import type { User } from '../components/models';

export const useUserStore = defineStore('user', {
  state: () => ({
    user: undefined as User | undefined,
  }),
});
