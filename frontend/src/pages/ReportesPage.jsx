import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportesApi, hatosApi } from '../services/api'
import { formatFecha } from '../services/helpers'
import { FileText, Download, BarChart2, Weight, TrendingUp, AlertTriangle, Calendar, Filter, Loader2, CheckCircle2, XCircle } from 'lucide-react'

/* ── Tokens de color de la marca JER-WEIGHT ── */
const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444'
}
/* ── Tokens de tipografía ── */
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

// ─── Descarga un blob como archivo ────────────────────────────────────────
function descargarBlob(blob, nombreArchivo) {
  const url  = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href        = url
  link.download    = nombreArchivo
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// ─── Tipos de reporte disponibles ─────────────────────────────────────────
const REPORTES = [
  { id: 'bcs', tipoDb: 'GENERAL', icon: BarChart2, title: 'Reporte BCS General', desc: 'Condición corporal de todos los animales registrados.', bcs_min: 1, bcs_max: 5 },
  { id: 'pesos', tipoDb: 'GENERAL', icon: Weight, title: 'Reporte de Pesos', desc: 'Evolución histórica de peso por animal y por hato.', bcs_min: undefined, bcs_max: undefined },
  { id: 'alertas', tipoDb: 'GENERAL', icon: AlertTriangle, title: 'Animales en Alerta', desc: 'Listado de animales con BCS fuera del rango recomendado (< 2.5).', bcs_min: 1, bcs_max: 2.49 },
  { id: 'tendencias', tipoDb: 'GENERAL', icon: TrendingUp, title: 'Tendencias Mensuales', desc: 'Comparativa de mediciones y BCS agrupadas por mes.', bcs_min: undefined, bcs_max: undefined },
]

export default function ReportesPage() {
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  const [hatoSeleccionado, setHatoSeleccionado] = useState('')
  const [raza, setRaza]             = useState('')
  const [loading, setLoading]       = useState(null)
  const [toastMsg, setToastMsg]     = useState(null)

  const { data: hatos = [] } = useQuery({
    queryKey: ['hatos'],
    queryFn:  () => hatosApi.listar().then(r => r.data),
  })

  const { data: historial = [], refetch: refetchHistorial } = useQuery({
    queryKey: ['reportes-historial'],
    queryFn:  () => reportesApi.historial().then(r => r.data),
  })

  function mostrarToast(msg, tipo = 'ok') {
    setToastMsg({ msg, tipo })
    setTimeout(() => setToastMsg(null), 3500)
  }

  async function handleExportar(reporte) {
    setLoading(reporte.id)
    try {
      const params = {
        titulo:      reporte.title,
        ...(fechaDesde && { fecha_desde: new Date(fechaDesde).toISOString() }),
        ...(fechaHasta && { fecha_hasta: new Date(fechaHasta + 'T23:59:59').toISOString() }),
        ...(hatoSeleccionado && { hato_id: hatoSeleccionado }),
        ...(raza && { raza }),
        ...(reporte.bcs_min !== undefined && { bcs_min: reporte.bcs_min }),
        ...(reporte.bcs_max !== undefined && { bcs_max: reporte.bcs_max }),
      }
      const res = await reportesApi.exportarPdf(params)
      const fecha = new Date().toISOString().slice(0,10).replace(/-/g,'')
      descargarBlob(res.data, `${reporte.id}_${fecha}.pdf`)
      mostrarToast('PDF descargado correctamente')
      refetchHistorial()
    } catch (e) {
      const msg = e.response?.data?.detail || 'Error al generar el PDF'
      mostrarToast(msg, 'error')
    } finally {
      setLoading(null)
    }
   
  }
   const hoy = new Date();
  const fechaActualLocal = new Date(hoy.getTime() - hoy.getTimezoneOffset() * 60000)
    .toISOString()
    .split('T')[0];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 relative z-10">

      {/* TOAST PERSONALIZADO */}
      {toastMsg && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl animate-in slide-in-from-top-4 fade-in duration-300"
          style={{
            background: toastMsg.tipo === 'error' ? '#FEF2F2' : C.primary,
            border: `1px solid ${toastMsg.tipo === 'error' ? '#FCA5A5' : C.accentDark}`,
          }}>
          {toastMsg.tipo === 'error' ? <XCircle size={20} color={C.danger} /> : <CheckCircle2 size={20} color={C.accent} />}
          <span className="font-mono text-xs font-bold uppercase tracking-wider" style={{ color: toastMsg.tipo === 'error' ? C.danger : C.white }}>
            {toastMsg.msg}
          </span>
        </div>
      )}

      {/* HEADER */}
      <div>
        <h1 style={{ fontFamily: F.brand, color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
          Generador de Reportes
        </h1>
        <p className="font-mono text-[11px] mt-2 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
          Exporta y analiza los datos del criadero en PDF
        </p>
      </div>

      {/* FILTROS DE REPORTE */}
      <div className="bg-white rounded-[1.5rem] p-6 shadow-sm border border-emerald-50">
        <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-widest mb-5" style={{ color: C.accentDark }}>
          <Filter size={14} /> Filtros de Exportación
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Desde la fecha</label>
            <input type="date" max={fechaActualLocal} className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary, fontFamily: F.body }} value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} />
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Hasta la fecha</label>
            <input type="date" min={fechaDesde} max={fechaActualLocal} className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary, fontFamily: F.body }} value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} />
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Ubicación / Hato</label>
            <select className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-sans font-medium" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} value={hatoSeleccionado} onChange={e => setHatoSeleccionado(e.target.value)}>
              <option value="">— Todos los hatos —</option>
              {hatos.map(h => <option key={h.id} value={h.id}>{h.nombre} — {h.finca}</option>)}
            </select>
          </div>
          <div>
            <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Filtrar por Raza</label>
            <input type="text" placeholder="Ej: Jersey" className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} value={raza} onChange={e => setRaza(e.target.value)} />
          </div>
        </div>
      </div>

      {/* TARJETAS DE REPORTE */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {REPORTES.map((r, i) => {
          const Icon = r.icon
          const esCargando = loading === r.id
          return (
            <div key={r.id} 
              className="bg-white rounded-[1.5rem] p-6 flex flex-col transition-all duration-300 relative overflow-hidden group"
              style={{ boxShadow: '0 10px 30px rgba(8, 28, 17, 0.04)', border: '1px solid rgba(82, 217, 160, 0.15)', animationDelay: `${i * 100}ms` }}>
              
              <div className="absolute top-0 left-0 w-full h-1 opacity-0 group-hover:opacity-100 transition-opacity" style={{ background: `linear-gradient(90deg, ${C.accent}, ${C.accentDark})` }} />

              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-inner" style={{ background: '#E8F8F1' }}>
                  <Icon size={20} style={{ color: C.accentDark }} />
                </div>
                <span className="font-mono text-[10px] px-3 py-1.5 rounded-lg uppercase tracking-widest font-bold" style={{ background: '#E8F8F1', color: C.accentDark }}>
                  Formato PDF
                </span>
              </div>
              
              <div className="flex-1 mb-6">
                <h3 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.25rem', fontWeight: 800, marginBottom: '8px' }}>
                  {r.title}
                </h3>
                <p className="font-sans text-sm font-medium" style={{ color: C.textSecondary, lineHeight: 1.6 }}>
                  {r.desc}
                </p>
              </div>
              
              <button onClick={() => handleExportar(r)} disabled={esCargando}
                className="w-full py-3.5 rounded-xl font-mono text-sm font-bold uppercase tracking-widest text-white transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed hover:scale-[1.02] active:scale-95 shadow-md"
                style={{ background: C.primary }}>
                {esCargando 
                  ? <><Loader2 size={16} className="animate-spin" style={{ color: C.accent }} /> Generando...</> 
                  : <><Download size={16} style={{ color: C.accent }} /> Exportar Documento</>
                }
              </button>
            </div>
          )
        })}
      </div>

      {/* HISTORIAL DE REPORTES GENERADOS */}
      <div className="bg-white rounded-[1.5rem] shadow-sm border border-emerald-50 overflow-hidden">
        <div className="px-8 py-5 flex items-center gap-3" style={{ borderBottom: '1px solid rgba(8,28,17,0.05)', background: '#F9FDFB' }}>
          <Calendar size={18} style={{ color: C.accentDark }} />
          <h3 className="font-mono text-sm font-bold uppercase tracking-widest" style={{ color: C.primary, margin: 0 }}>Historial de Descargas</h3>
        </div>
        
        {historial.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-[#E8F8F1] rounded-full flex items-center justify-center mx-auto mb-4">
              <FileText size={24} style={{ color: C.accentDark }} />
            </div>
            <p className="font-mono text-sm font-bold" style={{ color: C.primary }}>Aún no has generado reportes</p>
            <p className="font-sans text-sm mt-1" style={{ color: C.textSecondary }}>Tus descargas aparecerán aquí para referencia futura.</p>
          </div>
        ) : (
          <div className="divide-y divide-[rgba(8,28,17,0.03)]">
            {historial.map((h) => (
              <div key={h.id} className="flex items-center gap-5 px-8 py-4 transition-colors hover:bg-[#F0FBF6] group">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-inner" style={{ background: '#E8F8F1' }}>
                  <FileText size={18} style={{ color: C.accentDark }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-sans text-sm font-bold truncate" style={{ color: C.primary }}>
                    {h.titulo}
                  </div>
                  <div className="font-mono text-[11px] font-medium mt-1" style={{ color: C.textSecondary }}>
                    {h.parametros?.total_registros != null ? <span className="font-bold text-emerald-700">{h.parametros.total_registros} registros analizados</span> : ''} 
                    {h.parametros?.total_registros != null && ' • '}
                    {formatFecha(h.fecha_generado)}
                  </div>
                </div>
                <span className="font-mono text-[10px] px-3 py-1.5 rounded-lg uppercase tracking-widest font-bold shadow-sm" style={{ background: C.primary, color: C.white }}>
                  {h.formato?.toUpperCase() || 'PDF'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}