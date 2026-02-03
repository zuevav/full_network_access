import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Globe,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  Send
} from 'lucide-react'
import api from '../../api'

export default function PortalDomains() {
  const queryClient = useQueryClient()
  const [newDomain, setNewDomain] = useState('')
  const [reason, setReason] = useState('')
  const [showForm, setShowForm] = useState(false)

  const { data: domainsData, isLoading: domainsLoading } = useQuery({
    queryKey: ['portal-domains'],
    queryFn: () => api.getPortalDomains(),
  })

  const { data: requestsData, isLoading: requestsLoading } = useQuery({
    queryKey: ['portal-domain-requests'],
    queryFn: () => api.getPortalDomainRequests(),
  })

  const requestMutation = useMutation({
    mutationFn: () => api.requestDomain(newDomain, reason),
    onSuccess: () => {
      queryClient.invalidateQueries(['portal-domain-requests'])
      setNewDomain('')
      setReason('')
      setShowForm(false)
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (newDomain.trim()) {
      requestMutation.mutate()
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'approved':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'rejected':
        return <XCircle className="w-4 h-4 text-red-500" />
      default:
        return <Clock className="w-4 h-4 text-yellow-500" />
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'approved':
        return 'одобрен'
      case 'rejected':
        return 'отклонён'
      default:
        return 'на рассмотрении'
    }
  }

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Мои сайты</h1>
        <p className="text-gray-500 mt-1">
          Через VPN/прокси доступны следующие сайты
        </p>
      </div>

      {/* Domains list */}
      {domainsLoading ? (
        <div className="text-center py-8">Загрузка...</div>
      ) : (
        <div className="card">
          {Object.entries(domainsData?.grouped_by_template || {}).map(([group, domains]) => (
            <div key={group} className="border-b border-gray-100 last:border-0">
              <div className="p-4 bg-gray-50 font-medium text-gray-700 flex items-center gap-2">
                <Globe className="w-4 h-4" />
                {group}
                <span className="text-sm text-gray-500">({domains.length})</span>
              </div>
              <ul className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
                {domains.map((domain) => (
                  <li key={domain} className="flex items-center gap-2 text-gray-600">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span className="font-mono text-sm">{domain}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {Object.keys(domainsData?.grouped_by_template || {}).length === 0 && (
            <p className="p-8 text-center text-gray-500">
              Нет настроенных сайтов
            </p>
          )}
        </div>
      )}

      {/* Request new domain */}
      <div className="card p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Нужен ещё сайт?</h2>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="btn btn-primary btn-sm flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              Запросить
            </button>
          )}
        </div>

        {showForm && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Домен</label>
              <input
                type="text"
                className="input"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="example.com"
                required
              />
            </div>
            <div>
              <label className="label">Зачем нужен (необязательно)</label>
              <input
                type="text"
                className="input"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Для работы с клиентами"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="btn btn-secondary flex-1"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={requestMutation.isPending}
                className="btn btn-primary flex-1 flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" />
                Отправить
              </button>
            </div>
          </form>
        )}

        {!showForm && (
          <p className="text-sm text-gray-600">
            Отправьте запрос администратору на добавление нового сайта.
          </p>
        )}
      </div>

      {/* Requests history */}
      {requestsData?.length > 0 && (
        <div>
          <h2 className="font-semibold text-gray-900 mb-3">Мои запросы</h2>
          <div className="card divide-y divide-gray-100">
            {requestsData.map((request) => (
              <div key={request.id} className="p-4 flex items-start gap-3">
                {getStatusIcon(request.status)}
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{request.domain}</p>
                  <p className="text-sm text-gray-500">
                    {getStatusText(request.status)} &middot;{' '}
                    {new Date(request.created_at).toLocaleDateString('ru')}
                  </p>
                  {request.admin_comment && (
                    <p className="text-sm text-gray-600 mt-1 italic">
                      "{request.admin_comment}"
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
