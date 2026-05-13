import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'

import Layout        from './components/layout/Layout'
import AdminPage     from "./pages/AdminPage"
import AuditoriaPage from "./pages/AuditoriaPage"
import LoginPage     from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import HatosPage     from './pages/HatosPage'
import VacasPage     from './pages/VacasPage'
import AnalisisPage  from './pages/AnalisisPage'
import ReportesPage  from './pages/ReportesPage'
import Guiacaptura from './pages/Guiacaptura';
import RecuperarPassword from './components/RecuperarPassword';
import BovinosPage from './components/admin/bovinosPage'
import RestablecerPassword from './components/RestablecerPassword';
const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 1000 * 30 } }
})

function PrivateRoute({ children }) {
  const token = localStorage.getItem('access_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Toaster position="top-right" toastOptions={{
          style: { borderRadius: '12px', fontFamily: 'DM Sans, sans-serif', fontSize: '14px' }
        }}/>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/recuperarpassword" element={<RecuperarPassword />} />  
          <Route path="/reset-password" element={<RestablecerPassword />} />
          <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index          element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="hatos"     element={<HatosPage />} />
            <Route path="vacas"     element={<VacasPage />} />
            <Route path="analisis"  element={<AnalisisPage />} />
            <Route path="reportes"  element={<ReportesPage />} />
            <Route path="admin/usuarios"     element={<AdminPage />} />
            <Route path="admin/auditoria"    element={<AuditoriaPage />} />
            <Route path="admin/bovinos"      element={<BovinosPage />} />
            <Route path="guiacaptura"        element={<Guiacaptura />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
