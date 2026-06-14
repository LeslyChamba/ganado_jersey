import { useState, useRef, useEffect, useCallback } from 'react'
import { animalesApi, hatosApi, analisisApi } from '../services/api'
import { getBCSColor, getBCSLabel } from '../services/helpers'
import toast from 'react-hot-toast'
import {
  Scale, CheckCircle2, RotateCcw, Search, UserPlus, Check,
  ChevronDown, Info, Camera, BookOpen, AlertTriangle,
  ShieldAlert, ShieldCheck, Loader2, XCircle, RefreshCw,
  Ruler, TrendingDown, TrendingUp, Minus
} from 'lucide-react'
import GuiaCaptura from './Guiacaptura'

// ─── Tokens de Color ──────────────────────────────────────────────────────
const C = {
  bg: '#F0FBF6', card: '#FFFFFF', cardBorder: '#E0F4EC',
  primary: '#081C11', primaryVar: '#1B4332',
  accent: '#52D9A0', accentDark: '#1B6B3A',
  text: '#081C11', textSub: '#2A5C3A', textSecondary: '#4A8C5C',
  textLight: '#C0E8D4', border: '#E0F4EC', white: '#FFFFFF',
  success: '#1B4332', successText: '#52D9A0', successBg: 'rgba(82,217,160,0.1)',
  warning: '#F5C542', warningBg: '#FFFBEB', warningBorder: '#FDE68A',
  error: '#C0392B', errorBg: '#FEF2F2',
}
/* ── Tokens de tipografía ── */
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

// ─── Umbrales de confianza ────────────────────────────────────────────────
const BCS_CONFIDENCE_THRESHOLD  = 70
const PESO_CONFIDENCE_THRESHOLD = 45

const STEPS = [
  'Cargando imágenes al servidor seguro',
  'Segmentando silueta (SAM Neural Net)',
  'Extrayendo keypoints anatómicos',
  'Calculando morfometría computacional',
  'Estimando masa corporal (XGBoost)',
  'Determinando BCS (YOLOv8 Gen AI)',
  'Finalizando reporte métrico',
]

// ─── Normalizador de confianza ────────────────────────────────────────────
// El backend puede devolver 0-1 (decimal) o 0-100 (porcentaje).
// Esta función garantiza que SIEMPRE trabajemos en escala 0-100.
function normalizarConfianza(valor) {
  if (valor == null || isNaN(valor)) return 0
  return valor <= 1.0 ? valor * 100 : valor
}

// ─── Compresión de imagen ─────────────────────────────────────────────────
async function comprimirImagen(file, maxWidthPx = 1280, calidadJpeg = 0.82) {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const escala = Math.min(1, maxWidthPx / img.width)
      const canvas = document.createElement('canvas')
      canvas.width  = Math.round(img.width  * escala)
      canvas.height = Math.round(img.height * escala)
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height)
      URL.revokeObjectURL(url)
      canvas.toBlob(
        (blob) => resolve(new File([blob], file.name.replace(/\.\w+$/, '.jpg'), { type: 'image/jpeg' })),
        'image/jpeg', calidadJpeg
      )
    }
    img.src = url
  })
}

// ─── Validación básica local ──────────────────────────────────────────────
async function validarCalidadLocal(file) {
  return new Promise((resolve) => {
    const img = new Image()
    const url = URL.createObjectURL(file)
    img.onload = () => {
      const ladoCorto = Math.min(img.width, img.height)
      const ladoLargo = Math.max(img.width, img.height)
      if (ladoCorto < 240 || ladoLargo < 400) {
        URL.revokeObjectURL(url)
        return resolve({ ok: false, motivo: `Resolución insuficiente (${img.width}×${img.height}px).` })
      }
      const canvas = document.createElement('canvas')
      canvas.width = 80; canvas.height = 60
      const ctx = canvas.getContext('2d')
      ctx.drawImage(img, 0, 0, 80, 60)
      const data = ctx.getImageData(0, 0, 80, 60).data
      let suma = 0
      for (let i = 0; i < data.length; i += 4)
        suma += (data[i] * 0.299 + data[i+1] * 0.587 + data[i+2] * 0.114)
      const brillo = suma / (data.length / 4)
      URL.revokeObjectURL(url)
      if (brillo < 25)  return resolve({ ok: false, motivo: 'Imagen muy oscura.' })
      if (brillo > 245) return resolve({ ok: false, motivo: 'Imagen sobreexpuesta.' })
      resolve({ ok: true })
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve({ ok: false, motivo: 'No se pudo leer la imagen.' }) }
    img.src = url
  })
}

// ─── Modal de fuente de imagen ────────────────────────────────────────────
function ModalOpciones({ open, onClose, onCamara, onGaleria }) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
      style={{ background: 'rgba(8,28,17,0.55)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="w-full sm:w-80 rounded-t-[2rem] sm:rounded-[2rem] p-6 space-y-3"
        style={{ background: '#FFFFFF', border: '1px solid rgba(82,217,160,0.2)' }}
        onClick={e => e.stopPropagation()}
      >
        <p
          className="font-mono text-[10px] font-bold uppercase tracking-widest text-center mb-4"
          style={{ color: C.textSub }}
        >
          Seleccionar imagen
        </p>

        {/* Botón: Cámara */}
        <button
          type="button"
          onClick={() => { onClose(); setTimeout(onCamara, 80) }}   
          className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl transition-all active:scale-95"
          style={{ background: C.primary, color: '#FFFFFF' }}
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'rgba(82,217,160,0.15)' }}
          >
            <Camera size={20} style={{ color: C.accent }} />
          </div>
          <div className="text-left">
            <div className="font-mono text-xs font-bold uppercase tracking-widest">
              Tomar foto
            </div>
            <div className="font-sans text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.6)' }}>
              Abre la cámara del dispositivo
            </div>
          </div>
        </button>

        {/* Botón: Galería */}
        <button
          type="button"
          onClick={() => { onGaleria(); onClose() }}
          className="w-full flex items-center gap-4 px-5 py-4 rounded-2xl border transition-all active:scale-95"
          style={{ background: '#F9FDFB', borderColor: 'rgba(27,67,50,0.12)', color: C.primary }}
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: '#E8F8F1' }}
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
              stroke={C.accentDark} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="3"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
          </div>
          <div className="text-left">
            <div className="font-mono text-xs font-bold uppercase tracking-widest">
              Elegir de galería
            </div>
            <div className="font-sans text-[11px] mt-0.5" style={{ color: C.textSub }}>
              Selecciona una foto existente
            </div>
          </div>
        </button>

        {/* Cancelar */}
        <button
          type="button"
          onClick={onClose}
          className="w-full py-3 rounded-xl font-mono text-[10px] font-bold uppercase tracking-widest transition-all hover:bg-gray-50"
          style={{ color: C.textSub }}
        >
          Cancelar
        </button>
      </div>
    </div>
  )
}

// ─── Comparador de peso real ──────────────────────────────────────────────
function ComparadorPesoReal({ pesoEstimado }) {
  const [pesoReal, setPesoReal]         = useState('')
  const [comparado, setComparado]       = useState(null)
  const [inputFocused, setInputFocused] = useState(false)

  const calcularDiferencia = () => {
    const real = parseFloat(pesoReal)
    if (!real || real <= 0 || real > 1200) {
      return toast.error('Ingresa un peso real válido (1 – 1200 kg)')
    }
    const diferencia    = pesoEstimado - real
    const errorAbsoluto = Math.abs(diferencia)
    const errorPct      = (errorAbsoluto / real) * 100
    let nivel, color, icono
    if (errorPct <= 3)       { nivel = 'Excelente';      color = C.accentDark; icono = '🏆' }
    else if (errorPct <= 7)  { nivel = 'Muy bueno';      color = '#2563EB';    icono = '✅' }
    else if (errorPct <= 12) { nivel = 'Aceptable';      color = '#D97706';    icono = '⚠️' }
    else if (errorPct <= 18) { nivel = 'Regular';        color = '#EA580C';    icono = '⚠️' }
    else                     { nivel = 'Fuera de rango'; color = C.error;      icono = '❌' }
    setComparado({ real, diferencia, errorAbsoluto, errorPct, nivel, color, icono })
  }

  const resetComparador = () => { setPesoReal(''); setComparado(null) }

  return (
    <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-emerald-50">
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-[rgba(27,67,50,0.1)]">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center"
          style={{ background: '#E8F8F1' }}>
          <Ruler size={20} style={{ color: C.accentDark }} />
        </div>
        <div>
          <h3 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.3rem', fontWeight: 800 }}>
            Verificar con Peso Real
          </h3>
          <p className="font-mono text-[10px] mt-0.5 uppercase tracking-wider" style={{ color: C.textSecondary }}>
            Compara la estimación IA con báscula o cinta bovinométrica
          </p>
        </div>
      </div>

      {!comparado ? (
        <div className="space-y-4">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <input
                type="number" min="1" max="1200" step="0.5"
                placeholder="Ej: 390.5"
                value={pesoReal}
                onChange={e => setPesoReal(e.target.value)}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                onKeyDown={e => e.key === 'Enter' && calcularDiferencia()}
                className="w-full px-4 py-3.5 rounded-xl border font-mono text-sm focus:outline-none transition-all"
                style={{
                  borderColor: inputFocused ? C.accentDark : 'rgba(27,67,50,0.15)',
                  background: '#F9FDFB', color: C.primary,
                  boxShadow: inputFocused ? `0 0 0 3px rgba(82,217,160,0.15)` : 'none',
                }}
              />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-xs font-bold"
                style={{ color: C.textSub }}>kg</span>
            </div>
            <button type="button" onClick={calcularDiferencia} disabled={!pesoReal}
              className="px-6 py-3.5 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-all hover:-translate-y-0.5 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: C.primary, color: '#FFFFFF' }}>
              Calcular
            </button>
          </div>
          <div className="flex items-start gap-2 p-3.5 rounded-xl"
            style={{ background: '#F0FBF6', border: '1px solid rgba(82,217,160,0.2)' }}>
            <Info size={13} style={{ color: C.accentDark, flexShrink: 0, marginTop: 1 }} />
            <span className="font-sans text-xs leading-relaxed" style={{ color: C.textSub }}>
              Ingresa el peso obtenido con báscula o cinta bovinométrica{' '}
              <strong>en la misma sesión</strong> para validar la precisión del modelo.
            </span>
          </div>
        </div>
      ) : (
        <div className="space-y-5 animate-in zoom-in-95 duration-300">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-2xl p-5 text-center" style={{ background: C.primary }}>
              <div className="font-mono text-[9px] uppercase tracking-widest mb-1" style={{ color: C.accent }}>
                IA Estimó
              </div>
              <div style={{ fontFamily: F.brand, fontSize: '2.8rem', fontWeight: 900, color: '#FFFFFF', lineHeight: 1 }}>
                {pesoEstimado.toFixed(0)}
                <span className="font-mono text-lg" style={{ color: C.accent }}> kg</span>
              </div>
            </div>
            <div className="rounded-2xl p-5 text-center"
              style={{ background: '#F9FDFB', border: '1.5px solid rgba(27,67,50,0.1)' }}>
              <div className="font-mono text-[9px] uppercase tracking-widest mb-1" style={{ color: C.textSub }}>
                Peso Real
              </div>
              <div style={{ fontFamily: F.brand, fontSize: '2.8rem', fontWeight: 900, color: C.primary, lineHeight: 1 }}>
                {comparado.real.toFixed(0)}
                <span className="font-mono text-lg" style={{ color: C.textSub }}> kg</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl p-6"
            style={{ background: `${comparado.color}12`, border: `2px solid ${comparado.color}30` }}>
            <div className="flex items-center justify-between mb-5">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-widest mb-0.5" style={{ color: C.textSub }}>
                  Precisión del modelo
                </div>
                <div className="font-mono text-lg font-bold" style={{ color: comparado.color }}>
                  {comparado.icono} {comparado.nivel}
                </div>
              </div>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ background: `${comparado.color}20` }}>
                {comparado.diferencia > 0
                  ? <TrendingUp  size={22} style={{ color: comparado.color }} />
                  : comparado.diferencia < 0
                  ? <TrendingDown size={22} style={{ color: comparado.color }} />
                  : <Minus size={22} style={{ color: comparado.color }} />}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Error abs.', value: comparado.errorAbsoluto.toFixed(1), unit: 'kg' },
                { label: 'Error %',    value: comparado.errorPct.toFixed(1),      unit: 'MAPE' },
                {
                  label: 'Diferencia',
                  value: `${comparado.diferencia > 0 ? '+' : ''}${comparado.diferencia.toFixed(1)}`,
                  unit: comparado.diferencia > 0 ? 'sobrestimó' : comparado.diferencia < 0 ? 'subestimó' : 'exacto',
                  color: comparado.diferencia > 0 ? '#2563EB' : comparado.diferencia < 0 ? C.error : C.accentDark,
                },
              ].map(({ label, value, unit, color }) => (
                <div key={label} className="rounded-xl p-3.5 text-center"
                  style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
                  <div className="font-mono text-[8px] uppercase tracking-wider mb-1" style={{ color: C.textSub }}>
                    {label}
                  </div>
                  <div className="font-mono text-xl font-bold" style={{ color: color || comparado.color }}>
                    {value}
                  </div>
                  <div className="font-mono text-[9px]" style={{ color: C.textSub }}>{unit}</div>
                </div>
              ))}
            </div>

            <div className="mt-4">
              <div className="flex justify-between font-mono text-[9px] mb-1.5" style={{ color: C.textSub }}>
                <span>0%</span>
                <span>Error: {comparado.errorPct.toFixed(1)}%</span>
                <span>20%+</span>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden relative" style={{ background: 'rgba(0,0,0,0.08)' }}>
                <div className="absolute inset-y-0 left-0 rounded-l-full"
                  style={{ width: '25%', background: 'rgba(82,217,160,0.3)' }} />
                <div className="h-full rounded-full transition-all duration-1000"
                  style={{ width: `${Math.min(comparado.errorPct * 5, 100)}%`, background: comparado.color }} />
                <div className="absolute inset-y-0 w-0.5" style={{ left: '25%', background: 'rgba(0,0,0,0.25)' }} />
              </div>
              <div className="font-mono text-[8px] mt-1" style={{ color: C.textSub }}>
                ← Zona ideal (≤ 5%) | Literatura científica Jersey: MAE ≈ 4–15 kg
              </div>
            </div>
          </div>

          <button type="button" onClick={resetComparador}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-mono text-[10px] font-bold uppercase tracking-widest border transition-all hover:bg-gray-50 active:scale-95"
            style={{ color: C.textSub, borderColor: 'rgba(27,67,50,0.15)' }}>
            <RotateCcw size={12} /> Ingresar otro peso real
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Tarjeta de validación por foto ──────────────────────────────────────
function ValidacionFotoCard({ titulo, resultado, onRetomar }) {
  if (!resultado) return null
  const { es_valida, animal_detectado, confianza_deteccion,
          area_cobertura, posicion_correcta, motivo, sugerencia } = resultado
  const confianzaNorm = normalizarConfianza(confianza_deteccion)
  const color  = es_valida ? C.accentDark : C.error
  const bg     = es_valida ? '#E8F8F1'    : C.errorBg
  const border = es_valida ? 'rgba(82,217,160,0.4)' : '#FECACA'
  const Icon   = es_valida ? ShieldCheck  : ShieldAlert
  return (
    <div className="rounded-2xl p-5 transition-all animate-in slide-in-from-top-2"
      style={{ background: bg, border: `1.5px solid ${border}` }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon size={16} style={{ color }} />
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest" style={{ color }}>
            {titulo}
          </span>
        </div>
        {!es_valida && (
          <button onClick={onRetomar}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-[9px] font-bold uppercase tracking-wider transition-all hover:scale-105 active:scale-95"
            style={{ background: C.primary, color: '#FFFFFF' }}>
            <RefreshCw size={10} /> Retomar
          </button>
        )}
      </div>
      <p className="font-sans text-[13px] font-medium mb-3 leading-relaxed" style={{ color: C.primary }}>
        {motivo}
      </p>
      {!es_valida && sugerencia && (
        <div className="flex items-start gap-2 p-3 rounded-xl mb-3"
          style={{ background: 'rgba(0,0,0,0.04)', border: '1px solid rgba(0,0,0,0.08)' }}>
          <Info size={13} style={{ color: C.primary, flexShrink: 0, marginTop: 1 }} />
          <span className="font-sans text-xs leading-relaxed" style={{ color: C.primary }}>{sugerencia}</span>
        </div>
      )}
      {animal_detectado && (
        <div className="flex gap-3 mt-2">
          {[
            { label: 'Confianza', value: `${confianzaNorm.toFixed(0)}%` },
            { label: 'Cobertura', value: `${(area_cobertura * 100).toFixed(0)}%` },
            { label: 'Postura',   value: posicion_correcta ? '✓ OK' : '✗ Error' },
          ].map(({ label, value }) => (
            <div key={label} className="flex-1 rounded-lg p-2.5 text-center"
              style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(0,0,0,0.06)' }}>
              <div className="font-mono text-[8px] uppercase tracking-wider mb-0.5" style={{ color: C.textSub }}>
                {label}
              </div>
              <div className="font-mono text-sm font-bold" style={{ color }}>{value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Badge de confianza ───────────────────────────────────────────────────
function ConfianzaBadge({ valor, umbral, label }) {
  const baja  = valor < umbral
  const media = !baja && valor < umbral + 15
  const color = baja ? C.error : media ? '#D97706' : C.accentDark
  const bg    = baja ? C.errorBg : media ? C.warningBg : '#E8F8F1'
  const bord  = baja ? '#FECACA' : media ? C.warningBorder : 'rgba(82,217,160,0.3)'
  const Icon  = baja ? ShieldAlert : media ? AlertTriangle : Check
  return (
    <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-wider"
      style={{ background: bg, color, border: `1px solid ${bord}` }}>
      <Icon size={12} strokeWidth={baja ? 2 : 3} />
      {label}: {valor.toFixed(1)}%
    </div>
  )
}

// ─── Silueta SVG lateral ──────────────────────────────────────────────────
const SiluetaLateral = ({ ok }) => {
  const cs = ok ? C.accent : C.textSub
  const cf = ok ? 'url(#gradA)' : 'url(#gradI)'
  return (
    <svg viewBox="0 0 320 190"
      className="absolute inset-0 w-full h-full pointer-events-none transition-colors duration-500"
      style={{ zIndex: 10 }}>
      <defs>
        <linearGradient id="gradA" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor="#52D9A0" stopOpacity="0.2"/>
          <stop offset="100%" stopColor="#1B4332" stopOpacity="0.05"/>
        </linearGradient>
        <linearGradient id="gradI" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor="#2A5C3A" stopOpacity="0.1"/>
          <stop offset="100%" stopColor="#2A5C3A" stopOpacity="0.02"/>
        </linearGradient>
      </defs>
      <rect x="15" y="15" width="290" height="160" rx="12" fill="none"
        stroke={cs} strokeWidth="2" strokeDasharray="8,5" opacity={ok ? 0.9 : 0.4}/>
      <path d="M60 70 C 70 50, 110 45, 150 45 S 230 55, 240 80 C 250 110, 245 140, 210 150 S 100 155, 70 140 S 50 100, 60 70 Z"
        fill={cf} stroke={cs} strokeWidth={ok ? "3" : "2"}/>
      <path d="M235 60 C 245 40, 275 35, 290 50 S 295 80, 280 90 S 245 85, 235 60 Z"
        fill={cf} stroke={cs} strokeWidth="2"/>
      <ellipse cx="285" cy="55" rx="3" ry="5" fill={cs} opacity={0.6}/>
      <path d="M110 148 C 120 165, 170 165, 180 148" fill="none" stroke={cs} strokeWidth="1.8" opacity={0.7}/>
      <rect x="200" y="135" width="12" height="40" rx="3" fill={cf} stroke={cs} strokeWidth="1.8"/>
      <rect x="218" y="132" width="12" height="40" rx="3" fill={cf} stroke={cs} strokeWidth="1.8"/>
      <rect x="75"  y="132" width="13" height="42" rx="3" fill={cf} stroke={cs} strokeWidth="1.8"/>
      <rect x="95"  y="135" width="13" height="42" rx="3" fill={cf} stroke={cs} strokeWidth="1.8"/>
      <g opacity={ok ? 1 : 0.25}>
        <line x1="235" y1="130" x2="65" y2="130" stroke="#3D6B9E" strokeWidth="2"/>
        <circle cx="235" cy="130" r="3" fill="#3D6B9E"/>
        <circle cx="65"  cy="130" r="3" fill="#3D6B9E"/>
        <text x="150" y="142" textAnchor="middle" fill="#3D6B9E" fontSize="9" fontWeight="800">LC</text>
        <line x1="190" y1="48" x2="190" y2="148" stroke={C.error} strokeWidth="2" strokeDasharray="4,2"/>
        <text x="196" y="95" fill={C.error} fontSize="9" fontWeight="800">PT</text>
      </g>
      <rect x="70" y="14" width="180" height="16" rx="5"
        fill={ok ? C.primary : 'rgba(255,255,255,0.85)'}/>
      <text x="160" y="25" textAnchor="middle"
        fill={ok ? C.accent : C.textSub}
        fontSize="9" fontFamily="Arial, Helvetica, sans-serif" fontWeight="700" letterSpacing="0.06em">
        {ok ? '✓ ALINEACIÓN CORRECTA' : 'AJUSTE LA VACA AL CONTORNO'}
      </text>
    </svg>
  )
}

// ─── Foto Lateral ─────────────────────────────────────────────────────────
function FotoLateral({ file, onChange, inputRef }) {
  const [preview, setPreview]     = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const galeriaRef                = useRef()

  useEffect(() => {
    if (!file) { setPreview(null); return }
    const url = URL.createObjectURL(file); setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  return (
    <>
      <ModalOpciones
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCamara={() => inputRef.current?.click()}
        onGaleria={() => galeriaRef.current?.click()}
      />

      <div>
        <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2"
          style={{ color: C.textSub }}>📸 Foto lateral (Perfil) *</label>

        <div
          onClick={() => setModalOpen(true)}
          className="relative rounded-2xl cursor-pointer overflow-hidden transition-all duration-300 group shadow-sm"
          style={{
            height: '220px',
            border: `2px dashed ${file ? C.accent : 'rgba(82,217,160,0.3)'}`,
            background: file ? '#1a2e20' : '#F9FDFB',
          }}
        >
          {preview && (
            <img src={preview} alt="lateral"
              className="absolute inset-0 w-full h-full object-cover"
              style={{ opacity: 0.85 }} />
          )}
          <SiluetaLateral ok={!!file} />

          {!preview && (
            <div className="absolute inset-0 flex flex-col items-center justify-end pb-8 z-20">
              <Camera size={26} style={{ color: C.accentDark }} className="mb-2 opacity-70" />
              <span className="font-mono text-[10px] px-4 py-1.5 rounded-md shadow-sm border"
                style={{ background: C.card, color: C.primary, borderColor: 'rgba(82,217,160,0.2)', fontWeight: 700 }}>
                TOMAR O SUBIR FOTO
              </span>
            </div>
          )}

          {preview && (
            <div className="absolute bottom-3 right-3 z-20">
              <span className="font-mono text-[10px] px-3 py-1.5 rounded-md backdrop-blur-md"
                style={{ background: 'rgba(255,255,255,0.9)', color: C.primary, border: `1px solid ${C.cardBorder}`, fontWeight: 700 }}>
                Cambiar Foto
              </span>
            </div>
          )}
        </div>

        {/* Input con capture → cámara */}
        <input
          ref={inputRef} type="file" accept="image/*" capture="environment"
          className="hidden"
          onChange={e => { onChange(e.target.files[0] || null); e.target.value = '' }}
        />
        {/* Input sin capture → galería */}
        <input
          ref={galeriaRef} type="file" accept="image/*"
          className="hidden"
          onChange={e => { onChange(e.target.files[0] || null); e.target.value = '' }}
        />
      </div>
    </>
  )
}

// ─── Foto Trasera ─────────────────────────────────────────────────────────
function FotoUpload({ label, hint, file, onChange, inputRef }) {
  const [preview, setPreview]     = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const galeriaRef                = useRef()

  useEffect(() => {
    if (!file) { setPreview(null); return }
    const url = URL.createObjectURL(file); setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  return (
    <>
      <ModalOpciones
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCamara={() => inputRef.current?.click()}
        onGaleria={() => galeriaRef.current?.click()}
      />

      <div>
        <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2"
          style={{ color: C.textSub }}>{label}</label>

        <div
          onClick={() => setModalOpen(true)}
          className="relative rounded-2xl cursor-pointer transition-all duration-300 overflow-hidden flex flex-col items-center justify-center text-center group shadow-sm"
          style={{
            height: '220px',
            border: `2px dashed ${file ? C.accent : 'rgba(82,217,160,0.3)'}`,
            background: file ? 'transparent' : '#F9FDFB',
          }}
        >
          {preview ? (
            <>
              <img src={preview} alt="trasera"
                className="absolute inset-0 w-full h-full object-cover"
                style={{ opacity: 0.9 }} />
              <div className="absolute bottom-3 right-3 z-20">
                <span className="font-mono text-[10px] px-3 py-1.5 rounded-md backdrop-blur-md"
                  style={{ background: 'rgba(255,255,255,0.9)', color: C.primary, border: `1px solid ${C.cardBorder}`, fontWeight: 700 }}>
                  Cambiar Foto
                </span>
              </div>
            </>
          ) : (
            <div className="p-5">
              <Camera size={26} style={{ color: C.accentDark }} className="mb-2 mx-auto opacity-70" />
              <span className="font-mono text-[10px] block mb-1 uppercase tracking-wider"
                style={{ color: C.primary, fontWeight: 700 }}>
                TOMAR O SUBIR FOTO
              </span>
              <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: C.textSub }}>
                {hint} · Vista posterior · Grupa centrada
              </span>
            </div>
          )}
        </div>

        {/* Input con capture → cámara */}
        <input
          ref={inputRef} type="file" accept="image/*" capture="environment"
          className="hidden"
          onChange={e => { onChange(e.target.files[0] || null); e.target.value = '' }}
        />
        {/* Input sin capture → galería */}
        <input
          ref={galeriaRef} type="file" accept="image/*"
          className="hidden"
          onChange={e => { onChange(e.target.files[0] || null); e.target.value = '' }}
        />
      </div>
    </>
  )
}

// ─── Buscador de vaca ─────────────────────────────────────────────────────
function BuscadorVaca({ onVacaResuelta }) {
  const [arete, setArete]                   = useState('')
  const [buscando, setBuscando]             = useState(false)
  const [vacaEncontrada, setVacaEncontrada] = useState(null)
  const [nombre, setNombre]                 = useState('')
  const [hatoId, setHatoId]                 = useState('')
  const [hatos, setHatos]                   = useState([])
  const debounceRef = useRef()

  useEffect(() => { hatosApi.listar().then(r => setHatos(r.data)).catch(() => {}) }, [])

  useEffect(() => {
    if (!arete.trim()) { setVacaEncontrada(null); onVacaResuelta(null); return }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setBuscando(true)
      try {
        const res = await animalesApi.buscarPorArete(arete.trim())
        if (res.data) { setVacaEncontrada(res.data); onVacaResuelta(res.data) }
        else { setVacaEncontrada(false); onVacaResuelta(null) }
      } catch { setVacaEncontrada(false); onVacaResuelta(null) }
      finally { setBuscando(false) }
    }, 600)
    return () => clearTimeout(debounceRef.current)
  }, [arete])

  const confirmarNueva = () => {
    if (!hatoId) return toast.error('Selecciona el hato para la nueva vaca')
    onVacaResuelta({ _nuevo: true, arete: arete.trim(), nombre: nombre.trim() || null, hato_id: hatoId })
    toast.success('Datos de vaca nueva listos')
  }

  const esNueva     = vacaEncontrada === false
  const esExistente = vacaEncontrada && vacaEncontrada !== false
  const inputClass  = "w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-mono text-sm"

  return (
    <div className="space-y-4">
      <div>
        <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2"
          style={{ color: C.textSub }}>Identificador Visual (Arete) *</label>
        <div className="relative">
          <input
            className={inputClass}
            style={{ borderColor: 'rgba(27,67,50,0.15)', background: '#F9FDFB', color: C.primary }}
            placeholder="Ej: 0045, AR-123…"
            value={arete}
            onChange={e => { setArete(e.target.value); setVacaEncontrada(null); onVacaResuelta(null) }}
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2">
            {buscando
              ? <div className="w-4 h-4 border-2 rounded-full animate-spin"
                  style={{ borderColor: C.accentDark, borderTopColor: 'transparent' }} />
              : esExistente
              ? <CheckCircle2 size={18} style={{ color: C.accentDark }} />
              : esNueva
              ? <Info size={18} style={{ color: C.warning }} />
              : <Search size={16} style={{ color: C.textSub }} />}
          </div>
        </div>
      </div>

      {esExistente && (
        <div className="flex items-center gap-4 p-4 rounded-xl"
          style={{ background: '#E8F8F1', border: 'rgba(82,217,160,0.3) 1px solid' }}>
          <Check size={20} style={{ color: C.accentDark }} strokeWidth={3} />
          <div>
            <div className="font-mono text-xs font-bold uppercase tracking-widest" style={{ color: C.primary }}>
              VACA REGISTRADA · {vacaEncontrada.arete}
            </div>
            <div className="font-sans text-[13px] font-medium mt-0.5" style={{ color: C.textSub }}>
              {vacaEncontrada.nombre || 'Sin nombre'}
              {vacaEncontrada.ultimo_peso_kg ? ` • ${vacaEncontrada.ultimo_peso_kg} kg` : ''}
              {vacaEncontrada.ultimo_bcs ? ` • BCS ${vacaEncontrada.ultimo_bcs.toFixed(1)}` : ''}
            </div>
          </div>
        </div>
      )}

      {esNueva && (
        <div className="space-y-4 p-5 rounded-2xl"
          style={{ background: '#F9FDFB', border: '1px solid rgba(27,67,50,0.1)' }}>
          <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-widest"
            style={{ color: C.primary }}>
            <UserPlus size={14} style={{ color: C.accentDark }} /> REGISTRO DE ANIMAL NUEVO
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2"
                style={{ color: C.textSub }}>Nombre (opcional)</label>
              <input className={inputClass}
                style={{ borderColor: 'rgba(27,67,50,0.15)', background: C.white, color: C.primary }}
                placeholder="Ej: Manchita" value={nombre} onChange={e => setNombre(e.target.value)} />
            </div>
            <div>
              <label className="block font-mono text-[10px] font-bold uppercase tracking-wider mb-2"
                style={{ color: C.textSub }}>Hato *</label>
              <div className="relative">
                <select
                  className={`${inputClass} appearance-none pr-8`}
                  style={{ borderColor: 'rgba(27,67,50,0.15)', background: C.white, color: C.primary }}
                  value={hatoId} onChange={e => setHatoId(e.target.value)}>
                  <option value="">— Seleccionar hato</option>
                  {hatos.map(h => (
                    <option key={h.id} value={h.id}>{h.nombre} ({h.finca})</option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: C.textSub }} />
              </div>
            </div>
          </div>
          <button type="button" onClick={confirmarNueva}
            className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-all active:scale-95"
            style={{ background: C.primary, color: '#FFFFFF' }}>
            <Check size={14} /> Confirmar datos
          </button>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// PÁGINA PRINCIPAL
// ─────────────────────────────────────────────────────────────────────────────
export default function AnalisisPage() {
  const [vacaResuelta, setVacaResuelta]         = useState(null)
  const [imgLateral, setImgLateral]             = useState(null)
  const [imgTrasera, setImgTrasera]             = useState(null)
  const [notas, setNotas]                       = useState('')
  const [resultado, setResultado]               = useState(null)
  const [isPending, setIsPending]               = useState(false)
  const [stepActivo, setStepActivo]             = useState(-1)
  const [modalGuiaAbierto, setModalGuiaAbierto] = useState(false)
  const [validandoFotos, setValidandoFotos]     = useState(false)
  const [validacion, setValidacion]             = useState(null)
  const animationAbortRef = useRef(false)
  const lateralRef        = useRef()   // → cámara foto lateral
  const traseraRef        = useRef()   // → cámara foto trasera

  useEffect(() => { setValidacion(null) }, [imgLateral, imgTrasera])

  const runAnimation = useCallback(async () => {
    animationAbortRef.current = false
    for (let i = 0; i < STEPS.length; i++) {
      if (animationAbortRef.current) break
      setStepActivo(i)
      await new Promise(r => setTimeout(r, 280))
    }
  }, [])

  const handleValidarFotos = async () => {
    if (!imgLateral) return toast.error('Necesitas la foto lateral primero')
    if (!imgTrasera) return toast.error('Necesitas la foto trasera primero')
    
    const [calLat, calTra] = await Promise.all([
      validarCalidadLocal(imgLateral), validarCalidadLocal(imgTrasera),
    ])
    
    if (!calLat.ok) return toast.error(`Foto lateral: ${calLat.motivo}`, { duration: 5000 })
    if (!calTra.ok) return toast.error(`Foto trasera: ${calTra.motivo}`, { duration: 5000 })
    
    setValidandoFotos(true); 
    setValidacion(null)
    
    try {
      const [latComp, traComp] = await Promise.all([
        comprimirImagen(imgLateral), comprimirImagen(imgTrasera),
      ])
      
      const fd = new FormData()
      fd.append('imagen_lateral', latComp)
      fd.append('imagen_trasera', traComp)
      
      // Invocar el endpoint de validación en el servidor
      const res = await analisisApi.validar(fd)
      
      // SI LLEGA AQUÍ: El backend respondió 200 OK (Pasó el escudo perfectamente)
      setValidacion(res.data)
      toast.success('Ambas fotos son aptas para el análisis', { icon: '✅' })
      
    } catch (err) {
      console.error('Error en el escudo de validación:', err)
      
      // 🛑 CAPTURAMOS EL ERROR 400 DEL ESCUDO DE IA
      if (err.response && err.response.status === 400) {
        const mensajeIA = err.response.data?.detail || 'Una o ambas fotos necesitan corrección';
        
        // Lanzamos la notificación flotante
        toast.error(mensajeIA, { icon: '⚠️', duration: 5000 })
        
        // 🔥 MEJORA DE UX: Alimentamos las tarjetas de validación con el error de la IA
        setValidacion({
          par_valido: false,
          lateral: {
            es_valida: false,
            animal_detectado: false,
            motivo: mensajeIA,
            sugerencia: "Por favor, asegúrese de capturar la silueta completa de la vaca Jersey según la guía."
          },
          trasera: {
            es_valida: false,
            animal_detectado: false,
            motivo: mensajeIA,
            sugerencia: "Verifique que la grupa esté centrada y que el lente de la cámara esté limpio."
          }
        })
      } else {
        // Errores genéricos de red o caída de servidor
        toast.error('Error de comunicación con el motor de validación', { icon: '❌' })
        setValidacion(null)
      }
    } finally { 
      setValidandoFotos(false) 
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!vacaResuelta) return toast.error('Ingrese el arete de la vaca')
    if (vacaResuelta._nuevo && !vacaResuelta.hato_id) return toast.error('Confirme los datos de la nueva vaca')
    if (!imgLateral) return toast.error('Suba la fotografía LATERAL')
    if (!imgTrasera) return toast.error('Suba la fotografía TRASERA')
    if (!validacion) return toast.error('Valida las fotos antes de iniciar el análisis', { duration: 4000 })
    if (!validacion.par_valido) return toast.error('Corrige las fotos con errores y valida de nuevo', { duration: 4000 })
    setResultado(null); setIsPending(true)
    try {
      const [apiResult] = await Promise.all([
        _llamarAPI(vacaResuelta, imgLateral, imgTrasera, notas),
        runAnimation(),
      ])
      setResultado(apiResult.data); setStepActivo(-1)
      toast.success('Análisis finalizado con éxito', { icon: '📊' })
    } catch (err) {
      animationAbortRef.current = true; setStepActivo(-1)
      toast.error(err.response?.data?.detail || 'Error en el motor de análisis AI', { icon: '❌' })
    } finally { setIsPending(false) }
  }

  const _llamarAPI = async (vaca, lateral, trasera, notas) => {
    let animalId = vaca.id
    if (vaca._nuevo) {
      const res = await animalesApi.crear({
        arete: vaca.arete, nombre: vaca.nombre || null,
        hato_id: vaca.hato_id, raza: 'Jersey',
      })
      animalId = res.data.id
    }
    const [latComp, traComp] = await Promise.all([comprimirImagen(lateral), comprimirImagen(trasera)])
    const fd = new FormData()
    fd.append('animal_id', animalId)
    fd.append('imagen_lateral', latComp)
    fd.append('imagen_trasera', traComp)
    if (notas) fd.append('notas', notas)
    return analisisApi.analizar(fd)
  }

  const reset = () => {
    setResultado(null); setImgLateral(null); setImgTrasera(null)
    setVacaResuelta(null); setNotas(''); setStepActivo(-1)
    setIsPending(false); setValidacion(null)
    animationAbortRef.current = true
  }

  const confianzaPeso = normalizarConfianza(resultado?.confianza_peso ?? resultado?.confianza)
  const confianzaBcs  = normalizarConfianza(resultado?.confianza_bcs  ?? resultado?.bcs_confianza)
  const bcsInfo       = resultado ? getBCSColor(resultado.bcs) : null
  const bcsTextColor  = bcsInfo?.bg === '#10B981' ? C.primary : '#FFFFFF'
  const bcsBgColor    = bcsInfo?.bg === '#10B981' ? '#D4ECD9' : bcsInfo?.bg

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto space-y-8 relative z-10 pb-12">

      {/* Header */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b pb-6"
        style={{ borderColor: 'rgba(27,67,50,0.1)' }}>
        <h1 style={{ fontFamily: F.brand, color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
          Nueva Estimación AI
        </h1>
        {resultado && (
          <button onClick={reset}
            className="flex items-center gap-2 px-6 py-3 rounded-xl font-mono text-[10px] font-bold uppercase tracking-widest bg-white hover:bg-gray-50 shadow-sm border border-gray-200"
            style={{ color: C.primary }}>
            <RotateCcw size={14} /> NUEVA ENTRADA
          </button>
        )}
      </header>

      {/* ── RESULTADOS ──────────────────────────────────────────────────── */}
      {resultado ? (
        <div className="space-y-6 animate-in zoom-in-95 duration-500">
          <div className="bg-white p-8 shadow-sm border border-emerald-50 rounded-[2rem]">

            {/* Encabezado reporte */}
            <div className="flex items-center gap-4 mb-6 pb-6 border-b border-[rgba(27,67,50,0.1)]">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: '#E8F8F1' }}>
                <CheckCircle2 size={24} style={{ color: C.accentDark }} />
              </div>
              <div className="flex-1">
                <div style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.5rem', fontWeight: 800 }}>
                  Reporte Finalizado
                </div>
                <div className="font-mono text-[11px] mt-1 uppercase tracking-wider" style={{ color: C.textSecondary }}>
                  ID: <span className="font-bold">{vacaResuelta?.arete}</span> · {resultado.procesado_en_segundos?.toFixed(1)}s
                </div>
              </div>
              <div className="hidden sm:flex flex-col gap-1.5 items-end">
                <ConfianzaBadge valor={confianzaPeso} umbral={PESO_CONFIDENCE_THRESHOLD} label="Peso" />
                <ConfianzaBadge valor={confianzaBcs}  umbral={BCS_CONFIDENCE_THRESHOLD}  label="BCS"  />
              </div>
            </div>

            {/* Cards principales */}
            <div className="grid md:grid-cols-2 gap-6 mb-8">
              {/* Peso */}
              <div className="rounded-[1.5rem] p-8 text-center"
                style={{ background: C.primary, boxShadow: '0 10px 30px rgba(8,28,17,0.15)' }}>
                <div className="font-mono text-[10px] uppercase tracking-widest mb-2"
                  style={{ color: C.accent, fontWeight: 700 }}>Peso Corporal Estimado</div>
                <div style={{ fontFamily: F.brand, fontSize: '4.5rem', fontWeight: 900, color: '#FFFFFF', lineHeight: 1 }}>
                  {resultado.peso_estimado_kg?.toFixed(0)}
                  <span style={{ fontSize: '2rem', color: C.accent, fontWeight: 700, marginLeft: '4px' }}>kg</span>
                </div>
                <div className="font-mono text-[10px] mt-3 uppercase tracking-wider"
                  style={{ color: 'rgba(255,255,255,0.7)' }}>
                  Confianza: {confianzaPeso.toFixed(1)}%
                </div>
                <div className="mt-3 h-1.5 rounded-full overflow-hidden relative"
                  style={{ background: 'rgba(255,255,255,0.15)' }}>
                  <div className="h-full rounded-full transition-all duration-1000"
                    style={{ width: `${confianzaPeso}%`, background: confianzaPeso >= PESO_CONFIDENCE_THRESHOLD ? C.accent : C.warning }} />
                  <div className="absolute inset-y-0 w-0.5"
                    style={{ left: `${PESO_CONFIDENCE_THRESHOLD}%`, background: 'rgba(255,255,255,0.4)' }} />
                </div>
                {confianzaPeso < PESO_CONFIDENCE_THRESHOLD && (
                  <div className="mt-2 font-mono text-[9px] font-bold" style={{ color: C.warning }}>
                    ⚠ Baja confianza — repita foto lateral
                  </div>
                )}
              </div>

              {/* BCS */}
              <div className="rounded-[1.5rem] p-8 text-center" style={{ background: bcsBgColor }}>
                <div className="font-mono text-[10px] uppercase tracking-widest mb-2"
                  style={{ color: bcsTextColor, fontWeight: 700 }}>Condición Corporal (BCS)</div>
                <div style={{ fontFamily: F.brand, fontSize: '4.5rem', fontWeight: 900, color: bcsTextColor, lineHeight: 1 }}>
                  {resultado.bcs?.toFixed(1)}
                </div>
                <div className="inline-block mt-3 px-4 py-1.5 rounded-lg font-mono text-[10px] font-bold shadow-sm"
                  style={{ background: 'rgba(255,255,255,0.9)', color: C.primary }}>
                  {getBCSLabel(resultado.bcs)}
                </div>
                <div className="font-mono text-[10px] mt-4 uppercase tracking-wider font-bold"
                  style={{ color: bcsTextColor, opacity: 0.85 }}>
                  Confianza: {confianzaBcs.toFixed(1)}%
                </div>
                <div className="mt-2 h-1.5 rounded-full overflow-hidden relative"
                  style={{ background: 'rgba(0,0,0,0.15)' }}>
                  <div className="h-full rounded-full transition-all duration-1000"
                    style={{ width: `${confianzaBcs}%`, background: confianzaBcs >= BCS_CONFIDENCE_THRESHOLD ? bcsTextColor : '#7F1D1D' }} />
                  <div className="absolute inset-y-0 w-0.5"
                    style={{ left: `${BCS_CONFIDENCE_THRESHOLD}%`, background: 'rgba(0,0,0,0.4)' }} />
                </div>
                {confianzaBcs < BCS_CONFIDENCE_THRESHOLD && (
                  <div className="mt-2 font-mono text-[10px] font-bold" style={{ color: '#7F1D1D' }}>
                    ⚠ BCS de baja confianza — repita foto trasera
                  </div>
                )}
              </div>
            </div>

            {/* Escala BCS */}
            <div className="mb-8 p-6 rounded-[1.5rem] bg-[#F9FDFB] border border-[rgba(27,67,50,0.1)]">
              <div className="font-mono text-[10px] text-center mb-4 font-bold uppercase tracking-widest"
                style={{ color: C.textSecondary }}>ESCALA JERSEY (1–5)</div>
              <div className="flex gap-2">
                {[1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5].map(n => {
                  const isActive = Math.abs(n - resultado.bcs) < 0.125
                  const isNear   = !isActive && Math.abs(n - resultado.bcs) <= 0.5
                  return (
                    <div key={n} className="flex-1 h-10 rounded-lg flex items-center justify-center font-mono text-xs transition-all relative"
                      style={{
                        background: isActive ? C.primary : isNear ? '#E8F8F1' : '#FFFFFF',
                        color: isActive ? C.accent : isNear ? C.accentDark : '#9CA3AF',
                        border: `1px solid ${isActive ? C.primary : isNear ? 'rgba(82,217,160,0.3)' : '#E5E7EB'}`,
                        fontWeight: isActive ? 800 : 600,
                        transform: isActive ? 'scale(1.1)' : 'none',
                        zIndex: isActive ? 2 : 1,
                        boxShadow: isActive ? '0 4px 12px rgba(8,28,17,0.2)' : 'none',
                      }}>
                      {n}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Recomendación */}
            <div className="rounded-[1.5rem] p-6 bg-white border border-emerald-100 relative overflow-hidden">
              <div className="absolute left-0 top-0 bottom-0 w-1"
                style={{ background: confianzaBcs < BCS_CONFIDENCE_THRESHOLD || confianzaPeso < PESO_CONFIDENCE_THRESHOLD ? C.warning : C.accent }} />
              <div className="flex items-center gap-2 mb-3">
                <Info size={16} style={{ color: C.accentDark }} />
                <div className="font-mono text-[10px] font-bold uppercase tracking-widest" style={{ color: C.accentDark }}>
                  Análisis Nutricional
                </div>
              </div>
              <div className="text-sm leading-relaxed font-sans font-medium" style={{ color: C.primary }}>
                "{resultado.recomendacion}"
              </div>
            </div>
          </div>

          {/* Morfometría */}
          {resultado.morfometria && (
            <div className="bg-white p-8 shadow-sm border border-emerald-50 rounded-[2rem]">
              <div className="flex items-center gap-3 mb-6 pb-4 border-b border-[rgba(27,67,50,0.1)]">
                <Scale size={20} style={{ color: C.accentDark }} />
                <h3 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.4rem', fontWeight: 800 }}>
                  Análisis Morfométrico
                </h3>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-5">
                {[
                  ['Largo corporal',     resultado.morfometria.largo_corporal_cm],
                  ['Alzada a la cruz',   resultado.morfometria.alzada_cm],
                  ['Perímetro torácico', resultado.morfometria.perimetro_toracico_cm],
                  ['Ancho de cadera',    resultado.morfometria.ancho_caderas_cm],
                  ['Profund. torácica',  resultado.morfometria.profundidad_toracica_cm],
                  ['Longitud de grupa',  resultado.morfometria.longitud_grupa_cm],
                ].map(([label, val]) => val ? (
                  <div key={label} className="rounded-xl p-5 bg-[#F9FDFB] border border-[rgba(27,67,50,0.1)]">
                    <div className="font-mono text-[10px] mb-1 uppercase tracking-widest font-bold"
                      style={{ color: C.textSecondary }}>{label}</div>
                    <div style={{ fontFamily: F.brand, fontSize: '1.6rem', fontWeight: 800, color: C.primary, lineHeight: 1 }}>
                      {val.toFixed(1)} <span className="font-mono text-xs" style={{ color: C.textSecondary }}>cm</span>
                    </div>
                  </div>
                ) : null)}
              </div>
            </div>
          )}

          {/* Comparador de peso real */}
          <ComparadorPesoReal pesoEstimado={resultado.peso_estimado_kg} />
        </div>

      ) : (
        /* ── FORMULARIO / ANIMACIÓN ──────────────────────────────────── */
        <div className="space-y-6">
          {isPending && (
            <div className="bg-white p-12 rounded-[2rem] shadow-xl border border-emerald-50 text-center animate-in zoom-in-95">
              <div className="flex flex-col items-center gap-8">
                <div className="relative w-24 h-24 flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full border-4 animate-spin"
                    style={{ borderColor: `${C.accent}20`, borderTopColor: C.accentDark, animationDuration: '1.5s' }} />
                  <Scale size={32} style={{ color: C.accentDark }} className="animate-pulse" />
                </div>
                <div className="w-full max-w-sm space-y-4 bg-[#F9FDFB] p-8 rounded-2xl border border-[rgba(27,67,50,0.1)]">
                  <div className="font-mono text-[10px] font-bold mb-4 uppercase tracking-widest" style={{ color: C.primary }}>
                    EJECUTANDO PIPELINE NEURAL
                  </div>
                  {STEPS.map((s, i) => {
                    const done   = i < stepActivo
                    const active = i === stepActivo
                    return (
                      <div key={s} className="flex items-center gap-4 font-mono text-[11px] transition-all"
                        style={{ color: done ? C.accentDark : active ? C.primary : '#9CA3AF', fontWeight: active ? 700 : 500, opacity: done || active ? 1 : 0.5 }}>
                        <div className="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center transition-all"
                          style={{ background: done ? '#E8F8F1' : active ? C.primary : 'transparent', border: `1px solid ${done ? C.accentDark : active ? C.primary : '#E5E7EB'}` }}>
                          {done
                            ? <Check size={10} style={{ color: C.accentDark }} strokeWidth={4} />
                            : <div className={`w-1.5 h-1.5 rounded-full ${active ? 'animate-pulse' : ''}`}
                                style={{ background: active ? C.accent : 'transparent' }} />}
                        </div>
                        {s}
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {!isPending && (
            <form onSubmit={handleSubmit} className="space-y-6">

              {/* Paso 1: Identificación */}
              <section className="bg-white p-8 rounded-[2rem] shadow-sm border border-emerald-50">
                <div className="flex items-center gap-3 mb-6 pb-4 border-b border-[rgba(27,67,50,0.1)]">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center font-mono text-[11px] font-bold"
                    style={{ background: '#E8F8F1', color: C.accentDark }}>1</div>
                  <h2 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.4rem', fontWeight: 800 }}>
                    Identificación Bovina
                  </h2>
                </div>
                <BuscadorVaca onVacaResuelta={setVacaResuelta} />
              </section>

              {/* Paso 2: Imágenes */}
              <section className="bg-white p-8 rounded-[2rem] shadow-sm border border-emerald-50">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-[rgba(27,67,50,0.1)]">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center font-mono text-[11px] font-bold"
                      style={{ background: '#E8F8F1', color: C.accentDark }}>2</div>
                    <h2 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.4rem', fontWeight: 800 }}>
                      Adquisición de Imágenes
                    </h2>
                  </div>
                  <button type="button" onClick={() => setModalGuiaAbierto(true)}
                    className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-mono text-[10px] font-bold uppercase tracking-widest border shadow-sm hover:-translate-y-0.5 transition-all"
                    style={{ color: C.accentDark, background: '#F9FDFB', borderColor: 'rgba(82,217,160,0.3)' }}>
                    <BookOpen size={14} /> ¿Cómo tomar fotos?
                  </button>
                </div>

                <div className="grid md:grid-cols-2 gap-8 mb-6">
                  <FotoLateral
                    file={imgLateral}
                    onChange={setImgLateral}
                    inputRef={lateralRef}
                  />
                  <FotoUpload
                    label="📸 Foto trasera (Grupa/BCS) *"
                    hint="Vista Posterior"
                    file={imgTrasera}
                    onChange={setImgTrasera}
                    inputRef={traseraRef}
                  />
                </div>

                {(imgLateral && imgTrasera) && (
                  <div className="space-y-4">
                    <button type="button" onClick={handleValidarFotos} disabled={validandoFotos}
                      className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-all border-2 hover:-translate-y-0.5 active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
                      style={{
                        background: validacion?.par_valido ? '#E8F8F1' : validacion && !validacion.par_valido ? C.errorBg : '#F9FDFB',
                        borderColor: validacion?.par_valido ? C.accentDark : validacion && !validacion.par_valido ? '#FECACA' : 'rgba(27,67,50,0.2)',
                        color: validacion?.par_valido ? C.accentDark : validacion && !validacion.par_valido ? C.error : C.primary,
                      }}>
                      {validandoFotos
                        ? <><Loader2 size={15} className="animate-spin" /> Analizando fotos con YOLOv8…</>
                        : validacion?.par_valido
                        ? <><ShieldCheck size={15} /> Fotos validadas — listas para el análisis</>
                        : validacion && !validacion.par_valido
                        ? <><RefreshCw size={15} /> Re-validar fotos corregidas</>
                        : <><ShieldCheck size={15} /> Validar calidad de fotos</>}
                    </button>

                    {validacion && (
                      <div className="grid md:grid-cols-2 gap-4 animate-in slide-in-from-top-2">
                        <ValidacionFotoCard
                          titulo="Foto Lateral"
                          resultado={validacion.lateral}
                          onRetomar={() => lateralRef.current?.click()}
                        />
                        <ValidacionFotoCard
                          titulo="Foto Trasera"
                          resultado={validacion.trasera}
                          onRetomar={() => traseraRef.current?.click()}
                        />
                      </div>
                    )}
                  </div>
                )}
              </section>

              {/* Paso 3: Notas */}
              <section className="bg-white p-8 rounded-[2rem] shadow-sm border border-emerald-50">
                <div className="flex items-center gap-3 mb-6 pb-4 border-b border-[rgba(27,67,50,0.1)]">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center font-mono text-[11px] font-bold"
                    style={{ background: '#E8F8F1', color: C.accentDark }}>3</div>
                  <h2 style={{ fontFamily: F.brand, color: C.primary, fontSize: '1.4rem', fontWeight: 800 }}>
                    Contexto de Campo (Opcional)
                  </h2>
                </div>
                <textarea
                  className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-sans text-sm resize-none"
                  rows={3}
                  style={{ borderColor: 'rgba(27,67,50,0.15)', background: '#F9FDFB', color: C.primary }}
                  placeholder="Ej: Vaca en periodo de lactancia, tomada post-ordeño…"
                  value={notas}
                  onChange={e => setNotas(e.target.value)}
                />
              </section>

              {/* Botón submit */}
              <div className="space-y-2">
                <button type="submit" disabled={!validacion?.par_valido}
                  className="w-full flex items-center justify-center gap-3 py-4 rounded-2xl font-mono text-xs font-bold uppercase tracking-widest transition-all shadow-lg hover:shadow-xl hover:-translate-y-1 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-lg"
                  style={{ background: C.primary, color: '#FFFFFF' }}>
                  <Scale size={18} style={{ color: validacion?.par_valido ? C.accent : 'rgba(255,255,255,0.4)' }} />
                  Estimar masa y BCS
                </button>
                {(!validacion || !validacion.par_valido) && imgLateral && imgTrasera && (
                  <p className="text-center font-mono text-[10px] uppercase tracking-wider" style={{ color: C.textSub }}>
                    {!validacion
                      ? '↑ Valida las fotos primero para habilitar el análisis'
                      : '↑ Corrige las fotos marcadas y re-valida para continuar'}
                  </p>
                )}
              </div>
            </form>
          )}
        </div>
      )}

      <GuiaCaptura open={modalGuiaAbierto} onClose={() => setModalGuiaAbierto(false)} />
    </div>
  )
}