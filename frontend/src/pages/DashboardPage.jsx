import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi, animalesApi } from '../services/api'
import api from '../services/api'
import { getBCSColor, getBCSLabel, formatPeso, formatFechaHora } from '../services/helpers'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'
import { Users, TrendingUp, AlertTriangle, FolderOpen, X, ChevronRight } from 'lucide-react'
import useAuthStore from '../store/authStore'

const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF',
  danger: '#EF4444', warning: '#F5C542',
}
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

// ── Icono de vaca (reemplaza el icono de carne "Beef" de lucide-react) ──
// Componente local, sin dependencias nuevas, en el mismo estilo de trazo
// que el resto de iconos lucide (stroke 2, esquinas redondeadas).
function CowIcon({ size = 24, color = 'currentColor', style }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color}
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      <path d="M5 9c-1.5 0-2.5-1.2-2.5-2.5S3.5 4 5 4c1 0 1.8.5 2.2 1.3" />
      <path d="M19 9c1.5 0 2.5-1.2 2.5-2.5S20.5 4 19 4c-1 0-1.8.5-2.2 1.3" />
      <path d="M7 7.5C7 6 8.3 5 10 5h4c1.7 0 3 1 3 2.5v2c0 1-.3 1.8-1 2.5l-.7 4.3c-.2 1.5-1.5 2.7-3 2.7h-.6c-1.5 0-2.8-1.2-3-2.7L8 12c-.7-.7-1-1.5-1-2.5z" />
      <circle cx="9.5" cy="10.5" r="0.75" fill={color} />
      <circle cx="14.5" cy="10.5" r="0.75" fill={color} />
      <path d="M10.5 13.5h3" />
    </svg>
  )
}

export default function DashboardPage() {
  const { usuario } = useAuthStore()
  const isAdmin = usuario?.rol === 'admin' || usuario?.rol === 'ADMIN'
  const [mostrarAlertas, setMostrarAlertas] = useState(false)

  // ── Dashboard stats ──────────────────────────────────────
  const { data: dash } = useQuery({
    queryKey: ['dashboard-ganadero'],
    queryFn:  () => dashboardApi.ganadero().then(r => r.data),
    enabled:  !isAdmin,
    refetchInterval: 30_000,
  })

  const { data: dashAdmin } = useQuery({
    queryKey: ['dashboard-admin'],
    queryFn:  () => dashboardApi.admin().then(r => r.data),
    enabled:  isAdmin,
    refetchInterval: 30_000,
  })

  // ── FIX BUG #1: alertas con queryKey que incluye el rol ─
  // Antes: queryKey: ['alertas'] — mismo cache para admin y ganadero
  // Ahora: queryKey separado por rol, y refetch sincronizado con el dashboard
  const { data: alertas = [] } = useQuery({
    queryKey: ['alertas', usuario?.id],   // ← por usuario, no global
    queryFn:  () => dashboardApi.alertas().then(r => r.data),
    refetchInterval: 30_000,
    // Forzar refetch cuando se abre el modal para datos frescos
    staleTime: 15_000,
  })

  const { data: animales = [] } = useQuery({
    queryKey: ['animales', isAdmin],
    queryFn:  () => isAdmin
      ? api.get('/admin/bovinos').then(r => r.data)
      : animalesApi.listar().then(r => r.data),
  })

  // ── Datos para gráficas ──────────────────────────────────
  const recientes = animales
    .filter(a => a.ultima_medicion)
    .sort((a, b) => new Date(b.ultima_medicion) - new Date(a.ultima_medicion))
    .slice(0, 6)

  const chartData = animales
    .filter(a => a.ultimo_peso_kg)
    .slice(0, 14)
    .map(a => ({ name: a.arete, peso: a.ultimo_peso_kg }))

  // ── FIX BUG #1 (frontend): usar el MISMO valor de alerta
  // en el contador KPI y en el gráfico de anillo.
  // Antes: cada tarjeta leía de su propio campo, podían diferir.
  const totalAnimales   = dash?.total_animales   ?? dashAdmin?.total_bovinos     ?? 0
  const enAlerta        = dash?.animales_en_alerta ?? dashAdmin?.animales_en_alerta ?? 0

  const bcsData = [
    { name: 'Alerta (< 2.5)', value: enAlerta,                              color: C.danger },
    { name: 'Saludable',       value: Math.max(0, totalAnimales - enAlerta), color: C.accent },
  ]

  // ── KPI cards ───────────────────────────────────────────
  const tarjetas = isAdmin ? [
    { label: 'Total Usuarios',     value: dashAdmin?.total_usuarios   ?? '—', icon: Users,         accent: C.primary,    bg: '#E8F8F1' },
    { label: 'Total Bovinos',      value: dashAdmin?.total_bovinos    ?? '—', icon: CowIcon,       accent: C.accentDark, bg: '#EAF4EE' },
    { label: 'Evaluaciones Hoy',   value: dashAdmin?.evaluaciones_hoy ?? '—', icon: TrendingUp,    accent: C.warning,    bg: '#FFFBEB' },
    { label: 'Animales en Alerta', value: enAlerta,                          icon: AlertTriangle,  accent: C.danger,     bg: '#FEF2F2', clickable: true },
  ] : [
    { label: 'Total Vacas',        value: dash?.total_animales        ?? '—', icon: CowIcon,       accent: C.primary,    bg: '#E8F8F1' },
    { label: 'Mis Hatos',          value: dash?.total_hatos           ?? '—', icon: FolderOpen,    accent: C.accentDark, bg: '#EAF4EE' },
    { label: 'Evaluaciones Hoy',   value: dash?.evaluaciones_hoy      ?? '—', icon: TrendingUp,    accent: C.warning,    bg: '#FFFBEB' },
    { label: 'Animales en Alerta', value: enAlerta,                          icon: AlertTriangle,  accent: C.danger,     bg: '#FEF2F2', clickable: true },
  ]

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 relative z-10">

      {/* ── HEADER ── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: F.brand, color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
            {isAdmin ? 'Panel de Control' : 'Mi Ganadería'}
          </h1>
          <p className="font-mono text-xs mt-2 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
            {isAdmin
              ? <span className="bg-white px-3 py-1 rounded-md shadow-sm">{dashAdmin?.usuarios_activos ?? '—'} USUARIOS ACTIVOS</span>
              : <span>
                  BCS Promedio: <span style={{ color: C.accentDark, fontWeight: 900 }}>{dash?.bcs_promedio?.toFixed(1) ?? '—'}</span>
                  &nbsp;|&nbsp;
                  Peso Medio: <span style={{ color: C.accentDark, fontWeight: 900 }}>{dash?.peso_promedio_kg ? `${dash.peso_promedio_kg} kg` : '—'}</span>
                </span>
            }
          </p>
        </div>
      </div>

      {/* ── KPI CARDS ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {tarjetas.map(({ label, value, icon: Icon, accent, bg, clickable }, i) => (
          <div
            key={label}
            className={`bg-white rounded-[1.5rem] p-6 relative overflow-hidden transition-all duration-300 ${
              clickable ? 'cursor-pointer hover:-translate-y-1 hover:shadow-lg ring-1 ring-transparent hover:ring-red-100' : ''
            }`}
            style={{
              boxShadow: '0 10px 30px rgba(8, 28, 17, 0.04)',
              border: '1px solid rgba(82, 217, 160, 0.15)',
              animationDelay: `${i * 100}ms`,
            }}
            onClick={clickable ? () => setMostrarAlertas(true) : undefined}
          >
            <div className="flex justify-between items-start mb-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-inner" style={{ background: bg }}>
                <Icon size={24} style={{ color: accent }} />
              </div>
              {/* FIX: mostrar "Ver" solo si hay alertas reales */}
              {clickable && value > 0 && (
                <span className="flex items-center gap-1 font-mono text-[10px] uppercase font-bold tracking-widest px-2 py-1 rounded-md" style={{ background: '#FEF2F2', color: C.danger }}>
                  Ver <ChevronRight size={12} />
                </span>
              )}
            </div>
            <div style={{ fontFamily: F.brand, color: accent, fontSize: '2.5rem', fontWeight: 800, lineHeight: 1 }}>
              {value}
            </div>
            <div className="font-mono text-xs mt-2 font-bold uppercase tracking-wider" style={{ color: C.textSecondary }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* ── GRÁFICAS ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {chartData.length > 0 && (
          <div className="bg-white p-6 rounded-[1.5rem] shadow-sm border border-emerald-50 lg:col-span-2">
            <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-6" style={{ color: C.primary }}>
              Masa Corporal Reciente
            </h3>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorDashboardPeso" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={C.accentDark} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={C.accentDark} stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(27,67,50,0.08)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: C.textSecondary, fontFamily: F.body, fontWeight: 'bold' }} axisLine={false} tickLine={false} dy={10} />
                <YAxis tick={{ fontSize: 10, fill: C.primary, fontFamily: F.body, fontWeight: 'bold' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: C.primary, border: 'none', borderRadius: 12, color: 'white', fontSize: 12, fontFamily: F.body, boxShadow: '0 10px 25px rgba(0,0,0,0.2)' }}
                  itemStyle={{ color: 'white', fontWeight: 'bold' }}
                  formatter={v => [`${v} kg`, 'Peso Estimado']}
                />
                <Area
                  type="monotone" dataKey="peso"
                  stroke={C.accentDark} strokeWidth={3}
                  fill="url(#colorDashboardPeso)"
                  dot={{ r: 4, fill: C.white, stroke: C.accentDark, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: C.accent }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {(bcsData[0].value > 0 || bcsData[1].value > 0) && (
          <div className="bg-white p-6 rounded-[1.5rem] shadow-sm border border-emerald-50 flex flex-col items-center justify-center">
            <h3 className="font-mono text-sm font-bold uppercase tracking-widest mb-2 w-full text-center" style={{ color: C.primary }}>
              Salud de las vacas (BCS)
            </h3>
            <PieChart width={200} height={200}>
              <Pie data={bcsData} cx={100} cy={100} innerRadius={60} outerRadius={85} paddingAngle={5} dataKey="value" stroke="none">
                {bcsData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} itemStyle={{ fontWeight: 'bold', fontFamily: F.body }} />
            </PieChart>
            <div className="w-full space-y-2 mt-2">
              {bcsData.map(d => (
                <div key={d.name} className="flex items-center justify-between px-4 py-2 rounded-lg" style={{ background: '#F9FDFB' }}>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full shadow-sm" style={{ background: d.color }} />
                    <span className="font-mono text-xs font-bold" style={{ color: C.primary }}>{d.name}</span>
                  </div>
                  <span className="font-mono text-sm font-extrabold" style={{ color: C.primary }}>{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── ÚLTIMAS MEDICIONES ── */}
      {recientes.length > 0 && (
        <div className="bg-white rounded-[1.5rem] shadow-sm border border-emerald-50 overflow-hidden">
          <div className="px-8 py-5" style={{ borderBottom: '1px solid rgba(8,28,17,0.05)', background: '#F9FDFB' }}>
            <h3 className="font-mono text-sm font-bold uppercase tracking-widest" style={{ color: C.primary }}>Actividad Reciente</h3>
          </div>
          <div className="divide-y divide-[rgba(8,28,17,0.03)]">
            {recientes.map(a => {
              const bc = a.ultimo_bcs ? getBCSColor(a.ultimo_bcs) : null
              return (
                <div key={a.id} className="px-8 py-4 flex items-center justify-between hover:bg-[#F0FBF6] transition-colors group">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center font-mono text-sm font-bold shadow-inner" style={{ background: '#E8F8F1', color: C.accentDark }}>
                      {a.arete?.slice(-3)}
                    </div>
                    <div>
                      <div className="font-sans text-sm font-bold" style={{ color: C.primary }}>{a.nombre || `Vaca ${a.arete}`}</div>
                      <div className="font-mono text-[10px] uppercase font-bold tracking-wider mt-0.5" style={{ color: C.textSecondary }}>{formatFechaHora(a.ultima_medicion)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <div className="font-mono text-lg font-extrabold text-right" style={{ color: C.primary }}>
                      {formatPeso(a.ultimo_peso_kg)}
                    </div>
                    {bc && (
                      <span className="font-mono text-[10px] px-3 py-1.5 rounded-lg font-bold shadow-sm hidden sm:inline-flex items-center gap-1.5" style={{ background: bc.bg, color: bc.text }}>
                        <div className="w-1.5 h-1.5 rounded-full" style={{ background: bc.text }} /> BCS {a.ultimo_bcs?.toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── MODAL ALERTAS (HU-13) ── */}
      {mostrarAlertas && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(8,28,17,0.7)] backdrop-blur-md animate-in fade-in"
          onClick={e => { if (e.target === e.currentTarget) setMostrarAlertas(false) }}
        >
          <div className="w-full max-w-xl bg-white rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95">

            {/* Header modal */}
            <div className="px-8 py-6 flex items-center justify-between" style={{ background: '#FEF2F2', borderBottom: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <div>
                <h2 style={{ fontFamily: F.brand, fontWeight: 800, fontSize: '1.5rem', color: C.danger }} className="flex items-center gap-2">
                  <AlertTriangle size={24} /> Animales en Alerta
                </h2>
                {/* FIX: subtítulo ahora muestra todos los motivos, no solo BCS */}
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest mt-1" style={{ color: '#991B1B' }}>
                  BCS crítico o peso fuera de rango Jersey
                </p>
              </div>
              <button
                onClick={() => setMostrarAlertas(false)}
                className="p-2 rounded-full hover:bg-white transition-colors"
                style={{ color: C.danger }}
                aria-label="Cerrar alertas"
              >
                <X size={20} />
              </button>
            </div>

            {/* Cuerpo modal */}
            <div className="overflow-y-auto bg-[#F9FDFB]" style={{ maxHeight: '60vh' }}>
              {alertas.length === 0 ? (
                <div className="p-12 text-center">
                  <div className="w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-2xl">🌿</span>
                  </div>
                  <h3 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.2rem', fontWeight: 800 }}>
                    Todo en orden
                  </h3>
                  <p className="font-mono text-xs mt-2" style={{ color: C.textSecondary }}>
                    No hay animales que requieran atención inmediata.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-red-50">
                  {alertas.map(a => (
                    <div key={a.animal_id} className="px-8 py-5 flex items-center gap-4 bg-white hover:bg-red-50/30 transition-colors">
                      <div className="w-12 h-12 rounded-2xl flex items-center justify-center font-mono text-sm font-bold shadow-sm" style={{ background: '#FEF2F2', color: C.danger }}>
                        {a.arete?.slice(-3)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-sans text-base font-bold" style={{ color: C.primary }}>
                          {a.nombre || `Vaca ${a.arete}`}{' '}
                          <span className="text-sm font-normal text-gray-400 ml-1">en {a.hato_nombre}</span>
                        </div>
                        <div className="font-mono text-[11px] uppercase font-bold mt-1" style={{ color: C.danger }}>
                          {a.motivo}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        {a.ultimo_bcs != null && (
                          <span className="font-mono text-sm px-3 py-1 rounded-lg font-bold border border-red-200" style={{ background: '#FEF2F2', color: C.danger }}>
                            BCS {a.ultimo_bcs.toFixed(2)}
                          </span>
                        )}
                        {a.ultimo_peso_kg != null && (
                          <span className="font-mono text-[10px] font-bold text-gray-500">
                            {a.ultimo_peso_kg.toFixed(1)} kg
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}