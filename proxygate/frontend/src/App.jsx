import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'

// Admin pages
import AdminLogin from './admin/pages/Login'
import AdminLayout from './admin/Layout'
import Dashboard from './admin/pages/Dashboard'
import Clients from './admin/pages/Clients'
import ClientDetail from './admin/pages/ClientDetail'
import Templates from './admin/pages/Templates'
import DomainRequests from './admin/pages/DomainRequests'
import Security from './admin/pages/Security'
import Settings from './admin/pages/Settings'

// Portal pages
import PortalLogin from './portal/pages/PortalLogin'
import PortalLayout from './portal/PortalLayout'
import PortalHome from './portal/pages/PortalHome'
import PortalDevices from './portal/pages/PortalDevices'
import PortalDomains from './portal/pages/PortalDomains'
import PortalPayments from './portal/pages/PortalPayments'
import PortalSettings from './portal/pages/PortalSettings'

// Auth helpers
const isAdminAuthenticated = () => {
  const token = localStorage.getItem('admin_token')
  return !!token
}

const isClientAuthenticated = () => {
  const token = localStorage.getItem('client_token')
  return !!token
}

const AdminProtectedRoute = ({ children }) => {
  if (!isAdminAuthenticated()) {
    return <Navigate to="/admin/login" replace />
  }
  return children
}

const PortalProtectedRoute = ({ children }) => {
  if (!isClientAuthenticated()) {
    return <Navigate to="/my/login" replace />
  }
  return children
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Admin routes */}
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route
          path="/admin"
          element={
            <AdminProtectedRoute>
              <AdminLayout />
            </AdminProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="clients" element={<Clients />} />
          <Route path="clients/:id" element={<ClientDetail />} />
          <Route path="templates" element={<Templates />} />
          <Route path="domain-requests" element={<DomainRequests />} />
          <Route path="security" element={<Security />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        {/* Portal (client) routes */}
        <Route path="/my/login" element={<PortalLogin />} />
        <Route
          path="/my"
          element={
            <PortalProtectedRoute>
              <PortalLayout />
            </PortalProtectedRoute>
          }
        >
          <Route index element={<PortalHome />} />
          <Route path="devices" element={<PortalDevices />} />
          <Route path="domains" element={<PortalDomains />} />
          <Route path="payments" element={<PortalPayments />} />
          <Route path="settings" element={<PortalSettings />} />
        </Route>

        {/* Default redirect */}
        <Route path="/" element={<Navigate to="/admin" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
