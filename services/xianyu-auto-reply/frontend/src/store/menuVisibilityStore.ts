import { create } from 'zustand'

interface MenuVisibilityState {
  hiddenMenuKeys: string[]
  isExeMode: boolean
  setHiddenMenuKeys: (keys: string[]) => void
  setIsExeMode: (value: boolean) => void
}

export const useMenuVisibilityStore = create<MenuVisibilityState>((set) => ({
  hiddenMenuKeys: [],
  isExeMode: false,
  setHiddenMenuKeys: (keys) => {
    const uniqueKeys = Array.from(new Set(keys.filter(Boolean)))
    set({ hiddenMenuKeys: uniqueKeys })
  },
  setIsExeMode: (value) => set({ isExeMode: Boolean(value) }),
}))
