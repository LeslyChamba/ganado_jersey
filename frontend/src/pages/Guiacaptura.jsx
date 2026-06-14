// Modal con guía visual de captura de imágenes para el análisis bovino.
// Uso: <GuiaCaptura open={open} onClose={() => setOpen(false)} />

import { useEffect, useRef } from 'react'
import { X, CheckCircle2, XCircle, Camera } from 'lucide-react'

const IMG_LATERAL = '/img/guia_lateral.png'
const IMG_TRASERA = '/img/guia_trasera.png'

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
          maxWidth: 720,
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              
              {/* Lateral */}
              <div className="rounded-xl p-4 flex flex-col gap-3 border"
                style={{ background: C.bg, borderColor: C.border }}>
                <div className="font-mono text-[10px] font-bold uppercase tracking-wider"
                  style={{ color: C.accentDark }}>Vista lateral — para peso</div>
                
                {/* Contenedor de la Imagen Real */}
                <div className="w-full h-44 overflow-hidden rounded-lg border bg-emerald-950/20 flex items-center justify-center group relative" style={{ borderColor: C.border }}>
                  <img 
                    src={IMG_LATERAL} 
                    alt="Guía de encuadre lateral" 
                    className="w-full h-full object-contain p-1 transition-transform duration-300 group-hover:scale-105"
                    onError={(e) => { e.target.src = "https://placehold.co/400x300?text=Falta+Imagen+Lateral"; }}
                  />
                </div>

                <div className="space-y-1.5 w-full mt-1">
                  <ReqRow ok>Perfil completo del animal visible</ReqRow>
                  <ReqRow ok>Las 4 patas visibles en el suelo</ReqRow>
                  <ReqRow ok>Distancia: 2 – 4 metros del flanco</ReqRow>
                  <ReqRow ok={false}>No captures en diagonal</ReqRow>
                </div>
              </div>

              {/* Trasera */}
              <div className="rounded-xl p-4 flex flex-col gap-3 border"
                style={{ background: C.bg, borderColor: C.border }}>
                <div className="font-mono text-[10px] font-bold uppercase tracking-wider"
                  style={{ color: '#7C3AED' }}>Vista posterior — para BCS</div>
                
                {/* Contenedor de la Imagen Real */}
                <div className="w-full h-44 overflow-hidden rounded-lg border bg-emerald-950/20 flex items-center justify-center group relative" style={{ borderColor: C.border }}>
                  <img 
                    src={IMG_TRASERA} 
                    alt="Guía de encuadre trasera" 
                    className="w-full h-full object-contain p-1 transition-transform duration-300 group-hover:scale-105"
                    onError={(e) => { e.target.src = "https://placehold.co/400x300?text=Falta+Imagen+Trasera"; }}
                  />
                </div>

                <div className="space-y-1.5 w-full mt-1">
                  <ReqRow ok>Cola centrada, animal de frente</ReqRow>
                  <ReqRow ok>Grupa y caderas completamente visibles</ReqRow>
                  <ReqRow ok>Cámara a altura de la cadera del animal</ReqRow>
                  <ReqRow ok={false}>No captures en ángulo lateral</ReqRow>
                </div>
              </div>

            </div>
          </Seccion>

          {/* 2 · Condiciones */}
          <Seccion num="2" titulo="Condiciones de captura que afectan al modelo">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: 'Formatos aceptados', val: 'JPG · PNG · WEBP', ok: true },
                { label: 'Resolución mínima',  val: '1280 × 720 px',   ok: true },
                { label: 'Tamaño máximo',      val: '10 MB por foto',  ok: true },
                { label: 'Sin filtros',         val: 'Foto original',   ok: true },
                { label: 'Sin recortes',        val: 'Encuadre completo', ok: true },
                { label: 'Sin metadatos',       val: 'Directo de cámara', ok: true },
              ].map(({ label, val, ok }) => (
                <div key={label} className="rounded-xl p-3 border text-center flex flex-col justify-between"
                  style={{ background: C.bg, borderColor: C.border }}>
                  <div className="flex justify-center mb-1.5">
                    {ok
                      ? <CheckCircle2 size={16} style={{ color: C.accentDark }}/>
                      : <XCircle       size={16} style={{ color: '#C0392B' }}/>
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
              <span className="font-bold">Consejo:</span> captura primero la foto lateral (el modelo de peso la necesita con luz pareja), luego posiciona al animal para la foto trasera de BCS. Con dos fotos de buena calidad el pipeline entregará estimaciones con un margen de error mínimo.
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