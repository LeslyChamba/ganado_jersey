import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, X, ScanLine, LineChart, Info } from 'lucide-react'
import { getBCSColor, formatPeso } from '../services/helpers'

// ── DEFINICIÓN DE C Y F QUE FALTABAN EN ESTE ARCHIVO ──
const C = {
  primary: '#081C11', 
  accent: '#52D9A0', 
  accentDark: '#1B4332',
  textSecondary: '#2A5C3A', 
  bg: '#F0FBF6', 
  white: '#FFFFFF',
  danger: '#EF4444', 
  warning: '#F5C542',
  success: '#10B981',
  text: '#081C11',
  textMuted: '#6B7280',
  surfaceAlt: '#F9FDFB',
  border: 'rgba(8, 28, 17, 0.08)',
  overlay: 'rgba(8, 28, 17, 0.4)',
  tintDanger: '#FEF2F2',
  tintWarning: '#FFFBEB',
  tintPrimary: '#E8F8F1',
  warningBorder: '#FDE68A',
  warningText: '#92400E',
}

const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body: "Arial, Helvetica, sans-serif",
}

// Condición corporal = urgente (rojo). Solo peso = verificar (ámbar).
function clasificar(a) {
  const bcs = a.ultimo_bcs
  if (bcs != null && bcs < 2.5)
    return { nivel: 0, grupo: 'bcs', etiqueta: 'Condición baja', color: C.danger, tint: C.tintDanger }
  if (bcs != null && bcs >= 4.5)
    return { nivel: 0, grupo: 'bcs', etiqueta: 'Obesidad', color: C.danger, tint: C.tintDanger }
  return { nivel: 1, grupo: 'peso', etiqueta: 'Verificar peso', color: C.warning, tint: C.tintWarning }
}

export default function AlertasModal({ alertas, onClose }) {
  const navigate = useNavigate()
  const [filtro, setFiltro] = useState('todas')

  const items = useMemo(
    () => alertas.map(a => ({ ...a, ...clasificar(a) })).sort((x, y) => x.nivel - y.nivel),
    [alertas]
  )

  const nBcs  = items.filter(i => i.grupo === 'bcs').length
  const nPeso = items.filter(i => i.grupo === 'peso').length
  const visibles = filtro === 'todas' ? items : items.filter(i => i.grupo === filtro)

  const tabs = [
    { id: 'todas', label: 'Todas',    n: items.length },
    { id: 'bcs',   label: 'Condición', n: nBcs },
    { id: 'peso',  label: 'Peso',      n: nPeso },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-md animate-in fade-in"
      style={{ background: C.overlay }}
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-full max-w-xl bg-white rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95">

        {/* Cabecera */}
        <div className="px-8 pt-6 pb-4" style={{ background: C.surfaceAlt, borderBottom: `1px solid ${C.border}` }}>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="flex items-center gap-2" style={{ fontFamily: F.brand, fontWeight: 800, fontSize: '1.4rem', color: C.text }}>
                <AlertTriangle size={22} style={{ color: items.length ? C.warning : C.success }} />
                Alertas del hato
              </h2>
              <p className="font-mono text-[10px] font-bold uppercase tracking-widest mt-1" style={{ color: C.textSecondary }}>
                {nBcs} por condición corporal · {nPeso} por verificar peso
              </p>
            </div>
            <button onClick={onClose} aria-label="Cerrar alertas"
              className="p-2 rounded-full hover:bg-surface-muted transition-colors" style={{ color: C.textSecondary }}>
              <X size={20} />
            </button>
          </div>

          {/* Pestañas */}
          <div className="flex gap-2 mt-4">
            {tabs.map(t => {
              const activo = filtro === t.id
              return (
                <button key={t.id} onClick={() => setFiltro(t.id)}
                  className="px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest transition-all"
                  style={{
                    background: activo ? C.primary : C.white,
                    color: activo ? C.white : C.textSecondary,
                    border: `1px solid ${activo ? C.primary : C.border}`,
                  }}>
                  {t.label} ({t.n})
                </button>
              )
            })}
          </div>
        </div>

        {/* Lista */}
        <div className="overflow-y-auto" style={{ maxHeight: '52vh', background: C.surfaceAlt }}>
          {visibles.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: C.tintPrimary }}>
                <span className="text-2xl">🌿</span>
              </div>
              <h3 style={{ fontFamily: F.brand, color: C.text, fontSize: '1.2rem', fontWeight: 800 }}>Todo en orden</h3>
              <p className="font-mono text-xs mt-2" style={{ color: C.textSecondary }}>
                No hay animales que requieran atención.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {visibles.map(a => {
                const bc = a.ultimo_bcs != null ? getBCSColor(a.ultimo_bcs) : null
                return (
                  <div key={a.animal_id} className="px-8 py-5 bg-white">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl flex items-center justify-center font-mono text-sm font-bold flex-shrink-0"
                        style={{ background: a.tint, color: a.color }}>
                        {a.arete?.slice(-3)}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="font-sans text-base font-bold truncate" style={{ color: C.text }}>
                          {a.nombre || `Vaca ${a.arete}`}
                          <span className="text-sm font-normal ml-2" style={{ color: C.textMuted }}>en {a.hato_nombre}</span>
                        </div>
                        <span className="inline-block mt-1 px-2 py-0.5 rounded-md font-mono text-[10px] font-bold uppercase tracking-wider"
                          style={{ background: a.tint, color: a.color }}>
                          {a.etiqueta}
                        </span>
                        <div className="font-sans text-xs mt-1" style={{ color: C.textSecondary }}>{a.motivo}</div>
                      </div>

                      <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                        <div className="font-mono text-lg font-extrabold" style={{ color: C.text }}>
                          {a.ultimo_peso_kg != null ? formatPeso(a.ultimo_peso_kg) : '—'}
                        </div>
                        {bc && (
                          <span className="font-mono text-[10px] px-2.5 py-1 rounded-lg font-bold"
                            style={{ background: bc.bg, color: bc.text }}>
                            BCS {a.ultimo_bcs.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Acciones */}
                    <div className="flex gap-2 mt-3 ml-16">
                      <button onClick={() => { onClose(); navigate('/analisis') }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest"
                        style={{ background: C.primary, color: C.white }}>
                        <ScanLine size={12} /> Re-medir
                      </button>
                      <button onClick={() => { onClose(); navigate('/vacas') }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest"
                        style={{ color: C.textSecondary, border: `1px solid ${C.border}` }}>
                        <LineChart size={12} /> Ver vacas
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Nota */}
        {nPeso > 0 && (
          <div className="flex items-start gap-2 px-8 py-4" style={{ background: C.tintWarning, borderTop: `1px solid ${C.warningBorder}` }}>
            <Info size={14} style={{ color: C.warningText, flexShrink: 0, marginTop: 2 }} />
            <span className="font-sans text-xs leading-relaxed" style={{ color: C.warningText }}>
              Un peso fuera de rango puede ser un error de estimación. Repite la foto lateral o
              compáralo con báscula o cinta antes de tomar decisiones.
            </span>
          </div>
        )}
      </div>
    </div>
  )
}