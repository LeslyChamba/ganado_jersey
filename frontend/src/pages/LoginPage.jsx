import { useState, useEffect } from 'react'
import { useNavigate,Link } from 'react-router-dom'
import { authApi } from '../services/api'
import useAuthStore from '../store/authStore'
import toast from 'react-hot-toast'
import { Eye, EyeOff, AlertTriangle, Lock, ArrowRight } from 'lucide-react'
import logoVacas from '../../img/Logo_vacas.png'

/* ── Tokens de color (Sincronizados con Layout) ── */
const C = {
  primary: '#081C11',
  accent: '#52D9A0',
  accentDark: '#1B4332',
  textSecondary: '#2A5C3A',
  bg: '#F0FBF6',
  white: '#FFFFFF',
  error: '#C0392B',
  warning: '#F5C542',
  warningText: '#856404'
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)

  const [bloqueado, setBloqueado] = useState(false)
  const [segundosBloqueo, setSegundosBloqueo] = useState(0)
  const [intentosRestantes, setIntentosRestantes] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!bloqueado || segundosBloqueo <= 0) return
    const interval = setInterval(() => {
      setSegundosBloqueo(s => {
        if (s <= 1) { setBloqueado(false); clearInterval(interval); return 0 }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [bloqueado, segundosBloqueo])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (bloqueado) return
    setErrorMsg('')
    setIntentosRestantes(null)
    setLoading(true)
    try {
      const res = await authApi.login(form.email, form.password)
      login(res.data.usuario, res.data.access_token)
      toast.success(`Bienvenida, ${res.data.usuario.nombre}`)
      
      const role = res.data.usuario.rol?.toUpperCase()
      if (role === 'ADMIN') {
        navigate('/admin/usuarios')
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail || 'Credenciales incorrectas'

      if (status === 429) {
        const match = detail.match(/(\d+)\s*segundos/)
        const secs = match ? parseInt(match[1]) : 900
        setBloqueado(true)
        setSegundosBloqueo(secs)
        setErrorMsg(detail)
      } else if (status === 401) {
        const match = detail.match(/Intentos restantes:\s*(\d+)/)
        if (match) {
          setIntentosRestantes(parseInt(match[1]))
          setErrorMsg('Correo o contraseña incorrectos.')
        } else {
          setErrorMsg(detail)
        }
      } else {
        setErrorMsg(detail)
      }
    } finally {
      setLoading(false)
    }
  }

  // Suponiendo que segundosBloqueo son, por ejemplo, 125
const minutos = Math.floor(segundosBloqueo / 60); // Resultado: 2
const segs = segundosBloqueo % 60;                // Resultado: 5 (lo que sobra de 120)

  return (
    <div className="min-h-screen flex" style={{ background: C.bg }}>
      
      {/* PANEL IZQUIERDO: Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-14"
        style={{ background: C.primary, borderRight: `1px solid ${C.accentDark}` }}>
        <div style={{
          fontFamily: 'Syne, sans-serif', color: C.accent,
          fontWeight: 800, letterSpacing: '0.1em', fontSize: '14px',
        }}>
          JER-WEIGHT
        </div>
        
        <div className="flex flex-col items-center gap-8">
          <div className="relative">
            <div className="absolute inset-0 bg-emerald-500/20 blur-3xl rounded-full" />
            <img src={logoVacas} className="w-80 relative z-10 drop-shadow-2xl" alt="Logo" />
          </div>
          <div className="text-center z-10">
            <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.white, fontSize: '2.8rem', fontWeight: 800, lineHeight: 1 }}>
              Criadero El Puente
            </h2>
            <p style={{ fontFamily: 'JetBrains Mono, monospace', color: C.accent, letterSpacing: '0.4em', fontSize: '0.75rem', marginTop: '1rem', opacity: 0.8 }}>
              RIOBAMBA · ECUADOR
            </p>
          </div>
        </div>

        <div style={{ fontFamily: 'JetBrains Mono, monospace', color: C.textSecondary, fontSize: '0.7rem', letterSpacing: '0.2em' }}>
          SISTEMA DE ESTIMACIÓN BOVINA
        </div>
      </div>

      {/* PANEL DERECHO: Formulario */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md p-10 rounded-[2rem]" style={{
          background: C.white,
          boxShadow: '0 20px 50px rgba(8, 28, 17, 0.05)',
          border: '1px solid rgba(82, 217, 160, 0.1)'
        }}>
          <header className="mb-10 text-center lg:text-left">
            <h1 style={{ fontFamily: 'Syne, sans-serif', fontSize: '2.2rem', fontWeight: 800, color: C.primary, marginBottom: '8px' }}>
              Bienvenido
            </h1>
            <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.75rem', letterSpacing: '0.1em', color: C.textSecondary }}>
              INGRESE SUS CREDENCIALES PARA CONTINUAR
            </p>
          </header>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1">
              <label style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.65rem', color: C.textSecondary, marginLeft: '4px', textTransform: 'uppercase', fontWeight: 700 }}>Correo Electrónico</label>
              <input
                type="email"
                placeholder="ejemplo@correo.com"
                className="w-full px-5 py-3.5 rounded-xl border focus:outline-none transition-all"
                style={{ 
                  background: '#F9FDFB',
                  borderColor: 'rgba(27, 67, 50, 0.1)',
                  fontFamily: 'sans-serif',
                  fontSize: '0.9rem'
                }}
                value={form.email}
                disabled={bloqueado}
                onChange={e => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>

            <div className="space-y-1">
              <label style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.65rem', color: C.textSecondary, marginLeft: '4px', textTransform: 'uppercase', fontWeight: 700 }}>Contraseña</label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  placeholder="••••••••"
                  className="w-full px-5 py-3.5 rounded-xl border focus:outline-none transition-all"
                  style={{ 
                    background: '#F9FDFB',
                    borderColor: 'rgba(27, 67, 50, 0.1)',
                    fontSize: '0.9rem'
                  }}
                  value={form.password}
                  disabled={bloqueado}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  required
                />
                <div className="flex justify-end pt-1">
                <Link 
                  to="/recuperarpassword" 
                  className="hover:opacity-70 transition-opacity"
                  style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.65rem', color: C.textSecondary, fontWeight: 700, textDecoration: 'underline' }}
                >
                  ¿OLVIDÓ SU CONTRASEÑA?
                </Link>
              </div>
                <button type="button" onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 hover:scale-110 transition-transform"
                  style={{ color: C.textSecondary }}>
                  {showPass ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>
              
            {/* Mensajes de Alerta */}
            {(errorMsg || bloqueado) && (
              <div className="rounded-xl px-4 py-4 flex items-start gap-3 animate-in fade-in slide-in-from-top-2"
                style={{ 
                  background: bloqueado ? '#FFFBEB' : '#FFF5F5', 
                  border: `1px solid ${bloqueado ? C.warning : '#FCA5A5'}` 
                }}>
                {bloqueado
                  ? <Lock size={16} style={{ color: C.warningText, marginTop: 2, flexShrink: 0 }} />
                  : <AlertTriangle size={16} style={{ color: C.error, marginTop: 2, flexShrink: 0 }} />
                }
                <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.75rem', color: bloqueado ? C.warningText : C.error, lineHeight: 1.4 }}>
                  {bloqueado ? (
                    <>
                      <strong>Acceso restringido.</strong><br />
                      Reintento disponible en: <span className="font-bold underline">{minutos}m {segs}s</span>
                    </>
                  ) : (
                    <>
                      {errorMsg}
                      {intentosRestantes !== null && (
                        <span className="block mt-1 font-bold">
                          Intentos antes del bloqueo: {intentosRestantes}
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Visualizador de intentos */}
            {intentosRestantes !== null && !bloqueado && (
              <div className="flex gap-1.5 px-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex-1 h-1.5 rounded-full transition-all duration-500"
                    style={{ background: i < intentosRestantes ? C.accent : '#EF4444', opacity: i < intentosRestantes ? 1 : 0.4 }} />
                ))}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || bloqueado}
              className="w-full py-4 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.2em] text-white mt-4 flex items-center justify-center gap-2 transition-all active:scale-95"
              style={{
                background: (loading || bloqueado) ? '#A0AEC0' : C.primary,
                boxShadow: (loading || bloqueado) ? 'none' : `0 10px 20px rgba(8, 28, 17, 0.2)`,
                cursor: (loading || bloqueado) ? 'not-allowed' : 'pointer',
              }}>
              {loading ? 'Procesando...' : bloqueado ? `BLOQUEADO` : (
                <>ENTRAR <ArrowRight size={16} /></>
              )}
            </button>
          </form>

          <footer className="mt-8 text-center">
            <p style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '0.65rem', color: C.textSecondary, opacity: 0.6 }}>
              SOPORTE TÉCNICO: CONTACTAR AL ADMINISTRADOR
            </p>
          </footer>
        </div>
      </div>
    </div>
  )
}