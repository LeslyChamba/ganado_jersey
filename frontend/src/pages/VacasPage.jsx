import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { animalesApi, hatosApi } from '../services/api'
import { getBCSColor, getBCSLabel, formatPeso, formatFechaHora } from '../services/helpers'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import toast from 'react-hot-toast'
import { Plus, Search, Loader2, X, History, Trash2, Filter, MapPin, Activity } from 'lucide-react'

/* ── Tokens de color (Sincronizados) ── */
const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444'
}

export default function VacasPage() {
  const qc = useQueryClient()

  // Búsqueda con debounce
  const [buscarInput, setBuscarInput] = useState('')
  const [buscar, setBuscar]           = useState('')
  const debounceRef = useRef()
  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setBuscar(buscarInput), 400)
    return () => clearTimeout(debounceRef.current)
  }, [buscarInput])

  const [modal, setModal]               = useState(false)
  const [historialVaca, setHistorialVaca] = useState(null)
  
  const [histFechaDesde, setHistFechaDesde] = useState('')
  const [histFechaHasta, setHistFechaHasta] = useState('')

  const [form, setForm] = useState({
    arete: '', nombre: '', raza: 'Jersey',
    proposito: 'leche', notas: '', hato_id: '',
  })

  const { data: hatos = [] } = useQuery({
    queryKey: ['hatos'],
    queryFn:  () => hatosApi.listar().then(r => r.data),
  })

  const { data: animales = [], isLoading } = useQuery({
    queryKey: ['animales', buscar],
    queryFn:  () => animalesApi.listar(buscar ? { buscar } : {}).then(r => r.data),
  })

  const { data: medicionesRaw = [] } = useQuery({
    queryKey: ['mediciones', historialVaca?.id],
    queryFn:  () => animalesApi.mediciones(historialVaca.id).then(r => r.data),
    enabled:  !!historialVaca,
  })

  const mediciones = medicionesRaw.filter(m => {
    const fecha = new Date(m.fecha_medicion)
    if (histFechaDesde && fecha < new Date(histFechaDesde))          return false
    if (histFechaHasta && fecha > new Date(histFechaHasta + 'T23:59:59')) return false
    return true
  })

  // Preparar datos para el gráfico (Curva suave por fecha)
  const chartData = [...mediciones].reverse().map(m => ({
    fecha: new Date(m.fecha_medicion).toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }),
    peso:  m.peso_estimado_kg,
    bcs:   m.bcs,
  }))

  const crear = useMutation({
    mutationFn: animalesApi.crear,
    onSuccess: () => {
      qc.invalidateQueries(['animales'])
      toast.success('Vaca registrada con éxito')
      setModal(false)
      setForm({ arete: '', nombre: '', raza: 'Jersey', proposito: 'leche', notas: '', hato_id: '' })
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al registrar'),
  })

  const eliminar = useMutation({
    mutationFn: animalesApi.eliminar,
    onSuccess: () => { qc.invalidateQueries(['animales']); toast.success('Vaca eliminada') },
    onError:   (e) => toast.error(e.response?.data?.detail || 'Error al eliminar'),
  })

  const [confirmarEliminar, setConfirmarEliminar] = useState(null)

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6 relative z-10">
      
      {/* CABECERA */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '2rem', fontWeight: 800 }}>
            Ganado Jersey
          </h1>
          <p className="font-mono text-xs mt-1 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
            <span style={{ color: C.accentDark, fontWeight: 900 }}>{animales.length}</span> VACAS REGISTRADAS
          </p>
        </div>
        <button 
          onClick={() => setModal(true)} 
          className="flex items-center gap-2 px-5 py-3 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.1em] text-white transition-all hover:scale-105 active:scale-95 shadow-lg w-full sm:w-auto justify-center"
          style={{ background: C.primary }}
        >
          <Plus size={16} color={C.accent} /> Nueva Vaca
        </button>
      </div>

      {/* BÚSQUEDA */}
      <div className="relative max-w-md">
        <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: C.textSecondary }} />
        <input 
          className="w-full pl-12 pr-4 py-3.5 rounded-xl border focus:outline-none transition-all shadow-sm"
          style={{ background: C.white, borderColor: 'rgba(82, 217, 160, 0.2)', color: C.primary }}
          placeholder="Buscar por arete o nombre..."
          value={buscarInput} onChange={e => setBuscarInput(e.target.value)} 
        />
      </div>

      {/* CONTENIDO PRINCIPAL */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="animate-spin" size={32} style={{ color: C.accentDark }} />
        </div>
      ) : animales.length === 0 ? (
        <div className="w-full bg-white rounded-[2rem] border-2 border-dashed flex flex-col items-center justify-center p-16 text-center shadow-sm" style={{ borderColor: 'rgba(82, 217, 160, 0.3)' }}>
          <div className="w-20 h-20 bg-[#E8F8F1] rounded-full flex items-center justify-center mb-4">
            <Activity size={32} style={{ color: C.accentDark }} />
          </div>
          <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '1.5rem', fontWeight: 800 }}>
            Sin vacas registradas
          </h2>
          <p className="mt-2 text-sm max-w-md" style={{ color: C.textSecondary }}>
            No se encontraron animales. Registra una nueva vaca para comenzar sus estimaciones.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-[1.5rem] shadow-[0_10px_30px_rgba(8,28,17,0.04)] border border-[rgba(82,217,160,0.15)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr style={{ background: '#F9FDFB', borderBottom: '1px solid rgba(82, 217, 160, 0.2)' }}>
                  {['Arete', 'Nombre', 'Hato / Ubicación', 'Último peso', 'Condición (BCS)', 'Análisis', 'Acciones'].map(h => (
                    <th key={h} className="px-6 py-5 text-left font-mono text-[10px] uppercase font-bold tracking-widest" style={{ color: C.textSecondary }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {animales.map((a) => {
                  const bc = a.ultimo_bcs ? getBCSColor(a.ultimo_bcs) : null
                  return (
                    <tr key={a.id} className="transition-colors hover:bg-[#F0FBF6] group" style={{ borderBottom: '1px solid rgba(8, 28, 17, 0.05)' }}>
                      <td className="px-6 py-4 font-mono text-sm font-bold" style={{ color: C.primary }}>
                        {a.arete}
                      </td>
                      <td className="px-6 py-4 font-sans text-sm font-semibold" style={{ color: C.primary }}>
                        {a.nombre || '—'}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-1.5 font-mono text-xs font-bold" style={{ color: C.accentDark }}>
                          <MapPin size={12} color={C.accent} /> {a.hato_nombre || 'Sin asignar'}
                        </div>
                      </td>
                      <td className="px-6 py-4 font-mono text-sm font-bold" style={{ color: C.primary }}>
                        {a.ultimo_peso_kg ? formatPeso(a.ultimo_peso_kg) : '—'}
                      </td>
                      <td className="px-6 py-4">
                        {bc ? (
                          <span className="font-mono text-[11px] px-3 py-1.5 rounded-lg font-bold shadow-sm inline-flex items-center gap-1.5"
                            style={{ background: bc.bg, color: bc.text }}>
                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: bc.text }}></div>
                            {a.ultimo_bcs?.toFixed(1)} · {getBCSLabel(a.ultimo_bcs)}
                          </span>
                        ) : <span className="opacity-40 font-bold" style={{ color: C.textSecondary }}>—</span>}
                      </td>
                      <td className="px-6 py-4 font-mono text-xs font-bold" style={{ color: C.textSecondary }}>
                        {a.total_mediciones} Reg.
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <button onClick={() => { setHistorialVaca(a); setHistFechaDesde(''); setHistFechaHasta('') }}
                            className="p-2 rounded-lg transition-all hover:bg-emerald-100" 
                            style={{ color: C.accentDark }} title="Ver Historial y Curva">
                            <Activity size={18} />
                          </button>
                          <button onClick={() => setConfirmarEliminar(a)}
                            className="p-2 rounded-lg transition-all hover:bg-red-50 opacity-0 group-hover:opacity-100" 
                            style={{ color: C.danger }} title="Eliminar">
                            <Trash2 size={18} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* MODAL NUEVA VACA */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in" style={{ background: 'rgba(8, 28, 17, 0.6)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-lg bg-white rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="px-8 py-6 flex items-center justify-between" style={{ background: '#F9FDFB', borderBottom: '1px solid rgba(82, 217, 160, 0.2)' }}>
              <div>
                <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '1.5rem', fontWeight: 800 }}>
                  Nueva vaca Jersey
                </h2>
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest mt-1" style={{ color: C.textSecondary }}>
                  REGISTRO DE ANIMAL
                </p>
              </div>
              <button onClick={() => setModal(false)} className="p-2 rounded-full hover:bg-gray-200 transition-colors" style={{ color: C.primary }}><X size={20} /></button>
            </div>
            
            <form onSubmit={e => { e.preventDefault(); if (!form.hato_id) return toast.error('Selecciona un hato'); crear.mutate(form) }} className="p-8 space-y-5">
              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Arete *</label>
                  <input className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} placeholder="EC-001" required value={form.arete} onChange={e => setForm({ ...form, arete: e.target.value })} />
                </div>
                <div>
                  <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Nombre</label>
                  <input className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} placeholder="Opcional" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-5">
                <div>
                  <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Raza</label>
                  <input className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} value={form.raza} onChange={e => setForm({ ...form, raza: e.target.value })} />
                </div>
                <div>
                  <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Propósito</label>
                  <select className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} value={form.proposito} onChange={e => setForm({ ...form, proposito: e.target.value })}>
                    <option value="leche">Leche</option>
                    <option value="carne">Carne</option>
                    <option value="doble_proposito">Doble propósito</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Hato (Ubicación) *</label>
                <select className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-bold" style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} value={form.hato_id} required onChange={e => setForm({ ...form, hato_id: e.target.value })}>
                  <option value="">— Selecciona un hato —</option>
                  {hatos.map(h => <option key={h.id} value={h.id}>{h.nombre} — {h.finca}</option>)}
                </select>
              </div>

              <div className="flex gap-4 pt-4">
                <button type="button" onClick={() => setModal(false)} className="flex-1 py-3.5 rounded-xl font-mono text-sm font-bold uppercase tracking-widest transition-colors hover:bg-gray-100" style={{ color: C.primary, border: '1px solid #E5E7EB' }}>Cancelar</button>
                <button type="submit" disabled={crear.isPending} className="flex-1 py-3.5 rounded-xl font-mono text-sm font-bold uppercase tracking-widest text-white transition-all flex items-center justify-center gap-2 shadow-md hover:shadow-lg disabled:opacity-70" style={{ background: C.primary }}>
                  {crear.isPending && <Loader2 size={16} className="animate-spin" />} Registrar Vaca
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL HISTORIAL Y GRÁFICA */}
      {historialVaca && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(8,28,17,0.7)] backdrop-blur-md">
          <div className="w-full max-w-4xl animate-slide-up max-h-[90vh] flex flex-col bg-white rounded-[2rem] shadow-2xl overflow-hidden">
            
            {/* Header del Historial */}
            <div className="flex items-center justify-between px-8 py-6" style={{ background: C.primary }}>
              <div>
                <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.white, fontSize: '1.8rem', fontWeight: 800 }}>
                  {historialVaca.nombre || `Vaca ${historialVaca.arete}`}
                </h2>
                <div className="flex items-center gap-4 mt-2">
                  <p className="font-mono text-xs font-bold px-2 py-1 bg-white/20 rounded-md" style={{ color: C.accent }}>ARETE: {historialVaca.arete}</p>
                  <p className="font-mono text-xs font-bold text-white/70 flex items-center gap-1"><MapPin size={12}/> {historialVaca.hato_nombre}</p>
                </div>
              </div>
              <button onClick={() => setHistorialVaca(null)} className="text-white/70 hover:text-white transition-colors p-2 bg-white/10 rounded-full"><X size={20} /></button>
            </div>

            {/* Filtros */}
            <div className="px-8 py-4 flex flex-wrap items-center gap-4 bg-[#F9FDFB] border-b border-[rgba(82,217,160,0.2)]">
              <div className="flex items-center gap-2">
                <Filter size={16} style={{ color: C.accentDark }} />
                <span className="font-mono text-[10px] uppercase font-bold tracking-widest" style={{ color: C.textSecondary }}>Filtrar Curva:</span>
              </div>
              <input type="date" className="px-3 py-2 rounded-lg border focus:outline-none text-xs font-mono" style={{ borderColor: 'rgba(27,67,50,0.15)', color: C.primary }} value={histFechaDesde} onChange={e => setHistFechaDesde(e.target.value)} />
              <span className="font-mono text-[10px]" style={{ color: C.textSecondary }}>hasta</span>
              <input type="date" className="px-3 py-2 rounded-lg border focus:outline-none text-xs font-mono" style={{ borderColor: 'rgba(27,67,50,0.15)', color: C.primary }} value={histFechaHasta} onChange={e => setHistFechaHasta(e.target.value)} />
              {(histFechaDesde || histFechaHasta) && (
                <button onClick={() => { setHistFechaDesde(''); setHistFechaHasta('') }} className="font-mono text-[10px] font-bold uppercase tracking-widest hover:underline" style={{ color: C.danger }}>Limpiar</button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-[#F0FBF6]">
              
              {/* GRÁFICA MEJORADA CON CURVAS Y ÁREAS */}
              {chartData.length > 1 && (
                <div className="bg-white p-6 rounded-[1.5rem] shadow-sm border border-emerald-50">
                  <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-6" style={{ color: C.primary }}>Curva de Evolución de Masa</h3>
                  <ResponsiveContainer width="100%" height={260}>
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorPeso" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={C.primary} stopOpacity={0.3}/>
                          <stop offset="95%" stopColor={C.primary} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(27,67,50,0.08)" vertical={false} />
                      <XAxis dataKey="fecha" tick={{ fontSize: 11, fill: C.textSecondary, fontFamily: 'JetBrains Mono', fontWeight: 'bold' }} axisLine={false} tickLine={false} dy={10} />
                      <YAxis yAxisId="peso" tick={{ fontSize: 11, fill: C.primary, fontFamily: 'JetBrains Mono', fontWeight: 'bold' }} domain={['auto', 'auto']} axisLine={false} tickLine={false} />
                      <YAxis yAxisId="bcs" orientation="right" tick={{ fontSize: 11, fill: C.accentDark, fontFamily: 'JetBrains Mono', fontWeight: 'bold' }} domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} axisLine={false} tickLine={false} />
                      
                      <Tooltip contentStyle={{ background: C.primary, border: 'none', borderRadius: 12, color: 'white', fontSize: 12, fontFamily: 'JetBrains Mono', boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }} itemStyle={{ color: 'white' }} formatter={(v, name) => [name === 'peso' ? `${v} kg` : v, name === 'peso' ? 'Peso' : 'BCS']} />
                      <Legend formatter={v => <span style={{ color: C.primary, fontWeight: 'bold', fontSize: 11, fontFamily: 'JetBrains Mono', textTransform: 'uppercase' }}>{v === 'peso' ? 'Peso (kg)' : 'BCS'}</span>} iconType="circle" wrapperStyle={{ paddingTop: '20px' }}/>
                      
                      {/* Curvas suaves usando type="monotone" */}
                      <Area yAxisId="peso" type="monotone" dataKey="peso" stroke={C.primary} strokeWidth={4} fillOpacity={1} fill="url(#colorPeso)" dot={{ r: 4, fill: C.white, stroke: C.primary, strokeWidth: 2 }} activeDot={{ r: 6, fill: C.accent }} />
                      <Area yAxisId="bcs" type="monotone" dataKey="bcs" stroke={C.accent} strokeWidth={3} fill="none" dot={{ r: 4, fill: C.white, stroke: C.accent, strokeWidth: 2 }} activeDot={{ r: 6 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* LISTA DE MEDICIONES */}
              <div>
                <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-4" style={{ color: C.primary }}>Historial Clínico</h3>
                {mediciones.length === 0 ? (
                  <div className="p-8 text-center bg-white rounded-2xl border border-dashed border-emerald-200">
                    <p className="font-mono text-sm opacity-60" style={{ color: C.primary }}>No hay mediciones registradas.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {mediciones.map(m => {
                      const bc = getBCSColor(m.bcs)
                      return (
                        <div key={m.id} className="flex items-center gap-4 p-5 rounded-[1rem] bg-white transition-all hover:shadow-md border border-emerald-50">
                          <div className="font-mono text-xs w-32 flex-shrink-0 font-bold" style={{ color: C.textSecondary }}>{formatFechaHora(m.fecha_medicion)}</div>
                          <div className="font-mono text-xl w-28 flex-shrink-0 font-extrabold" style={{ color: C.primary }}>{formatPeso(m.peso_estimado_kg)}</div>
                          <div className="flex-1">
                            <span className="font-mono text-[11px] px-3 py-1.5 rounded-lg font-bold inline-flex items-center gap-1.5" style={{ background: bc.bg, color: bc.text }}>
                              <div className="w-1.5 h-1.5 rounded-full" style={{ background: bc.text }}></div> BCS {m.bcs?.toFixed(1)}
                            </span>
                          </div>
                          {m.notas && <div className="flex-1 font-sans text-sm italic text-gray-500 line-clamp-1">"{m.notas}"</div>}
                          <div className="font-mono text-[10px] uppercase font-bold tracking-widest flex-shrink-0 px-3 py-1 bg-gray-50 rounded-md" style={{ color: C.textSecondary }}>{m.confianza?.toFixed(0)}% Precisión</div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* MODAL ELIMINAR (Se mantiene igual, solo ajustado color) */}
      {confirmarEliminar && (
         <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(8,28,17,0.6)] backdrop-blur-sm animate-in fade-in">
           <div className="w-full max-w-sm bg-white rounded-[2rem] p-8 text-center shadow-2xl animate-in zoom-in-95">
             <div className="w-16 h-16 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4"><Trash2 size={24} /></div>
             <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '1.5rem', fontWeight: 800, marginBottom: '8px' }}>¿Eliminar vaca?</h2>
             <p className="font-mono text-sm opacity-80 mb-8" style={{ color: C.primary }}>Se eliminará <strong>{confirmarEliminar.nombre || confirmarEliminar.arete}</strong> y sus análisis. Irreversible.</p>
             <div className="flex gap-3">
               <button onClick={() => setConfirmarEliminar(null)} className="flex-1 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-colors hover:bg-gray-100" style={{ color: C.primary, border: '1px solid #E5E7EB' }}>Cancelar</button>
               <button onClick={() => { eliminar.mutate(confirmarEliminar.id); setConfirmarEliminar(null) }} className="flex-1 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest text-white transition-all shadow-md hover:shadow-lg" style={{ background: C.danger }}>Eliminar</button>
             </div>
           </div>
         </div>
       )}
    </div>
  )
}