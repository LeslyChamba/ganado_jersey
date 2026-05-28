// src/components/admin/UsuarioModal.jsx
// Modal reutilizable para CREAR y EDITAR usuarios
// Props:
//   abierto   {boolean}          – muestra u oculta el modal
//   usuario   {object|null}      – null = crear, objeto = editar
//   onGuardar {fn(datos)}        – callback al guardar
//   onCerrar  {fn()}             – callback al cancelar

import { useEffect, useState } from "react";

const ROLES = [
  { value: "GANADERO", label: "Ganadero" },
  { value: "ADMIN",    label: "Administrador" },
];

const camposVacios = {
  nombre:   "",
  apellido: "",
  email:    "",
  telefono: "",
  rol:      "GANADERO",
  password: "",
};

export default function UsuarioModal({ abierto, usuario, onGuardar, onCerrar }) {
  const [form,    setForm]    = useState(camposVacios);
  const [errores, setErrores] = useState({});
  const [cargando, setCargando] = useState(false);

  const esEdicion = Boolean(usuario);

  // Cargar datos al abrir
  useEffect(() => {
    if (abierto) {
      setForm(
        usuario
          ? { ...camposVacios, ...usuario, password: "" }
          : camposVacios
      );
      setErrores({});
    }
  }, [abierto, usuario]);

  function cambiar(e) {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
    if (errores[name]) setErrores(e => ({ ...e, [name]: undefined }));
  }

  function validar() {
    const e = {};
    if (!form.nombre.trim())   e.nombre   = "El nombre es obligatorio";
    if (!form.apellido.trim()) e.apellido = "El apellido es obligatorio";
    if (!form.email.trim())    e.email    = "El correo es obligatorio";
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = "Correo no válido";
    if (!esEdicion){
      // Usamos .trim() por si el usuario pone solo espacios en blanco por error
      if (form.password.trim().length < 8) {
        e.password = "La contraseña debe tener al menos 8 caracteres";
      }
    }
    return e;
  }

  async function submit(e) {
    e.preventDefault();
    const e2 = validar();
    if (Object.keys(e2).length) { setErrores(e2); return; }
    setCargando(true);
    try {
      const datos = esEdicion
        ? { nombre: form.nombre, apellido: form.apellido,
            email:  form.email,  telefono: form.telefono }
        : { ...form };
      // En edición no mandamos password vacío
      if (esEdicion) delete datos.password;
      await onGuardar(datos);
    } finally {
      setCargando(false);
    }
  }

  if (!abierto) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCerrar}
      />

      {/* Panel */}
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden">
        {/* Cabecera */}
        <div className="px-6 py-5" style={{ background: '#F9FDFB', borderBottom: '1px solid rgba(82,217,160,0.2)' }}>
          <h2 className="font-bold text-xl" style={{ fontFamily: "Cambria, 'Times New Roman', serif", color: '#081C11' }}>
            {esEdicion ? "Editar usuario" : "Nuevo usuario"}
          </h2>
          <p className="text-sm mt-0.5" style={{ fontFamily: "Arial, Helvetica, sans-serif", color: '#2A5C3A' }}>
            {esEdicion
              ? "Modifica los datos básicos del usuario"
              : "Completa el formulario para crear la cuenta"}
          </p>
        </div>

        {/* Formulario */}
        <form onSubmit={submit} className="p-6 space-y-4">
          {/* Nombre + Apellido */}
          <div className="grid grid-cols-2 gap-4">
            <Campo
              label="Nombre" name="nombre" value={form.nombre}
              onChange={cambiar} error={errores.nombre}
            />
            <Campo
              label="Apellido" name="apellido" value={form.apellido}
              onChange={cambiar} error={errores.apellido}
            />
          </div>

          {/* Email */}
          <Campo
            label="Correo electrónico" name="email" type="email"
            value={form.email} onChange={cambiar} error={errores.email}
          />

          {/* Teléfono */}
          <Campo
            label="Teléfono (opcional)" name="telefono" type="tel"
            value={form.telefono} onChange={cambiar}
          />

          {/* Rol — solo al crear */}
          {!esEdicion && (
            <div>
              <label className="block text-sm font-semibold mb-1.5" style={{ fontFamily: "Arial, Helvetica, sans-serif", color: '#2A5C3A' }}>
                Rol
              </label>
              <select
                name="rol"
                value={form.rol}
                onChange={cambiar}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm
                           bg-gray-50 focus:outline-none focus:ring-2 focus:ring-emerald-400
                           focus:border-transparent transition"
              >
                {ROLES.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
          )}

          {/* Contraseña — solo al crear */}
          {!esEdicion && (
            <Campo
              label="Contraseña" name="password" type="password"
              value={form.password} onChange={cambiar} error={errores.password}
              placeholder="Mínimo 8 caracteres"
            />
          )}

          {/* Acciones */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onCerrar}
              className="flex-1 border rounded-xl py-2.5 text-sm font-semibold transition hover:bg-gray-50"
              style={{ fontFamily: "Arial, Helvetica, sans-serif", color: '#081C11', borderColor: '#E5E7EB' }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={cargando}
              className="flex-1 rounded-xl py-2.5 text-sm font-semibold transition text-white disabled:opacity-60 disabled:cursor-not-allowed"
              style={{ fontFamily: "Arial, Helvetica, sans-serif", background: '#081C11' }}
            >
              {cargando ? "Guardando…" : esEdicion ? "Guardar cambios" : "Crear usuario"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Campo reutilizable ────────────────────────────────────────────────────────
function Campo({ label, name, value, onChange, error, type = "text", placeholder }) {
  return (
    <div>
      <label className="block text-sm font-semibold mb-1.5" style={{ fontFamily: "Arial, Helvetica, sans-serif", color: '#2A5C3A' }}>
        {label}
      </label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={`w-full border rounded-xl px-3 py-2.5 text-sm bg-gray-50
                    focus:outline-none focus:ring-2 focus:ring-emerald-400
                    focus:border-transparent transition
                    ${error ? "border-red-400 bg-red-50" : "border-gray-200"}`}
      />
      {error && <p className="text-red-500 text-xs mt-1">{error}</p>}
    </div>
  );
}