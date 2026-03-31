import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('usuario')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ─── AUTH ─────────────────────────────────────────────────────────────────
export const authApi = {
  login:    (email, password) => api.post('/auth/login', { email, password }),
  registro: (datos)           => api.post('/auth/registro', datos),
}

// ─── HATOS ────────────────────────────────────────────────────────────────
export const hatosApi = {
  listar:       ()           => api.get('/hatos/'),
  crear:        (datos)      => api.post('/hatos/', datos),
  obtener:      (id)         => api.get(`/hatos/${id}`),
  actualizar:   (id, datos)  => api.put(`/hatos/${id}`, datos),
  eliminar:     (id)         => api.delete(`/hatos/${id}`),
  estadisticas: (id)         => api.get(`/hatos/${id}/estadisticas`),
}

// ─── ANIMALES ─────────────────────────────────────────────────────────────
export const animalesApi = {
  listar:         (params)      => api.get('/animales/', { params }),
  crear:          (datos)       => api.post('/animales/', datos),
  obtener:        (id)          => api.get(`/animales/${id}`),
  actualizar:     (id, datos)   => api.put(`/animales/${id}`, datos),
  eliminar:       (id)          => api.delete(`/animales/${id}`),
  mediciones:     (id)          => api.get(`/animales/${id}/mediciones`),
  buscarPorArete: (arete)       => api.get('/animales/buscar/arete', { params: { arete } }),
}

// ─── ANÁLISIS ─────────────────────────────────────────────────────────────
export const analisisApi = {
  analizar:       (formData) => api.post('/analisis/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  obtenerMedicion: (id)      => api.get(`/analisis/medicion/${id}`),
}

// ─── REPORTES ─────────────────────────────────────────────────────────────
export const reportesApi = {
  listar:   ()           => api.get('/reportes/'),
  crear:    (datos)      => api.post('/reportes/', datos),
  obtener:  (id)         => api.get(`/reportes/${id}`),
  eliminar: (id)         => api.delete(`/reportes/${id}`),
}

export default api
