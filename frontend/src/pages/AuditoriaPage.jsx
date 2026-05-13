import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../services/api'
import { formatFechaHora } from '../services/helpers'
import { Shield, Search, Filter, ChevronDown, RefreshCw, Database } from 'lucide-react'

/* ── Tokens de color de la marca JER-WEIGHT ── */
const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444'
}

const ACCIONES = ['', 'login', 'logout', 'crear', 'modificar', 'eliminar', 'generar_reporte']

// Colores semánticos más vibrantes para la auditoría
const ACCION_BADGE = {
  login:            { bg: '#E8F8F1', text: '#10B981', border: 'rgba(16, 185, 129, 0.2)' }, // Verde
  logout:           { bg: '#F3F4F6', text: '#6B7280', border: 'rgba(107, 114, 128, 0.2)' }, // Gris
  crear:            { bg: '#EFF6FF', text: '#8B5CF6', border: 'rgba(139, 92, 246, 0.2)' }, // Morado
  modificar:        { bg: '#FFFBEB', text: '#F59E0B', border: 'rgba(245, 158, 11, 0.2)' }, // Ámbar
  eliminar:         { bg: '#FEF2F2', text: '#EF4444', border: 'rgba(239, 68, 68, 0.2)' }, // Rojo
  generar_reporte:  { bg: '#F0FDF4', text: '#14B8A6', border: 'rgba(20, 184, 166, 0.2)' }, // Teal
}

export default function AuditoriaPage() {
  const [filtros, setFiltros] = useState({
    usuario_email: '', accion: '', fecha_desde: '', fecha_hasta: '',
  })
  const [aplicados, setAplicados] = useState({})

  const { data: logs = [], isLoading, refetch, isFetching } = useQuery({
    queryKey: ['auditoria', aplicados],
    queryFn: () => {
      const params = {}
      if (aplicados.usuario_email) params.usuario_email = aplicados.usuario_email
      if (aplicados.accion)        params.accion        = aplicados.accion
      if (aplicados.fecha_desde)   params.fecha_desde   = new Date(aplicados.fecha_desde).toISOString()
      if (aplicados.fecha_hasta)   params.fecha_hasta   = new Date(aplicados.fecha_hasta + 'T23:59:59').toISOString()
      return dashboardApi.auditoria(params).then(r => r.data)
    },
  })

  const aplicarFiltros = () => setAplicados({ ...filtros })
  const limpiarFiltros = () => { 
    setFiltros({ usuario_email: '', accion: '', fecha_desde: '', fecha_hasta: '' }); 
    setAplicados({}) 
  }

  const inputClass = "w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-mono text-[11px]"
  const inputStyle = { background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 relative z-10">
      
      {/* ── HEADER ── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
            Log de Auditoría
          </h1>
          <p className="font-mono text-[11px] mt-2 font-bold tracking-widest uppercase flex items-center gap-2" style={{ color: C.textSecondary }}>
            <Shield size={14} /> Solo lectura · Inmutable por seguridad
          </p>
        </div>
        <button onClick={() => refetch()} disabled={isFetching}
          className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.1em] transition-all bg-white shadow-sm hover:shadow-md disabled:opacity-70"
          style={{ color: C.primary, border: '1px solid rgba(82, 217, 160, 0.2)' }}>
          <RefreshCw size={16} className={isFetching ? 'animate-spin' : ''} color={C.accentDark} /> 
          {isFetching ? 'Actualizando...' : 'Actualizar'}
        </button>
      </div>

      {/* ── FILTROS ── */}
      <div className="bg-white rounded-[1.5rem] p-6 shadow-sm border border-emerald-50">
        <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-widest mb-5" style={{ color: C.accentDark }}>
          <Filter size={14} /> Filtros de Búsqueda
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Usuario (Correo)</label>
            <input className={inputClass} style={inputStyle} placeholder="ejemplo@email.com" value={filtros.usuario_email} onChange={e => setFiltros(f => ({ ...f, usuario_email: e.target.value }))} />
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Tipo de Acción</label>
            <div className="relative">
              <select className={`${inputClass} appearance-none cursor-pointer`} style={inputStyle} value={filtros.accion} onChange={e => setFiltros(f => ({ ...f, accion: e.target.value }))}>
                {ACCIONES.map(a => (
                  <option key={a} value={a}>{a === '' ? 'Todas las acciones' : a.toUpperCase().replace('_', ' ')}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: C.textSecondary }} />
            </div>
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Desde</label>
            <input type="date" className={inputClass} style={inputStyle} value={filtros.fecha_desde} onChange={e => setFiltros(f => ({ ...f, fecha_desde: e.target.value }))} />
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Hasta</label>
            <input type="date" className={inputClass} style={inputStyle} value={filtros.fecha_hasta} onChange={e => setFiltros(f => ({ ...f, fecha_hasta: e.target.value }))} />
          </div>
        </div>
        
        <div className="flex gap-4 mt-6 pt-6 border-t border-[rgba(82,217,160,0.1)]">
          <button onClick={limpiarFiltros} className="flex-1 sm:flex-none px-6 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-colors hover:bg-gray-100" style={{ color: C.primary, border: '1px solid #E5E7EB' }}>
            Limpiar
          </button>
          <button onClick={aplicarFiltros} className="flex-1 sm:flex-none px-8 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest text-white transition-all flex items-center justify-center gap-2 shadow-md hover:shadow-lg hover:-translate-y-0.5" style={{ background: C.primary }}>
            <Search size={14} /> Aplicar Filtros
          </button>
        </div>
      </div>

      {/* ── TABLA DE REGISTROS ── */}
      <div className="bg-white rounded-[1.5rem] shadow-sm border border-emerald-50 overflow-hidden">
        <div className="px-6 py-5 flex items-center justify-between bg-[#F9FDFB] border-b border-[rgba(82,217,160,0.2)]">
          <div className="flex items-center gap-3">
            <Database size={16} style={{ color: C.accentDark }} />
            <span className="font-mono text-sm font-bold uppercase tracking-widest" style={{ color: C.primary }}>Registro de Eventos</span>
          </div>
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest px-3 py-1 bg-white rounded-md shadow-sm" style={{ color: C.textSecondary }}>
            {logs.length} Resultados
          </span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center font-mono text-xs font-bold uppercase tracking-widest animate-pulse" style={{ color: C.textSecondary }}>
            Recuperando registros...
          </div>
        ) : logs.length === 0 ? (
          <div className="p-16 text-center">
            <Shield size={32} className="mx-auto mb-4 opacity-20" style={{ color: C.primary }} />
            <p className="font-sans font-bold text-lg" style={{ color: C.primary }}>No hay eventos registrados</p>
            <p className="font-mono text-xs mt-1" style={{ color: C.textSecondary }}>Intenta cambiar los filtros de búsqueda.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[900px]">
              {/* Encabezado */}
              <div className="grid grid-cols-[1.5fr_2fr_1fr_1.5fr_3fr_1fr] gap-4 px-6 py-4 bg-[#F9FDFB] border-b border-[rgba(8,28,17,0.05)]">
                {['Fecha / Hora', 'Usuario', 'Acción', 'Tabla', 'Detalle Técnico', 'IP'].map(h => (
                  <span key={h} className="font-mono text-[10px] uppercase font-bold tracking-widest" style={{ color: C.textSecondary }}>{h}</span>
                ))}
              </div>
              
              {/* Filas */}
              <ul className="divide-y divide-[rgba(8,28,17,0.03)]">
                {logs.map((log) => {
                  const badge = ACCION_BADGE[log.accion] || { bg: '#F3F4F6', text: '#6B7280', border: 'rgba(107, 114, 128, 0.2)' }
                  return (
                    <li key={log.id} className="grid grid-cols-[1.5fr_2fr_1fr_1.5fr_3fr_1fr] gap-4 px-6 py-4 items-center transition-colors hover:bg-[#F0FBF6] group">
                      <div className="font-mono text-[11px] font-bold" style={{ color: C.accentDark }}>
                        {formatFechaHora(log.fecha)}
                      </div>
                      <div className="font-mono text-xs truncate" style={{ color: C.primary }}>
                        {log.usuario_email || '—'}
                      </div>
                      <div>
                        <span className="font-mono text-[10px] px-2.5 py-1 rounded-md font-bold uppercase tracking-wider inline-block"
                          style={{ background: badge.bg, color: badge.text, border: `1px solid ${badge.border}` }}>
                          {log.accion.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="font-mono text-[11px] font-bold uppercase tracking-wider" style={{ color: C.textSecondary }}>
                        {log.tabla_afectada || '—'}
                      </div>
                      <div className="font-sans text-xs text-gray-600 truncate pr-4" title={log.detalle}>
                        {log.detalle || '—'}
                      </div>
                      <div className="font-mono text-[10px] text-gray-400">
                        {log.ip_address || '—'}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}