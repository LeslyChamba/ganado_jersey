import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Lock, CheckCircle } from "lucide-react";

export default function RestablecerPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token"); // Atrapa el código de la URL
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  const [exito, setExito] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setMensaje("");

    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setCargando(true);
    try {
      const respuesta = await fetch("http://localhost:8000/api/v1/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: token,
          nueva_password: password,
        }),
      });

      const datos = await respuesta.json();

      if (respuesta.ok) {
        setExito(true);
        setMensaje("¡Tu contraseña ha sido actualizada exitosamente!");
        setTimeout(() => navigate("/login"), 3000); // Redirige al login en 3 seg
      } else {
        setError(datos.detail || "El enlace es inválido o ya expiró.");
      }
    } catch (err) {
      setError("Error de conexión con el servidor.");
    } finally {
      setCargando(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F0FBF6]">
        <p className="text-red-500 font-bold">Error: No se encontró el token de seguridad en la URL.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F0FBF6] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-10 rounded-[2rem] shadow-[0_20px_50px_rgba(8,28,17,0.05)] border border-emerald-100">
        
        {exito ? (
          <div className="text-center space-y-4 animate-in fade-in zoom-in duration-500">
            <CheckCircle className="mx-auto h-16 w-16 text-emerald-500" />
            <h2 className="text-2xl font-extrabold text-[#081C11]" style={{ fontFamily: 'Syne, sans-serif' }}>
              ¡Contraseña Cambiada!
            </h2>
            <p className="text-[#2A5C3A] text-sm">Redirigiendo al inicio de sesión...</p>
          </div>
        ) : (
          <>
            <div className="text-center">
              <h2 className="text-3xl font-extrabold text-[#081C11]" style={{ fontFamily: 'Syne, sans-serif' }}>
                Nueva Contraseña
              </h2>
              <p className="mt-2 text-xs text-[#2A5C3A] uppercase tracking-wider font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                INGRESA TUS NUEVAS CREDENCIALES
              </p>
            </div>
            <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-[#2A5C3A] ml-1 uppercase font-bold tracking-wide" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    Nueva Contraseña
                  </label>
                  <div className="relative mt-1">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                    <input
                      type="password"
                      required
                      className="w-full pl-10 pr-4 py-3 rounded-xl border border-emerald-100 bg-[#F9FDFB] focus:outline-none focus:border-emerald-500"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-[#2A5C3A] ml-1 uppercase font-bold tracking-wide" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    Confirmar Contraseña
                  </label>
                  <div className="relative mt-1">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                    <input
                      type="password"
                      required
                      className="w-full pl-10 pr-4 py-3 rounded-xl border border-emerald-100 bg-[#F9FDFB] focus:outline-none focus:border-emerald-500"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg text-center font-medium">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={cargando}
                className="w-full py-4 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.2em] text-white bg-[#081C11] hover:bg-[#1B4332] transition-all disabled:opacity-50"
              >
                {cargando ? "GUARDANDO..." : "GUARDAR CONTRASEÑA"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}