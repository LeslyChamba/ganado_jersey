import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1'
  headers: { 'Content-Type': 'application/json' },
})

// HU-14: Rastreo de inactividad — actualizar timestamp en cada petición
let _lastActivity = Date.now()
const INACTIVIDAD_MS = 30 * 60 * 1000  // 30 minutos

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  // Detectar sesión expirada por inactividad ANTES de enviar la petición
  if (token && Date.now() - _lastActivity > INACTIVIDAD_MS) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('usuario')
    window.location.href = '/login?expired=1'
    return Promise.reject(new Error('Sesión expirada por inactividad'))
  }
  _lastActivity = Date.now()
  return config
})

// Actualizar lastActivity también en eventos de usuario
if (typeof window !== 'undefined') {
  ;['click', 'keydown', 'touchstart', 'scroll'].forEach(ev =>
    window.addEventListener(ev, () => { _lastActivity = Date.now() }, { passive: true })
  )
}

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
  validar: (formData) => api.post('/analisis/validar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  analizar:       (formData) => api.post('/analisis/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  obtenerMedicion: (id)      => api.get(`/analisis/medicion/${id}`),
}

// ─── REPORTES ─────────────────────────────────────────────────────────────
export const reportesApi = {
  listar:    ()      => api.get('/reportes/'),
  crear:     (datos) => api.post('/reportes/', datos),
  obtener:   (id)    => api.get(`/reportes/${id}`),
  eliminar:  (id)    => api.delete(`/reportes/${id}`),
  historial: ()      => api.get('/reportes/historial'),
  // RF-15: descarga PDF real con filtros
  exportarPdf: (params) => api.get('/reportes/exportar/pdf', {
    params,
    responseType: 'blob',
  }),
}

// ─── DASHBOARD ────────────────────────────────────────────────────────────
export const dashboardApi = {
  ganadero: ()       => api.get('/dashboard/ganadero'),
  admin:    ()       => api.get('/dashboard/admin'),
  alertas:  ()       => api.get('/dashboard/alertas'),
  auditoria: (params) => api.get('/dashboard/auditoria', { params }),
}

export default api