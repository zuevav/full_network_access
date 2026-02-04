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
  ExternalLink,
  X,
  Shield,
  Globe
} from 'lucide-react'
import api from '../../api'

// Modal for choosing VPN or Proxy
function ConnectionTypeModal({ isOpen, onClose, platform, profileInfo, t, downloadBase }) {
  if (!isOpen || !platform) return null

  const hasVpn = !!profileInfo?.vpn
  const hasProxy = !!profileInfo?.proxy

  // Build VPN profile URL using public endpoint
  const vpnProfileUrl = `${downloadBase}/${platform.id}`

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {platform.icon} {platform.name}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          {t('portalDevices.chooseConnectionType')}
        </p>

        <div className="space-y-3">
          {hasVpn && (
            <a
              href={vpnProfileUrl}
              className="flex items-center gap-4 p-4 bg-green-50 border-2 border-green-200 rounded-xl hover:border-green-400 transition-colors"
              onClick={onClose}
            >
              <div className="p-3 bg-green-100 rounded-lg">
                <Shield className="w-6 h-6 text-green-600" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-green-900">VPN</h3>
                <p className="text-sm text-green-700">{t('portalDevices.vpnTypeDescription')}</p>
              </div>
              <Download className="w-5 h-5 text-green-600" />
            </a>
          )}

          {hasProxy && (
            <div className="p-4 bg-orange-50 border-2 border-orange-200 rounded-xl">
              <div className="flex items-center gap-4 mb-3">
                <div className="p-3 bg-orange-100 rounded-lg">
                  <Globe className="w-6 h-6 text-orange-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-orange-900">Proxy</h3>
                  <p className="text-sm text-orange-700">{t('portalDevices.proxyTypeDescription')}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <a
                  href={`${downloadBase}/pac`}
                  className="btn btn-secondary btn-sm text-center"
                  onClick={onClose}
                >
                  <Download className="w-4 h-4 mr-1" />
                  PAC
                </a>
                <a
                  href={`${downloadBase}/proxy-setup`}
                  className="btn btn-secondary btn-sm text-center"
                  onClick={onClose}
                >
                  <Download className="w-4 h-4 mr-1" />
                  {t('portalDevices.setup')}
                </a>
              </div>
            </div>
          )}
        </div>

        <button
          onClick={onClose}
          className="btn btn-secondary w-full mt-4"
        >
          {t('common.cancel')}
        </button>
      </div>
    </div>
  )
}

// Platform configuration
const PLATFORMS = [
  { id: 'ios', name: 'iPhone', icon: '📱' },
  { id: 'android', name: 'Android', icon: '🤖' },
  { id: 'windows', name: 'Windows', icon: '🪟' },
  { id: 'macos', name: 'macOS', icon: '🍏' },
]

export default function PortalDevices() {
  const { t } = useTranslation()
  const [showPassword, setShowPassword] = useState(false)
  const [copied, setCopied] = useState('')
  const [selectedPlatform, setSelectedPlatform] = useState(null)

  const { data: profileInfo, isLoading } = useQuery({
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

  // Helper to safely get translation (returns string or fallback)
  const safeT = (key, fallback = '') => {
    const result = t(key)
    return typeof result === 'string' ? result : fallback
  }

  const hasVpn = !!profileInfo?.vpn
  const hasProxy = !!profileInfo?.proxy
  const hasBoth = hasVpn && hasProxy

  // Use public download URLs with access_token (no auth headers needed for direct links)
  const accessToken = profileInfo?.access_token
  const downloadBase = accessToken ? `/api/download/${accessToken}` : '/api/portal/profiles'

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">{t('common.loading')}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">{t('common.error')}: {error.message}</p>
      </div>
    )
  }

  const hasAnyService = profileInfo?.vpn || profileInfo?.proxy

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('portalDevices.title')}</h1>
        <p className="text-gray-500 mt-1">
          {t('portalDevices.subtitle')}
        </p>
      </div>

      {/* No services configured message */}
      {!hasAnyService && (
        <div className="card p-6 text-center">
          <span className="text-4xl mb-4 block">⚠️</span>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            {t('portalDevices.noServicesTitle', 'Сервисы не настроены')}
          </h2>
          <p className="text-gray-500">
            {t('portalDevices.noServicesDescription', 'Обратитесь к администратору для настройки VPN или Proxy доступа.')}
          </p>
        </div>
      )}

      {/* Unified credentials section */}
      {(hasVpn || hasProxy) && (
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
        </div>
      )}

      {/* Quick Download Section */}
      <div className="card p-4 sm:p-6">
        <h2 className="font-semibold text-gray-900 mb-4 uppercase text-sm tracking-wide">
          {t('portalDevices.quickDownload')}
        </h2>

        <div className="grid grid-cols-2 gap-3">
          {PLATFORMS.map((platform) => (
            <button
              key={platform.id}
              onClick={() => {
                if (hasBoth) {
                  // Show modal to choose
                  setSelectedPlatform(platform)
                } else if (hasVpn) {
                  // Direct VPN download using public URL
                  window.location.href = `${downloadBase}/${platform.id}`
                } else if (hasProxy) {
                  // Show modal for proxy options
                  setSelectedPlatform(platform)
                }
              }}
              className="flex flex-col items-center justify-center p-6 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors border-2 border-transparent hover:border-primary-200"
            >
              <span className="text-4xl mb-2">{platform.icon}</span>
              <span className="font-medium text-gray-900">{platform.name}</span>
              {!hasBoth && (
                <span className="text-xs text-gray-500 mt-1">
                  {hasVpn ? 'VPN' : hasProxy ? 'Proxy' : ''}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Proxy Section - detailed info */}
      {hasProxy && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-2 uppercase text-sm tracking-wide">
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
                href={`${downloadBase}/pac`}
                className="btn btn-secondary flex items-center justify-center gap-2"
              >
                <Download className="w-4 h-4" />
                {t('portalDevices.downloadPac')}
              </a>
              <a
                href={`${downloadBase}/proxy-setup`}
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

      {/* VPN Section - detailed info */}
      {hasVpn && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-2 uppercase text-sm tracking-wide">
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

          {/* Android app link */}
          <a
            href="https://play.google.com/store/apps/details?id=org.strongswan.android"
            target="_blank"
            rel="noopener noreferrer"
            className="block p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
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

      {/* Connection Type Modal */}
      <ConnectionTypeModal
        isOpen={!!selectedPlatform}
        onClose={() => setSelectedPlatform(null)}
        platform={selectedPlatform}
        profileInfo={profileInfo}
        t={t}
        downloadBase={downloadBase}
      />
    </div>
  )
}
