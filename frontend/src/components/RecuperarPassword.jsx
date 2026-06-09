import { useState } from "react"
import { Link } from "react-router-dom"
import api from "../services/api"

export default function RecuperarPassword() {
  const [email, setEmail]     = useState("")
  const [mensaje, setMensaje] = useState("")
  const [cargando, setCargando] = useState(false)
  const [error, setError]     = useState("")

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMensaje("")
    setError("")
    if (!email) { setError("Por favor, ingresa tu correo electrónico."); return }

    setCargando(true)
    try {
      // ✅ Usa api.js en lugar de fetch hardcodeado
      await api.post("/auth/recuperar-password", { email })
      setMensaje("¡Listo! Si el correo está registrado, te enviamos un enlace para recuperar tu contraseña.")
      setEmail("")
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(detail || "Error de conexión con el servidor.")
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold" style={{ fontFamily: "Cambria, 'Times New Roman', serif", color: '#081C11' }}>
            Recuperar Contraseña
          </h2>
          <p className="mt-2 text-center text-sm" style={{ fontFamily: "Arial, Helvetica, sans-serif", color: '#2A5C3A' }}>
            Ingresa el correo de tu cuenta en JER-WEIGHT
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <input
            type="email"
            required
            className="appearance-none block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500 sm:text-sm"
            placeholder="ejemplo@correo.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          {error   && <p className="text-red-500 text-sm text-center font-medium">{error}</p>}
          {mensaje && <p className="text-emerald-600 text-sm text-center font-medium">{mensaje}</p>}

          <button
            type="submit"
            disabled={cargando}
            className="w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none disabled:opacity-50"
          >
            {cargando ? "Enviando enlace..." : "Enviar enlace de recuperación"}
          </button>

          <div className="text-center">
            <Link to="/login" className="font-medium text-emerald-600 hover:text-emerald-500 text-sm">
              Volver a Iniciar Sesión
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}