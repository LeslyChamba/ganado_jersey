import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/api'
import useAuthStore from '../store/authStore'
import toast from 'react-hot-toast'
import { Eye, EyeOff } from 'lucide-react'
import logoVacas from '../../img/logo_vacas.png'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await authApi.login(form.email, form.password)
      login(res.data.usuario, res.data.access_token)
      toast.success(`Bienvenida, ${res.data.usuario.nombre}`)
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Credenciales incorrectas')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* PANEL IZQUIERDO */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-14"
        style={{ background: '#2E4D38' }}>

        <div style={{
          fontFamily: 'Syne, sans-serif',
          color: '#D4ECD9',
          fontWeight: 800,
          letterSpacing: '0.08em',
          fontSize: '13px',
        }}>
          JER-WEIGHT
        </div>

        <div className="flex flex-col items-center gap-6">
          <img
            src={logoVacas}
            className="w-72 drop-shadow-[0_25px_50px_rgba(0,0,0,0.25)]"
            alt="Logo Vacas"
          />

          <div className="text-center">
            <p style={{
              fontFamily: 'Syne, sans-serif',
              color: '#FFFFFF',
              fontSize: '2.3rem',
              fontWeight: 900,
              lineHeight: 1.1,
            }}>
              Criadero El Puente
            </p>

            <p style={{
              fontFamily: 'JetBrains Mono, monospace',
              color: '#89B99A',
              letterSpacing: '0.3em',
              fontSize: '0.72rem',
              marginTop: '0.6rem',
            }}>
              RIOBAMBA · ECUADOR
            </p>
          </div>
        </div>

        <div style={{
          fontFamily: 'JetBrains Mono, monospace',
          color: '#6B9E7A',
          fontSize: '0.68rem',
          letterSpacing: '0.2em',
        }}>
          SISTEMA DE ESTIMACIÓN BOVINA
        </div>
      </div>

      {/* PANEL DERECHO */}
      <div className="flex-1 flex items-center justify-center p-10"
        style={{ background: '#F5F0E8' }}>

        <div className="w-full max-w-sm p-10 rounded-3xl"
          style={{
            background: '#FFFFFF',
            border: '0.5px solid #E0D8C8',
            boxShadow: '0 4px 24px rgba(46,77,56,0.08)',
          }}>

          <h1 style={{
            fontFamily: 'Syne, sans-serif',
            fontSize: '2rem',
            fontWeight: 900,
            color: '#1A1A1A',
            marginBottom: '4px',
          }}>
            Iniciar sesión
          </h1>

          <p style={{
            fontFamily: 'JetBrains Mono, monospace',
            fontSize: '0.72rem',
            letterSpacing: '0.18em',
            color: '#8B7D6B',
            marginBottom: '2rem',
          }}>
            ACCESO AL SISTEMA
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="email"
              placeholder="Correo"
              className="input"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })}
            />

            <div className="relative">
              <input
                type={showPass ? 'text' : 'password'}
                placeholder="Contraseña"
                className="input pr-10"
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
              />
              <button
                type="button"
                onClick={() => setShowPass(!showPass)}
                className="absolute right-3 top-1/2 -translate-y-1/2"
                style={{ color: '#B0A090' }}>
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl font-mono text-xs uppercase tracking-widest text-white mt-2 transition-all"
              style={{
                background: loading ? '#89B99A' : '#5C8B6A',
                boxShadow: '0 4px 14px rgba(92,139,106,0.25)',
              }}>
              {loading ? 'Ingresando…' : 'INGRESAR'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}