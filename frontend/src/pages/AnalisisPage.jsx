import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { animalesApi, hatosApi, analisisApi } from '../services/api'
import { getBCSColor, getBCSLabel } from '../services/helpers'
import toast from 'react-hot-toast'
import {
  Upload, Scale, CheckCircle2, RotateCcw,
  AlertTriangle, Search, UserPlus, Check, ChevronDown
} from 'lucide-react'

const STEPS = [
  'Cargando imágenes',
  'Segmentando silueta (SAM)',
  'Extrayendo keypoints',
  'Calculando morfometría',
  'Estimando masa (XGBoost)',
  'Calculando BCS (YOLOv8)',
  'Generando reporte',
]

// ─── Silueta SVG lateral ──────────────────────────────────────────────────
const SiluetaLateral = ({ ok }) => (
  <svg viewBox="0 0 320 180" className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 10 }}>
    <rect x="22" y="10" width="276" height="160" rx="6" fill="none"
      stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.2" strokeDasharray="6,3" opacity="0.7"/>
    <ellipse cx="148" cy="90" rx="95" ry="44"
      fill={ok ? 'rgba(92,139,106,0.12)' : 'rgba(137,185,154,0.10)'}
      stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.8"/>
    <ellipse cx="222" cy="74" rx="30" ry="22"
      fill={ok ? 'rgba(92,139,106,0.10)' : 'rgba(137,185,154,0.08)'}
      stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.5"/>
    <ellipse cx="256" cy="64" rx="22" ry="18"
      fill={ok ? 'rgba(92,139,106,0.10)' : 'rgba(137,185,154,0.08)'}
      stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.5"/>
    {[75, 105, 165, 195].map((px, i) => (
      <rect key={i} x={px - 7} y="130" width="14" height="38" rx="4"
        fill={ok ? 'rgba(92,139,106,0.08)' : 'rgba(137,185,154,0.06)'}
        stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.2"/>
    ))}
    <path d="M54 85 Q36 72 32 58" stroke={ok ? '#5C8B6A' : '#89B99A'} strokeWidth="1.5" fill="none"/>
    <line x1="232" y1="128" x2="60" y2="128" stroke="#3D6B9E" strokeWidth="1.2"/>
    <polygon points="232,128 225,124 225,132" fill="#3D6B9E"/>
    <polygon points="60,128 67,124 67,132"   fill="#3D6B9E"/>
    <text x="146" y="142" textAnchor="middle" fill="#3D6B9E" fontSize="7" fontFamily="monospace" fontWeight="700">LC</text>
    <line x1="188" y1="54" x2="188" y2="130" stroke="#C0392B" strokeWidth="1.3"/>
    <text x="192" y="88" fill="#C0392B" fontSize="7" fontFamily="monospace" fontWeight="700">PT</text>
    <line x1="148" y1="50" x2="148" y2="168" stroke="#C8914A" strokeWidth="1" strokeDasharray="3,2"/>
    <text x="152" y="100" fill="#C8914A" fontSize="7" fontFamily="monospace" fontWeight="700">AC</text>
    <circle cx="232" cy="82" r="5" fill="#3D6B9E" opacity="0.9"/>
    <circle cx="60"  cy="82" r="5" fill="#3D6B9E" opacity="0.9"/>
    <text x="220" y="72" fill="#3D6B9E" fontSize="6" fontFamily="monospace">ENC</text>
    <text x="42"  y="72" fill="#3D6B9E" fontSize="6" fontFamily="monospace">ISQ</text>
    {ok ? (
      <text x="160" y="18" textAnchor="middle" fill="#5C8B6A" fontSize="7" fontFamily="monospace" fontWeight="700">
        ✓ ALINEADA — LISTO PARA ANALIZAR
      </text>
    ) : (
      <text x="160" y="18" textAnchor="middle" fill="#89B99A" fontSize="7" fontFamily="monospace">
        ALINEA LA VACA CON EL CONTORNO
      </text>
    )}
  </svg>
)

// ─── Foto lateral con overlay ─────────────────────────────────────────────
function FotoLateral({ file, onChange, inputRef }) {
  const preview = file ? URL.createObjectURL(file) : null
  return (
    <div>
      <label className="label">📸 Foto lateral *</label>
      <div onClick={() => inputRef.current?.click()}
        className="relative rounded-xl cursor-pointer overflow-hidden"
        style={{
          height: '180px',
          border: file ? '1.5px solid #89B99A' : '1.5px dashed #C8D8C0',
          background: file ? 'transparent' : 'rgba(137,185,154,0.04)',
        }}>
        {preview && (
          <img src={preview} alt="lateral" className="absolute inset-0 w-full h-full object-cover" style={{ opacity: 0.65 }} />
        )}
        <SiluetaLateral ok={!!file} />
        {!preview && (
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-4 z-20">
            <Upload size={18} style={{ color: '#C8D8C0' }} className="mb-1" />
            <span className="font-mono text-xs" style={{ color: '#B0A090' }}>Toca para subir la foto</span>
          </div>
        )}
        {preview && (
          <div className="absolute bottom-2 right-2 z-20">
            <span className="font-mono text-xs px-2 py-1 rounded-lg"
              style={{ background: 'rgba(255,255,255,0.92)', color: '#5C8B6A', border: '0.5px solid #D0C5B0' }}>
              cambiar
            </span>
          </div>
        )}
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp"
          className="hidden" onChange={e => onChange(e.target.files[0] || null)} />
      </div>
      <div className="flex gap-3 mt-1.5">
        {[['#3D6B9E', 'LC largo corporal'], ['#C0392B', 'PT perímetro'], ['#C8914A', 'AC alzada']].map(([color, label]) => (
          <div key={label} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: color }} />
            <span className="font-mono" style={{ color: '#B0A090', fontSize: '10px' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Foto trasera simple ──────────────────────────────────────────────────
function FotoUpload({ label, hint, file, onChange, inputRef }) {
  const preview = file ? URL.createObjectURL(file) : null
  return (
    <div>
      <label className="label">{label}</label>
      <div onClick={() => inputRef.current?.click()}
        className="relative rounded-xl cursor-pointer transition-all overflow-hidden flex flex-col items-center justify-center text-center"
        style={{
          height: '180px',
          border: file ? '1.5px solid #89B99A' : '1.5px dashed #C8D8C0',
          background: file ? 'transparent' : 'rgba(137,185,154,0.03)',
        }}
        onMouseOver={e => { if (!file) e.currentTarget.style.borderColor = '#89B99A' }}
        onMouseOut={e  => { if (!file) e.currentTarget.style.borderColor = '#C8D8C0' }}>
        {preview ? (
          <>
            <img src={preview} alt="" className="w-full h-full object-cover" />
            <div className="absolute bottom-2 right-2">
              <span className="font-mono text-xs px-2 py-1 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.92)', color: '#5C8B6A', border: '0.5px solid #D0C5B0' }}>
                cambiar
              </span>
            </div>
          </>
        ) : (
          <>
            <Upload size={20} style={{ color: '#C8D8C0' }} className="mb-2" />
            <span className="font-mono text-xs px-3" style={{ color: '#B0A090' }}>{hint}</span>
          </>
        )}
        <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp"
          className="hidden" onChange={e => onChange(e.target.files[0] || null)} />
      </div>
      <div className="flex items-center gap-1 mt-1.5">
        <div className="w-2 h-2 rounded-full" style={{ background: '#8B5CF6' }} />
        <span className="font-mono" style={{ color: '#B0A090', fontSize: '10px' }}>Ancho cadera · BCS</span>
      </div>
    </div>
  )
}

// ─── Buscador de vaca por arete ───────────────────────────────────────────
function BuscadorVaca({ onVacaResuelta }) {
  const [arete, setArete]                   = useState('')
  const [buscando, setBuscando]             = useState(false)
  const [vacaEncontrada, setVacaEncontrada] = useState(null)
  const [nombre, setNombre]                 = useState('')
  const [hatoId, setHatoId]                 = useState('')
  const [hatos, setHatos]                   = useState([])
  const debounceRef = useRef()

  useEffect(() => {
    hatosApi.listar().then(r => setHatos(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!arete.trim()) { setVacaEncontrada(null); onVacaResuelta(null); return }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setBuscando(true)
      try {
        const res = await animalesApi.buscarPorArete(arete.trim())
        if (res.data) {
          setVacaEncontrada(res.data)
          onVacaResuelta(res.data)
        } else {
          setVacaEncontrada(false)
          onVacaResuelta(null)
        }
      } catch {
        setVacaEncontrada(false)
        onVacaResuelta(null)
      } finally {
        setBuscando(false)
      }
    }, 600)
    return () => clearTimeout(debounceRef.current)
  }, [arete])

  const confirmarNueva = () => {
    if (!hatoId) return toast.error('Selecciona el hato')
    onVacaResuelta({ _nuevo: true, arete: arete.trim(), nombre: nombre.trim() || null, hato_id: hatoId })
  }

  const esNueva     = vacaEncontrada === false
  const esExistente = vacaEncontrada && vacaEncontrada !== false

  return (
    <div className="space-y-3">
      <div>
        <label className="label">Arete de la vaca *</label>
        <div className="relative">
          <input
            className="input pr-10"
            placeholder="Ej: 0045, AR-123…"
            value={arete}
            onChange={e => { setArete(e.target.value); setVacaEncontrada(null); onVacaResuelta(null) }}
          />
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {buscando
              ? <div className="w-4 h-4 border-2 rounded-full animate-spin"
                     style={{ borderColor: '#89B99A', borderTopColor: 'transparent' }} />
              : esExistente
                ? <Check size={16} style={{ color: '#5C8B6A' }} />
                : <Search size={14} style={{ color: '#C8BBA8' }} />
            }
          </div>
        </div>
      </div>

      {esExistente && (
        <div className="flex items-center gap-3 p-3 rounded-xl"
          style={{ background: '#EAF4EE', border: '0.5px solid #89B99A' }}>
          <CheckCircle2 size={16} style={{ color: '#5C8B6A' }} />
          <div className="flex-1">
            <div className="font-mono text-xs font-bold" style={{ color: '#2E4D38' }}>
              Vaca encontrada · {vacaEncontrada.arete}
            </div>
            <div className="font-mono text-xs" style={{ color: '#8B7D6B' }}>
              {vacaEncontrada.nombre || 'Sin nombre'}
              {vacaEncontrada.ultimo_peso_kg ? ` · Último peso: ${vacaEncontrada.ultimo_peso_kg} kg` : ''}
              {vacaEncontrada.ultimo_bcs     ? ` · BCS: ${vacaEncontrada.ultimo_bcs}` : ''}
            </div>
          </div>
        </div>
      )}

      {esNueva && (
        <div className="space-y-3 p-3 rounded-xl"
          style={{ background: '#F5F0E8', border: '0.5px solid #D0C5B0' }}>
          <div className="flex items-center gap-2 font-mono text-xs" style={{ color: '#5C8B6A' }}>
            <UserPlus size={13} /> Vaca nueva — completa los datos
          </div>
          <div>
            <label className="label">Nombre (opcional)</label>
            <input className="input" placeholder="Ej: Manchita, Princesa…"
              value={nombre} onChange={e => setNombre(e.target.value)} />
          </div>
          <div>
            <label className="label">Hato *</label>
            <div className="relative">
              <select className="input appearance-none pr-8" value={hatoId} onChange={e => setHatoId(e.target.value)}>
                <option value="">— Selecciona el hato</option>
                {hatos.map(h => <option key={h.id} value={h.id}>{h.nombre} · {h.finca}</option>)}
              </select>
              <ChevronDown size={13} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none"
                style={{ color: '#B0A090' }} />
            </div>
          </div>
          <button type="button" onClick={confirmarNueva}
            className="btn-secondary w-full justify-center text-xs py-2">
            <Check size={13} /> Confirmar vaca nueva
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Página principal ─────────────────────────────────────────────────────
export default function AnalisisPage() {
  const [vacaResuelta, setVacaResuelta] = useState(null)
  const [imgLateral, setImgLateral]     = useState(null)
  const [imgTrasera, setImgTrasera]     = useState(null)
  const [notas, setNotas]               = useState('')
  const [resultado, setResultado]       = useState(null)
  const [stepActivo, setStepActivo]     = useState(-1)
  const lateralRef = useRef()
  const traseraRef = useRef()

  const analizar = useMutation({
    mutationFn: async ({ vaca, imgLateral, imgTrasera, notas }) => {
      let animalId = vaca.id
      if (vaca._nuevo) {
        const res = await animalesApi.crear({ arete: vaca.arete, nombre: vaca.nombre || null, hato_id: vaca.hato_id, raza: 'Jersey' })
        animalId = res.data.id
      }
      const fd = new FormData()
      fd.append('animal_id', animalId)
      fd.append('imagen_lateral', imgLateral)
      fd.append('imagen_trasera', imgTrasera)
      if (notas) fd.append('notas', notas)
      return analisisApi.analizar(fd)
    },
    onMutate: async () => {
      for (let i = 0; i < STEPS.length; i++) {
        setStepActivo(i)
        await new Promise(r => setTimeout(r, 600 + Math.random() * 400))
      }
    },
    onSuccess: (res) => { setResultado(res.data); setStepActivo(-1); toast.success('Análisis completado') },
    onError:   (e)   => { setStepActivo(-1); toast.error(e.response?.data?.detail || 'Error en el análisis') },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!vacaResuelta) return toast.error('Ingresa el arete de la vaca')
    if (vacaResuelta._nuevo && !vacaResuelta.hato_id) return toast.error('Confirma los datos de la vaca nueva')
    if (!imgLateral) return toast.error('Sube la foto lateral')
    if (!imgTrasera) return toast.error('Sube la foto trasera')
    analizar.mutate({ vaca: vacaResuelta, imgLateral, imgTrasera, notas })
  }

  const reset = () => {
    setResultado(null); setImgLateral(null); setImgTrasera(null)
    setVacaResuelta(null); setNotas(''); setStepActivo(-1)
  }

  const bcsColor = resultado ? getBCSColor(resultado.bcs) : null

  return (
    <div className="animate-fade-in max-w-3xl mx-auto space-y-6 relative z-10">
      <div>
        <h1 style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.75rem', fontWeight: 900 }}>
          Nueva Medición
        </h1>
        <p className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
          ADQUISICIÓN → PROCESAMIENTO → ESTIMACIÓN
        </p>
      </div>

      {/* ── Resultado ── */}
      {resultado ? (
        <div className="space-y-4 animate-slide-up">
          <div className="card p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: '#EAF4EE' }}>
                <CheckCircle2 size={20} style={{ color: '#5C8B6A' }} />
              </div>
              <div>
                <div style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '1.1rem', fontWeight: 700 }}>
                  Análisis completado
                </div>
                <div className="font-mono text-xs" style={{ color: '#8B7D6B' }}>
                  {vacaResuelta?.nombre || vacaResuelta?.arete} · {resultado.procesado_en_segundos}s
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-5">
              {/* Peso */}
              <div className="rounded-xl p-5 text-center"
                   style={{ background: '#EAF4EE', border: '0.5px solid #89B99A' }}>
                <div className="metric-big">{resultado.peso_estimado_kg}</div>
                <div className="font-mono text-xs mt-1" style={{ color: '#8B7D6B' }}>
                  kilogramos · ±{Math.round(resultado.peso_estimado_kg * 0.05)} kg
                </div>
              </div>
              {/* BCS */}
              <div className="rounded-xl p-5 text-center"
                   style={{
                     background: bcsColor ? `${bcsColor.bg}` : '#F5F0E8',
                     border: `0.5px solid ${bcsColor?.bg || '#E0D8C8'}`,
                   }}>
                <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '3rem', fontWeight: 900, color: bcsColor?.text || '#5C8B6A' }}>
                  {resultado.bcs?.toFixed(1)}
                </div>
                <div className="font-mono text-xs mt-1" style={{ color: bcsColor?.text || '#8B7D6B' }}>
                  BCS · {getBCSLabel(resultado.bcs)}
                </div>
              </div>
            </div>

            {/* Escala BCS */}
            <div className="flex gap-1.5 mb-4">
              {[1, 2, 3, 3.25, 3.5, 4, 4.5, 5].map(n => {
                const bcsVal   = resultado.bcs
                const bcsRound = bcsVal % 1 === 0.5 ? Math.floor(bcsVal) : Math.round(bcsVal)
                const isActive = bcsRound === n
                const isNear   = !isActive && Math.abs(n - bcsVal) <= 1
                return (
                  <div key={n} className="flex-1 h-7 rounded-lg flex items-center justify-center font-mono text-xs"
                       style={{
                         background: isActive
                           ? '#5C8B6A'
                           : isNear
                             ? '#D4ECD9'
                             : '#F5F0E8',
                         color: isActive ? 'white' : isNear ? '#2E4D38' : '#C8BBA8',
                         border: `0.5px solid ${isActive ? '#5C8B6A' : isNear ? '#89B99A' : '#E0D8C8'}`,
                       }}>
                    {n}
                  </div>
                )
              })}
            </div>

            {/* Recomendación */}
            <div className="rounded-xl p-4 mb-4"
                 style={{ background: '#F5F0E8', border: '0.5px solid #D0C5B0' }}>
              <div className="font-mono text-xs mb-1" style={{ color: '#5C8B6A' }}>RECOMENDACIÓN</div>
              <div className="text-sm leading-relaxed" style={{ color: '#1A1A1A', fontFamily: 'Lora, serif' }}>
                {resultado.recomendacion}
              </div>
            </div>

            <div className="flex items-center justify-between font-mono text-xs" style={{ color: '#B0A090' }}>
              <span>Confianza: <span style={{ color: '#5C8B6A' }}>{resultado.confianza?.toFixed(1)}%</span></span>
              <span>Motor: <span style={{ color: '#89B99A' }}>{resultado.procesado_por ?? 'sam+xgboost'}</span></span>
            </div>
          </div>

          {/* Morfometría */}
          {resultado.morfometria && (
            <div className="card p-5 animate-slide-up">
              <div className="panel-title">Morfometría</div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {[
                  ['Largo corporal',     resultado.morfometria.largo_corporal_cm,       'cm'],
                  ['Alzada a la cruz',   resultado.morfometria.alzada_cm,               'cm'],
                  ['Perímetro torácico', resultado.morfometria.perimetro_toracico_cm,   'cm'],
                  ['Ancho de cadera',    resultado.morfometria.ancho_caderas_cm,        'cm'],
                  ['Prof. torácica',     resultado.morfometria.profundidad_toracica_cm, 'cm'],
                  ['Longitud grupa',     resultado.morfometria.longitud_grupa_cm,       'cm'],
                ].map(([label, val, unit]) => val ? (
                  <div key={label} className="rounded-xl p-3"
                       style={{ background: '#F5F0E8', border: '0.5px solid #E0D8C8' }}>
                    <div className="font-mono text-xs mb-1" style={{ color: '#8B7D6B' }}>{label}</div>
                    <div style={{ fontFamily: 'Syne, sans-serif', fontSize: '1.25rem', fontWeight: 700, color: '#1A1A1A' }}>
                      {val} <span className="font-mono text-xs" style={{ color: '#B0A090' }}>{unit}</span>
                    </div>
                  </div>
                ) : null)}
              </div>
            </div>
          )}

          <button onClick={reset} className="btn-secondary w-full justify-center">
            <RotateCcw size={14} /> Nueva medición
          </button>
        </div>

      ) : (
        <div className="space-y-4">

          {/* Processing */}
          {analizar.isPending && (
            <div className="card p-8 animate-fade-in">
              <div className="flex flex-col items-center gap-6">
                <div className="w-12 h-12 rounded-full border-2 flex items-center justify-center"
                     style={{ borderColor: '#D4ECD9' }}>
                  <div className="w-2 h-8 rounded-full scan-anim"
                       style={{ background: 'linear-gradient(180deg, transparent, #5C8B6A, transparent)' }} />
                </div>
                <div className="w-full max-w-xs space-y-2">
                  {STEPS.map((s, i) => (
                    <div key={s} className="flex items-center gap-3 font-mono text-xs transition-all duration-300"
                         style={{
                           color: i < stepActivo
                             ? '#5C8B6A'
                             : i === stepActivo
                               ? '#1A1A1A'
                               : '#C8BBA8',
                         }}>
                      <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                           style={{
                             background: i < stepActivo ? '#5C8B6A' : i === stepActivo ? '#89B99A' : '#E0D8C8',
                             animation: i === stepActivo ? 'pulse 0.8s ease-in-out infinite' : undefined,
                           }} />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!analizar.isPending && (
            <form onSubmit={handleSubmit} className="card p-6 space-y-5">

              {/* Sección 1 */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-5 h-5 rounded-md flex items-center justify-center font-mono text-xs font-bold"
                       style={{ background: '#D4ECD9', color: '#2E4D38' }}>1</div>
                  <span className="font-mono text-xs uppercase tracking-widest" style={{ color: '#5C8B6A' }}>
                    Identificación
                  </span>
                </div>
                <BuscadorVaca onVacaResuelta={setVacaResuelta} />
              </div>

              <div style={{ borderTop: '0.5px solid #E8E0D0' }} />

              {/* Sección 2 */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-5 h-5 rounded-md flex items-center justify-center font-mono text-xs font-bold"
                       style={{ background: '#D4ECD9', color: '#2E4D38' }}>2</div>
                  <span className="font-mono text-xs uppercase tracking-widest" style={{ color: '#5C8B6A' }}>
                    Fotografías
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <FotoLateral file={imgLateral} onChange={setImgLateral} inputRef={lateralRef} />
                  <FotoUpload  label="📸 Foto trasera *" hint="Vista posterior · Grupa centrada"
                               file={imgTrasera} onChange={setImgTrasera} inputRef={traseraRef} />
                </div>
              </div>

              <div style={{ borderTop: '0.5px solid #E8E0D0' }} />

              {/* Sección 3 */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <div className="w-5 h-5 rounded-md flex items-center justify-center font-mono text-xs font-bold"
                       style={{ background: '#D4ECD9', color: '#2E4D38' }}>3</div>
                  <span className="font-mono text-xs uppercase tracking-widest" style={{ color: '#5C8B6A' }}>
                    Notas
                  </span>
                </div>
                <textarea className="input resize-none" rows={2}
                  placeholder="Observaciones opcionales sobre esta medición…"
                  value={notas} onChange={e => setNotas(e.target.value)} />
              </div>

              <button type="submit" className="btn-primary w-full justify-center py-3">
                <Scale size={16} /> Estimar peso y BCS
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  )
}