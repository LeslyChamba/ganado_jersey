import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Beef, FolderOpen, Scale, FileText, LogOut, Menu } from 'lucide-react'
import { useState } from 'react'
import useAuthStore from '../../store/authStore'
import clsx from 'clsx'

const nav = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/hatos',     icon: FolderOpen,      label: 'Hatos'     },
  { to: '/vacas',     icon: Beef,            label: 'Vacas'     },
  { to: '/analisis',  icon: Scale,           label: 'Medición'  },
  { to: '/reportes',  icon: FileText,        label: 'Reportes'  },
]

export default function Layout() {
  const { usuario, logout } = useAuthStore()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden relative z-10">
      {open && (
        <div className="fixed inset-0 bg-black/20 z-20 lg:hidden" onClick={() => setOpen(false)} />
      )}

      {/* ── Sidebar ── */}
      <aside className={clsx(
        'fixed lg:static inset-y-0 left-0 z-30 w-56 flex flex-col transition-transform duration-300 lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full'
      )} style={{
        background: '#F5F0E8',
        borderRight: '0.5px solid #DDD5C4',
      }}>

        {/* Logo */}
        <div className="px-5 py-5" style={{ borderBottom: '0.5px solid #DDD5C4' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
                 style={{ background: 'linear-gradient(135deg, #5C8B6A, #89B99A)' }}>
              🐄
            </div>
            <div>
              <div style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontSize: '13px', fontWeight: 700, letterSpacing: '0.04em' }}>
                JER-WEIGHT
              </div>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', color: '#8B7D6B', fontSize: '10px' }}>
                Vacas Jersey
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-4 py-6 space-y-2">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setOpen(false)}
              className={({ isActive }) => clsx(
                "group flex items-center gap-3 px-4 py-3 rounded-xl font-mono text-xs uppercase tracking-widest transition-all duration-300",

                isActive
                  ? "bg-gradient-to-r from-[#2f5e4e] to-[#3f7a63] text-white shadow-md scale-[1.02]"
                  : "text-[#5f7d6b] hover:bg-[#edf6f1] hover:text-[#24463D] hover:scale-[1.02]"
              )}
            >
              <Icon
                size={16}
                className="transition-transform duration-300 group-hover:scale-110"
              />
              {label}
            </NavLink>
          ))}
        </nav>
        {/* User + logout */}
        <div className="px-3 py-4" style={{ borderTop: '0.5px solid #DDD5C4' }}>
          <div className="flex items-center gap-2.5 px-3 py-2 mb-1">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                 style={{ background: '#D4ECD9', color: '#2E4D38' }}>
              {usuario?.nombre?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '14px', color: '#1A1A1A' }} className="truncate">
                {usuario?.nombre} {usuario?.apellido}
              </div>
              <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '14px', color: '#8B7D6B' }} className="truncate">
                {usuario?.rol}
              </div>
            </div>
          </div>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl font-mono text-l uppercase tracking-widest transition-all"
            style={{ color: '#B0A090' }}
            onMouseOver={e => { e.currentTarget.style.color = '#C0392B'; e.currentTarget.style.background = 'rgba(192,57,43,0.06)' }}
            onMouseOut={e  => { e.currentTarget.style.color = '#B0A090'; e.currentTarget.style.background = 'transparent' }}>
            <LogOut size={14} /> Salir
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile header */}
        <header className="lg:hidden flex items-center gap-4 px-4 py-3"
                style={{
                  background: '#F5F0E8',
                  borderBottom: '0.5px solid #DDD5C4',
                }}>
          <button onClick={() => setOpen(true)} style={{ color: '#8B7D6B' }}>
            <Menu size={20} />
          </button>
          <span style={{ fontFamily: 'Syne, sans-serif', color: '#1A1A1A', fontWeight: 700 }}>JER-WEIGHT</span>
        </header>

        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}