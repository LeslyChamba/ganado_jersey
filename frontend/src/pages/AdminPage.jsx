// src/pages/AdminPage.jsx
import { useCallback, useEffect, useMemo, useState } from "react";
import UsuarioModal from "../components/admin/usuariomodal";
import {
  actualizarUsuario, cambiarEstado, cambiarRol,
  crearUsuario, eliminarUsuario, listarUsuarios,
} from "../services/adminService";
import { Search, Plus, Loader2, CheckCircle2, XCircle, Trash2, Edit2, Shield, Users, RefreshCcw, UserX } from 'lucide-react';

/* ── Tokens de color de la marca JER-WEIGHT ── */
const C = {
  primary: '#081C11', accent: '#52D9A0', accentDark: '#1B4332',
  textSecondary: '#2A5C3A', bg: '#F0FBF6', white: '#FFFFFF', danger: '#EF4444', warning: '#F59E0B'
}

const ROL_BADGE = {
  admin:    { bg: '#E8F8F1', text: C.accentDark, label: 'Administrador' },
  ganadero: { bg: '#F9FDFB', text: C.textSecondary, label: 'Ganadero', border: '1px solid rgba(82,217,160,0.3)' },
  ADMIN:    { bg: '#E8F8F1', text: C.accentDark, label: 'Administrador' },
  GANADERO: { bg: '#F9FDFB', text: C.textSecondary, label: 'Ganadero', border: '1px solid rgba(82,217,160,0.3)' },
}

export default function AdminPage() {
  const [usuarios,    setUsuarios]    = useState([]);
  const [cargando,    setCargando]    = useState(true);
  const [error,       setError]       = useState(null);

  const [filtroBuscar, setFiltroBuscar] = useState("");
  const [filtroRol,    setFiltroRol]    = useState("");
  const [filtroActivo, setFiltroActivo] = useState("");

  const [modalAbierto,   setModalAbierto]   = useState(false);
  const [usuarioEditando, setUsuarioEditando] = useState(null);
  const [confirmEliminar, setConfirmEliminar] = useState(null);
  const [toast, setToast] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true); setError(null);
    try {
      const data = await listarUsuarios({ rol: filtroRol, activo: filtroActivo, buscar: filtroBuscar });
      setUsuarios(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, [filtroRol, filtroActivo, filtroBuscar]);

  useEffect(() => { cargar(); }, [cargar]);

  function mostrarToast(msg, tipo = "ok") {
    setToast({ msg, tipo });
    setTimeout(() => setToast(null), 3500);
  }

  function abrirCrear() { setUsuarioEditando(null); setModalAbierto(true); }
  function abrirEditar(u) { setUsuarioEditando(u); setModalAbierto(true); }

  async function handleGuardar(datos) {
    try {
      if (usuarioEditando) {
        await actualizarUsuario(usuarioEditando.id, datos)
        mostrarToast('Usuario actualizado correctamente')
      } else {
        await crearUsuario(datos)
        mostrarToast('Usuario creado correctamente')
      }
      setModalAbierto(false)
      cargar()
    } catch (e) {
      mostrarToast(e.response?.data?.detail || e.message, 'error')
    }
  }

  async function handleToggleEstado(u) {
    try {
      await cambiarEstado(u.id, !u.activo)
      mostrarToast(`Cuenta ${!u.activo ? 'activada' : 'desactivada'}`)
      cargar()
    } catch (e) {
      mostrarToast(e.response?.data?.detail || e.message, 'error')
    }
  }

  async function handleCambiarRol(u) {
    const rolActual = u.rol.toLowerCase()
    const nuevoRol  = rolActual === 'admin' ? 'ganadero' : 'admin'
    try {
      await cambiarRol(u.id, nuevoRol)
      mostrarToast(`Rol cambiado a ${ROL_BADGE[nuevoRol].label}`)
      cargar()
    } catch (e) {
      mostrarToast(e.response?.data?.detail || e.message, 'error')
    }
  }

  async function handleEliminar() {
    if (!confirmEliminar) return;
    try {
      await eliminarUsuario(confirmEliminar.id);
      mostrarToast("Usuario eliminado permanentemente");
      setConfirmEliminar(null);
      cargar();
    } catch (e) {
      mostrarToast(e.response?.data?.detail || e.message, "error");
      setConfirmEliminar(null);
    }
  }

  const stats = useMemo(() => ({
    total:     usuarios.length,
    admins:    usuarios.filter(u => u.rol === 'admin'    || u.rol === 'ADMIN').length,
    ganaderos: usuarios.filter(u => u.rol === 'ganadero' || u.rol === 'GANADERO').length,
    inactivos: usuarios.filter(u => !u.activo).length,
  }), [usuarios])

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-8 relative z-10">

      {/* TOAST PERSONALIZADO */}
      {toast && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl animate-in slide-in-from-top-4 fade-in duration-300"
          style={{ background: toast.tipo === 'error' ? '#FEF2F2' : C.primary, border: `1px solid ${toast.tipo === 'error' ? '#FCA5A5' : C.accentDark}` }}>
          {toast.tipo === 'error' ? <XCircle size={20} color={C.danger} /> : <CheckCircle2 size={20} color={C.accent} />}
          <span className="font-mono text-[11px] font-bold uppercase tracking-wider" style={{ color: toast.tipo === 'error' ? C.danger : C.white }}>
            {toast.msg}
          </span>
        </div>
      )}

      {/* ── HEADER ── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '2.2rem', fontWeight: 800, lineHeight: 1.1 }}>
            Gestión de Usuarios
          </h1>
          <p className="font-mono text-[11px] mt-2 font-bold tracking-widest uppercase" style={{ color: C.textSecondary }}>
            Administración de accesos y roles del sistema
          </p>
        </div>
        <button onClick={abrirCrear} 
          className="flex items-center gap-2 px-5 py-3 rounded-xl font-mono text-sm font-bold uppercase tracking-[0.1em] text-white transition-all hover:scale-105 active:scale-95 shadow-lg w-full sm:w-auto justify-center"
          style={{ background: C.primary }}>
          <Plus size={16} color={C.accent} /> Nuevo Usuario
        </button>
      </div>

      {/* ── TARJETAS DE RESUMEN (KPIs) ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
        {[
          { label: "Total Usuarios", valor: stats.total,     icon: Users,  color: C.primary,    bg: '#E8F8F1' },
          { label: "Administradores",valor: stats.admins,    icon: Shield, color: C.accentDark, bg: '#EAF4EE' },
          { label: "Ganaderos",      valor: stats.ganaderos, icon: Users,  color: C.textSecondary, bg: '#F9FDFB', border: true },
          { label: "Cuentas Inactivas",valor: stats.inactivos, icon: UserX,  color: C.warning,    bg: '#FFFBEB' },
        ].map((s, i) => (
          <div key={s.label} className="bg-white rounded-[1.5rem] p-6 relative overflow-hidden transition-all duration-300"
            style={{ boxShadow: '0 10px 30px rgba(8, 28, 17, 0.04)', border: s.border ? '1px solid rgba(82,217,160,0.15)' : '1px solid transparent', animationDelay: `${i * 100}ms` }}>
            <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-inner mb-4" style={{ background: s.bg }}>
              <s.icon size={20} style={{ color: s.color }} />
            </div>
            <div style={{ fontFamily: 'Syne, sans-serif', color: s.color, fontSize: '2rem', fontWeight: 800, lineHeight: 1 }}>{s.valor}</div>
            <div className="font-mono text-[10px] mt-2 font-bold uppercase tracking-wider" style={{ color: C.textSecondary }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── FILTROS ── */}
      <div className="bg-white rounded-[1.5rem] p-6 shadow-sm border border-emerald-50">
        <div className="flex items-center gap-2 font-mono text-[11px] font-bold uppercase tracking-widest mb-4" style={{ color: C.accentDark }}>
           Filtros de Búsqueda
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-[2fr_1fr_1fr] gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2" style={{ color: C.textSecondary }} />
            <input type="text" placeholder="Buscar por nombre, correo o arete..." value={filtroBuscar} onChange={e => setFiltroBuscar(e.target.value)}
              className="w-full pl-11 pr-4 py-3 rounded-xl border focus:outline-none transition-all font-sans font-medium"
              style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }} />
          </div>
          <select value={filtroRol} onChange={e => setFiltroRol(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-mono text-[11px] font-bold uppercase tracking-wider"
            style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }}>
            <option value="">Todos los roles</option>
            <option value="ADMIN">Administradores</option>
            <option value="GANADERO">Ganaderos</option>
          </select>
          <select value={filtroActivo} onChange={e => setFiltroActivo(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border focus:outline-none transition-all font-mono text-[11px] font-bold uppercase tracking-wider"
            style={{ background: '#F9FDFB', borderColor: 'rgba(27, 67, 50, 0.15)', color: C.primary }}>
            <option value="">Todos los estados</option>
            <option value="true">Solo Activos</option>
            <option value="false">Solo Inactivos</option>
          </select>
        </div>
      </div>

      {/* ── TABLA DE USUARIOS ── */}
      <div className="bg-white rounded-[1.5rem] border border-[rgba(82,217,160,0.15)] shadow-sm overflow-hidden">
        {cargando ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="animate-spin" size={32} style={{ color: C.accentDark }} />
            <span className="font-mono text-xs font-bold uppercase tracking-widest" style={{ color: C.textSecondary }}>Cargando usuarios...</span>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-2"><XCircle size={32} color={C.danger}/></div>
            <p className="font-sans font-bold" style={{ color: C.danger }}>{error}</p>
            <button onClick={cargar} className="font-mono text-xs font-bold uppercase tracking-widest underline" style={{ color: C.primary }}>Reintentar</button>
          </div>
        ) : usuarios.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <div className="w-16 h-16 bg-[#E8F8F1] rounded-full flex items-center justify-center mb-2"><Users size={32} color={C.accentDark}/></div>
            <p className="font-sans font-bold text-lg" style={{ color: C.primary }}>No se encontraron usuarios</p>
            <p className="font-mono text-xs" style={{ color: C.textSecondary }}>Ajusta los filtros de búsqueda e intenta de nuevo.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[800px]">
              {/* Encabezado */}
              <div className="grid grid-cols-[2fr_2fr_1fr_1fr_1.5fr_auto] gap-4 px-6 py-4" style={{ background: '#F9FDFB', borderBottom: '1px solid rgba(82, 217, 160, 0.2)' }}>
                {['Usuario', 'Correo Electrónico', 'Rol', 'Estado', 'Actividad', 'Acciones'].map(h => (
                  <span key={h} className="font-mono text-[10px] uppercase font-bold tracking-widest" style={{ color: C.textSecondary }}>{h}</span>
                ))}
              </div>
              {/* Filas */}
              <ul className="divide-y divide-[rgba(8,28,17,0.05)]">
                {usuarios.map(u => (
                  <FilaUsuario key={u.id} usuario={u} onEditar={() => abrirEditar(u)} onToggleEstado={() => handleToggleEstado(u)} onCambiarRol={() => handleCambiarRol(u)} onEliminar={() => setConfirmEliminar(u)} />
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* ── MODALES ── */}
      <UsuarioModal abierto={modalAbierto} usuario={usuarioEditando} onGuardar={handleGuardar} onCerrar={() => setModalAbierto(false)} />

      {/* Modal Eliminar */}
      {confirmEliminar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[rgba(8,28,17,0.6)] backdrop-blur-sm animate-in fade-in">
          <div className="w-full max-w-sm bg-white rounded-[2rem] p-8 text-center shadow-2xl animate-in zoom-in-95">
            <div className="w-16 h-16 bg-red-50 text-red-500 rounded-full flex items-center justify-center mx-auto mb-4"><Trash2 size={28} /></div>
            <h2 style={{ fontFamily: 'Syne, sans-serif', color: C.primary, fontSize: '1.5rem', fontWeight: 800, marginBottom: '8px' }}>¿Eliminar usuario?</h2>
            <p className="font-mono text-sm mb-6" style={{ color: C.primary }}>
              Se eliminará a <strong style={{ color: C.danger }}>{confirmEliminar.nombre} {confirmEliminar.apellido}</strong>. Esta acción no se puede deshacer.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmEliminar(null)} className="flex-1 py-3.5 rounded-xl font-mono text-xs font-bold uppercase tracking-widest transition-colors hover:bg-gray-100" style={{ color: C.primary, border: '1px solid #E5E7EB' }}>Cancelar</button>
              <button onClick={handleEliminar} className="flex-1 py-3.5 rounded-xl font-mono text-xs font-bold uppercase tracking-widest text-white transition-all shadow-md hover:shadow-lg hover:scale-105 active:scale-95" style={{ background: C.danger }}>Eliminar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
function FilaUsuario({ usuario: u, onEditar, onToggleEstado, onCambiarRol, onEliminar }) {
  const iniciales = `${u.nombre?.[0]||''}${u.apellido?.[0]||''}`.toUpperCase() || 'U';
  const rolStyle = ROL_BADGE[u.rol] || ROL_BADGE.ganadero;

  return (
    <li className="grid grid-cols-[2fr_2fr_1fr_1fr_1.5fr_auto] gap-4 px-6 py-4 items-center transition-colors hover:bg-[#F0FBF6] group">
      
      {/* Avatar + nombre */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-mono text-sm font-bold shadow-inner flex-shrink-0"
          style={{ background: u.activo ? '#E8F8F1' : '#F3F4F6', color: u.activo ? C.accentDark : '#9CA3AF' }}>
          {iniciales}
        </div>
        <div className="min-w-0">
          <p className="font-sans text-sm font-bold truncate" style={{ color: u.activo ? C.primary : '#9CA3AF' }}>
            {u.nombre} {u.apellido}
          </p>
          {u.telefono && <p className="font-mono text-[10px] text-gray-400 mt-0.5">{u.telefono}</p>}
        </div>
      </div>

      {/* Email */}
      <p className="font-mono text-xs text-gray-500 truncate pr-4">{u.email}</p>

      {/* Rol */}
      <div>
        <span className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest"
          style={{ background: rolStyle.bg, color: rolStyle.text, border: rolStyle.border || 'none' }}>
          {rolStyle.label}
        </span>
      </div>

      {/* Estado toggle */}
      <div>
        <button onClick={onToggleEstado} title={u.activo ? "Clic para desactivar" : "Clic para activar"}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-[10px] font-bold uppercase tracking-widest transition-all"
          style={{ 
            background: u.activo ? '#E8F8F1' : '#F3F4F6', 
            color: u.activo ? C.accentDark : '#6B7280',
            border: u.activo ? `1px solid rgba(82,217,160,0.3)` : '1px solid #E5E7EB'
          }}>
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: u.activo ? C.accent : '#9CA3AF' }} />
          {u.activo ? "Activo" : "Inactivo"}
        </button>
      </div>

      {/* Actividad */}
      <div className="flex flex-col gap-1">
        <span className="font-mono text-[10px] uppercase font-bold tracking-wider" style={{ color: C.textSecondary }}>{u.total_animales || 0} Animales</span>
        <span className="font-mono text-[10px] uppercase font-bold tracking-wider text-gray-400">{u.total_mediciones || 0} Análisis</span>
      </div>

      {/* Acciones */}
      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <IconBtn onClick={onEditar} title="Editar datos" hoverColor={C.accentDark} hoverBg="#E8F8F1"><Edit2 size={16} /></IconBtn>
        <IconBtn onClick={onCambiarRol} title="Cambiar Rol" hoverColor="#6D28D9" hoverBg="#F5F3FF"><RefreshCcw size={16} /></IconBtn>
        <IconBtn onClick={onToggleEstado} title={u.activo ? "Inactivar Cuenta" : "Activar Cuenta"} hoverColor={u.activo ? C.warning : C.accent} hoverBg={u.activo ? "#FFFBEB" : "#E8F8F1"}>{u.activo ? <UserX size={16} /> : <CheckCircle2 size={16} />}</IconBtn>
        <IconBtn onClick={onEliminar} title="Eliminar" hoverColor={C.danger} hoverBg="#FEF2F2"><Trash2 size={16} /></IconBtn>
      </div>
    </li>
  );
}

// ── Botón icono ───────────────────────────────────────────────────────────────
function IconBtn({ children, onClick, title, hoverColor, hoverBg }) {
  return (
    <button onClick={onClick} title={title}
      className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 transition-colors"
      onMouseOver={e => { e.currentTarget.style.color = hoverColor; e.currentTarget.style.background = hoverBg; }}
      onMouseOut={e => { e.currentTarget.style.color = '#9CA3AF'; e.currentTarget.style.background = 'transparent'; }}>
      {children}
    </button>
  );
}