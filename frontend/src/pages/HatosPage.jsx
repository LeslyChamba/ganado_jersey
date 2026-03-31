import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { hatosApi } from '../services/api'
import { formatFecha } from '../services/helpers'
import toast from 'react-hot-toast'
import { Plus, FolderOpen, MapPin, Loader2, X, Trash2 } from 'lucide-react'

export default function HatosPage() {
  const qc = useQueryClient()
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ nombre: '', finca: '', ubicacion: '', descripcion: '' })

  const { data: hatos = [], isLoading } = useQuery({
    queryKey: ['hatos'],
    queryFn: () => hatosApi.listar().then(r => r.data),
  })

  const crear = useMutation({
    mutationFn: hatosApi.crear,
    onSuccess: () => {
      qc.invalidateQueries(['hatos'])
      toast.success('Hato creado')
      setModal(false)
      setForm({ nombre: '', finca: '', ubicacion: '', descripcion: '' })
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error'),
  })

  const eliminar = useMutation({
    mutationFn: hatosApi.eliminar,
    onSuccess: () => { qc.invalidateQueries(['hatos']); toast.success('Eliminado') },
  })

  return (
    <div className="animate-fade-in space-y-6 relative z-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.75rem', fontWeight: 900 }}>
            Hatos
          </h1>
          <p className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
            GESTIÓN DE HATOS
          </p>
        </div>
        <button onClick={() => setModal(true)} className="btn-primary">
          <Plus size={14} /> Nuevo hato
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="animate-spin" size={26} style={{ color: '#89B99A' }} />
        </div>
      ) : hatos.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-4xl mb-3">🏡</div>
          <p style={{ fontFamily: 'Syne, sans-serif', color: '#B0A090', fontSize: '1.1rem', fontWeight: 700 }}>
            Sin hatos registrados
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {hatos.map((h, i) => (
            <div key={h.id} className="card p-5 animate-slide-up transition-all"
                 style={{ animationDelay: `${i * 60}ms` }}
                 onMouseOver={e => e.currentTarget.style.borderColor = '#89B99A'}
                 onMouseOut={e  => e.currentTarget.style.borderColor = '#E0D8C8'}>
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                     style={{ background: '#D4ECD9' }}>
                  <FolderOpen size={18} style={{ color: '#5C8B6A' }} />
                </div>
                <button
                  onClick={() => { if (confirm('¿Eliminar?')) eliminar.mutate(h.id) }}
                  style={{ color: '#C8BBA8' }}
                  onMouseOver={e => e.currentTarget.style.color = '#C0392B'}
                  onMouseOut={e  => e.currentTarget.style.color = '#C8BBA8'}>
                  <Trash2 size={14} />
                </button>
              </div>
              <h3 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.1rem', fontWeight: 700 }}>
                {h.nombre}
              </h3>
              <p className="font-mono text-xs mt-0.5" style={{ color: '#8B7D6B' }}>{h.finca}</p>
              {h.ubicacion && (
                <div className="flex items-center gap-1.5 mt-2 font-mono text-xs" style={{ color: '#B0A090' }}>
                  <MapPin size={11} /> {h.ubicacion}
                </div>
              )}
              <div className="mt-4 pt-4 flex items-center justify-between"
                   style={{ borderTop: '0.5px solid #E8E0D0' }}>
                <div className="font-mono text-xs" style={{ color: '#8B7D6B' }}>
                  <span style={{ color: '#5C8B6A', fontWeight: 600 }}>{h.total_animales || 0}</span> vacas
                </div>
                <div className="font-mono text-xs" style={{ color: '#B0A090' }}>{formatFecha(h.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
             style={{ background: 'rgba(26,26,26,0.45)', backdropFilter: 'blur(6px)' }}>
          <div className="w-full max-w-md animate-slide-up"
               style={{ background: '#FFFFFF', border: '0.5px solid #D0C5B0', borderRadius: 20, boxShadow: '0 8px 40px rgba(46,77,56,0.12)' }}>
            <div className="flex items-center justify-between px-6 py-4"
                 style={{ borderBottom: '0.5px solid #E8E0D0' }}>
              <h2 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.2rem', fontWeight: 700 }}>
                Nuevo hato
              </h2>
              <button onClick={() => setModal(false)} style={{ color: '#B0A090' }}><X size={20} /></button>
            </div>
            <form onSubmit={e => { e.preventDefault(); crear.mutate(form) }} className="p-6 space-y-4">
              {[
                ['nombre',    'Nombre del hato *',  'Hato Principal',     true],
                ['finca',     'Nombre de la finca *','Finca El Paraíso',  true],
                ['ubicacion', 'Ubicación',           'Riobamba, Ecuador', false],
              ].map(([k, l, p, req]) => (
                <div key={k}>
                  <label className="label">{l}</label>
                  <input className="input" placeholder={p} required={req}
                    value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} />
                </div>
              ))}
              <div>
                <label className="label">Descripción</label>
                <textarea className="input resize-none" rows={2}
                  value={form.descripcion}
                  onChange={e => setForm({ ...form, descripcion: e.target.value })} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setModal(false)} className="btn-secondary flex-1 justify-center">
                  Cancelar
                </button>
                <button type="submit" disabled={crear.isPending} className="btn-primary flex-1 justify-center">
                  {crear.isPending && <Loader2 size={13} className="animate-spin" />} Crear hato
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}