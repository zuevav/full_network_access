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
  Smartphone
} from 'lucide-react'
import api from '../../api'

const tabs = ['Profiles', 'Domains', 'Payments', 'Settings']

export default function ClientDetail() {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('Profiles')

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
    return <div className="text-center py-12">Loading...</div>
  }

  if (!client) {
    return <div className="text-center py-12">Client not found</div>
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
          Back to clients
        </button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{client.name}</h1>
            <div className="flex items-center gap-4 mt-2">
              {client.is_active ? (
                <span className="inline-flex items-center gap-1 text-green-600">
                  <CheckCircle className="w-4 h-4" />
                  Active
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-red-600">
                  <XCircle className="w-4 h-4" />
                  Inactive
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
                Deactivate
              </button>
            ) : (
              <button
                onClick={() => activateMutation.mutate()}
                className="btn btn-primary"
              >
                Activate
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
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-3 px-1 border-b-2 font-medium transition-colors ${
                activeTab === tab
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'Profiles' && <ProfilesTab client={client} />}
      {activeTab === 'Domains' && <DomainsTab client={client} />}
      {activeTab === 'Payments' && <PaymentsTab clientId={id} />}
      {activeTab === 'Settings' && <SettingsTab client={client} />}
    </div>
  )
}

function ProfilesTab({ client }) {
  const [copied, setCopied] = useState(false)
  const portalUrl = `${window.location.origin}/connect/${client.access_token}`

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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
          Download Profiles
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
          Client Portal Link
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
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          Share this link with the client for quick access
        </p>
      </div>

      {/* VPN credentials */}
      {client.vpn_config && (
        <VpnCredentials clientId={client.id} />
      )}

      {/* Proxy credentials */}
      {client.proxy_account && (
        <ProxyCredentials clientId={client.id} />
      )}
    </div>
  )
}

function VpnCredentials({ clientId }) {
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
        <h3 className="font-semibold text-gray-900">VPN Credentials</h3>
        <button
          onClick={() => resetMutation.mutate()}
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          Reset Password
        </button>
      </div>
      <div className="space-y-2 text-sm">
        <p><span className="text-gray-500">Server:</span> {data?.server}</p>
        <p><span className="text-gray-500">Username:</span> {data?.username}</p>
        <p><span className="text-gray-500">Password:</span> {data?.password}</p>
      </div>
    </div>
  )
}

function ProxyCredentials({ clientId }) {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['proxy-credentials', clientId],
    queryFn: () => api.getProxyCredentials(clientId),
  })

  const resetMutation = useMutation({
    mutationFn: () => api.resetProxyPassword(clientId),
    onSuccess: () => queryClient.invalidateQueries(['proxy-credentials', clientId]),
  })

  if (isLoading) return null

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">Proxy Credentials</h3>
        <button
          onClick={() => resetMutation.mutate()}
          className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
        >
          <RefreshCw className="w-4 h-4" />
          Reset Password
        </button>
      </div>
      <div className="space-y-2 text-sm">
        <p><span className="text-gray-500">HTTP:</span> {data?.http_host}:{data?.http_port}</p>
        <p><span className="text-gray-500">SOCKS5:</span> {data?.socks_host}:{data?.socks_port}</p>
        <p><span className="text-gray-500">Username:</span> {data?.username}</p>
        <p><span className="text-gray-500">Password:</span> {data?.password}</p>
      </div>
    </div>
  )
}

function DomainsTab({ client }) {
  const queryClient = useQueryClient()
  const [newDomain, setNewDomain] = useState('')

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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 card">
        <div className="p-4 border-b border-gray-100">
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
          <p className="p-4 text-center text-gray-500">Loading...</p>
        ) : domains?.length === 0 ? (
          <p className="p-8 text-center text-gray-500">No domains configured</p>
        ) : (
          <ul>
            {domains?.map((domain) => (
              <li
                key={domain.id}
                className="flex items-center justify-between p-4 border-b border-gray-50 last:border-0"
              >
                <div>
                  <p className="font-medium">{domain.domain}</p>
                  <p className="text-sm text-gray-500">
                    {domain.include_subdomains ? 'Including subdomains' : 'Exact domain only'}
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
        )}
      </div>

      <div className="card p-4">
        <h3 className="font-semibold text-gray-900 mb-4">Apply Template</h3>
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
                ({template.domains.length} domains)
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

function PaymentsTab({ clientId }) {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [amount, setAmount] = useState('')
  const [validFrom, setValidFrom] = useState('')
  const [validUntil, setValidUntil] = useState('')

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
      setValidFrom('')
      setValidUntil('')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (paymentId) => api.deletePayment(paymentId),
    onSuccess: () => queryClient.invalidateQueries(['client-payments', clientId]),
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    createMutation.mutate({
      amount: parseFloat(amount),
      valid_from: validFrom,
      valid_until: validUntil,
    })
  }

  return (
    <div className="card">
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Payment History</h3>
          {data && (
            <p className={`text-sm ${data.status === 'active' ? 'text-green-600' : 'text-red-600'}`}>
              Status: {data.status}
              {data.days_left !== null && ` (${data.days_left} days left)`}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Payment
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="p-4 border-b border-gray-100 bg-gray-50">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Amount (RUB)</label>
              <input
                type="number"
                className="input"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label">Valid From</label>
              <input
                type="date"
                className="input"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label">Valid Until</label>
              <input
                type="date"
                className="input"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button type="button" onClick={() => setShowForm(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Save Payment
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <p className="p-4 text-center text-gray-500">Loading...</p>
      ) : data?.payments?.length === 0 ? (
        <p className="p-8 text-center text-gray-500">No payments yet</p>
      ) : (
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left p-4 font-medium text-gray-600">Date</th>
              <th className="text-left p-4 font-medium text-gray-600">Amount</th>
              <th className="text-left p-4 font-medium text-gray-600">Period</th>
              <th className="text-left p-4 font-medium text-gray-600">Status</th>
              <th className="p-4"></th>
            </tr>
          </thead>
          <tbody>
            {data?.payments?.map((payment) => (
              <tr key={payment.id} className="border-b border-gray-50">
                <td className="p-4">
                  {new Date(payment.paid_at).toLocaleDateString('ru')}
                </td>
                <td className="p-4">{payment.amount} {payment.currency}</td>
                <td className="p-4">
                  {new Date(payment.valid_from).toLocaleDateString('ru')} - {new Date(payment.valid_until).toLocaleDateString('ru')}
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

function SettingsTab({ client }) {
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
        <h3 className="font-semibold text-gray-900 mb-4">Client Information</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name</label>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Email</label>
            <input
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Phone</label>
            <input
              type="text"
              className="input"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Telegram ID</label>
            <input
              type="text"
              className="input"
              value={telegramId}
              onChange={(e) => setTelegramId(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Save Changes
          </button>
        </form>
      </div>

      <div className="card p-6">
        <h3 className="font-semibold text-red-600 mb-4">Danger Zone</h3>
        <p className="text-gray-600 mb-4">
          Deleting a client will remove all their data including VPN config, proxy account, domains, and payment history.
        </p>
        <button
          onClick={() => {
            if (confirm('Are you sure you want to delete this client?')) {
              deleteMutation.mutate()
            }
          }}
          className="btn btn-danger"
        >
          Delete Client
        </button>
      </div>
    </div>
  )
}
