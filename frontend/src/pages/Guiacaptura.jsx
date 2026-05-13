// pages/GuiaCaptura.jsx
// Modal con guía visual de captura de imágenes para el análisis bovino.
// Uso: <GuiaCaptura open={open} onClose={() => setOpen(false)} />

import { useEffect, useRef } from 'react'
import { X, CheckCircle2, XCircle, Camera } from 'lucide-react'

const C = {
  primary:    '#081C11',
  accent:     '#52D9A0',
  accentDark: '#1B6B3A',
  textSub:    '#2A5C3A',
  textSecond: '#4A8C5C',
  card:       '#FFFFFF',
  border:     '#E0F4EC',
  bg:         '#F9FDFB',
}

// ── Silueta vaca lateral (SVG inline) ─────────────────────────────────────
function SiluetaLateral({ size = 130 }) {
  return (
    <svg viewBox="0 0 320 190" width={size} height={size * 0.6} aria-hidden="true">
      <rect x="15" y="15" width="290" height="160" rx="12"
        fill="none" stroke={C.accent} strokeWidth="2" strokeDasharray="8,5" opacity="0.6"/>
      <path d="M60 70 C70 50 110 45 150 45 S230 55 240 80 C250 110 245 140 210 150 S100 155 70 140 S50 100 60 70Z"
        fill="rgba(82,217,160,0.15)" stroke={C.accent} strokeWidth="2.5"/>
      <path d="M235 60 C245 40 275 35 290 50 S295 80 280 90 S245 85 235 60Z"
        fill="rgba(82,217,160,0.1)" stroke={C.accent} strokeWidth="1.8"/>
      <ellipse cx="285" cy="55" rx="3" ry="5" fill={C.accent} opacity="0.7"/>
      <rect x="200" y="135" width="11" height="38" rx="3" fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.6"/>
      <rect x="217" y="132" width="11" height="38" rx="3" fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.6"/>
      <rect x="76" y="132" width="12" height="40" rx="3" fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.6"/>
      <rect x="95" y="135" width="12" height="40" rx="3" fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.6"/>
      <path d="M65 85 C50 80 45 100 48 120" stroke={C.accent} strokeWidth="2" fill="none" strokeLinecap="round"/>
      <line x1="235" y1="128" x2="65" y2="128" stroke="#3D6B9E" strokeWidth="1.8"/>
      <circle cx="235" cy="128" r="2.5" fill="#3D6B9E"/>
      <circle cx="65"  cy="128" r="2.5" fill="#3D6B9E"/>
      <text x="150" y="140" textAnchor="middle" fill="#3D6B9E" fontSize="9" fontFamily="monospace" fontWeight="700">LC</text>
      <line x1="190" y1="46" x2="190" y2="146" stroke="#C0392B" strokeWidth="1.8" strokeDasharray="4,2"/>
      <text x="197" y="93" fill="#C0392B" fontSize="9" fontFamily="monospace" fontWeight="700">PT</text>
      <text x="50" y="20" fill={C.accent} fontSize="9" fontFamily="monospace" fontWeight="700">2 – 4 m →</text>
    </svg>
  )
}

// ── Silueta vaca posterior (SVG inline) ────────────────────────────────────
function SiluetaTrasera({ size = 100 }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size} aria-hidden="true">
      <ellipse cx="100" cy="90" rx="65" ry="60"
        fill="rgba(82,217,160,0.12)" stroke={C.accent} strokeWidth="2.5"/>
      <ellipse cx="62" cy="148" rx="13" ry="28"
        fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.8"/>
      <ellipse cx="138" cy="148" rx="13" ry="28"
        fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.8"/>
      <path d="M100 30 Q88 50 100 68 Q112 50 100 30"
        fill="rgba(82,217,160,0.2)" stroke={C.accent} strokeWidth="1.6"/>
      <line x1="100" y1="30" x2="100" y2="170"
        stroke={C.accentDark} strokeWidth="1.2" strokeDasharray="3,3" opacity="0.5"/>
      <line x1="35" y1="115" x2="165" y2="115"
        stroke="#8B5CF6" strokeWidth="1.8"/>
      <circle cx="35"  cy="115" r="3" fill="#8B5CF6"/>
      <circle cx="165" cy="115" r="3" fill="#8B5CF6"/>
      <text x="100" y="108" textAnchor="middle" fill="#8B5CF6" fontSize="9" fontFamily="monospace" fontWeight="700">AC</text>
      <text x="100" y="185" textAnchor="middle" fill={C.accent} fontSize="9" fontFamily="monospace" fontWeight="700">cola centrada</text>
    </svg>
  )
}

// ── Fila de requisito ──────────────────────────────────────────────────────
function ReqRow({ ok, children }) {
  return (
    <div className="flex items-start gap-2.5">
      {ok
        ? <CheckCircle2 size={14} style={{ color: C.accentDark, flexShrink: 0, marginTop: 2 }}/>
        : <XCircle      size={14} style={{ color: '#C0392B',    flexShrink: 0, marginTop: 2 }}/>
      }
      <span className="text-sm leading-snug" style={{ color: ok ? C.primary : '#C0392B' }}>{children}</span>
    </div>
  )
}

// ── Sección numerada ───────────────────────────────────────────────────────
function Seccion({ num, titulo, children }) {
  return (
    <div className="rounded-2xl border overflow-hidden" style={{ borderColor: C.border }}>
      <div className="flex items-center gap-3 px-5 py-3.5 border-b" style={{ background: C.bg, borderColor: C.border }}>
        <div className="w-7 h-7 rounded-lg flex items-center justify-center font-mono text-[11px] font-bold"
          style={{ background: '#E8F8F1', color: C.accentDark }}>{num}</div>
        <span className="font-semibold text-[15px]" style={{ color: C.primary }}>{titulo}</span>
      </div>
      <div className="p-5 bg-white">{children}</div>
    </div>
  )
}

// ── Componente principal ───────────────────────────────────────────────────
export default function GuiaCaptura({ open, onClose }) {
  const overlayRef = useRef()

  // Cerrar con Escape
  useEffect(() => {
    if (!open) return
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Bloquear scroll del body
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    // Overlay — fondo semitransparente fuera del modal
    <div
      ref={overlayRef}
      onClick={(e) => { if (e.target === overlayRef.current) onClose() }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(8,28,17,0.55)', backdropFilter: 'blur(3px)' }}
    >
      {/* Panel modal */}
      <div
        className="relative w-full rounded-3xl shadow-2xl flex flex-col"
        style={{
          maxWidth: 680,
          maxHeight: '92vh',
          background: C.card,
          border: `1.5px solid ${C.border}`,
        }}
      >
        {/* Cabecera fija */}
        <div className="flex items-center justify-between px-6 py-4 border-b flex-shrink-0"
          style={{ borderColor: C.border }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: '#E8F8F1' }}>
              <Camera size={18} style={{ color: C.accentDark }} />
            </div>
            <div>
              <p className="font-bold text-base leading-tight" style={{ color: C.primary }}>
                Guía de captura de imágenes
              </p>
              <p className="font-mono text-[10px] uppercase tracking-wider mt-0.5" style={{ color: C.textSecond }}>
                Ganado Jersey · Sistema JER-WEIGHT
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
            style={{ background: '#F9FDFB', border: `1px solid ${C.border}` }}
            aria-label="Cerrar guía"
          >
            <X size={16} style={{ color: C.textSub }} />
          </button>
        </div>

        {/* Contenido scrollable */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">

          {/* 1 · Posición del animal */}
          <Seccion num="1" titulo="Posiciona el animal correctamente">
            <div className="grid grid-cols-2 gap-4">
              {/* Lateral */}
              <div className="rounded-xl p-4 flex flex-col items-center gap-3 border"
                style={{ background: C.bg, borderColor: C.border }}>
                <div className="font-mono text-[10px] font-bold uppercase tracking-wider self-start"
                  style={{ color: C.accentDark }}>Vista lateral — para peso</div>
                <SiluetaLateral size={200} />
                <div className="space-y-1.5 self-start w-full">
                  <ReqRow ok>Perfil completo del animal visible</ReqRow>
                  <ReqRow ok>Las 4 patas visibles en el suelo</ReqRow>
                  <ReqRow ok>Distancia: 2 – 4 metros del flanco</ReqRow>
                  <ReqRow ok={false}>No captures en diagonal</ReqRow>
                </div>
                <div className="flex gap-3 mt-1 self-start">
                  {[['#3D6B9E','LC largo'],['#C0392B','PT perímetro'],['#C8914A','AC alzada']].map(([c, l]) => (
                    <div key={l} className="flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full" style={{ background: c }}/>
                      <span className="font-mono text-[9px] font-bold uppercase" style={{ color: C.textSub }}>{l}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Trasera */}
              <div className="rounded-xl p-4 flex flex-col items-center gap-3 border"
                style={{ background: C.bg, borderColor: C.border }}>
                <div className="font-mono text-[10px] font-bold uppercase tracking-wider self-start"
                  style={{ color: '#7C3AED' }}>Vista posterior — para BCS</div>
                <SiluetaTrasera size={130} />
                <div className="space-y-1.5 self-start w-full">
                  <ReqRow ok>Cola centrada, animal de frente</ReqRow>
                  <ReqRow ok>Grupa y caderas completamente visibles</ReqRow>
                  <ReqRow ok>Cámara a altura de la cadera del animal</ReqRow>
                  <ReqRow ok={false}>No captures en ángulo lateral</ReqRow>
                </div>
                <div className="flex items-center gap-1.5 mt-1 self-start">
                  <div className="w-2 h-2 rounded-full" style={{ background: '#8B5CF6' }}/>
                  <span className="font-mono text-[9px] font-bold uppercase" style={{ color: C.textSub }}>AC ancho cadera · BCS</span>
                </div>
              </div>
            </div>
          </Seccion>

          {/* 2 · Condiciones */}
          <Seccion num="2" titulo="Condiciones de captura que afectan al modelo">
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  titulo: 'Iluminación', color: '#FAEEDA', colorText: '#854F0B',
                  ok: ['Luz natural difusa (exterior nublado)', 'Interior con luz pareja sin sombras duras'],
                  no: ['Contraluz directo (sol detrás del animal)', 'Flash directo muy cercano'],
                },
                {
                  titulo: 'Fondo', color: '#E6F1FB', colorText: '#185FA5',
                  ok: ['Fondo claro para ganado Jersey oscuro', 'Pared, malla o corredor sin vegetación'],
                  no: ['Fondo con vegetación densa', 'Fondo del mismo tono que el pelaje'],
                },
                {
                  titulo: 'Postura del animal', color: '#E8F8F1', colorText: C.accentDark,
                  ok: ['Animal de pie y quieto', 'Sin objetos que tapen el perfil'],
                  no: ['Animal en movimiento o agachado', 'Otro animal interpuesto'],
                },
                {
                  titulo: 'Resolución', color: '#EDE9FE', colorText: '#5B21B6',
                  ok: ['Mínimo 1280 × 720 px (HD)', 'Modo foto estándar del teléfono'],
                  no: ['Video capturado en baja resolución', 'Imagen con zoom digital excesivo'],
                },
              ].map(({ titulo, color, colorText, ok, no }) => (
                <div key={titulo} className="rounded-xl p-3.5 border" style={{ background: color + '30', borderColor: color + '80' }}>
                  <p className="font-mono text-[10px] font-bold uppercase tracking-wider mb-2.5" style={{ color: colorText }}>{titulo}</p>
                  <div className="space-y-1.5">
                    {ok.map(t => <ReqRow key={t} ok>{t}</ReqRow>)}
                    {no.map(t => <ReqRow key={t} ok={false}>{t}</ReqRow>)}
                  </div>
                </div>
              ))}
            </div>
          </Seccion>

          {/* 3 · Requisitos del archivo */}
          <Seccion num="3" titulo="Requisitos del archivo de imagen">
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Formatos aceptados', val: 'JPG · PNG · WEBP', ok: true },
                { label: 'Resolución mínima',  val: '1280 × 720 px',   ok: true },
                { label: 'Tamaño máximo',      val: '10 MB por foto',  ok: true },
                { label: 'Sin filtros',         val: 'Foto original',   ok: true },
                { label: 'Sin recortes',        val: 'Encuadre completo', ok: true },
                { label: 'Sin metadatos alterados', val: 'Directo de cámara', ok: true },
              ].map(({ label, val, ok }) => (
                <div key={label} className="rounded-xl p-3 border text-center"
                  style={{ background: C.bg, borderColor: C.border }}>
                  <div className="flex justify-center mb-1.5">
                    {ok
                      ? <CheckCircle2 size={16} style={{ color: C.accentDark }}/>
                      : <XCircle      size={16} style={{ color: '#C0392B' }}/>
                    }
                  </div>
                  <p className="font-mono text-[9px] uppercase tracking-wider font-bold mb-0.5" style={{ color: C.textSub }}>{label}</p>
                  <p className="font-mono text-[11px] font-bold" style={{ color: C.primary }}>{val}</p>
                </div>
              ))}
            </div>
          </Seccion>

          {/* Tip final */}
          <div className="rounded-2xl px-5 py-4 flex items-start gap-3"
            style={{ background: '#E8F8F1', border: `1px solid rgba(82,217,160,0.3)` }}>
            <div className="w-5 h-5 mt-0.5 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: C.accent }}>
              <span style={{ color: C.primary, fontSize: 10, fontWeight: 800 }}>!</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: C.primary }}>
              <span className="font-bold">Consejo:</span> captura primero la foto lateral (el modelo de peso la necesita con luz pareja), luego pide a un ayudante que posicione el animal de frente para la foto trasera de BCS. Con dos fotos de buena calidad el pipeline entregará estimaciones con margen de error mínimo.
            </p>
          </div>
        </div>

        {/* Footer fijo */}
        <div className="px-6 py-4 border-t flex-shrink-0" style={{ borderColor: C.border }}>
          <button
            onClick={onClose}
            className="w-full py-3 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-all active:scale-95"
            style={{ background: C.primary, color: '#FFFFFF' }}
          >
            Entendido — volver al formulario
          </button>
        </div>
      </div>
    </div>
  )
}