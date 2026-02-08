import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Globe,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  Send,
  Search,
  Loader,
  Check,
  Download
} from 'lucide-react'
import api from '../../api'

export default function PortalDomains() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  // Domain request form (legacy)
  const [newDomain, setNewDomain] = useState('')
  const [reason, setReason] = useState('')
  const [showRequestForm, setShowRequestForm] = useState(false)

  // Self-service add domain form
  const [domainInput, setDomainInput] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [suggestions, setSuggestions] = useState(null)
  const [selectedSuggestions, setSelectedSuggestions] = useState(new Set())

  const { data: domainsData, isLoading: domainsLoading } = useQuery({
    queryKey: ['portal-domains'],
    queryFn: () => api.getPortalDomains(),
  })

  const { data: requestsData } = useQuery({
    queryKey: ['portal-domain-requests'],
    queryFn: () => api.getPortalDomainRequests(),
  })

  const { data: templates, isLoading: templatesLoading } = useQuery({
    queryKey: ['portal-templates'],
    queryFn: () => api.getPortalTemplates(),
  })

  const requestMutation = useMutation({
    mutationFn: () => api.requestDomain(newDomain, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-domain-requests'] })
      setNewDomain('')
      setReason('')
      setShowRequestForm(false)
    },
  })

  const applyTemplateMutation = useMutation({
    mutationFn: (templateId) => api.applyPortalTemplate(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-domains'] })
      queryClient.invalidateQueries({ queryKey: ['portal-templates'] })
    },
  })

  const addDomainsMutation = useMutation({
    mutationFn: ({ domains, includeSubdomains }) => api.addPortalDomains(domains, includeSubdomains),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portal-domains'] })
      setDomainInput('')
      setSuggestions(null)
      setSelectedSuggestions(new Set())
    },
  })

  const handleRequestSubmit = (e) => {
    e.preventDefault()
    if (newDomain.trim()) {
      requestMutation.mutate()
    }
  }

  // Check if all template domains are already added
  const clientDomainsSet = new Set((domainsData?.domains || []).map(d => d.domain))

  const isTemplateApplied = (template) => {
    return template.domains.every(d => clientDomainsSet.has(d))
  }

  // Domain analysis
  const handleAnalyze = async () => {
    if (!domainInput.trim()) return
    setAnalyzing(true)
    setSuggestions(null)

    try {
      const result = await api.analyzePortalDomain(domainInput.trim())
      if (result.suggested && result.suggested.length > 0) {
        setSuggestions(result)
        setSelectedSuggestions(new Set(result.suggested))
      } else {
        // No suggestions — add domain directly
        addDomainsMutation.mutate({ domains: [domainInput.trim()], includeSubdomains: true })
      }
    } catch {
      // On error — add domain directly
      addDomainsMutation.mutate({ domains: [domainInput.trim()], includeSubdomains: true })
    } finally {
      setAnalyzing(false)
    }
  }

  const handleAddWithSelected = () => {
    const domainsToAdd = [domainInput.trim(), ...Array.from(selectedSuggestions)]
    addDomainsMutation.mutate({ domains: domainsToAdd, includeSubdomains: true })
  }

  const handleAddOnly = () => {
    addDomainsMutation.mutate({ domains: [domainInput.trim()], includeSubdomains: true })
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

      {/* Public templates */}
      {!templatesLoading && templates?.length > 0 && (
        <div>
          <h2 className="font-semibold text-gray-900 mb-3">Готовые наборы сайтов</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {templates.map((template) => {
              const applied = isTemplateApplied(template)
              const applying = applyTemplateMutation.isPending && applyTemplateMutation.variables === template.id
              return (
                <div key={template.id} className="card p-4">
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{template.icon || '🌐'}</span>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900">{template.name}</h3>
                      {template.description && (
                        <p className="text-sm text-gray-500 mt-0.5">{template.description}</p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">
                        {template.domains_count} сайтов
                      </p>
                    </div>
                    <div className="flex-shrink-0">
                      {applied ? (
                        <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-green-50 text-green-700 rounded-lg text-sm font-medium">
                          <Check className="w-4 h-4" />
                          Подключён
                        </span>
                      ) : (
                        <button
                          onClick={() => applyTemplateMutation.mutate(template.id)}
                          disabled={applying}
                          className="btn btn-primary btn-sm flex items-center gap-1"
                        >
                          {applying ? (
                            <Loader className="w-4 h-4 animate-spin" />
                          ) : (
                            <Download className="w-4 h-4" />
                          )}
                          Подключить
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Show template domains preview */}
                  <div className="flex flex-wrap gap-1 mt-3">
                    {template.domains.slice(0, 4).map((domain) => (
                      <span
                        key={domain}
                        className={`px-2 py-0.5 rounded text-xs font-mono ${
                          clientDomainsSet.has(domain)
                            ? 'bg-green-50 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {domain}
                      </span>
                    ))}
                    {template.domains.length > 4 && (
                      <span className="px-2 py-0.5 text-xs text-gray-500">
                        +{template.domains.length - 4}
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Add custom domain with analysis */}
      <div className="card p-4 sm:p-6">
        <h2 className="font-semibold text-gray-900 mb-3">Добавить свой сайт</h2>
        <p className="text-sm text-gray-500 mb-4">
          Введите адрес сайта — мы проанализируем его и предложим связанные домены
        </p>

        <div className="flex gap-2">
          <input
            type="text"
            className="input flex-1"
            value={domainInput}
            onChange={(e) => setDomainInput(e.target.value)}
            placeholder="example.com"
            disabled={analyzing || addDomainsMutation.isPending}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleAnalyze()
              }
            }}
          />
          <button
            onClick={handleAnalyze}
            disabled={analyzing || !domainInput.trim() || addDomainsMutation.isPending}
            className="btn btn-primary flex items-center gap-2"
          >
            {analyzing ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Анализировать
          </button>
        </div>

        {/* Analysis suggestions */}
        {suggestions && (
          <div className="mt-4 p-3 border-2 border-blue-200 bg-blue-50/50 rounded-lg">
            <h4 className="font-medium text-gray-900 text-sm mb-2">
              Найдены связанные домены
            </h4>

            {suggestions.redirects?.length > 0 && (
              <div className="mb-2">
                <p className="text-xs text-gray-500 uppercase mb-1">Редиректы</p>
                <div className="flex flex-wrap gap-1">
                  {suggestions.redirects.map(domain => (
                    <button
                      key={domain}
                      type="button"
                      onClick={() => toggleSuggestion(domain)}
                      className={`px-2 py-0.5 rounded text-xs font-mono flex items-center gap-1 transition-colors ${
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

            {suggestions.resources?.length > 0 && (
              <div className="mb-2">
                <p className="text-xs text-gray-500 uppercase mb-1">Ресурсы (CDN, API)</p>
                <div className="flex flex-wrap gap-1">
                  {suggestions.resources.map(domain => (
                    <button
                      key={domain}
                      type="button"
                      onClick={() => toggleSuggestion(domain)}
                      className={`px-2 py-0.5 rounded text-xs font-mono flex items-center gap-1 transition-colors ${
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

            {suggestions.error && (
              <p className="text-xs text-amber-600 mb-2">
                Анализ завершён с предупреждением: {suggestions.error}
              </p>
            )}

            <div className="flex gap-2 mt-3 pt-2 border-t border-blue-200">
              <button
                onClick={handleAddWithSelected}
                disabled={addDomainsMutation.isPending}
                className="btn btn-primary btn-sm flex-1 flex items-center justify-center gap-1"
              >
                {addDomainsMutation.isPending ? (
                  <Loader className="w-3 h-3 animate-spin" />
                ) : (
                  <Plus className="w-3 h-3" />
                )}
                Добавить с выбранными ({1 + selectedSuggestions.size})
              </button>
              <button
                onClick={handleAddOnly}
                disabled={addDomainsMutation.isPending}
                className="btn btn-secondary btn-sm"
              >
                Только основной
              </button>
            </div>
          </div>
        )}

        {addDomainsMutation.isSuccess && !suggestions && (
          <p className="mt-3 text-sm text-green-600">Домен добавлен!</p>
        )}
      </div>

      {/* Current domains list */}
      {domainsLoading ? (
        <div className="text-center py-8">Загрузка...</div>
      ) : (
        <div>
          <h2 className="font-semibold text-gray-900 mb-3">Текущие сайты</h2>
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
        </div>
      )}

      {/* Request domain (legacy form) */}
      <div className="card p-4 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Не нашли нужный сайт?</h2>
          {!showRequestForm && (
            <button
              onClick={() => setShowRequestForm(true)}
              className="btn btn-secondary btn-sm flex items-center gap-1"
            >
              <Send className="w-4 h-4" />
              Запросить
            </button>
          )}
        </div>

        {showRequestForm && (
          <form onSubmit={handleRequestSubmit} className="space-y-4">
            <div>
              <label className="label">{t('portalDomains.domain')}</label>
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
              <label className="label">{t('portalDomains.reasonLabel')}</label>
              <input
                type="text"
                className="input"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t('portalDomains.reasonPlaceholder')}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowRequestForm(false)}
                className="btn btn-secondary flex-1"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                disabled={requestMutation.isPending}
                className="btn btn-primary flex-1 flex items-center justify-center gap-2"
              >
                <Send className="w-4 h-4" />
                {t('portalDomains.submit')}
              </button>
            </div>
          </form>
        )}

        {!showRequestForm && (
          <p className="text-sm text-gray-600">
            Отправьте запрос администратору на добавление нужного сайта
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
