import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
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
  Download
} from 'lucide-react'
import api from '../api'
import LanguageSwitcher from '../shared/LanguageSwitcher'

export default function AdminLayout() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [appVersion, setAppVersion] = useState('')

  useEffect(() => {
    api.getVersion().then(data => setAppVersion(data.version || '')).catch(() => {})
  }, [])

  const navItems = [
    { path: '/admin', icon: LayoutDashboard, label: t('admin.dashboard'), exact: true },
    { path: '/admin/clients', icon: Users, label: t('admin.clients') },
    { path: '/admin/templates', icon: FileText, label: t('admin.templates') },
    { path: '/admin/domain-requests', icon: MessageSquare, label: t('admin.requests') },
    { path: '/admin/security', icon: Shield, label: t('admin.security') },
    { path: '/admin/settings', icon: Settings, label: t('admin.settings') },
    { path: '/admin/updates', icon: Download, label: t('admin.updates') },
  ]

  const handleLogout = () => {
    api.adminLogout()
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Globe className="w-8 h-8 text-primary-600" />
              <span className="text-xl font-bold text-gray-900">ProxyGate</span>
            </div>
            <LanguageSwitcher />
          </div>
          <p className="text-sm text-gray-500 mt-1">{t('admin.panel')}</p>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-1">
            {navItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  end={item.exact}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
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

        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2 w-full text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
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
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
