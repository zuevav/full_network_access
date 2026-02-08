import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Download,
  Plus,
  Trash2,
  RefreshCw,
  Copy,
  CheckCircle,
  XCircle,
  Globe,
  CreditCard,
  Settings,
  Smartphone,
  ChevronDown,
  ChevronUp,
  Search,
  Loader,
  X,
  Check
} from 'lucide-react'
import api from '../../api'

function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const value = bytes / Math.pow(1024, i)
  return `${value.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

function formatRelativeTime(dateStr) {
  if (!dateStr) return null
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 60) return `${diffSec} сек. назад`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} мин. назад`
  const diffHour = Math.floor(diffMin / 60)
  if (diffHour < 24) return `${diffHour} ч. назад`
  const diffDay = Math.floor(diffHour / 24)
  return `${diffDay} дн. назад`
}

export default function ClientDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('Profiles')

  const tabs = [
    { key: 'Profiles', label: t('clients.tabProfiles') },
    { key: 'Domains', label: t('clients.tabDomains') },
    { key: 'Payments', label: t('clients.tabPayments') },
    { key: 'Settings', label: t('clients.tabSettings') }
  ]

  const { data: client, isLoading } = useQuery({
    queryKey: ['client', id],
    queryFn: () => api.getClient(id),
  })

  const activateMutation = useMutation({
    mutationFn: () => api.activateClient(id),
    onSuccess: () => queryClient.invalidateQueries(['client', id]),
  })

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateClient(id),
    onSuccess: () => queryClient.invalidateQueries(['client', id]),
  })

  if (isLoading) {
    return <div className="text-center py-12">{t('common.loading')}</div>
  }

  if (!client) {
    return <div className="text-center py-12">{t('clients.clientNotFound')}</div>
  }

  return (
    <div className="pb-20 md:pb-0">
      {/* Header */}
      <div className="mb-4 sm:mb-6">
        <button
          onClick={() => navigate('/admin/clients')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-3 sm:mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="text-sm sm:text-base">{t('clients.backToClients')}</span>
        </button>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">{client.name}</h1>
            <div className="flex items-center gap-3 sm:gap-4 mt-2">
              {client.is_active ? (
                <span className="inline-flex items-center gap-1 text-green-600 text-sm sm:text-base">
                  <CheckCircle className="w-4 h-4" />
                  {t('common.active')}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-red-600 text-sm sm:text-base">
                  <XCircle className="w-4 h-4" />
                  {t('common.inactive')}
                </span>
              )}
              <span className="px-2 py-1 bg-gray-100 rounded text-xs sm:text-sm">
                {client.service_type}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {client.is_active ? (
              <button
                onClick={() => deactivateMutation.mutate()}
                className="btn btn-danger w-full sm:w-auto"
              >
                {t('clients.deactivate')}
              </button>
            ) : (
              <button
                onClick={() => activateMutation.mutate()}
                className="btn btn-primary w-full sm:w-auto"
              >
                {t('clients.activate')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs - horizontally scrollable on mobile */}
      <div className="border-b border-gray-200 mb-4 sm:mb-6 -mx-4 px-4 sm:mx-0 sm:px-0">
        <nav className="flex gap-1 sm:gap-4 overflow-x-auto scrollbar-hide">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`py-3 px-3 sm:px-1 border-b-2 font-medium transition-colors whitespace-nowrap text-sm sm:text-base ${
                activeTab === tab.key
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'Profiles' && <ProfilesTab client={client} t={t} />}
      {activeTab === 'Domains' && <DomainsTab client={client} t={t} />}
      {activeTab === 'Payments' && <PaymentsTab clientId={id} t={t} />}
      {activeTab === 'Settings' && <SettingsTab client={client} t={t} />}
    </div>
  )
}

function ProfilesTab({ client, t }) {
  const [copied, setCopied] = useState(false)
  const [showRegenerate, setShowRegenerate] = useState(false)
  const [expiresInDays, setExpiresInDays] = useState('')
  const queryClient2 = useQueryClient()
  const portalUrl = `${window.location.origin}/api/connect/${client.access_token}`

  const regenerateMutation = useMutation({
    mutationFn: () => {
      const days = expiresInDays ? parseInt(expiresInDays) : null
      return api.regenerateClientToken(client.id, days)
    },
    onSuccess: () => {
      queryClient2.invalidateQueries(['client', String(client.id)])
      setShowRegenerate(false)
      setExpiresInDays('')
    },
  })

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      // Fallback for older browsers or HTTP context
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      document.body.appendChild(textArea)
      textArea.select()
      try {
        document.execCommand('copy')
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (e) {
        console.error('Copy failed:', e)
      }
      document.body.removeChild(textArea)
    }
  }

  const downloadProfile = (platform) => {
    window.open(`/api/admin/clients/${client.id}/profiles/${platform}`, '_blank')
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
      {/* Download profiles */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-900 mb-3 sm:mb-4 flex items-center gap-2 text-sm sm:text-base">
          <Smartphone className="w-5 h-5" />
          {t('clients.downloadProfiles')}
        </h3>
        <div className="grid grid-cols-2 gap-2 sm:gap-3">
          {[
            { platform: 'windows', label: 'Windows', icon: '🪟' },
            { platform: 'ios', label: 'iPhone/iPad', icon: '📱' },
            { platform: 'macos', label: 'macOS', icon: '🍏' },
            { platform: 'android', label: 'Android', icon: '🤖' },
          ].map(({ platform, label, icon }) => (
            <button
              key={platform}
              onClick={() => downloadProfile(platform)}
              className="flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 p-3 sm:p-4 bg-gray-50 rounded-lg hover:bg-gray-100 active:bg-gray-200 transition-colors"
            >
              <span className="text-xl sm:text-2xl">{icon}</span>
              <span className="font-medium text-xs sm:text-sm">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Portal link */}
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-900 mb-3 sm:mb-4 flex items-center gap-2 text-sm sm:text-base">
          <Globe className="w-5 h-5" />
          {t('clients.portalLink')}
        </h3>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            className="input flex-1 text-xs sm:text-sm"
            value={portalUrl}
            readOnly
          />
          <button
            onClick={() => copyToClipboard(portalUrl)}
            className="btn btn-secondary flex items-center justify-center gap-2 w-full sm:w-auto"
          >
            {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? t('clients.copied') : t('clients.copy')}
          </button>
        </div>
        <div className="flex items-center justify-between mt-2">
          <p className="text-xs sm:text-sm text-gray-500">
            {client.access_token_expires_at ? (
              <span className={new Date(client.access_token_expires_at) < new Date() ? 'text-red-600' : ''}>
                {new Date(client.access_token_expires_at) < new Date()
                  ? `Ссылка истекла ${new Date(client.access_token_expires_at).toLocaleDateString()}`
                  : `Действует до: ${new Date(client.access_token_expires_at).toLocaleDateString()}`
                }
              </span>
            ) : (
              <span>Бессрочная ссылка</span>
            )}
          </p>
          <button
            onClick={() => setShowRegenerate(!showRegenerate)}
            className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            <RefreshCw className="w-3 h-3" />
            Перегенерировать
          </button>
        </div>
        {showRegenerate && (
          <div className="mt-3 p-3 bg-gray-50 rounded-lg space-y-2">
            <div>
              <label className="text-xs text-gray-500">Срок действия (дней, пусто = бессрочно)</label>
              <input
                type="number"
                min="1"
                max="3650"
                className="input text-sm mt-1"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                placeholder="Бессрочно"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (confirm('Старая ссылка перестанет работать. Продолжить?')) {
                    regenerateMutation.mutate()
                  }
                }}
                disabled={regenerateMutation.isPending}
                className="btn btn-primary btn-sm flex items-center gap-1"
              >
                {regenerateMutation.isPending && <Loader className="w-3 h-3 animate-spin" />}
                Создать новую ссылку
              </button>
              <button
                onClick={() => setShowRegenerate(false)}
                className="btn btn-secondary btn-sm"
              >
                Отмена
              </button>
            </div>
          </div>
        )}
      </div>

      {/* VPN credentials */}
      {client.vpn_config && (
        <VpnCredentials clientId={client.id} t={t} />
      )}

      {/* Proxy credentials */}
      {client.proxy_account && (
        <ProxyCredentials clientId={client.id} t={t} />
      )}

      {/* XRay VLESS */}
      <XrayCredentials clientId={client.id} t={t} />

      {/* WireGuard */}
      <WireguardCredentials clientId={client.id} t={t} />
    </div>
  )
}

function VpnCredentials({ clientId, t }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['vpn-credentials', clientId],
    queryFn: () => api.getVpnCredentials(clientId),
  })

  const resetMutation = useMutation({
    mutationFn: () => api.resetVpnPassword(clientId),
    onSuccess: () => queryClient.invalidateQueries(['vpn-credentials', clientId]),
  })

  if (isLoading) return null

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">{t('clients.vpnCredentials')}</h3>
        <button
          onClick={() => resetMutation.mutate()}
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          {t('clients.resetPassword')}
        </button>
      </div>
      <div className="space-y-2 text-sm">
        <p><span className="text-gray-500">{t('clients.server')}:</span> {data?.server}</p>
        <p><span className="text-gray-500">{t('clients.username')}:</span> {data?.username}</p>
        <p><span className="text-gray-500">{t('clients.password')}:</span> {data?.password}</p>
      </div>
    </div>
  )
}

function ProxyCredentials({ clientId, t }) {
  const queryClient = useQueryClient()
  const [showIpEdit, setShowIpEdit] = useState(false)
  const [ipInput, setIpInput] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['proxy-credentials', clientId],
    queryFn: () => api.getProxyCredentials(clientId),
  })

  const resetMutation = useMutation({
    mutationFn: () => api.resetProxyPassword(clientId),
    onSuccess: () => queryClient.invalidateQueries(['proxy-credentials', clientId]),
  })

  const updateIpsMutation = useMutation({
    mutationFn: (ips) => api.updateProxyAllowedIps(clientId, ips),
    onSuccess: () => {
      queryClient.invalidateQueries(['proxy-credentials', clientId])
      setShowIpEdit(false)
    },
  })

  // Initialize IP input when data loads or edit mode opens
  const handleOpenIpEdit = () => {
    setIpInput(data?.allowed_ips?.join('\n') || '')
    setShowIpEdit(true)
  }

  const handleSaveIps = () => {
    const ips = ipInput.split('\n').map(ip => ip.trim()).filter(Boolean)
    updateIpsMutation.mutate(ips)
  }

  if (isLoading) return null

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">{t('clients.proxyCredentials')}</h3>
        <button
          onClick={() => resetMutation.mutate()}
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          {t('clients.resetPassword')}
        </button>
      </div>
      <div className="space-y-2 text-sm">
        <p><span className="text-gray-500">HTTP:</span> {data?.http_host}:{data?.http_port}</p>
        <p><span className="text-gray-500">SOCKS5:</span> {data?.socks_host}:{data?.socks_port}</p>
        <p><span className="text-gray-500">{t('clients.username')}:</span> {data?.username}</p>
        <p><span className="text-gray-500">{t('clients.password')}:</span> {data?.password}</p>
      </div>

      {/* IP Whitelist section */}
      <div className="mt-4 pt-4 border-t">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-gray-700 text-sm">{t('clients.allowedIps')}</h4>
          {!showIpEdit && (
            <button
              onClick={handleOpenIpEdit}
              className="text-sm text-primary-600 hover:text-primary-700"
            >
              {t('common.edit')}
            </button>
          )}
        </div>

        {showIpEdit ? (
          <div className="space-y-2">
            <textarea
              className="input text-sm font-mono h-24"
              value={ipInput}
              onChange={(e) => setIpInput(e.target.value)}
              placeholder={t('clients.allowedIpsPlaceholder')}
            />
            <p className="text-xs text-gray-500">{t('clients.allowedIpsHint')}</p>
            <div className="flex gap-2">
              <button
                onClick={handleSaveIps}
                disabled={updateIpsMutation.isPending}
                className="btn btn-primary btn-sm"
              >
                {t('common.save')}
              </button>
              <button
                onClick={() => setShowIpEdit(false)}
                className="btn btn-secondary btn-sm"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        ) : (
          <div>
            {data?.allowed_ips?.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {data.allowed_ips.map((ip, idx) => (
                  <span key={idx} className="px-2 py-1 bg-green-50 text-green-700 rounded text-xs font-mono">
                    {ip}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">{t('clients.noAllowedIps')}</p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function XrayCredentials({ clientId, t }) {
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [enableError, setEnableError] = useState('')

  const { data: serverStatus } = useQuery({
    queryKey: ['xray-status'],
    queryFn: () => api.getXrayStatus(),
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['xray-config', clientId],
    queryFn: () => api.getClientXray(clientId),
    enabled: serverStatus?.is_installed,
    retry: false,
  })

  const enableMutation = useMutation({
    mutationFn: () => api.enableClientXray(clientId),
    onSuccess: () => {
      setEnableError('')
      queryClient.invalidateQueries(['xray-config', clientId])
    },
    onError: (err) => {
      setEnableError(err.message || 'Ошибка при включении XRay')
    },
  })

  const disableMutation = useMutation({
    mutationFn: () => api.disableClientXray(clientId),
    onSuccess: () => queryClient.invalidateQueries(['xray-config', clientId]),
  })

  const regenerateMutation = useMutation({
    mutationFn: () => api.regenerateClientXray(clientId),
    onSuccess: () => queryClient.invalidateQueries(['xray-config', clientId]),
  })

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  // Server not installed or not configured
  if (!serverStatus?.is_installed || !serverStatus?.is_enabled) {
    return (
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-900 mb-2 text-sm sm:text-base">XRay (VLESS + REALITY)</h3>
        <p className="text-sm text-gray-500">
          {!serverStatus?.is_installed
            ? 'XRay не установлен на сервере'
            : 'XRay сервер не настроен. Настройте его в разделе "Настройки".'
          }
        </p>
      </div>
    )
  }

  if (isLoading) return null

  const hasConfig = data && !error

  return (
    <div className="card p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 text-sm sm:text-base">XRay (VLESS + REALITY)</h3>
        {hasConfig && data.is_active && (
          <button
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            <RefreshCw className={`w-4 h-4 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
            {t('clients.regenerateKeys')}
          </button>
        )}
      </div>

      {!hasConfig || !data.is_active ? (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500 mb-3">XRay не активирован для этого клиента</p>
          {enableError && (
            <p className="text-sm text-red-600 mb-3">{enableError}</p>
          )}
          <button
            onClick={() => enableMutation.mutate()}
            disabled={enableMutation.isPending}
            className="btn btn-primary btn-sm"
          >
            {enableMutation.isPending ? <Loader className="w-4 h-4 animate-spin" /> : 'Включить XRay'}
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-2 text-sm mb-4">
            <p><span className="text-gray-500">UUID:</span> <code className="bg-gray-100 px-1 rounded text-xs">{data.uuid}</code></p>
            {data.short_id && <p><span className="text-gray-500">Short ID:</span> {data.short_id}</p>}
            <div className="flex gap-4 pt-1">
              <p><span className="text-gray-500">Upload:</span> {formatBytes(data.traffic_up)}</p>
              <p><span className="text-gray-500">Download:</span> {formatBytes(data.traffic_down)}</p>
            </div>
          </div>

          {data.vless_url && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs text-gray-500 mb-2">VLESS URL:</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  className="input flex-1 text-xs font-mono"
                  value={data.vless_url}
                  readOnly
                />
                <button
                  onClick={() => copyToClipboard(data.vless_url)}
                  className="btn btn-secondary btn-sm"
                >
                  {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}

          <div className="mt-4 pt-3 border-t">
            <button
              onClick={() => disableMutation.mutate()}
              disabled={disableMutation.isPending}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Отключить XRay
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function WireguardCredentials({ clientId, t }) {
  const queryClient = useQueryClient()
  const [copied, setCopied] = useState(false)
  const [enableError, setEnableError] = useState('')

  const { data: serverStatus } = useQuery({
    queryKey: ['wireguard-status'],
    queryFn: () => api.getWireguardStatus(),
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['wireguard-config', clientId],
    queryFn: () => api.getClientWireguard(clientId),
    enabled: serverStatus?.is_installed,
    retry: false,
  })

  const enableMutation = useMutation({
    mutationFn: () => api.enableClientWireguard(clientId),
    onSuccess: () => {
      setEnableError('')
      queryClient.invalidateQueries(['wireguard-config', clientId])
    },
    onError: (err) => {
      setEnableError(err.message || 'Ошибка при включении WireGuard')
    },
  })

  const disableMutation = useMutation({
    mutationFn: () => api.disableClientWireguard(clientId),
    onSuccess: () => queryClient.invalidateQueries(['wireguard-config', clientId]),
  })

  const regenerateMutation = useMutation({
    mutationFn: () => api.regenerateClientWireguard(clientId),
    onSuccess: () => queryClient.invalidateQueries(['wireguard-config', clientId]),
  })

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  const downloadConfig = () => {
    if (data?.config) {
      const blob = new Blob([data.config], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `wireguard-${clientId}.conf`
      a.click()
      URL.revokeObjectURL(url)
    }
  }

  // Server not installed or not configured
  if (!serverStatus?.is_installed || !serverStatus?.is_enabled) {
    return (
      <div className="card p-4 sm:p-6">
        <h3 className="font-semibold text-gray-900 mb-2 text-sm sm:text-base">WireGuard VPN</h3>
        <p className="text-sm text-gray-500">
          {!serverStatus?.is_installed
            ? 'WireGuard не установлен на сервере'
            : 'WireGuard сервер не настроен. Настройте его в разделе "Настройки".'
          }
        </p>
      </div>
    )
  }

  if (isLoading) return null

  const hasConfig = data && !error

  return (
    <div className="card p-4 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900 text-sm sm:text-base">WireGuard VPN</h3>
        {hasConfig && data.is_active && (
          <button
            onClick={() => regenerateMutation.mutate()}
            disabled={regenerateMutation.isPending}
            className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
          >
            <RefreshCw className={`w-4 h-4 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
            {t('clients.regenerateKeys')}
          </button>
        )}
      </div>

      {!hasConfig || !data.is_active ? (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500 mb-3">WireGuard не активирован для этого клиента</p>
          {enableError && (
            <p className="text-sm text-red-600 mb-3">{enableError}</p>
          )}
          <button
            onClick={() => enableMutation.mutate()}
            disabled={enableMutation.isPending}
            className="btn btn-primary btn-sm"
          >
            {enableMutation.isPending ? <Loader className="w-4 h-4 animate-spin" /> : 'Включить WireGuard'}
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-2 text-sm mb-4">
            <p><span className="text-gray-500">IP:</span> {data.assigned_ip}</p>
            <p><span className="text-gray-500">Public Key:</span> <code className="bg-gray-100 px-1 rounded text-xs break-all">{data.public_key}</code></p>
            <div className="flex gap-4 pt-1">
              <p><span className="text-gray-500">Upload:</span> {formatBytes(data.traffic_up)}</p>
              <p><span className="text-gray-500">Download:</span> {formatBytes(data.traffic_down)}</p>
            </div>
            {data.last_handshake && (
              <p><span className="text-gray-500">Last handshake:</span> {formatRelativeTime(data.last_handshake)}</p>
            )}
          </div>

          {data.config && (
            <div className="flex gap-2 mt-3 pt-3 border-t">
              <button
                onClick={downloadConfig}
                className="btn btn-secondary btn-sm flex items-center gap-1"
              >
                <Download className="w-4 h-4" />
                Скачать .conf
              </button>
              <button
                onClick={() => copyToClipboard(data.config)}
                className="btn btn-secondary btn-sm flex items-center gap-1"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                Копировать
              </button>
            </div>
          )}

          <div className="mt-4 pt-3 border-t">
            <button
              onClick={() => disableMutation.mutate()}
              disabled={disableMutation.isPending}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Отключить WireGuard
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function DomainsTab({ client, t }) {
  const queryClient = useQueryClient()
  const [newDomain, setNewDomain] = useState('')
  const [expandedGroups, setExpandedGroups] = useState({})
  // Domain suggestions state
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [suggestions, setSuggestions] = useState(null)
  const [selectedSuggestions, setSelectedSuggestions] = useState(new Set())
  const [pendingDomain, setPendingDomain] = useState('')

  const { data: domains, isLoading } = useQuery({
    queryKey: ['client-domains', client.id],
    queryFn: () => api.getClientDomains(client.id),
  })

  const { data: templates } = useQuery({
    queryKey: ['templates'],
    queryFn: () => api.getTemplates(),
  })

  const addMutation = useMutation({
    mutationFn: (domains) => api.addClientDomains(client.id, domains),
    onSuccess: () => {
      queryClient.invalidateQueries(['client-domains', client.id])
      setNewDomain('')
      setShowSuggestions(false)
      setSuggestions(null)
      setPendingDomain('')
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: (domain) => api.analyzeDomain(domain),
    onSuccess: (data) => {
      if (data.suggested && data.suggested.length > 0) {
        setSuggestions(data)
        setSelectedSuggestions(new Set(data.suggested))
        setShowSuggestions(true)
      } else {
        // No suggestions, add domain directly
        addMutation.mutate([pendingDomain])
      }
    },
    onError: () => {
      // On error, just add the domain
      addMutation.mutate([pendingDomain])
    }
  })

  const deleteMutation = useMutation({
    mutationFn: (domainId) => api.deleteClientDomain(client.id, domainId),
    onSuccess: () => queryClient.invalidateQueries(['client-domains', client.id]),
  })

  const applyTemplateMutation = useMutation({
    mutationFn: (templateId) => api.applyTemplate(client.id, templateId),
    onSuccess: () => queryClient.invalidateQueries(['client-domains', client.id]),
  })

  const handleAddDomain = (e) => {
    e.preventDefault()
    if (newDomain.trim()) {
      const domain = newDomain.trim()
      setPendingDomain(domain)
      analyzeMutation.mutate(domain)
    }
  }

  const handleAddWithSuggestions = () => {
    const domainsToAdd = [pendingDomain, ...Array.from(selectedSuggestions)]
    addMutation.mutate(domainsToAdd)
  }

  const handleAddWithoutSuggestions = () => {
    addMutation.mutate([pendingDomain])
  }

  const toggleSuggestion = (domain) => {
    setSelectedSuggestions(prev => {
      const newSet = new Set(prev)
      if (newSet.has(domain)) {
        newSet.delete(domain)
      } else {
        newSet.add(domain)
      }
      return newSet
    })
  }

  const toggleGroup = (groupName) => {
    setExpandedGroups(prev => ({ ...prev, [groupName]: !prev[groupName] }))
  }

  // Group domains by template
  const groupedDomains = () => {
    if (!domains || !templates) return { groups: [], manual: [] }

    const usedDomains = new Set()
    const groups = []

    // Match domains against each template
    templates.forEach(template => {
      const templateDomainSet = new Set(template.domains || [])
      const matchedDomains = domains.filter(d => templateDomainSet.has(d.domain) && !usedDomains.has(d.domain))

      if (matchedDomains.length > 0) {
        matchedDomains.forEach(d => usedDomains.add(d.domain))
        groups.push({
          name: template.name,
          icon: template.icon,
          domains: matchedDomains,
          templateId: template.id
        })
      }
    })

    // Remaining domains are "manually added"
    const manual = domains.filter(d => !usedDomains.has(d.domain))

    return { groups, manual }
  }

  const { groups, manual } = groupedDomains()
  const totalDomains = domains?.length || 0

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        {/* Add domain form */}
        <div className="card p-4">
          <form onSubmit={handleAddDomain} className="flex gap-2">
            <input
              type="text"
              className="input flex-1"
              placeholder={t('clients.addDomainPlaceholder')}
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              disabled={analyzeMutation.isPending}
            />
            <button
              type="submit"
              className="btn btn-primary flex items-center gap-2"
              disabled={analyzeMutation.isPending || !newDomain.trim()}
            >
              {analyzeMutation.isPending ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              {analyzeMutation.isPending ? t('clients.analyzing') : t('common.add')}
            </button>
          </form>
        </div>

        {/* Domain Suggestions Dialog */}
        {showSuggestions && suggestions && (
          <div className="card p-4 border-2 border-blue-200 bg-blue-50/50">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h4 className="font-semibold text-gray-900 flex items-center gap-2">
                  <Search className="w-5 h-5 text-blue-600" />
                  {t('clients.relatedDomainsFound')}
                </h4>
                <p className="text-sm text-gray-600 mt-1">
                  {t('clients.relatedDomainsDescription', { domain: suggestions.original_domain })}
                </p>
              </div>
              <button
                onClick={() => setShowSuggestions(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Redirects */}
            {suggestions.redirects?.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-gray-500 uppercase mb-1">{t('clients.redirectDomains')}</p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.redirects.map(domain => (
                    <button
                      key={domain}
                      onClick={() => toggleSuggestion(domain)}
                      className={`px-2 py-1 rounded text-sm font-mono flex items-center gap-1 transition-colors ${
                        selectedSuggestions.has(domain)
                          ? 'bg-blue-100 text-blue-700 border border-blue-300'
                          : 'bg-gray-100 text-gray-500 border border-gray-200'
                      }`}
                    >
                      {selectedSuggestions.has(domain) && <Check className="w-3 h-3" />}
                      {domain}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Resources */}
            {suggestions.resources?.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-gray-500 uppercase mb-1">{t('clients.resourceDomains')}</p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.resources.map(domain => (
                    <button
                      key={domain}
                      onClick={() => toggleSuggestion(domain)}
                      className={`px-2 py-1 rounded text-sm font-mono flex items-center gap-1 transition-colors ${
                        selectedSuggestions.has(domain)
                          ? 'bg-green-100 text-green-700 border border-green-300'
                          : 'bg-gray-100 text-gray-500 border border-gray-200'
                      }`}
                    >
                      {selectedSuggestions.has(domain) && <Check className="w-3 h-3" />}
                      {domain}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 mt-4 pt-3 border-t border-blue-200">
              <button
                onClick={handleAddWithSuggestions}
                disabled={addMutation.isPending}
                className="btn btn-primary flex-1"
              >
                {addMutation.isPending ? (
                  <Loader className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Plus className="w-4 h-4 mr-2" />
                )}
                {t('clients.addWithSelected')} ({1 + selectedSuggestions.size})
              </button>
              <button
                onClick={handleAddWithoutSuggestions}
                disabled={addMutation.isPending}
                className="btn btn-secondary"
              >
                {t('clients.addOnlyOriginal')}
              </button>
            </div>
          </div>
        )}

        {isLoading ? (
          <p className="p-4 text-center text-gray-500">{t('common.loading')}</p>
        ) : totalDomains === 0 ? (
          <div className="card p-8 text-center text-gray-500">{t('clients.noDomains')}</div>
        ) : (
          <>
            {/* Grouped domains by template */}
            {groups.map((group) => (
              <div key={group.name} className="card">
                <button
                  onClick={() => toggleGroup(group.name)}
                  className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span>{group.icon}</span>
                    <span className="font-semibold">{group.name}</span>
                    <span className="text-sm text-gray-500">({group.domains.length})</span>
                  </div>
                  {expandedGroups[group.name] ? (
                    <ChevronUp className="w-5 h-5 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-5 h-5 text-gray-400" />
                  )}
                </button>

                {expandedGroups[group.name] && (
                  <ul className="border-t border-gray-100">
                    {group.domains.map((domain) => (
                      <li
                        key={domain.id}
                        className="flex items-center justify-between px-4 py-2 border-b border-gray-50 last:border-0 hover:bg-gray-50"
                      >
                        <span className="text-sm font-mono">{domain.domain}</span>
                        <button
                          onClick={() => deleteMutation.mutate(domain.id)}
                          className="text-gray-400 hover:text-red-600"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}

            {/* Manually added domains */}
            {manual.length > 0 && (
              <div className="card">
                <div className="p-4 border-b border-gray-100">
                  <div className="flex items-center gap-2">
                    <Globe className="w-5 h-5 text-gray-500" />
                    <span className="font-semibold">{t('clients.manuallyAdded')}</span>
                    <span className="text-sm text-gray-500">({manual.length})</span>
                  </div>
                </div>
                <ul>
                  {manual.map((domain) => (
                    <li
                      key={domain.id}
                      className="flex items-center justify-between px-4 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50"
                    >
                      <div>
                        <p className="font-medium">{domain.domain}</p>
                        <p className="text-xs text-gray-500">
                          {domain.include_subdomains ? t('clients.includeSubdomains') : t('clients.exactDomainOnly')}
                        </p>
                      </div>
                      <button
                        onClick={() => deleteMutation.mutate(domain.id)}
                        className="text-gray-400 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>

      <div className="card p-4 h-fit">
        <h3 className="font-semibold text-gray-900 mb-4">{t('clients.applyTemplate')}</h3>
        <div className="space-y-2">
          {templates?.map((template) => (
            <button
              key={template.id}
              onClick={() => applyTemplateMutation.mutate(template.id)}
              className="w-full text-left p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <span className="mr-2">{template.icon}</span>
              <span className="font-medium">{template.name}</span>
              <span className="text-sm text-gray-500 ml-2">
                ({template.domains?.length || 0} {t('clients.domainsCount')})
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function PaymentsTab({ clientId, t }) {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [amount, setAmount] = useState('')
  const [duration, setDuration] = useState('1')

  // Duration options in months
  const durationOptions = [
    { value: '1', label: t('clients.duration1Month') },
    { value: '2', label: t('clients.duration2Months') },
    { value: '3', label: t('clients.duration3Months') },
    { value: '4', label: t('clients.duration4Months') },
    { value: '6', label: t('clients.duration6Months') },
    { value: '12', label: t('clients.duration1Year') },
    { value: '24', label: t('clients.duration2Years') },
  ]

  const { data, isLoading } = useQuery({
    queryKey: ['client-payments', clientId],
    queryFn: () => api.getClientPayments(clientId),
  })

  const createMutation = useMutation({
    mutationFn: (payment) => api.createPayment(clientId, payment),
    onSuccess: () => {
      queryClient.invalidateQueries(['client-payments', clientId])
      queryClient.invalidateQueries(['client', clientId])
      setShowForm(false)
      setAmount('')
      setDuration('1')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (paymentId) => api.deletePayment(paymentId),
    onSuccess: () => queryClient.invalidateQueries(['client-payments', clientId]),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    const months = parseInt(duration)
    const validFrom = new Date()
    const validUntil = new Date()
    validUntil.setMonth(validUntil.getMonth() + months)

    createMutation.mutate({
      amount: parseFloat(amount) || 0,
      valid_from: validFrom.toISOString().split('T')[0],
      valid_until: validUntil.toISOString().split('T')[0],
    })
  }

  return (
    <div className="card">
      <div className="p-3 sm:p-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-sm sm:text-base">{t('clients.paymentHistory')}</h3>
          {data && (
            <p className={`text-xs sm:text-sm ${data.status === 'active' ? 'text-green-600' : 'text-red-600'}`}>
              {t('common.status')}: {data.status}
              {data.days_left !== null && ` (${data.days_left} ${t('clients.daysLeft')})`}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary flex items-center justify-center gap-2 w-full sm:w-auto"
        >
          <Plus className="w-4 h-4" />
          {t('clients.addSubscription')}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="p-3 sm:p-4 border-b border-gray-100 bg-gray-50">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label className="label">{t('clients.subscriptionDuration')}</label>
              <select
                className="input"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
              >
                {durationOptions.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t('clients.amount')} (RUB) - {t('clients.optional')}</label>
              <input
                type="number"
                className="input"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0"
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary flex-1 sm:flex-none">
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn-primary flex-1 sm:flex-none">
              {t('clients.giveSubscription')}
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <p className="p-4 text-center text-gray-500">{t('common.loading')}</p>
      ) : data?.payments?.length === 0 ? (
        <p className="p-8 text-center text-gray-500">{t('clients.noPayments')}</p>
      ) : (
        <>
          {/* Desktop table */}
          <table className="w-full hidden sm:table">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-4 font-medium text-gray-600">{t('common.date')}</th>
                <th className="text-left p-4 font-medium text-gray-600">{t('clients.amount')}</th>
                <th className="text-left p-4 font-medium text-gray-600">{t('clients.period')}</th>
                <th className="text-left p-4 font-medium text-gray-600">{t('common.status')}</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {data?.payments?.map((payment) => (
                <tr key={payment.id} className="border-b border-gray-50">
                  <td className="p-4">
                    {new Date(payment.paid_at).toLocaleDateString()}
                  </td>
                  <td className="p-4">{payment.amount} {payment.currency}</td>
                  <td className="p-4">
                    {new Date(payment.valid_from).toLocaleDateString()} - {new Date(payment.valid_until).toLocaleDateString()}
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded text-sm ${
                      payment.status === 'paid' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {payment.status}
                    </span>
                  </td>
                  <td className="p-4">
                    <button
                      onClick={() => deleteMutation.mutate(payment.id)}
                      className="text-gray-400 hover:text-red-600"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Mobile cards */}
          <div className="sm:hidden divide-y divide-gray-100">
            {data?.payments?.map((payment) => (
              <div key={payment.id} className="p-3">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <p className="font-medium text-sm">
                      {new Date(payment.paid_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-gray-500">
                      {new Date(payment.valid_from).toLocaleDateString()} - {new Date(payment.valid_until).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => deleteMutation.mutate(payment.id)}
                    className="text-gray-400 hover:text-red-600 p-1"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{payment.amount} {payment.currency}</span>
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    payment.status === 'paid' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {payment.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function SettingsTab({ client, t }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState(client.name)
  const [email, setEmail] = useState(client.email || '')
  const [phone, setPhone] = useState(client.phone || '')
  const [telegramId, setTelegramId] = useState(client.telegram_id || '')

  const updateMutation = useMutation({
    mutationFn: (data) => api.updateClient(client.id, data),
    onSuccess: () => queryClient.invalidateQueries(['client', client.id]),
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteClient(client.id),
    onSuccess: () => navigate('/admin/clients'),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    updateMutation.mutate({ name, email, phone, telegram_id: telegramId })
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="card p-6">
        <h3 className="font-semibold text-gray-900 mb-4">{t('clients.clientInfo')}</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">{t('clients.name')}</label>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">{t('clients.email')}</label>
            <input
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label">{t('clients.phone')}</label>
            <input
              type="text"
              className="input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div>
            <label className="label">{t('clients.telegramId')}</label>
            <input
              type="text"
              className="input"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            {t('clients.saveChanges')}
          </button>
        </form>
      </div>

      <div className="card p-6">
        <h3 className="font-semibold text-red-600 mb-4">{t('clients.dangerZone')}</h3>
        <p className="text-gray-600 mb-4">
          {t('clients.deleteWarning')}
        </p>
        <button
          onClick={() => {
            if (confirm(t('clients.deleteConfirm'))) {
              deleteMutation.mutate()
            }
          }}
          className="btn btn-danger"
        >
          {t('clients.deleteClient')}
        </button>
      </div>
    </div>
  )
}
