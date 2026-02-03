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

        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full mt-3 text-sm text-gray-500 flex items-center justify-center gap-1 hover:text-gray-700"
        >
          {t('portalDevices.howToInstall')}
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {expanded && (
          <ol className="mt-3 text-sm text-gray-600 space-y-2 pl-5 list-decimal">
            {instructions.map((step, idx) => (
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

  const { data: profileInfo, isLoading } = useQuery({
    queryKey: ['portal-profiles'],
    queryFn: () => api.getPortalProfiles(),
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

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('portalDevices.title')}</h1>
        <p className="text-gray-500 mt-1">
          {t('portalDevices.subtitle')}
        </p>
      </div>

      {/* Device cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {devices.map((device, idx) => (
          <DeviceCard key={idx} {...device} t={t} />
        ))}
      </div>

      {/* Proxy section */}
      {profileInfo?.proxy && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-4">
            {t('portalDevices.proxyAlternative')}
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            {t('portalDevices.proxyDescription')}
          </p>

          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-500">HTTP</span>
              <code className="font-mono">{profileInfo.proxy.host}:{profileInfo.proxy.http_port}</code>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-500">SOCKS5</span>
              <code className="font-mono">{profileInfo.proxy.host}:{profileInfo.proxy.socks_port}</code>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-500">{t('portalDevices.username')}</span>
              <div className="flex items-center gap-2">
                <code className="font-mono">{profileInfo.proxy.username}</code>
                <button
                  onClick={() => copyToClipboard(profileInfo.proxy.username, 'username')}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-500">{t('portalDevices.password')}</span>
              <div className="flex items-center gap-2">
                <code className="font-mono">
                  {showPassword ? profileInfo.proxy.password : '••••••••'}
                </code>
                <button
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                <button
                  onClick={() => copyToClipboard(profileInfo.proxy.password, 'password')}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <a
            href="/api/portal/profiles/pac"
            className="btn btn-secondary w-full mt-4 flex items-center justify-center gap-2"
          >
            <Download className="w-4 h-4" />
            {t('portalDevices.downloadPac')}
          </a>
          <p className="text-xs text-gray-500 mt-2 text-center">
            {t('portalDevices.pacDescription')}
          </p>
        </div>
      )}

      {/* Android app link */}
      <a
        href="https://play.google.com/store/apps/details?id=org.strongswan.android"
        target="_blank"
        rel="noopener noreferrer"
        className="block card p-4 hover:bg-gray-50 transition-colors"
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
  )
}
