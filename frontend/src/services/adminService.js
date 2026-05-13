// src/services/adminService.js
// Usa el mismo axios instance que el resto del proyecto (con token y proxy)
import api from './api'

// Convierte rol a minúscula para el backend (el backend espera 'admin'/'ganadero')
function normalizarRol(rol) {
  return rol ? rol.toLowerCase() : rol
}

// ── Listar usuarios ───────────────────────────────────────────────────────────
export async function listarUsuarios({ rol, activo, buscar } = {}) {
  const params = {}
  if (rol    !== undefined && rol    !== '') params.rol    = normalizarRol(rol)
  if (activo !== undefined && activo !== '') params.activo = activo
  if (buscar)                                params.buscar = buscar

  const res = await api.get('/admin/usuarios', { params })
  return res.data
}

// ── Detalle de un usuario ─────────────────────────────────────────────────────
export async function obtenerUsuario(id) {
  const res = await api.get(`/admin/usuarios/${id}`)
  return res.data
}

// ── Crear usuario ─────────────────────────────────────────────────────────────
export async function crearUsuario(datos) {
  const payload = { ...datos, rol: normalizarRol(datos.rol) }
  const res = await api.post('/admin/usuarios', payload)
  return res.data
}

// ── Editar datos básicos ──────────────────────────────────────────────────────
export async function actualizarUsuario(id, datos) {
  const res = await api.put(`/admin/usuarios/${id}`, datos)
  return res.data
}

// ── Cambiar rol ───────────────────────────────────────────────────────────────
export async function cambiarRol(id, rol) {
  const res = await api.patch(`/admin/usuarios/${id}/rol`, { rol: normalizarRol(rol) })
  return res.data
}

// ── Activar / desactivar ──────────────────────────────────────────────────────
export async function cambiarEstado(id, activo) {
  const res = await api.patch(`/admin/usuarios/${id}/estado`, { activo })
  return res.data
}

// ── Eliminar ──────────────────────────────────────────────────────────────────
export async function eliminarUsuario(id) {
  await api.delete(`/admin/usuarios/${id}`)
  return null
}
