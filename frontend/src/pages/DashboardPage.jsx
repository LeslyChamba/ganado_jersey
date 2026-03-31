import { useQuery } from '@tanstack/react-query'
import { hatosApi, animalesApi } from '../services/api'
import { getBCSColor, getBCSLabel, formatPeso, formatFechaHora } from '../services/helpers'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Beef, Scale, TrendingUp, AlertTriangle } from 'lucide-react'

export default function DashboardPage() {
  const { data: hatos = [] } = useQuery({ queryKey: ['hatos'], queryFn: () => hatosApi.listar().then(r => r.data) })
  const primerHato = hatos[0]
  const { data: stats } = useQuery({
    queryKey: ['stats', primerHato?.id],
    queryFn: () => hatosApi.estadisticas(primerHato.id).then(r => r.data),
    enabled: !!primerHato,
  })
  const { data: animales = [] } = useQuery({ queryKey: ['animales'], queryFn: () => animalesApi.listar().then(r => r.data) })

  const recientes = animales
    .filter(a => a.ultima_medicion)
    .sort((a, b) => new Date(b.ultima_medicion) - new Date(a.ultima_medicion))
    .slice(0, 6)

  const chartData = animales.filter(a => a.ultimo_peso_kg).slice(0, 14).map(a => ({
    name: a.arete, peso: a.ultimo_peso_kg,
  }))

  const tarjetas = [
    { label: 'Total vacas',   value: stats?.total_animales ?? animales.length,                         icon: Beef,          accent: '#2E4D38', bg: '#D4ECD9' },
    { label: 'Peso promedio', value: stats?.peso_promedio_kg ? formatPeso(stats.peso_promedio_kg) : '—', icon: Scale,         accent: '#5C8B6A', bg: '#EAF4EE' },
    { label: 'BCS promedio',  value: stats?.bcs_promedio?.toFixed(1) ?? '—',                           icon: TrendingUp,    accent: '#C8914A', bg: '#F5E6CC' },
    { label: 'Bajo BCS <2.5', value: stats?.animales_bajo_bcs ?? '—',                                  icon: AlertTriangle, accent: '#C0392B', bg: '#FDECEA' },
  ]

  return (
    <div className="animate-fade-in space-y-7 relative z-10">
      <div>
        <h1 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.75rem', fontWeight: 900 }}>
          Dashboard
        </h1>
        <p className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
          {primerHato ? `${primerHato.nombre} — ${primerHato.finca}` : 'Vista general del sistema'}
        </p>
      </div>

      {/* Tarjetas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {tarjetas.map(({ label, value, icon: Icon, accent, bg }, i) => (
          <div key={label} className="card p-5 animate-slide-up" style={{ animationDelay: `${i * 80}ms` }}>
            <div className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                 style={{ background: bg }}>
              <Icon size={16} style={{ color: accent }} />
            </div>
            <div style={{ fontFamily: 'Syne, sans-serif', color: accent, fontSize: '1.75rem', fontWeight: 900, lineHeight: 1 }}>
              {value}
            </div>
            <div className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>{label}</div>
          </div>
        ))}
      </div>

      {/* Gráfica */}
      {chartData.length > 0 && (
        <div className="card p-6 animate-slide-up delay-200">
          <div className="panel-title">Peso por vaca</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#89B99A" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#89B99A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(208,197,176,0.5)" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#B0A090', fontFamily: 'JetBrains Mono' }} />
              <YAxis tick={{ fontSize: 10, fill: '#B0A090', fontFamily: 'JetBrains Mono' }} />
              <Tooltip
                contentStyle={{
                  background: '#FFFFFF',
                  border: '0.5px solid #D0C5B0',
                  borderRadius: 12,
                  fontSize: 12,
                  fontFamily: 'JetBrains Mono',
                  color: '#1A1A1A',
                  boxShadow: '0 4px 16px rgba(46,77,56,0.08)',
                }}
                formatter={v => [`${v} kg`, 'Peso']}
              />
              <Area type="monotone" dataKey="peso" stroke="#5C8B6A" strokeWidth={2} fill="url(#g1)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Últimas mediciones */}
      {recientes.length > 0 && (
        <div className="card animate-slide-up delay-300">
          <div className="px-6 py-4" style={{ borderBottom: '0.5px solid #E8E0D0' }}>
            <div className="panel-title mb-0">Últimas mediciones</div>
          </div>
          <div>
            {recientes.map((a) => {
              const bc = a.ultimo_bcs ? getBCSColor(a.ultimo_bcs) : null
              return (
                <div key={a.id}
                     className="px-6 py-3.5 flex items-center gap-4 transition-colors"
                     style={{ borderBottom: '0.5px solid #F0EBE0' }}
                     onMouseOver={e => e.currentTarget.style.background = '#FAFAF7'}
                     onMouseOut={e  => e.currentTarget.style.background = 'transparent'}>
                  <div className="w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs"
                       style={{ background: '#D4ECD9', color: '#2E4D38' }}>
                    {a.arete?.slice(-2)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-mono text-sm truncate" style={{ color: '#1A1A1A' }}>{a.nombre || a.arete}</div>
                    <div className="font-mono text-xs" style={{ color: '#B0A090' }}>{formatFechaHora(a.ultima_medicion)}</div>
                  </div>
                  <div className="font-mono text-sm font-semibold" style={{ color: '#5C8B6A' }}>
                    {formatPeso(a.ultimo_peso_kg)}
                  </div>
                  {bc && (
                    <span className="font-mono text-xs px-2.5 py-1 rounded-lg"
                          style={{ background: bc.bg, color: bc.text }}>
                      BCS {a.ultimo_bcs?.toFixed(1)}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {animales.length === 0 && (
        <div className="card p-12 text-center animate-slide-up">
          <div className="text-4xl mb-3">🐄</div>
          <p style={{ fontFamily: 'Syne, sans-serif', color: '#B0A090', fontSize: '1.1rem', fontWeight: 700 }}>
            Sin vacas registradas aún
          </p>
          <p className="font-mono text-xs mt-1" style={{ color: '#C8BBA8' }}>
            Crea un hato y registra tus vacas Jersey para comenzar
          </p>
        </div>
      )}
    </div>
  )
}