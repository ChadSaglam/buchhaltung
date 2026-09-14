import { create } from 'zustand';
import { mutate } from 'swr';
import type { UserResponse } from '@/lib/api-schema';
import { useNotificationsStore } from '@/lib/notifications-store';

type User = UserResponse;

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  setAuth: (token, user) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, user: null });
    // B-44: nothing of this session may survive into the next login — the SWR cache
    // still held tenant A's KPIs for tenant B; the bell still showed A's review queue.
    void mutate(() => true, undefined, { revalidate: false });
    useNotificationsStore.getState().reset();
  },
  hydrate: () => {
    const token = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      try { set({ token, user: JSON.parse(userStr) }); } catch { /* ignore */ }
    }
  },
}));
