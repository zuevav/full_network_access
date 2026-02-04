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
  ChevronUp
} from 'lucide-react'
import api from '../../api'

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
    <div>
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/admin/clients')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('clients.backToClients')}
        </button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{client.name}</h1>
            <div className="flex items-center gap-4 mt-2">
              {client.is_active ? (
                <span className="inline-flex items-center gap-1 text-green-600">
                  <CheckCircle className="w-4 h-4" />
                  {t('common.active')}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-red-600">
                  <XCircle className="w-4 h-4" />
                  {t('common.inactive')}
                </span>
              )}
              <span className="px-2 py-1 bg-gray-100 rounded text-sm">
                {client.service_type}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            {client.is_active ? (
              <button
                onClick={() => deactivateMutation.mutate()}
                className="btn btn-danger"
              >
                {t('clients.deactivate')}
              </button>
            ) : (
              <button
                onClick={() => activateMutation.mutate()}
                className="btn btn-primary"
              >
                {t('clients.activate')}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`py-3 px-1 border-b-2 font-medium transition-colors ${
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
  const portalUrl = `${window.location.origin}/api/connect/${client.access_token}`

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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Download profiles */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Smartphone className="w-5 h-5" />
          {t('clients.downloadProfiles')}
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {[
            { platform: 'windows', label: 'Windows', icon: '🪟' },
            { platform: 'ios', label: 'iPhone/iPad', icon: '📱' },
            { platform: 'macos', label: 'macOS', icon: '🍏' },
            { platform: 'android', label: 'Android', icon: '🤖' },
          ].map(({ platform, label, icon }) => (
            <button
              key={platform}
              onClick={() => downloadProfile(platform)}
              className="flex items-center justify-center gap-2 p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <span className="text-2xl">{icon}</span>
              <span className="font-medium">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Portal link */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Globe className="w-5 h-5" />
          {t('clients.portalLink')}
        </h3>
        <div className="flex gap-2">
          <input
            type="text"
            className="input flex-1"
            value={portalUrl}
            readOnly
          />
          <button
            onClick={() => copyToClipboard(portalUrl)}
            className="btn btn-secondary flex items-center gap-2"
          >
            {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            {copied ? t('clients.copied') : t('clients.copy')}
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          {t('clients.portalLinkHint')}
        </p>
      </div>

      {/* VPN credentials */}
      {client.vpn_config && (
        <VpnCredentials clientId={client.id} t={t} />
      )}

      {/* Proxy credentials */}
      {client.proxy_account && (
        <ProxyCredentials clientId={client.id} t={t} />
      )}
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

function DomainsTab({ client, t }) {
  const queryClient = useQueryClient()
  const [newDomain, setNewDomain] = useState('')
  const [expandedGroups, setExpandedGroups] = useState({})

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
    },
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
      addMutation.mutate([newDomain.trim()])
    }
  }

  const toggleGroup = (groupName) => {
    setExpandedGroups(prev => ({ ...prev, [groupName]: !prev[groupName] }))
  }

  // Group domains by template
  const groupedDomains = () => {
    if (!domains || !templates) return { groups: [], manual: [] }

    const domainMap = new Map(domains.map(d => [d.domain, d]))
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
            />
            <button type="submit" className="btn btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />
              {t('common.add')}
            </button>
          </form>
        </div>

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
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">{t('clients.paymentHistory')}</h3>
          {data && (
            <p className={`text-sm ${data.status === 'active' ? 'text-green-600' : 'text-red-600'}`}>
              {t('common.status')}: {data.status}
              {data.days_left !== null && ` (${data.days_left} ${t('clients.daysLeft')})`}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          {t('clients.addSubscription')}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="p-4 border-b border-gray-100 bg-gray-50">
          <div className="grid grid-cols-2 gap-4">
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
            <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary">
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn-primary">
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
        <table className="w-full">
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
