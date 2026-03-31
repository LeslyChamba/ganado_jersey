import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportesApi, hatosApi, animalesApi } from '../services/api'
import { formatFechaHora } from '../services/helpers'
import toast from 'react-hot-toast'
import { FileText, Trash2, Plus, X, ChevronDown, Download } from 'lucide-react'

const TIPOS    = ['individual', 'hato', 'general']
const FORMATOS = ['pdf', 'excel']

function BadgeTipo({ tipo }) {
  const colors = {
    individual: { bg: '#EAF4EE', text: '#2E4D38' },
    hato:       { bg: '#F5E6CC', text: '#7A4A10' },
    general:    { bg: '#E8EEF5', text: '#1E3F6E' },
  }
  const c = colors[tipo] || colors.general
  return (
    <span className="font-mono text-xs px-2 py-0.5 rounded-lg capitalize"
      style={{ background: c.bg, color: c.text }}>{tipo}</span>
  )
}

function ModalNuevoReporte({ onClose, hatos, animales }) {
  const qc = useQueryClient()
  const [titulo,     setTitulo]     = useState('')
  const [tipo,       setTipo]       = useState('individual')
  const [formato,    setFormato]    = useState('pdf')
  const [hatoId,     setHatoId]     = useState('')
  const [animalId,   setAnimalId]   = useState('')
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')

  const crear = useMutation({
    mutationFn: () => reportesApi.crear({
      titulo:      titulo || `Reporte ${tipo} — ${new Date().toLocaleDateString('es-EC')}`,
      tipo,
      formato,
      hato_id:     hatoId     || null,
      animal_id:   animalId   || null,
      fecha_desde: fechaDesde || null,
      fecha_hasta: fechaHasta || null,
    }),
    onSuccess: () => { qc.invalidateQueries(['reportes']); toast.success('Reporte generado'); onClose() },
    onError:   (e) => toast.error(e.response?.data?.detail || 'Error al generar reporte'),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: 'rgba(26,26,26,0.45)', backdropFilter: 'blur(6px)' }}>
      <div className="w-full max-w-md animate-slide-up"
           style={{ background: '#FFFFFF', border: '0.5px solid #D0C5B0', borderRadius: 20, boxShadow: '0 8px 40px rgba(46,77,56,0.12)' }}>
        <div className="flex items-center justify-between px-6 py-4"
             style={{ borderBottom: '0.5px solid #E8E0D0' }}>
          <h2 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.2rem', fontWeight: 700 }}>
            Nuevo reporte
          </h2>
          <button onClick={onClose} style={{ color: '#B0A090' }}><X size={18} /></button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="label">Título (opcional)</label>
            <input className="input" placeholder="Se genera automáticamente si se deja vacío"
              value={titulo} onChange={e => setTitulo(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Tipo</label>
              <div className="relative">
                <select className="input appearance-none pr-8" value={tipo}
                  onChange={e => { setTipo(e.target.value); setHatoId(''); setAnimalId('') }}>
                  {TIPOS.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#B0A090' }} />
              </div>
            </div>
            <div>
              <label className="label">Formato</label>
              <div className="relative">
                <select className="input appearance-none pr-8" value={formato}
                  onChange={e => setFormato(e.target.value)}>
                  {FORMATOS.map(f => <option key={f} value={f}>{f.toUpperCase()}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#B0A090' }} />
              </div>
            </div>
          </div>

          {(tipo === 'hato' || tipo === 'individual') && (
            <div>
              <label className="label">Hato {tipo === 'hato' ? '*' : '(opcional)'}</label>
              <div className="relative">
                <select className="input appearance-none pr-8" value={hatoId}
                  onChange={e => { setHatoId(e.target.value); setAnimalId('') }}>
                  <option value="">— Todos los hatos</option>
                  {hatos.map(h => <option key={h.id} value={h.id}>{h.nombre} · {h.finca}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#B0A090' }} />
              </div>
            </div>
          )}

          {tipo === 'individual' && (
            <div>
              <label className="label">Vaca (opcional)</label>
              <div className="relative">
                <select className="input appearance-none pr-8" value={animalId}
                  onChange={e => setAnimalId(e.target.value)}>
                  <option value="">— Todas las vacas</option>
                  {animales
                    .filter(a => !hatoId || a.hato_id === hatoId)
                    .map(a => <option key={a.id} value={a.id}>{a.arete}{a.nombre ? ` — ${a.nombre}` : ''}</option>)}
                </select>
                <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#B0A090' }} />
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Desde (opcional)</label>
              <input type="date" className="input" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} />
            </div>
            <div>
              <label className="label">Hasta (opcional)</label>
              <input type="date" className="input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} />
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">
              Cancelar
            </button>
            <button type="button" onClick={() => crear.mutate()} disabled={crear.isPending}
              className="btn-primary flex-1 justify-center">
              {crear.isPending
                ? <div className="w-4 h-4 border-2 rounded-full animate-spin"
                       style={{ borderColor: 'white', borderTopColor: 'transparent' }} />
                : <><FileText size={14} /> Generar</>
              }
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ReportesPage() {
  const qc = useQueryClient()
  const [modalAbierto, setModalAbierto] = useState(false)

  const { data: reportes = [], isLoading } = useQuery({
    queryKey: ['reportes'],
    queryFn: () => reportesApi.listar().then(r => r.data),
  })
  const { data: hatos    = [] } = useQuery({ queryKey: ['hatos'],    queryFn: () => hatosApi.listar().then(r => r.data)    })
  const { data: animales = [] } = useQuery({ queryKey: ['animales'], queryFn: () => animalesApi.listar().then(r => r.data) })

  const eliminar = useMutation({
    mutationFn: (id) => reportesApi.eliminar(id),
    onSuccess: () => { qc.invalidateQueries(['reportes']); toast.success('Reporte eliminado') },
    onError:   () => toast.error('No se pudo eliminar'),
  })

  return (
    <div className="animate-fade-in max-w-3xl mx-auto space-y-6 relative z-10">
      <div className="flex items-start justify-between">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.75rem', fontWeight: 900 }}>
            Reportes
          </h1>
          <p className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
            {reportes.length} REPORTE{reportes.length !== 1 ? 'S' : ''}
          </p>
        </div>
        <button onClick={() => setModalAbierto(true)} className="btn-primary">
          <Plus size={14} /> Nuevo reporte
        </button>
      </div>

      {isLoading ? (
        <div className="card p-8 flex items-center justify-center">
          <div className="w-5 h-5 border-2 rounded-full animate-spin"
               style={{ borderColor: '#89B99A', borderTopColor: 'transparent' }} />
        </div>
      ) : reportes.length === 0 ? (
        <div className="card p-10 flex flex-col items-center gap-3" style={{ opacity: 0.6 }}>
          <FileText size={32} style={{ color: '#89B99A' }} />
          <div className="font-mono text-xs text-center" style={{ color: '#B0A090' }}>
            No hay reportes generados.<br />Crea el primero con el botón de arriba.
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {reportes.map(r => (
            <div key={r.id} className="card p-4 flex items-center gap-4">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                   style={{ background: r.formato === 'pdf' ? '#FDECEA' : '#EAF4EE' }}>
                <FileText size={16} style={{ color: r.formato === 'pdf' ? '#C0392B' : '#5C8B6A' }} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-sm truncate" style={{ color: '#1A1A1A' }}>{r.titulo}</span>
                  <BadgeTipo tipo={r.tipo} />
                  <span className="font-mono text-xs px-2 py-0.5 rounded-lg uppercase"
                    style={{ background: '#F5F0E8', color: '#8B7D6B' }}>
                    {r.formato}
                  </span>
                </div>
                <div className="font-mono text-xs mt-0.5" style={{ color: '#B0A090' }}>
                  {formatFechaHora(r.fecha_generado)}
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {r.url_archivo && (
                  <a href={r.url_archivo} target="_blank" rel="noreferrer"
                    className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
                    style={{ background: '#F5E6CC', color: '#C8914A' }}
                    onMouseOver={e => e.currentTarget.style.background = '#EDD5A8'}
                    onMouseOut={e  => e.currentTarget.style.background = '#F5E6CC'}>
                    <Download size={14} />
                  </a>
                )}
                <button
                  onClick={() => { if (window.confirm('¿Eliminar este reporte?')) eliminar.mutate(r.id) }}
                  className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
                  style={{ background: '#FDECEA', color: '#C0392B' }}
                  onMouseOver={e => e.currentTarget.style.background = '#F9C8C5'}
                  onMouseOut={e  => e.currentTarget.style.background = '#FDECEA'}>
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalAbierto && (
        <ModalNuevoReporte
          onClose={() => setModalAbierto(false)}
          hatos={hatos}
          animales={animales}
        />
      )}
    </div>
  )
}