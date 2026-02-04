import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  Smartphone,
  Monitor,
  Tablet,
  Download,
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  EyeOff,
  ExternalLink
} from 'lucide-react'
import api from '../../api'

function DeviceCard({ icon: Icon, title, description, profileUrl, instructions, t }) {
  const [expanded, setExpanded] = useState(false)
  // Ensure instructions is always an array
  const instructionsList = Array.isArray(instructions) ? instructions : []

  return (
    <div className="card">
      <div className="p-4 sm:p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-primary-50 rounded-xl">
            {typeof Icon === 'function' ? <Icon className="w-6 h-6 text-primary-600" /> : Icon}
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-500 mt-1">{description}</p>
          </div>
        </div>

        <a
          href={profileUrl}
          className="btn btn-primary w-full mt-4 flex items-center justify-center gap-2"
        >
          <Download className="w-4 h-4" />
          {t('portalDevices.downloadProfile')}
        </a>

        {instructionsList.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full mt-3 text-sm text-gray-500 flex items-center justify-center gap-1 hover:text-gray-700"
          >
            {t('portalDevices.howToInstall')}
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        )}

        {expanded && instructionsList.length > 0 && (
          <ol className="mt-3 text-sm text-gray-600 space-y-2 pl-5 list-decimal">
            {instructionsList.map((step, idx) => (
              <li key={idx}>{step}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

export default function PortalDevices() {
  const { t } = useTranslation()
  const [showPassword, setShowPassword] = useState(false)
  const [copied, setCopied] = useState('')

  const { data: profileInfo, isLoading, error } = useQuery({
    queryKey: ['portal-profiles'],
    queryFn: () => api.getPortalProfiles(),
    retry: 1,
    staleTime: 60000,
  })

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text)
    setCopied(field)
    setTimeout(() => setCopied(''), 2000)
  }

  const devices = [
    {
      icon: Smartphone,
      title: t('portalDevices.devices.iphone.title'),
      description: t('portalDevices.devices.iphone.description'),
      profileUrl: '/api/portal/profiles/ios',
      instructions: t('portalDevices.devices.iphone.instructions', { returnObjects: true }),
    },
    {
      icon: <span className="text-2xl">🤖</span>,
      title: t('portalDevices.devices.android.title'),
      description: t('portalDevices.devices.android.description'),
      profileUrl: '/api/portal/profiles/android',
      instructions: t('portalDevices.devices.android.instructions', { returnObjects: true }),
    },
    {
      icon: Monitor,
      title: t('portalDevices.devices.windows.title'),
      description: t('portalDevices.devices.windows.description'),
      profileUrl: '/api/portal/profiles/windows',
      instructions: t('portalDevices.devices.windows.instructions', { returnObjects: true }),
    },
    {
      icon: <span className="text-2xl">🍏</span>,
      title: t('portalDevices.devices.macos.title'),
      description: t('portalDevices.devices.macos.description'),
      profileUrl: '/api/portal/profiles/macos',
      instructions: t('portalDevices.devices.macos.instructions', { returnObjects: true }),
    },
  ]

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('portalDevices.title')}</h1>
        <p className="text-gray-500 mt-1">
          {t('portalDevices.subtitle')}
        </p>
      </div>

      {/* Unified credentials section */}
      {(profileInfo?.vpn || profileInfo?.proxy) && (
        <div className="card p-4 sm:p-6 border-2 border-primary-200 bg-primary-50/30">
          <h2 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <span className="text-xl">🔑</span>
            {t('portalDevices.yourCredentials')}
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            {t('portalDevices.sameCredentialsNote')}
          </p>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center p-3 bg-white rounded-lg border border-primary-100">
              <span className="text-gray-700 font-medium">{t('portalDevices.username')}</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-primary-700">{profileInfo?.vpn?.username || profileInfo?.proxy?.username}</code>
                <button
                  onClick={() => copyToClipboard(profileInfo?.vpn?.username || profileInfo?.proxy?.username, 'username')}
                  className="text-primary-400 hover:text-primary-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'username' && <span className="text-xs text-green-600">{t('common.copied')}</span>}
              </div>
            </div>
            <div className="flex justify-between items-center p-3 bg-white rounded-lg border border-primary-100">
              <span className="text-gray-700 font-medium">{t('portalDevices.password')}</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-primary-700">
                  {showPassword ? (profileInfo?.vpn?.password || profileInfo?.proxy?.password) : '••••••••'}
                </code>
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-primary-400 hover:text-primary-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => copyToClipboard(profileInfo?.vpn?.password || profileInfo?.proxy?.password, 'password')}
                  className="text-primary-400 hover:text-primary-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'password' && <span className="text-xs text-green-600">{t('common.copied')}</span>}
              </div>
            </div>
          </div>

          <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
            <p className="font-medium mb-1">{t('portalDevices.usedFor')}</p>
            <ul className="list-disc list-inside space-y-1 text-blue-600">
              {profileInfo?.vpn && <li>{t('portalDevices.vpnConnection')}</li>}
              {profileInfo?.proxy && <li>{t('portalDevices.proxyConnection')}</li>}
            </ul>
          </div>
        </div>
      )}

      {/* VPN Section */}
      {profileInfo?.vpn && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <span className="text-xl">🛡️</span>
            {t('portalDevices.vpnSection')}
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            {t('portalDevices.vpnSectionDescription')}
          </p>

          {/* VPN Server info */}
          <div className="mb-4 p-3 bg-green-50 rounded-lg border border-green-100">
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-600">{t('portalDevices.vpnServer')}</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-green-700">{profileInfo.vpn.server}</code>
                <button
                  onClick={() => copyToClipboard(profileInfo.vpn.server, 'vpnserver')}
                  className="text-green-400 hover:text-green-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'vpnserver' && <span className="text-xs text-green-600">{t('common.copied')}</span>}
              </div>
            </div>
          </div>

          {/* VPN Device cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {devices.map((device, idx) => (
              <DeviceCard key={idx} {...device} t={t} />
            ))}
          </div>

          {/* Android app link */}
          <a
            href="https://play.google.com/store/apps/details?id=org.strongswan.android"
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-4 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">🤖</span>
              <div className="flex-1">
                <p className="font-medium text-gray-900">{t('portalDevices.strongswanAndroid')}</p>
                <p className="text-sm text-gray-500">{t('portalDevices.freeInPlayStore')}</p>
              </div>
              <ExternalLink className="w-5 h-5 text-gray-400" />
            </div>
          </a>
        </div>
      )}

      {/* Proxy Section */}
      {profileInfo?.proxy && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-2 flex items-center gap-2">
            <span className="text-xl">🌐</span>
            {t('portalDevices.proxySection')}
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            {t('portalDevices.proxyDescription')}
          </p>

          {/* Proxy addresses */}
          <div className="space-y-3 text-sm mb-4">
            <div className="flex justify-between items-center p-3 bg-orange-50 rounded-lg border border-orange-100">
              <span className="text-gray-600">HTTP Proxy</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-orange-700">{profileInfo.proxy.host}:{profileInfo.proxy.http_port}</code>
                <button
                  onClick={() => copyToClipboard(`${profileInfo.proxy.host}:${profileInfo.proxy.http_port}`, 'http')}
                  className="text-orange-400 hover:text-orange-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'http' && <span className="text-xs text-green-600">{t('common.copied')}</span>}
              </div>
            </div>
            <div className="flex justify-between items-center p-3 bg-orange-50 rounded-lg border border-orange-100">
              <span className="text-gray-600">SOCKS5 Proxy</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-orange-700">{profileInfo.proxy.host}:{profileInfo.proxy.socks_port}</code>
                <button
                  onClick={() => copyToClipboard(`${profileInfo.proxy.host}:${profileInfo.proxy.socks_port}`, 'socks')}
                  className="text-orange-400 hover:text-orange-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'socks' && <span className="text-xs text-green-600">{t('common.copied')}</span>}
              </div>
            </div>
          </div>

          {/* Proxy setup options */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-gray-700">{t('portalDevices.proxySetupOptions')}</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <a
                href="/api/portal/profiles/pac"
                className="btn btn-secondary flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                {t('portalDevices.downloadPac')}
              </a>
              <a
                href="/api/portal/profiles/proxy-setup"
                className="btn btn-secondary flex items-center justify-center gap-2"
              >
                <Monitor className="w-4 h-4" />
                {t('portalDevices.downloadProxySetup')}
              </a>
            </div>
            <p className="text-xs text-gray-500 text-center">
              {t('portalDevices.pacDescription')}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
