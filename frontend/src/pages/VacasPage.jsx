import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { animalesApi, hatosApi } from '../services/api'
import { getBCSColor, getBCSLabel, formatPeso, formatFechaHora } from '../services/helpers'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import toast from 'react-hot-toast'
import { Plus, Search, Loader2, X, History, Trash2 } from 'lucide-react'

export default function VacasPage() {
  const qc = useQueryClient()
  const [buscar, setBuscar] = useState('')
  const [modal, setModal] = useState(false)
  const [historialVaca, setHistorialVaca] = useState(null)
  const [form, setForm] = useState({ arete: '', nombre: '', raza: 'Jersey', proposito: 'leche', notas: '', hato_id: '' })

  const { data: hatos = [] } = useQuery({ queryKey: ['hatos'], queryFn: () => hatosApi.listar().then(r => r.data) })
  const { data: animales = [], isLoading } = useQuery({
    queryKey: ['animales', buscar],
    queryFn: () => animalesApi.listar(buscar ? { buscar } : {}).then(r => r.data),
  })
  const { data: mediciones = [] } = useQuery({
    queryKey: ['mediciones', historialVaca?.id],
    queryFn: () => animalesApi.mediciones(historialVaca.id).then(r => r.data),
    enabled: !!historialVaca,
  })

  const crear = useMutation({
    mutationFn: animalesApi.crear,
    onSuccess: () => {
      qc.invalidateQueries(['animales'])
      toast.success('Vaca registrada')
      setModal(false)
      setForm({ arete: '', nombre: '', raza: 'Jersey', proposito: 'leche', notas: '', hato_id: '' })
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  })

  const eliminar = useMutation({
    mutationFn: animalesApi.eliminar,
    onSuccess: () => { qc.invalidateQueries(['animales']); toast.success('Eliminada') },
  })

  const chartData = [...mediciones].reverse().map(m => ({
    fecha: new Date(m.fecha_medicion).toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }),
    peso: m.peso_estimado_kg,
    bcs: m.bcs,
  }))

  return (
    <div className="animate-fade-in space-y-6 relative z-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.75rem', fontWeight: 900 }}>
            Vacas Jersey
          </h1>
          <p className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
            <span style={{ color: '#5C8B6A', fontWeight: 600 }}>{animales.length}</span> VACAS REGISTRADAS
          </p>
        </div>
        <button onClick={() => setModal(true)} className="btn-primary">
          <Plus size={14} /> Nueva vaca
        </button>
      </div>

      {/* Búsqueda */}
      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: '#B0A090' }} />
        <input className="input pl-9" placeholder="Buscar por arete o nombre…"
          value={buscar} onChange={e => setBuscar(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin" size={26} style={{ color: '#89B99A' }} />
        </div>
      ) : animales.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-4xl mb-3">🐄</div>
          <p style={{ fontFamily: 'Syne, sans-serif', color: '#B0A090', fontSize: '1.1rem', fontWeight: 700 }}>
            Sin vacas registradas
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr style={{ background: '#FAFAF7', borderBottom: '0.5px solid #E8E0D0' }}>
                  {['Arete', 'Nombre', 'Último peso', 'BCS', 'Mediciones', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-mono text-xs uppercase tracking-widest"
                        style={{ color: '#B0A090' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {animales.map((a) => {
                  const bc = a.ultimo_bcs ? getBCSColor(a.ultimo_bcs) : null
                  return (
                    <tr key={a.id} className="transition-colors"
                        style={{ borderBottom: '0.5px solid #F0EBE0' }}
                        onMouseOver={e => e.currentTarget.style.background = '#FAFAF7'}
                        onMouseOut={e  => e.currentTarget.style.background = 'transparent'}>
                      <td className="px-4 py-3 font-mono text-sm" style={{ color: '#5C8B6A', fontWeight: 600 }}>
                        {a.arete}
                      </td>
                      <td className="px-4 py-3 font-mono text-sm" style={{ color: '#1A1A1A' }}>
                        {a.nombre || '—'}
                      </td>
                      <td className="px-4 py-3 font-mono text-sm" style={{ color: '#2E4D38', fontWeight: 600 }}>
                        {a.ultimo_peso_kg ? formatPeso(a.ultimo_peso_kg) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        {bc ? (
                          <span className="font-mono text-xs px-2.5 py-1 rounded-lg"
                                style={{ background: bc.bg, color: bc.text }}>
                            {a.ultimo_bcs?.toFixed(1)} · {getBCSLabel(a.ultimo_bcs)}
                          </span>
                        ) : <span style={{ color: '#C8BBA8' }}>—</span>}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs" style={{ color: '#B0A090' }}>
                        {a.total_mediciones}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 justify-end">
                          <button onClick={() => setHistorialVaca(a)}
                            className="p-1.5 rounded-lg transition-colors"
                            style={{ color: '#B0A090' }}
                            onMouseOver={e => { e.currentTarget.style.background = '#D4ECD9'; e.currentTarget.style.color = '#5C8B6A' }}
                            onMouseOut={e  => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#B0A090' }}>
                            <History size={14} />
                          </button>
                          <button onClick={() => { if (confirm('¿Eliminar?')) eliminar.mutate(a.id) }}
                            className="p-1.5 rounded-lg transition-colors"
                            style={{ color: '#B0A090' }}
                            onMouseOver={e => { e.currentTarget.style.background = '#FDECEA'; e.currentTarget.style.color = '#C0392B' }}
                            onMouseOut={e  => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#B0A090' }}>
                            <Trash2 size={14} />
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

      {/* Modal nueva vaca */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
             style={{ background: 'rgba(26,26,26,0.45)', backdropFilter: 'blur(6px)' }}>
          <div className="w-full max-w-md animate-slide-up"
               style={{ background: '#FFFFFF', border: '0.5px solid #D0C5B0', borderRadius: 20, boxShadow: '0 8px 40px rgba(46,77,56,0.12)' }}>
            <div className="flex items-center justify-between px-6 py-4"
                 style={{ borderBottom: '0.5px solid #E8E0D0' }}>
              <h2 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.2rem', fontWeight: 700 }}>
                Nueva vaca Jersey
              </h2>
              <button onClick={() => setModal(false)} style={{ color: '#B0A090' }}><X size={20} /></button>
            </div>
            <form onSubmit={e => { e.preventDefault(); if (!form.hato_id) return toast.error('Selecciona un hato'); crear.mutate(form) }}
                  className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Arete *</label>
                  <input className="input" placeholder="EC-001" required value={form.arete}
                    onChange={e => setForm({ ...form, arete: e.target.value })} />
                </div>
                <div>
                  <label className="label">Nombre</label>
                  <input className="input" placeholder="Opcional" value={form.nombre}
                    onChange={e => setForm({ ...form, nombre: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Raza</label>
                  <input className="input" value={form.raza}
                    onChange={e => setForm({ ...form, raza: e.target.value })} />
                </div>
                <div>
                  <label className="label">Propósito</label>
                  <select className="input" value={form.proposito}
                    onChange={e => setForm({ ...form, proposito: e.target.value })}>
                    <option value="leche">Leche</option>
                    <option value="carne">Carne</option>
                    <option value="doble_proposito">Doble propósito</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="label">Hato *</label>
                <select className="input" value={form.hato_id} required
                  onChange={e => setForm({ ...form, hato_id: e.target.value })}>
                  <option value="">— Selecciona un hato</option>
                  {hatos.map(h => <option key={h.id} value={h.id}>{h.nombre} — {h.finca}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Notas</label>
                <textarea className="input resize-none" rows={2} value={form.notas}
                  onChange={e => setForm({ ...form, notas: e.target.value })} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)} className="btn-secondary flex-1 justify-center">
                  Cancelar
                </button>
                <button type="submit" disabled={crear.isPending} className="btn-primary flex-1 justify-center">
                  {crear.isPending && <Loader2 size={13} className="animate-spin" />} Registrar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal historial */}
      {historialVaca && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
             style={{ background: 'rgba(26,26,26,0.45)', backdropFilter: 'blur(6px)' }}>
          <div className="w-full max-w-2xl animate-slide-up max-h-[90vh] flex flex-col"
               style={{ background: '#FFFFFF', border: '0.5px solid #D0C5B0', borderRadius: 20, boxShadow: '0 8px 40px rgba(46,77,56,0.12)' }}>
            <div className="flex items-center justify-between px-6 py-4"
                 style={{ borderBottom: '0.5px solid #E8E0D0' }}>
              <div>
                <h2 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.2rem', fontWeight: 700 }}>
                  {historialVaca.nombre || historialVaca.arete}
                </h2>
                <p className="font-mono text-xs" style={{ color: '#8B7D6B' }}>Arete: {historialVaca.arete}</p>
              </div>
              <button onClick={() => setHistorialVaca(null)} style={{ color: '#B0A090' }}><X size={20} /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {chartData.length > 1 && (
                <div>
                  <div className="panel-title">Evolución del peso</div>
                  <ResponsiveContainer width="100%" height={150}>
                    <LineChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(208,197,176,0.5)" />
                      <XAxis dataKey="fecha" tick={{ fontSize: 10, fill: '#B0A090', fontFamily: 'JetBrains Mono' }} />
                      <YAxis tick={{ fontSize: 10, fill: '#B0A090', fontFamily: 'JetBrains Mono' }} />
                      <Tooltip
                        contentStyle={{
                          background: '#FFFFFF', border: '0.5px solid #D0C5B0',
                          borderRadius: 10, fontSize: 13, fontFamily: 'JetBrains Mono', color: '#1A1A1A',
                        }}
                        formatter={v => [`${v} kg`, 'Peso']}
                      />
                      <Line type="monotone" dataKey="peso" stroke="#5C8B6A" strokeWidth={2}
                        dot={{ r: 3, fill: '#5C8B6A', stroke: '#FFFFFF', strokeWidth: 2 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div>
                <div className="panel-title">Registros</div>
                {mediciones.length === 0 ? (
                  <p className="font-mono text-xs text-center py-6" style={{ color: '#B0A090' }}>
                    Sin mediciones aún
                  </p>
                ) : (
                  <div className="space-y-2">
                    {mediciones.map(m => {
                      const bc = getBCSColor(m.bcs)
                      return (
                        <div key={m.id} className="flex items-center gap-4 p-3 rounded-xl"
                             style={{ background: '#FAFAF7', border: '0.5px solid #E8E0D0' }}>
                          <div className="font-mono text-xs w-28 flex-shrink-0" style={{ color: '#B0A090' }}>
                            {formatFechaHora(m.fecha_medicion)}
                          </div>
                          <div className="font-mono text-sm w-24 flex-shrink-0 font-semibold" style={{ color: '#5C8B6A' }}>
                            {formatPeso(m.peso_estimado_kg)}
                          </div>
                          <span className="font-mono text-xs px-2.5 py-1 rounded-lg flex-shrink-0"
                                style={{ background: bc.bg, color: bc.text }}>
                            BCS {m.bcs?.toFixed(1)}
                          </span>
                          <div className="font-mono text-xs flex-shrink-0" style={{ color: '#C8BBA8' }}>
                            {m.confianza?.toFixed(0)}% conf.
                          </div>
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
    </div>
  )
}