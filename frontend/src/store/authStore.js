import { create } from 'zustand'

const useAuthStore = create((set) => ({
  usuario: JSON.parse(localStorage.getItem('usuario') || 'null'),
  token: localStorage.getItem('access_token') || null,

  login: (usuario, token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('usuario', JSON.stringify(usuario))
    set({ usuario, token })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('usuario')
    set({ usuario: null, token: null })
  },

  isAuthenticated: () => !!localStorage.getItem('access_token'),
}))

export default useAuthStore
