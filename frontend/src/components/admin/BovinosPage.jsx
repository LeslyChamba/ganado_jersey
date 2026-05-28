import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts'
import { Beef, Scale, AlertTriangle, TrendingUp, Search, X, Database } from 'lucide-react'
import { getBCSColor, formatFechaHora } from '../../services/helpers'
import api from '../../services/api'

/* ── Tokens de color de la marca JER-WEIGHT ── */
const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444', warning: '#F59E0B'
}
/* ── Tokens de tipografía ── */
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

export default function AdminBovinosPage() {
  const [pesoMin, setPesoMin] = useState('')
  const [pesoMax, setPesoMax] = useState('')
  const [filtrosActivos, setFiltrosActivos] = useState({ min: null, max: null })
  const [busqueda, setBusqueda] = useState('')

  // Stats generales
  const { data: stats } = useQuery({
    queryKey: ['admin-bovinos-stats'],
    queryFn: () => api.get('/admin/bovinos/stats').then(r => r.data),
  })

  // Lista con filtros
  const { data: bovinos = [], isLoading } = useQuery({
    queryKey: ['admin-bovinos', filtrosActivos],
    queryFn: () => {
      const params = new URLSearchParams()
      if (filtrosActivos.min) params.append('peso_min', filtrosActivos.min)
      if (filtrosActivos.max) params.append('peso_max', filtrosActivos.max)
      return api.get(`/admin/bovinos?${params}`).then(r => r.data)
    },
  })

  const aplicarFiltros = () => setFiltrosActivos({ min: pesoMin || null, max: pesoMax || null })
  const limpiarFiltros = () => { setPesoMin(''); setPesoMax(''); setFiltrosActivos({ min: null, max: null }) }

  // Filtro local por búsqueda
  const bovinosFiltrados = bovinos.filter(b => {
    if (!busqueda) return true
    const q = busqueda.toLowerCase()
    return (
      b.arete?.toLowerCase().includes(q) ||
      b.nombre?.toLowerCase().includes(q) ||
      b.ganadero?.toLowerCase().includes(q) ||
      b.hato_nombre?.toLowerCase().includes(q)
    )
  })

  // Datos para gráfica de distribución de peso
  const rangos = [
    { label: '<200',    min: 0,   max: 200  },
    { label: '200-250', min: 200, max: 250  },
    { label: '250-300', min: 250, max: 300  },
    { label: '300-350', min: 300, max: 350  },
    { label: '350-400', min: 350, max: 400  },
    { label: '>400',    min: 400, max: 9999 },
  ]
  const distPeso = rangos.map(r => ({
    label: r.label,
    cantidad: bovinos.filter(b => b.ultimo_peso_kg >= r.min && b.ultimo_peso_kg < r.max).length,
  }))

  // Datos para gráfica de tendencia (últimos 14 con medición)
  const conMedicion = bovinos
    .filter(b => b.ultimo_peso_kg && b.ultima_medicion)
    .sort((a, b) => new Date(b.ultima_medicion) - new Date(a.ultima_medicion))
    .slice(0, 14)
    .reverse()

  const tarjetas = [
    { label: 'Total Bovinos',       value: stats?.total         ?? '—', icon: Beef,          accent: C.primary,    bg: '#E8F8F1' },
    { label: 'Peso Promedio',       value: stats?.peso_promedio ? `${stats.peso_promedio} kg` : '—', icon: Scale, accent: C.accentDark, bg: '#EAF4EE' },
    { label: 'BCS Promedio',        value: stats?.bcs_promedio  ?? '—', icon: TrendingUp,    accent: C.warning,    bg: '#FFFBEB' },
    { label: 'En Alerta (BCS<2.5)', value: stats?.en_alerta     ?? '—', icon: AlertTriangle, accent: C.danger,     bg: '#FEF2F2' },
  ]

  const inputClass = "px-4 py-3 rounded-xl border focus:outline-none transition-all font-mono text-xs"
  const inputStyle = { background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 relative z-10">

      {/* ── HEADER ── */}
      <div>
        <h1 style={{ fontFamily: F.brand, color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
          Supervisión de Bovinos
        </h1>
        <p className="font-mono text-[11px] mt-2 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
          Rango Global: <span style={{ color: C.accentDark }}>{stats?.peso_min ?? '—'} – {stats?.peso_max ?? '—'} kg</span> &nbsp;|&nbsp; {bovinos.length} Registros
        </p>
      </div>

      {/* ── TARJETAS (KPIs) ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {tarjetas.map(({ label, value, icon: Icon, accent, bg }, i) => (
          <div key={label} className="bg-white rounded-[1.5rem] p-6 relative overflow-hidden transition-all duration-300"
               style={{ boxShadow: '0 10px 30px rgba(8, 28, 17, 0.04)', border: '1px solid rgba(82, 217, 160, 0.15)', animationDelay: `${i * 100}ms` }}>
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-inner mb-4" style={{ background: bg }}>
              <Icon size={20} style={{ color: accent }} />
            </div>
            <div style={{ fontFamily: F.brand, color: accent, fontSize: '2rem', fontWeight: 800, lineHeight: 1 }}>
              {value}
            </div>
            <div className="font-mono text-[10px] mt-2 font-bold uppercase tracking-wider" style={{ color: C.textSecondary }}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── GRÁFICAS ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Tendencia últimas mediciones */}
        {conMedicion.length > 0 && (
          <div className="bg-white p-6 rounded-[1.5rem] shadow-sm border border-emerald-50">
            <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-6" style={{ color: C.primary }}>Tendencia de Masa Reciente</h3>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={conMedicion} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gAdminPeso" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={C.accentDark} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={C.accentDark} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(27,67,50,0.08)" vertical={false} />
                <XAxis dataKey="arete" tick={{ fontSize: 10, fill: C.textSecondary, fontFamily: F.body, fontWeight: 'bold' }} axisLine={false} tickLine={false} dy={10} />
                <YAxis tick={{ fontSize: 10, fill: C.primary, fontFamily: F.body, fontWeight: 'bold' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: C.primary, border: 'none', borderRadius: 12, color: 'white', fontSize: 12, fontFamily: F.body, boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}
                  itemStyle={{ color: 'white', fontWeight: 'bold' }}
                  formatter={v => [`${v} kg`, 'Peso']}
                />
                <Area type="monotone" dataKey="ultimo_peso_kg" stroke={C.accentDark} strokeWidth={3} fill="url(#gAdminPeso)" dot={{ r: 4, fill: C.white, stroke: C.accentDark, strokeWidth: 2 }} activeDot={{ r: 6, fill: C.accent }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Distribución por rango de peso */}
        <div className="bg-white p-6 rounded-[1.5rem] shadow-sm border border-emerald-50">
          <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-6" style={{ color: C.primary }}>Distribución por Rangos (kg)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={distPeso} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(27,67,50,0.08)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: C.textSecondary, fontFamily: F.body, fontWeight: 'bold' }} axisLine={false} tickLine={false} dy={10} />
              <YAxis tick={{ fontSize: 10, fill: C.primary, fontFamily: F.body, fontWeight: 'bold' }} allowDecimals={false} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: 'rgba(82,217,160,0.1)' }}
                contentStyle={{ background: C.primary, border: 'none', borderRadius: 12, color: 'white', fontSize: 12, fontFamily: F.body, boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}
                itemStyle={{ color: 'white', fontWeight: 'bold' }}
                formatter={v => [v, 'Bovinos']}
              />
              <Bar dataKey="cantidad" radius={[6, 6, 0, 0]} maxBarSize={50}>
                {distPeso.map((_, i) => (
                  <Cell key={i} fill={i === 2 || i === 3 ? C.accentDark : C.accent} fillOpacity={i === 2 || i === 3 ? 1 : 0.6} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── SECCIÓN DE FILTROS ── */}
      <div className="bg-white rounded-[1.5rem] p-6 shadow-sm border border-emerald-50">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-5">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Peso Min (kg)</label>
              <input type="number" placeholder="ej. 200" value={pesoMin} onChange={e => setPesoMin(e.target.value)} className={inputClass} style={{ ...inputStyle, width: '130px' }} />
            </div>
            <div>
              <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Peso Máx (kg)</label>
              <input type="number" placeholder="ej. 400" value={pesoMax} onChange={e => setPesoMax(e.target.value)} className={inputClass} style={{ ...inputStyle, width: '130px' }} />
            </div>
            <button onClick={aplicarFiltros} className="px-6 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest text-white transition-all shadow-md hover:shadow-lg" style={{ background: C.primary, height: '42px' }}>
              Aplicar
            </button>
            {(filtrosActivos.min || filtrosActivos.max) && (
              <button onClick={limpiarFiltros} className="px-4 py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest flex items-center gap-1 transition-colors hover:bg-red-50" style={{ color: C.danger, border: '1px solid rgba(239,68,68,0.2)', height: '42px' }}>
                <X size={14} /> Limpiar
              </button>
            )}
          </div>

          {/* Búsqueda general */}
          <div className="relative w-full lg:w-80">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: C.textSecondary }} />
            <input type="text" placeholder="Buscar arete, nombre, ganadero..." value={busqueda} onChange={e => setBusqueda(e.target.value)} className={`${inputClass} pl-11 w-full`} style={inputStyle} />
          </div>
        </div>
      </div>

      {/* ── TABLA DE DATOS ── */}
      <div className="bg-white rounded-[1.5rem] shadow-sm border border-emerald-50 overflow-hidden">
        <div className="px-6 py-5 flex items-center justify-between bg-[#F9FDFB] border-b border-[rgba(82,217,160,0.2)]">
          <div className="flex items-center gap-3">
            <Database size={16} style={{ color: C.accentDark }} />
            <span className="font-mono text-sm font-bold uppercase tracking-widest" style={{ color: C.primary }}>Directorio de Bovinos</span>
          </div>
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest px-3 py-1 bg-white rounded-md shadow-sm" style={{ color: C.textSecondary }}>
            {bovinosFiltrados.length} Resultados
          </span>
        </div>

        {isLoading ? (
          <div className="p-16 text-center font-mono text-xs font-bold uppercase tracking-widest animate-pulse" style={{ color: C.textSecondary }}>
            Cargando bovinos...
          </div>
        ) : bovinosFiltrados.length === 0 ? (
          <div className="p-16 text-center">
            <Beef size={32} className="mx-auto mb-4 opacity-20" style={{ color: C.primary }} />
            <p className="font-sans font-bold text-lg" style={{ color: C.primary }}>Sin resultados</p>
            <p className="font-mono text-xs mt-1" style={{ color: C.textSecondary }}>Ajusta los filtros de búsqueda o peso.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[900px]">
              {/* Encabezado de Grid */}
              <div className="grid grid-cols-[1fr_1.5fr_1.5fr_1.5fr_1fr_1fr_1.5fr] gap-4 px-6 py-4 bg-[#F9FDFB] border-b border-[rgba(8,28,17,0.05)]">
                {['Arete', 'Nombre', 'Propietario', 'Hato / Ubicación', 'Peso', 'BCS', 'Último Registro'].map(h => (
                  <span key={h} className="font-mono text-[10px] uppercase font-bold tracking-widest" style={{ color: C.textSecondary }}>{h}</span>
                ))}
              </div>

              {/* Filas */}
              <ul className="divide-y divide-[rgba(8,28,17,0.03)]">
                {bovinosFiltrados.map((b) => {
                  const bc = b.ultimo_bcs ? getBCSColor(b.ultimo_bcs) : null
                  return (
                    <li key={b.id} className="grid grid-cols-[1fr_1.5fr_1.5fr_1.5fr_1fr_1fr_1.5fr] gap-4 px-6 py-4 items-center transition-colors hover:bg-[#F0FBF6] group">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-mono text-sm font-bold shadow-inner flex-shrink-0" style={{ background: '#E8F8F1', color: C.accentDark }}>
                          {b.arete?.slice(-3)}
                        </div>
                        <span className="font-mono text-xs font-bold" style={{ color: C.primary }}>{b.arete}</span>
                      </div>
                      <div className="font-sans text-sm font-bold truncate pr-2" style={{ color: C.primary }}>
                        {b.nombre || '—'}
                      </div>
                      <div className="font-mono text-[11px] font-bold uppercase tracking-wider truncate pr-2" style={{ color: C.textSecondary }}>
                        {b.ganadero}
                      </div>
                      <div className="font-mono text-[11px] text-gray-500 truncate pr-2">
                        {b.hato_nombre}
                      </div>
                      <div className="font-mono text-sm font-extrabold" style={{ color: C.primary }}>
                        {b.ultimo_peso_kg ? `${b.ultimo_peso_kg.toFixed(1)} kg` : '—'}
                      </div>
                      <div>
                        {bc ? (
                          <span className="inline-flex items-center gap-1.5 font-mono text-[10px] px-2.5 py-1.5 rounded-lg font-bold shadow-sm" style={{ background: bc.bg, color: bc.text }}>
                            <div className="w-1.5 h-1.5 rounded-full" style={{ background: bc.text }}></div> {b.ultimo_bcs?.toFixed(2)}
                          </span>
                        ) : <span className="text-gray-400 font-bold">—</span>}
                      </div>
                      <div className="font-mono text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                        {b.ultima_medicion ? formatFechaHora(b.ultima_medicion) : '—'}
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