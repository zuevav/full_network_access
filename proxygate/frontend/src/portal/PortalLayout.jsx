import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Home, Smartphone, Globe, CreditCard, Settings, LogOut } from 'lucide-react'
import api from '../api'
import LanguageSwitcher from '../shared/LanguageSwitcher'

export default function PortalLayout() {
  const navigate = useNavigate()
  const { t } = useTranslation()

  const navItems = [
    { path: '/my', icon: Home, label: t('portal.home'), exact: true },
    { path: '/my/devices', icon: Smartphone, label: t('portal.devices') },
    { path: '/my/domains', icon: Globe, label: t('portal.domains') },
    { path: '/my/payments', icon: CreditCard, label: t('portal.payments') },
    { path: '/my/settings', icon: Settings, label: t('portal.settings') },
  ]

  const handleLogout = () => {
    api.clientLogout()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <Globe className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-gray-900">ProxyGate</span>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            <button
              onClick={handleLogout}
              className="text-gray-500 hover:text-gray-700 flex items-center gap-1 text-sm"
            >
              <LogOut className="w-4 h-4" />
              {t('auth.logout')}
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        <Outlet />
      </main>

      {/* Bottom navigation (mobile) */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 md:hidden">
        <div className="flex justify-around py-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) =>
                `flex flex-col items-center py-2 px-3 ${
                  isActive ? 'text-primary-600' : 'text-gray-500'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="text-xs mt-1">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Side navigation (desktop) */}
      <aside className="hidden md:block fixed left-4 top-24">
        <nav className="bg-white rounded-xl shadow-sm border border-gray-100 p-2 w-48">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
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
          ))}
        </nav>
      </aside>
    </div>
  )
}
