import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  LayoutDashboard,
  Users,
  FileText,
  Settings,
  LogOut,
  Globe,
  MessageSquare,
  Shield,
  Download,
  Menu,
  X
} from 'lucide-react'
import api from '../api'
import LanguageSwitcher from '../shared/LanguageSwitcher'

export default function AdminLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const [appVersion, setAppVersion] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    api.getVersion().then(data => setAppVersion(data.version || '')).catch(() => {})
  }, [])

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  const navItems = [
    { path: '/admin', icon: LayoutDashboard, label: t('admin.dashboard'), exact: true },
    { path: '/admin/clients', icon: Users, label: t('admin.clients') },
    { path: '/admin/templates', icon: FileText, label: t('admin.templates') },
    { path: '/admin/domain-requests', icon: MessageSquare, label: t('admin.requests') },
    { path: '/admin/security', icon: Shield, label: t('admin.security') },
    { path: '/admin/settings', icon: Settings, label: t('admin.settings') },
    { path: '/admin/updates', icon: Download, label: t('admin.updates') },
  ]

  // Bottom nav items for mobile (first 4 most important)
  const bottomNavItems = navItems.slice(0, 4)

  const handleLogout = () => {
    api.adminLogout()
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col md:flex-row">
      {/* Mobile Header */}
      <header className="md:hidden bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-2">
          <Globe className="w-6 h-6 text-primary-600" />
          <span className="font-bold text-gray-900">ZETIT FNA</span>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            <Menu className="w-6 h-6" />
          </button>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-white border-r border-gray-200 flex flex-col
        transform transition-transform duration-300 ease-in-out
        md:relative md:translate-x-0 md:w-64
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Sidebar Header */}
        <div className="p-4 md:p-6 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="w-8 h-8 text-primary-600" />
              <div>
                <span className="text-xl font-bold text-gray-900">ZETIT FNA</span>
                <p className="text-xs text-gray-400">Full Network Access</p>
              </div>
            </div>
            {/* Close button for mobile */}
            <button
              onClick={() => setSidebarOpen(false)}
              className="md:hidden p-2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
            {/* Language switcher for desktop */}
            <div className="hidden md:block">
              <LanguageSwitcher />
            </div>
          </div>
          <p className="text-sm text-gray-500 mt-1">{t('admin.panel')}</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 overflow-y-auto">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.exact}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-3 md:py-2 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-primary-50 text-primary-700'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`
                  }
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-3 md:py-2 w-full text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
          >
            <LogOut className="w-5 h-5" />
            <span>{t('auth.logout')}</span>
          </button>
          {appVersion && (
            <p className="text-xs text-gray-400 text-center mt-3">v{appVersion}</p>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-4 md:p-8 overflow-auto pb-20 md:pb-8">
        <Outlet />
      </main>

      {/* Mobile Bottom Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40">
        <div className="flex justify-around items-center h-16">
          {bottomNavItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center flex-1 h-full transition-colors ${
                  isActive
                    ? 'text-primary-600'
                    : 'text-gray-500'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="text-xs mt-1 truncate max-w-[60px]">{item.label}</span>
            </NavLink>
          ))}
          {/* More button to open sidebar */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="flex flex-col items-center justify-center flex-1 h-full text-gray-500"
          >
            <Menu className="w-5 h-5" />
            <span className="text-xs mt-1">{t('common.more', 'Ещё')}</span>
          </button>
        </div>
      </nav>
    </div>
  )
}
