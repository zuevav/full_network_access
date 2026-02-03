import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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

function DeviceCard({ icon: Icon, title, description, profileUrl, instructions }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="card">
      <div className="p-4 sm:p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-primary-50 rounded-xl">
            <Icon className="w-6 h-6 text-primary-600" />
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
          Скачать профиль
        </a>

        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full mt-3 text-sm text-gray-500 flex items-center justify-center gap-1 hover:text-gray-700"
        >
          Как установить
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
      title: 'iPhone / iPad',
      description: 'Автоматическая настройка — ничего устанавливать не нужно!',
      profileUrl: '/api/portal/profiles/ios',
      instructions: [
        'Нажмите кнопку "Скачать профиль" (в Safari)',
        'Откройте "Настройки"',
        'Вверху появится "Профиль загружен"',
        'Нажмите "Установить"',
        'Готово! VPN включится автоматически',
      ],
    },
    {
      icon: () => <span className="text-2xl">🤖</span>,
      title: 'Android',
      description: 'Нужно приложение strongSwan (бесплатное)',
      profileUrl: '/api/portal/profiles/android',
      instructions: [
        'Установите strongSwan из Play Store',
        'Скачайте профиль .sswan',
        'Откройте файл в strongSwan',
        'Нажмите "Импорт"',
        'Подключитесь к VPN',
      ],
    },
    {
      icon: Monitor,
      title: 'Windows 10/11',
      description: 'Автоматическая настройка — запустите скрипт',
      profileUrl: '/api/portal/profiles/windows',
      instructions: [
        'Скачайте файл .ps1',
        'Правый клик → "Запуск от имени администратора"',
        'Дождитесь завершения скрипта',
        'Откройте Настройки → Сеть → VPN',
        'Нажмите "ProxyGate VPN" → Подключить',
        'Введите пароль (только при первом разе)',
      ],
    },
    {
      icon: () => <span className="text-2xl">🍏</span>,
      title: 'macOS',
      description: 'Профиль для Mac',
      profileUrl: '/api/portal/profiles/macos',
      instructions: [
        'Скачайте профиль .mobileconfig',
        'Дважды кликните на файл',
        'Откройте Системные настройки → Профили',
        'Установите профиль ProxyGate',
        'VPN появится в строке меню',
      ],
    },
  ]

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Мои устройства</h1>
        <p className="text-gray-500 mt-1">
          Выберите устройство и скачайте профиль для настройки VPN
        </p>
      </div>

      {/* Device cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {devices.map((device, idx) => (
          <DeviceCard key={idx} {...device} />
        ))}
      </div>

      {/* Proxy section */}
      {profileInfo?.proxy && (
        <div className="card p-4 sm:p-6">
          <h2 className="font-semibold text-gray-900 mb-4">
            Альтернатива: Прокси (для браузера)
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Если VPN не подходит, настройте прокси в браузере или системе.
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
              <span className="text-gray-500">Логин</span>
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
              <span className="text-gray-500">Пароль</span>
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
            Скачать PAC-файл
          </a>
          <p className="text-xs text-gray-500 mt-2 text-center">
            PAC автоматически направляет нужные сайты через прокси
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
            <p className="font-medium text-gray-900">strongSwan для Android</p>
            <p className="text-sm text-gray-500">Бесплатно в Play Store</p>
          </div>
          <ExternalLink className="w-5 h-5 text-gray-400" />
        </div>
      </a>
    </div>
  )
}
