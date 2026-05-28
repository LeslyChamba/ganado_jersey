import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { hatosApi } from '../services/api'
import { formatFecha } from '../services/helpers'
import toast from 'react-hot-toast'
import { Plus, MapPin, Loader2, X, Trash2, Edit2, Home } from 'lucide-react'

const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444'
}
/* ── Tokens de tipografía ── */
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

export default function HatosPage() {
  const qc = useQueryClient()
  const [modal, setModal] = useState(false)
  
  // NUEVO: Estado para saber si estamos editando
  const [editando, setEditando] = useState(false) 
  const [form, setForm] = useState({ id: null, nombre: '', finca: '', ubicacion: '', descripcion: '' })

  const { data: hatos = [], isLoading } = useQuery({
    queryKey: ['hatos'],
    queryFn: () => hatosApi.listar().then(r => r.data),
  })

  // MUTACIONES
  const crear = useMutation({
    mutationFn: hatosApi.crear,
    onSuccess: () => {
      qc.invalidateQueries(['hatos'])
      toast.success('Hato creado exitosamente')
      cerrarModal()
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al crear'),
  })

  const actualizar = useMutation({
    // Asume que tu API recibe (id, datos_a_actualizar)
    mutationFn: (datos) => hatosApi.actualizar(datos.id, datos), 
    onSuccess: () => {
      qc.invalidateQueries(['hatos'])
      toast.success('Hato actualizado correctamente')
      cerrarModal()
    },
    onError: (e) => toast.error(e.response?.data?.detail || 'Error al actualizar'),
  })

  const eliminar = useMutation({
    mutationFn: hatosApi.eliminar,
    onSuccess: () => { qc.invalidateQueries(['hatos']); toast.success('Hato eliminado') },
  })

  // MANEJO DEL MODAL
  const abrirModalCrear = () => {
    setForm({ id: null, nombre: '', finca: '', ubicacion: '', descripcion: '' })
    setEditando(false)
    setModal(true)
  }

  const abrirModalEditar = (hato) => {
    setForm({
      id: hato.id,
      nombre: hato.nombre,
      finca: hato.finca,
      ubicacion: hato.ubicacion || '',
      descripcion: hato.descripcion || ''
    })
    setEditando(true)
    setModal(true)
  }

  const cerrarModal = () => {
    setModal(false)
    // Limpiamos el formulario con un ligero retraso para que la animación de cierre se vea fluida
    setTimeout(() => setForm({ id: null, nombre: '', finca: '', ubicacion: '', descripcion: '' }), 200)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (editando) {
      actualizar.mutate(form)
    } else {
      crear.mutate(form)
    }
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-6 relative z-10">
      
      {/* HEADER */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: F.brand, color: C.primary, fontSize: '2rem', fontWeight: 800 }}>
            Hatos y Propiedades
          </h1>
          <p className="font-mono text-xs mt-1 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
            Gestión de ubicaciones de estimación
          </p>
        </div>
        <button 
          onClick={abrirModalCrear} 
          className="flex items-center gap-2 px-5 py-3 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.1em] text-white transition-all hover:scale-105 active:scale-95 shadow-lg"
          style={{ background: C.primary }}
        >
          <Plus size={16} color={C.accent} /> Nuevo Hato
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="animate-spin" size={32} style={{ color: C.accentDark }} />
        </div>
      ) : hatos.length === 0 ? (
        <div className="w-full bg-white rounded-[2rem] border-2 border-dashed flex flex-col items-center justify-center p-16 text-center shadow-sm" style={{ borderColor: 'rgba(82, 217, 160, 0.3)' }}>
          <div className="w-20 h-20 bg-[#E8F8F1] rounded-full flex items-center justify-center mb-4">
            <Home size={32} style={{ color: C.accentDark }} />
          </div>
          <h2 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.5rem', fontWeight: 800 }}>
            Ningún hato registrado
          </h2>
          <p className="mt-2 text-sm max-w-md" style={{ color: C.textSecondary }}>
            Comienza agregando las propiedades o divisiones de la finca.
          </p>
          <button 
            onClick={abrirModalCrear} 
            className="mt-6 font-mono text-xs font-bold uppercase tracking-widest px-6 py-3 rounded-lg text-white"
            style={{ background: C.accentDark }}
          >
            Crear mi primer hato
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {hatos.map((h, i) => (
            <div 
              key={h.id} 
              className="bg-white rounded-[1.5rem] p-6 transition-all duration-300 hover:-translate-y-1 relative group overflow-hidden flex flex-col"
              style={{ boxShadow: '0 10px 30px rgba(8, 28, 17, 0.04)', border: '1px solid rgba(82, 217, 160, 0.15)', animationDelay: `${i * 75}ms` }}
            >
              <div className="absolute top-0 left-0 w-full h-1" style={{ background: `linear-gradient(90deg, ${C.accent}, ${C.accentDark})` }} />

              <div className="flex items-start justify-between mb-4 mt-2">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center shadow-inner" style={{ background: '#E8F8F1' }}>
                  <Home size={22} style={{ color: C.accentDark }} />
                </div>
                
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {/* BOTÓN EDITAR CON FUNCIONALIDAD */}
                  <button 
                    onClick={() => abrirModalEditar(h)} 
                    className="p-2 rounded-lg hover:bg-gray-100 transition-colors" 
                    style={{ color: C.textSecondary }} title="Editar"
                  >
                    <Edit2 size={16} />
                  </button>

                  <button 
                    onClick={() => { if (confirm(`¿Seguro que deseas eliminar ${h.nombre}?`)) eliminar.mutate(h.id) }} 
                    className="p-2 rounded-lg hover:bg-red-50 transition-colors" 
                    style={{ color: C.danger }} title="Eliminar"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div className="flex-1">
                <h3 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.4rem', fontWeight: 800, lineHeight: 1.2 }}>
                  {h.nombre}
                </h3>
                <p className="font-mono text-xs mt-1.5 font-bold uppercase tracking-wider" style={{ color: C.accentDark }}>
                  {h.finca}
                </p>
                {h.ubicacion && (
                  <div className="flex items-start gap-1.5 mt-3 text-sm font-medium" style={{ color: C.textSecondary }}>
                    <MapPin size={16} className="mt-0.5 flex-shrink-0" style={{ color: C.accent }} /> 
                    <span className="leading-tight">{h.ubicacion}</span>
                  </div>
                )}
              </div>

              <div className="mt-6 pt-4 flex items-center justify-between" style={{ borderTop: '1px solid rgba(8, 28, 17, 0.05)' }}>
                <div className="flex flex-col">
                  <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-gray-400">Total Bovinos</span>
                  <div className="font-mono text-lg font-bold" style={{ color: C.primary }}>{h.total_animales || 0}</div>
                </div>
                <div className="flex flex-col text-right">
                  <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-gray-400">Registro</span>
                  <div className="font-mono text-xs font-medium" style={{ color: C.textSecondary }}>{formatFecha(h.created_at)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* MODAL */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in"
             style={{ background: 'rgba(8, 28, 17, 0.6)', backdropFilter: 'blur(8px)' }}>
          <div className="w-full max-w-lg bg-white rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            
            <div className="px-8 py-6 flex items-center justify-between" style={{ background: '#F9FDFB', borderBottom: '1px solid rgba(82, 217, 160, 0.2)' }}>
              <div>
                <h2 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.5rem', fontWeight: 800 }}>
                  {editando ? 'Editar Hato' : 'Registrar Hato'}
                </h2>
                <p className="font-mono text-[10px] font-bold uppercase tracking-widest mt-1" style={{ color: C.textSecondary }}>
                  {editando ? 'ACTUALIZAR DATOS' : 'NUEVA PROPIEDAD'}
                </p>
              </div>
              <button onClick={cerrarModal} className="p-2 rounded-full hover:bg-gray-200 transition-colors" style={{ color: C.primary }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-8 space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {[
                  ['nombre',    'Nombre del hato *',  'Ej. Hato Norte', true],
                  ['finca',     'Nombre de la finca *','Ej. El Puente', true],
                ].map(([k, l, p, req]) => (
                  <div key={k}>
                    <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>{l}</label>
                    <input 
                      required={req}
                      placeholder={p}
                      className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all"
                      style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }}
                      value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} 
                    />
                  </div>
                ))}
              </div>

              <div>
                <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Ubicación exacta</label>
                <input 
                  placeholder="Ej. Sector La Providencia, Riobamba"
                  className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all"
                  style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }}
                  value={form.ubicacion} onChange={e => setForm({ ...form, ubicacion: e.target.value })} 
                />
              </div>

              <div>
                <label className="block font-mono text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: C.textSecondary }}>Descripción (Opcional)</label>
                <textarea 
                  rows={2}
                  className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all resize-none"
                  style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }}
                  value={form.descripcion} onChange={e => setForm({ ...form, descripcion: e.target.value })} 
                />
              </div>

              <div className="flex gap-4 pt-4">
                <button type="button" onClick={cerrarModal} className="flex-1 py-3.5 rounded-xl font-mono text-sm font-bold uppercase tracking-widest transition-colors hover:bg-gray-100" style={{ color: C.primary, border: '1px solid #E5E7EB' }}>
                  Cancelar
                </button>
                <button type="submit" disabled={crear.isPending || actualizar.isPending} className="flex-1 py-3.5 rounded-xl font-mono text-sm font-bold uppercase tracking-widest text-white transition-all flex items-center justify-center gap-2 shadow-md hover:shadow-lg disabled:opacity-70" style={{ background: C.primary }}>
                  {(crear.isPending || actualizar.isPending) && <Loader2 size={16} className="animate-spin" />} 
                  {editando ? 'Guardar Cambios' : 'Crear Hato'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}