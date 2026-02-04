import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Plus,
  Search,
  ChevronRight,
  CheckCircle,
  XCircle,
  X
} from 'lucide-react'
import api from '../../api'

function NewClientModal({ isOpen, onClose, onSuccess, t }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [serviceType, setServiceType] = useState('both')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.createClient({ name, email, phone, service_type: serviceType })
      onSuccess()
      onClose()
      setName('')
      setEmail('')
      setPhone('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl w-full max-w-md p-6 m-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{t('clients.newClient')}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg">{error}</div>
          )}

          <div>
            <label className="label">{t('clients.name')} *</label>
            <input
              type="text"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
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
            <label className="label">{t('clients.serviceType')}</label>
            <select
              className="input"
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
            >
              <option value="both">{t('clients.vpnAndProxy')}</option>
              <option value="vpn">{t('clients.vpnOnly')}</option>
              <option value="proxy">{t('clients.proxyOnly')}</option>
            </select>
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              {t('common.cancel')}
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">
              {loading ? t('clients.creating') : t('clients.create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Clients() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showModal, setShowModal] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['clients', search, statusFilter],
    queryFn: () => api.getClients({ search, status: statusFilter }),
  })

  const handleSuccess = () => {
    queryClient.invalidateQueries(['clients'])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('clients.title')}</h1>
        <button
          onClick={() => setShowModal(true)}
          className="btn btn-primary flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          {t('clients.newClient')}
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4 mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder={t('clients.searchPlaceholder')}
                className="input pl-10"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <select
            className="input w-auto"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">{t('common.all')}</option>
            <option value="active">{t('common.active')}</option>
            <option value="inactive">{t('common.inactive')}</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="text-left p-4 font-medium text-gray-600">{t('clients.name')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('common.status')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('clients.service')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('clients.domains')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('clients.validUntil')}</th>
              <th className="p-4"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-500">
                  {t('common.loading')}
                </td>
              </tr>
            ) : data?.items?.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-500">
                  {t('clients.noClients')}
                </td>
              </tr>
            ) : (
              data?.items?.map((client) => (
                <tr key={client.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="p-4">
                    <div>
                      <p className="font-medium text-gray-900">{client.name}</p>
                      {client.email && (
                        <p className="text-sm text-gray-500">{client.email}</p>
                      )}
                    </div>
                  </td>
                  <td className="p-4">
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
                  </td>
                  <td className="p-4">
                    <span className="px-2 py-1 bg-gray-100 rounded text-sm">
                      {client.service_type}
                    </span>
                  </td>
                  <td className="p-4 text-gray-600">{client.domains_count}</td>
                  <td className="p-4 text-gray-600">
                    {client.valid_until
                      ? new Date(client.valid_until).toLocaleDateString()
                      : '-'
                    }
                  </td>
                  <td className="p-4">
                    <Link
                      to={`/admin/clients/${client.id}`}
                      className="text-primary-600 hover:text-primary-700"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <NewClientModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={handleSuccess}
        t={t}
      />
    </div>
  )
}
