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
  Globe,
  QrCode,
  Zap,
  Wifi
} from 'lucide-react'
import api from '../../api'

// Modal for choosing VPN or Proxy with instructions
function ConnectionTypeModal({ isOpen, onClose, platform, profileInfo, t, downloadBase }) {
  if (!isOpen || !platform) return null

  const hasVpn = !!profileInfo?.vpn
  const hasProxy = !!profileInfo?.proxy

  // Build VPN profile URL using public endpoint
  const vpnProfileUrl = `${downloadBase}/${platform.id}`

  // Platform-specific instructions
  const getVpnInstructions = () => {
    switch (platform.id) {
      case 'ios':
        return [
          'Нажмите "Скачать профиль VPN" ниже',
          'В появившемся окне нажмите "Разрешить"',
          'Откройте Настройки → Основные → VPN и управление устройством',
          'Нажмите на загруженный профиль и установите его',
          'Введите пароль устройства, если потребуется',
          'VPN появится в Настройки → VPN. Включите его!'
        ]
      case 'android':
        return [
          'Сначала установите приложение strongSwan VPN Client из Google Play',
          'Нажмите "Скачать профиль VPN" ниже',
          'Откройте скачанный файл .sswan',
          'Приложение strongSwan предложит импортировать профиль',
          'Нажмите "Импортировать" и подтвердите',
          'Подключитесь к VPN в приложении strongSwan'
        ]
      case 'windows':
        return [
          'Нажмите "Скачать профиль VPN" ниже',
          'Откройте скачанный файл .exe',
          'Если Windows спросит разрешение — нажмите "Да"',
          'Следуйте инструкциям установщика',
          'После установки VPN появится в сетевых подключениях',
          'Откройте Настройки → Сеть → VPN и подключитесь'
        ]
      case 'macos':
        return [
          'Нажмите "Скачать профиль VPN" ниже',
          'Откройте скачанный файл .mobileconfig',
          'Откройте Системные настройки → Профили',
          'Нажмите на загруженный профиль и установите его',
          'Введите пароль компьютера для подтверждения',
          'VPN появится в Системные настройки → VPN. Включите его!'
        ]
      default:
        return ['Скачайте и установите профиль VPN']
    }
  }

  const getProxyInstructions = () => {
    switch (platform.id) {
      case 'ios':
        return [
          'Откройте Настройки → Wi-Fi',
          'Нажмите (i) рядом с вашей сетью',
          'Прокрутите вниз до "Настройка прокси"',
          'Выберите "Автоматически"',
          `Введите URL: ${window.location.origin}${downloadBase}/pac`,
          'Нажмите "Сохранить"'
        ]
      case 'android':
        return [
          'Откройте Настройки → Wi-Fi',
          'Долгое нажатие на вашу сеть → Изменить сеть',
          'Разверните "Расширенные настройки"',
          'Найдите "Прокси" и выберите "Авто-настройка"',
          `Введите URL: ${window.location.origin}${downloadBase}/pac`,
          'Сохраните настройки'
        ]
      case 'windows':
        return [
          'Откройте Настройки → Сеть и Интернет → Прокси',
          'Включите "Использовать сценарий настройки"',
          `Введите адрес: ${window.location.origin}${downloadBase}/pac`,
          'Нажмите "Сохранить"',
          'Перезапустите браузер для применения настроек'
        ]
      case 'macos':
        return [
          'Откройте Системные настройки → Сеть',
          'Выберите вашу сеть и нажмите "Дополнительно"',
          'Перейдите на вкладку "Прокси"',
          'Включите "Автоматическая настройка прокси"',
          `Введите URL: ${window.location.origin}${downloadBase}/pac`,
          'Нажмите "OK" и "Применить"'
        ]
      default:
        return ['Настройте прокси в системных настройках']
    }
  }

  const vpnInstructions = getVpnInstructions()
  const proxyInstructions = getProxyInstructions()

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-xl w-full max-w-lg my-4">
        <div className="p-6 border-b">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">
              {platform.icon} Настройка {platform.name}
            </h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Выберите тип подключения и следуйте инструкциям
          </p>
        </div>

        <div className="p-6 space-y-6 max-h-[60vh] overflow-y-auto">
          {hasVpn && (
            <div className="border-2 border-green-200 rounded-xl overflow-hidden">
              <div className="bg-green-50 p-4 flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <Shield className="w-6 h-6 text-green-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-green-900">VPN подключение</h3>
                  <p className="text-sm text-green-700">Полная защита всего трафика устройства</p>
                </div>
              </div>

              <div className="p-4 bg-white">
                <h4 className="font-medium text-gray-900 mb-3">📋 Инструкция:</h4>
                <ol className="space-y-2 text-sm text-gray-700">
                  {vpnInstructions.map((step, index) => (
                    <li key={index} className="flex gap-3">
                      <span className="flex-shrink-0 w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center text-xs font-bold">
                        {index + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>

                {platform.id === 'android' && (
                  <a
                    href="https://play.google.com/store/apps/details?id=org.strongswan.android"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-4 flex items-center gap-2 text-sm text-green-700 hover:text-green-900"
                  >
                    <ExternalLink className="w-4 h-4" />
                    Открыть strongSwan в Google Play
                  </a>
                )}

                <a
                  href={vpnProfileUrl}
                  className="mt-4 btn btn-primary w-full flex items-center justify-center gap-2"
                  onClick={onClose}
                >
                  <Download className="w-5 h-5" />
                  Скачать профиль VPN
                </a>
              </div>
            </div>
          )}

          {hasProxy && (
            <div className="border-2 border-orange-200 rounded-xl overflow-hidden">
              <div className="bg-orange-50 p-4 flex items-center gap-3">
                <div className="p-2 bg-orange-100 rounded-lg">
                  <Globe className="w-6 h-6 text-orange-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-orange-900">Proxy подключение</h3>
                  <p className="text-sm text-orange-700">Только для определённых сайтов (браузер)</p>
                </div>
              </div>

              <div className="p-4 bg-white">
                <h4 className="font-medium text-gray-900 mb-3">📋 Инструкция:</h4>
                <ol className="space-y-2 text-sm text-gray-700">
                  {proxyInstructions.map((step, index) => (
                    <li key={index} className="flex gap-3">
                      <span className="flex-shrink-0 w-6 h-6 bg-orange-100 text-orange-700 rounded-full flex items-center justify-center text-xs font-bold">
                        {index + 1}
                      </span>
                      <span className="break-all">{step}</span>
                    </li>
                  ))}
                </ol>

                <div className="mt-4 p-3 bg-orange-50 rounded-lg">
                  <p className="text-xs text-orange-800 mb-2">
                    <strong>Данные для входа:</strong>
                  </p>
                  <p className="text-xs text-orange-700 font-mono">
                    Логин: {profileInfo?.proxy?.username}<br/>
                    Пароль: используйте ваш пароль из раздела "Учётные данные"
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t bg-gray-50">
          <button
            onClick={onClose}
            className="btn btn-secondary w-full"
          >
            Закрыть
          </button>
        </div>
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

// Platform instruction accordion component
function PlatformAccordion({ platforms, colorClass }) {
  const [openPlatform, setOpenPlatform] = useState(null)

  const colorMap = {
    purple: {
      bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700',
      stepBg: 'bg-purple-100', stepText: 'text-purple-700', linkText: 'text-purple-600 hover:text-purple-800'
    },
    blue: {
      bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-700',
      stepBg: 'bg-blue-100', stepText: 'text-blue-700', linkText: 'text-blue-600 hover:text-blue-800'
    }
  }
  const c = colorMap[colorClass] || colorMap.purple

  return (
    <div className="space-y-2">
      {platforms.map(({ key, label, icon, data }) => {
        if (!data) return null
        const isOpen = openPlatform === key
        const appLink = data.app_store || data.play_store || data.github || data.download
        return (
          <div key={key} className={`rounded-lg border ${c.border} overflow-hidden`}>
            <button
              onClick={() => setOpenPlatform(isOpen ? null : key)}
              className={`w-full flex items-center justify-between p-3 ${c.bg} hover:opacity-80 transition-opacity`}
            >
              <span className="flex items-center gap-2 font-medium text-gray-800">
                <span>{icon}</span> {label}
                <span className={`text-xs ${c.text}`}>({data.app})</span>
              </span>
              {isOpen ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
            </button>
            {isOpen && (
              <div className="p-3 bg-white">
                {data.price && (
                  <p className="text-xs text-gray-500 mb-2">Цена: {data.price}</p>
                )}
                <ol className="space-y-2 text-sm text-gray-700">
                  {data.steps?.map((step, i) => (
                    <li key={i} className="flex gap-3">
                      <span className={`flex-shrink-0 w-6 h-6 ${c.stepBg} ${c.stepText} rounded-full flex items-center justify-center text-xs font-bold`}>
                        {i + 1}
                      </span>
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
                {appLink && (
                  <a
                    href={appLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`mt-3 flex items-center gap-2 text-sm ${c.linkText}`}
                  >
                    <ExternalLink className="w-4 h-4" />
                    Скачать {data.app}
                  </a>
                )}
                {data.alternative_apps && (
                  <p className="mt-2 text-xs text-gray-500">
                    Альтернативы: {data.alternative_apps.join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function PortalDevices() {
  const { t } = useTranslation()
  const [showPassword, setShowPassword] = useState(false)
  const [copied, setCopied] = useState('')
  const [selectedPlatform, setSelectedPlatform] = useState(null)
  const [showXrayQr, setShowXrayQr] = useState(false)
  const [showWgQr, setShowWgQr] = useState(false)

  const { data: profileInfo, isLoading, error } = useQuery({
    queryKey: ['portal-profiles'],
    queryFn: () => api.getPortalProfiles(),
    retry: 1,
    staleTime: 60000,
  })

  const { data: xrayData } = useQuery({
    queryKey: ['portal-xray'],
    queryFn: () => api.getPortalXray(),
    retry: 1,
    staleTime: 60000,
  })

  const { data: wgData } = useQuery({
    queryKey: ['portal-wireguard'],
    queryFn: () => api.getPortalWireguard(),
    retry: 1,
    staleTime: 60000,
  })

  const { data: xrayQr, isFetching: xrayQrLoading } = useQuery({
    queryKey: ['portal-xray-qr'],
    queryFn: () => api.getPortalXrayQrcode(),
    enabled: showXrayQr,
    retry: 1,
    staleTime: 300000,
  })

  const { data: wgQr, isFetching: wgQrLoading } = useQuery({
    queryKey: ['portal-wg-qr'],
    queryFn: () => api.getPortalWireguardQrcode(),
    enabled: showWgQr,
    retry: 1,
    staleTime: 300000,
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
              onClick={() => setSelectedPlatform(platform)}
              className="flex flex-col items-center justify-center p-6 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors border-2 border-transparent hover:border-primary-200"
            >
              <span className="text-4xl mb-2">{platform.icon}</span>
              <span className="font-medium text-gray-900">{platform.name}</span>
              <span className="text-xs text-gray-500 mt-1">
                {hasBoth ? 'VPN + Proxy' : hasVpn ? 'VPN' : hasProxy ? 'Proxy' : ''}
              </span>
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

      {/* XRay (VLESS + REALITY) Section */}
      {xrayData?.available && (
        <div className="card p-4 sm:p-6 border-2 border-purple-200">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 rounded-lg">
              <Zap className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900 uppercase text-sm tracking-wide">
                XRay (VLESS + REALITY)
              </h2>
              <p className="text-sm text-gray-500">Современный протокол с маскировкой трафика</p>
            </div>
          </div>

          {/* VLESS URL */}
          <div className="mt-4 p-3 bg-purple-50 rounded-lg border border-purple-100">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-purple-700">VLESS URL</span>
              <button
                onClick={() => copyToClipboard(xrayData.vless_url, 'vless')}
                className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-800"
              >
                <Copy className="w-3.5 h-3.5" />
                {copied === 'vless' ? 'Скопировано!' : 'Копировать'}
              </button>
            </div>
            <code className="block text-xs text-purple-800 font-mono break-all bg-white p-2 rounded border border-purple-100 max-h-20 overflow-y-auto">
              {xrayData.vless_url}
            </code>
          </div>

          {/* QR Code toggle */}
          <div className="mt-3">
            <button
              onClick={() => setShowXrayQr(!showXrayQr)}
              className="flex items-center gap-2 text-sm text-purple-600 hover:text-purple-800 font-medium"
            >
              <QrCode className="w-4 h-4" />
              {showXrayQr ? 'Скрыть QR-код' : 'Показать QR-код'}
            </button>
            {showXrayQr && (
              <div className="mt-3 flex justify-center">
                {xrayQrLoading ? (
                  <div className="w-48 h-48 bg-purple-50 rounded-lg flex items-center justify-center">
                    <span className="text-sm text-purple-500">Загрузка...</span>
                  </div>
                ) : xrayQr?.qrcode ? (
                  <img src={xrayQr.qrcode} alt="XRay QR Code" className="w-48 h-48 rounded-lg border border-purple-200" />
                ) : (
                  <p className="text-sm text-gray-500">QR-код недоступен</p>
                )}
              </div>
            )}
          </div>

          {/* Platform instructions */}
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Инструкции по платформам</h3>
            <PlatformAccordion
              colorClass="purple"
              platforms={[
                { key: 'ios', label: 'iPhone / iPad', icon: '📱', data: xrayData.instructions?.ios },
                { key: 'android', label: 'Android', icon: '🤖', data: xrayData.instructions?.android },
                { key: 'windows', label: 'Windows', icon: '🪟', data: xrayData.instructions?.windows },
                { key: 'macos', label: 'macOS', icon: '🍏', data: xrayData.instructions?.mac },
              ]}
            />
          </div>
        </div>
      )}

      {/* WireGuard VPN Section */}
      {wgData?.available && (
        <div className="card p-4 sm:p-6 border-2 border-blue-200">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Wifi className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900 uppercase text-sm tracking-wide">
                WireGuard VPN
              </h2>
              <p className="text-sm text-gray-500">Быстрый и лёгкий VPN-протокол</p>
            </div>
          </div>

          {/* Download .conf + QR */}
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              href={`/api/portal/profiles/wireguard/config`}
              onClick={(e) => {
                e.preventDefault()
                const token = localStorage.getItem('client_token')
                fetch('/api/portal/profiles/wireguard/config', {
                  headers: { 'Authorization': `Bearer ${token}` }
                })
                  .then(r => r.blob())
                  .then(blob => {
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = 'wireguard.conf'
                    a.click()
                    URL.revokeObjectURL(url)
                  })
              }}
              className="btn btn-primary flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Скачать .conf
            </a>
            <button
              onClick={() => setShowWgQr(!showWgQr)}
              className="btn btn-secondary flex items-center gap-2"
            >
              <QrCode className="w-4 h-4" />
              {showWgQr ? 'Скрыть QR-код' : 'Показать QR-код'}
            </button>
          </div>

          {/* QR Code */}
          {showWgQr && (
            <div className="mt-3 flex justify-center">
              {wgQrLoading ? (
                <div className="w-48 h-48 bg-blue-50 rounded-lg flex items-center justify-center">
                  <span className="text-sm text-blue-500">Загрузка...</span>
                </div>
              ) : wgQr?.qrcode ? (
                <img src={wgQr.qrcode} alt="WireGuard QR Code" className="w-48 h-48 rounded-lg border border-blue-200" />
              ) : (
                <p className="text-sm text-gray-500">QR-код недоступен</p>
              )}
            </div>
          )}

          {/* Server info */}
          <div className="mt-4 space-y-2">
            <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg border border-blue-100 text-sm">
              <span className="text-gray-600">Сервер</span>
              <div className="flex items-center gap-2">
                <code className="font-mono text-blue-700">{wgData.server_ip}:{wgData.server_port}</code>
                <button
                  onClick={() => copyToClipboard(`${wgData.server_ip}:${wgData.server_port}`, 'wgserver')}
                  className="text-blue-400 hover:text-blue-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
                {copied === 'wgserver' && <span className="text-xs text-green-600">Скопировано!</span>}
              </div>
            </div>
            <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg border border-blue-100 text-sm">
              <span className="text-gray-600">Ваш IP</span>
              <code className="font-mono text-blue-700">{wgData.client_ip}</code>
            </div>
          </div>

          {/* Platform instructions */}
          <div className="mt-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Инструкции по платформам</h3>
            <PlatformAccordion
              colorClass="blue"
              platforms={[
                { key: 'ios', label: 'iPhone / iPad', icon: '📱', data: wgData.instructions?.ios },
                { key: 'android', label: 'Android', icon: '🤖', data: wgData.instructions?.android },
                { key: 'windows', label: 'Windows', icon: '🪟', data: wgData.instructions?.windows },
                { key: 'macos', label: 'macOS', icon: '🍏', data: wgData.instructions?.mac },
                { key: 'linux', label: 'Linux', icon: '🐧', data: wgData.instructions?.linux },
              ]}
            />
          </div>
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
