import { useState } from "react";

export default function RecuperarPassword() {
  const [email, setEmail] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMensaje("");
    setError("");

    if (!email) {
      setError("Por favor, ingresa tu correo electrónico.");
      return;
    }

    setCargando(true);
    try {
      // Ajusta esta URL si tu backend corre en otro puerto (ej. localhost:8000)
       const respuesta = await fetch("http://localhost:8000/api/v1/auth/recuperar-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email }),
      });

      const datos = await respuesta.json();

      if (respuesta.ok) {
        setMensaje("¡Listo! Si el correo está registrado, te enviamos un enlace para recuperar tu contraseña.");
        setEmail(""); // Limpiar el campo
      } else {
        // Manejar errores del backend si es necesario (aunque configuramos para que siempre diga éxito)
        setError(datos.detail || "Ocurrió un error. Inténtalo de nuevo.");
      }
    } catch (err) {
      setError("Error de conexión con el servidor.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Recuperar Contraseña
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Ingresa el correo de tu cuenta en JER-WEIGHT
          </p>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="email-address" className="sr-only">
                Correo electrónico
              </label>
              <input
                id="email-address"
                name="email"
                type="email"
                autoComplete="email"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md rounded-b-md focus:outline-none focus:ring-emerald-500 focus:border-emerald-500 focus:z-10 sm:text-sm"
                placeholder="ejemplo@correo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          {error && <p className="text-red-500 text-sm text-center font-medium">{error}</p>}
          {mensaje && <p className="text-emerald-600 text-sm text-center font-medium">{mensaje}</p>}

          <div>
            <button
              type="submit"
              disabled={cargando}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-emerald-600 hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 disabled:opacity-50"
            >
              {cargando ? "Enviando enlace..." : "Enviar enlace de recuperación"}
            </button>
          </div>
          
          <div className="text-center mt-4">
             {/* Cambia el href a donde esté tu login real */}
             <a href="/login" className="font-medium text-emerald-600 hover:text-emerald-500 text-sm">
                Volver a Iniciar Sesión
             </a>
          </div>
        </form>
      </div>
    </div>
  );
}