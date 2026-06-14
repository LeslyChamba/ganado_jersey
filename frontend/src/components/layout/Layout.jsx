import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Beef, FolderOpen, Scale, FileText, LogOut, Menu, Users, Shield, Activity } from 'lucide-react'
import { useState } from 'react'
import useAuthStore from '../../store/authStore'
import clsx from 'clsx'
import { PiCow } from 'react-icons/pi'
const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/hatos',     icon: FolderOpen,      label: 'Hatos'     },
  { to: '/vacas',     icon: PiCow,            label: 'Vacas'     },
  { to: '/analisis',  icon: Activity,        label: 'Medición'  },
  { to: '/reportes',  icon: FileText,        label: 'Reportes'  },
]

const navAdmin = [
  { to: '/admin/usuarios',  icon: Users,  label: 'Usuarios'  },
  { to: '/admin/auditoria', icon: Shield, label: 'Auditoría' },
  { to: '/admin/bovinos',   icon: PiCow,   label: 'Bovinos'   }, 
]

/* ── Tokens de color (Sincronizados con la marca) ── */
const C = {
  sidebar:      '#081C11', // Verde muy oscuro (Fondo)
  sidebarBorder:'rgba(82, 217, 160, 0.1)', // Borde sutil esmeralda
  activeBase:   '#1B4332', // Verde oscuro (Fondo item activo)
  activeText:   '#52D9A0', // Esmeralda (Texto item activo)
  itemText:     '#89B99A', // Verde desaturado (Texto inactivo)
  itemHoverBg:  'rgba(82, 217, 160, 0.08)',
  itemHoverTx:  '#FFFFFF',
  divider:      'rgba(82, 217, 160, 0.1)',
  bg:           '#F0FBF6', // Fondo general de la app
  topbar:       '#FFFFFF',
  topbarBorder: 'rgba(82, 217, 160, 0.2)',
  logoutText:   '#89B99A',
  logoutHover:  'rgba(239, 68, 68, 0.1)',
  logoutHoverTx:'#EF4444',
  avatarBg:     '#1B4332',
  avatarText:   '#52D9A0',
  userName:     '#FFFFFF',
  userRole:     '#52D9A0',
  brandName:    '#FFFFFF',
  brandSub:     '#52D9A0',
  sectionLabel: '#5C8B6A',
}
/* ── Tokens de tipografía ── */
const F = {
  brand: "Cambria, 'Times New Roman', serif",
  body:  "Arial, Helvetica, sans-serif",
}

export default function Layout() {
  const { usuario, logout } = useAuthStore()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const isAdmin = usuario?.rol?.toUpperCase() === 'ADMIN'

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', position: 'relative', zIndex: 10, background: C.bg }}>

      {/* Overlay mobile */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="lg:hidden animate-in fade-in duration-300"
          style={{ position: 'fixed', inset: 0, background: 'rgba(8, 28, 17, 0.6)', backdropFilter: 'blur(4px)', zIndex: 20 }}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={clsx(
          'fixed lg:static inset-y-0 left-0 z-30 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 shadow-2xl lg:shadow-none',
          open ? 'translate-x-0' : '-translate-x-full'
        )}
        style={{
          width: '240px',
          background: C.sidebar,
          borderRight: `1px solid ${C.sidebarBorder}`,
          flexShrink: 0,
        }}
      >
        {/* LOGO Y MARCA */}
        <div style={{ padding: '24px 20px', borderBottom: `1px solid ${C.sidebarBorder}`, display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px', height: '36px',
            background: `linear-gradient(135deg, ${C.activeBase}, ${C.sidebar})`,
            border: `1px solid ${C.activeText}40`,
            borderRadius: '10px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(82, 217, 160, 0.15)'
          }}>
            <Scale size={18} color={C.activeText} />
          </div>
          <div>
            <div style={{ fontFamily: F.brand, fontSize: '15px', fontWeight: 800, color: C.brandName, letterSpacing: '0.05em', lineHeight: 1 }}>
              JER-WEIGHT
            </div>
            <div style={{ fontFamily: F.body, fontSize: '9px', color: C.brandSub, letterSpacing: '0.1em', marginTop: '4px', textTransform: 'uppercase', fontWeight: 'bold' }}>
              Estimación Bovina
            </div>
          </div>
        </div>

        {/* NAVEGACIÓN */}
        <nav style={{ flex: 1, padding: '20px 12px', overflowY: 'auto' }} className="custom-scrollbar">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to} to={to} onClick={() => setOpen(false)}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: '12px',
                padding: '10px 14px', borderRadius: '10px', marginBottom: '4px',
                fontFamily: F.body, fontSize: '11px', fontWeight: isActive ? 700 : 600,
                letterSpacing: '0.05em', textTransform: 'uppercase', textDecoration: 'none',
                transition: 'all 0.2s ease',
                background: isActive ? C.activeBase : 'transparent',
                color: isActive ? C.activeText : C.itemText,
                borderLeft: isActive ? `3px solid ${C.activeText}` : '3px solid transparent',
              })}
              onMouseOver={e => {
                if (!e.currentTarget.classList.contains('active')) {
                  e.currentTarget.style.background = C.itemHoverBg; e.currentTarget.style.color = C.itemHoverTx
                }
              }}
              onMouseOut={e => {
                if (!e.currentTarget.classList.contains('active')) {
                  e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = C.itemText
                }
              }}
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }} />
                  {label}
                </>
              )}
            </NavLink>
          ))}

          {/* SECCIÓN ADMIN */}
          {isAdmin && (
            <>
              <div style={{ height: '1px', background: C.divider, margin: '20px 8px 16px 8px' }} />
              <div style={{
                fontFamily: F.body, fontSize: '9px', color: C.sectionLabel,
                letterSpacing: '0.15em', textTransform: 'uppercase', fontWeight: 800, padding: '0 14px', marginBottom: '8px',
              }}>
                Administración
              </div>
              {navAdmin.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to} to={to} onClick={() => setOpen(false)}
                  style={({ isActive }) => ({
                    display: 'flex', alignItems: 'center', gap: '12px',
                    padding: '10px 14px', borderRadius: '10px', marginBottom: '4px',
                    fontFamily: F.body, fontSize: '11px', fontWeight: isActive ? 700 : 600,
                    letterSpacing: '0.05em', textTransform: 'uppercase', textDecoration: 'none',
                    transition: 'all 0.2s ease',
                    background: isActive ? C.activeBase : 'transparent',
                    color: isActive ? C.activeText : C.itemText,
                    borderLeft: isActive ? `3px solid ${C.activeText}` : '3px solid transparent',
                  })}
                  onMouseOver={e => {
                    if (!e.currentTarget.classList.contains('active')) {
                      e.currentTarget.style.background = C.itemHoverBg; e.currentTarget.style.color = C.itemHoverTx
                    }
                  }}
                  onMouseOut={e => {
                    if (!e.currentTarget.classList.contains('active')) {
                      e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = C.itemText
                    }
                  }}
                >
                  {({ isActive }) => (
                    <>
                      <Icon size={16} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }} />
                      {label}
                    </>
                  )}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* PERFIL DE USUARIO Y LOGOUT */}
        <div style={{ padding: '16px', borderTop: `1px solid ${C.sidebarBorder}`, background: 'rgba(0,0,0,0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px', marginBottom: '8px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px' }}>
            <div style={{
              width: '34px', height: '34px', background: C.avatarBg, borderRadius: '10px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '14px', fontWeight: 800, color: C.avatarText, flexShrink: 0,
              border: `1px solid ${C.activeText}30`
            }}>
              {usuario?.nombre?.[0]?.toUpperCase() || 'U'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: F.body, fontSize: '13px', fontWeight: 700, color: C.userName, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {usuario?.nombre} {usuario?.apellido}
              </div>
              <div style={{ fontFamily: F.body, fontSize: '9px', color: C.userRole, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 'bold' }}>
                {usuario?.rol}
              </div>
            </div>
          </div>

          <button
            onClick={() => { logout(); navigate('/login') }}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
              padding: '10px', borderRadius: '10px', background: 'transparent', border: '1px solid transparent',
              cursor: 'pointer', fontFamily: F.body, fontSize: '10px', fontWeight: 700,
              letterSpacing: '0.1em', textTransform: 'uppercase', color: C.logoutText, transition: 'all 0.2s',
            }}
            onMouseOver={e => { e.currentTarget.style.color = C.logoutHoverTx; e.currentTarget.style.background = C.logoutHover; e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.2)' }}
            onMouseOut={e => { e.currentTarget.style.color = C.logoutText; e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent' }}
          >
            <LogOut size={14} /> Cerrar Sesión
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* HEADER MÓVIL */}
        <header
          className="lg:hidden"
          style={{
            display: 'flex', alignItems: 'center', gap: '14px', padding: '16px 20px',
            background: C.topbar, borderBottom: `1px solid ${C.topbarBorder}`, flexShrink: 0,
            boxShadow: '0 2px 10px rgba(8, 28, 17, 0.03)'
          }}
        >
          <button onClick={() => setOpen(true)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.sidebar, padding: 0 }}>
            <Menu size={24} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '24px', height: '24px', background: C.sidebar, borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Scale size={12} color={C.activeText} />
            </div>
            <span style={{ fontFamily: F.brand, color: C.sidebar, fontWeight: 800, fontSize: '16px', letterSpacing: '0.02em' }}>
              JER-WEIGHT
            </span>
          </div>
        </header>

        {/* ÁREA DE RENDERIZADO (Dashboard, Vacas, etc.) */}
        <main 
          style={{ flex: 1, overflowY: 'auto', padding: '32px 40px', background: C.bg }}
          className="custom-scrollbar"
        >
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}