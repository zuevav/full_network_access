import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit, Trash2, X, Search, Loader, Check } from 'lucide-react'
import api from '../../api'

function TemplateModal({ isOpen, onClose, template, onSuccess, t }) {
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('')
  const [description, setDescription] = useState('')
  const [domainsText, setDomainsText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Domain analysis state
  const [domainInput, setDomainInput] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [suggestions, setSuggestions] = useState(null)
  const [selectedSuggestions, setSelectedSuggestions] = useState(new Set())

  // Reset form when template changes or modal opens
  useEffect(() => {
    if (isOpen) {
      setName(template?.name || '')
      setIcon(template?.icon || '')
      setDescription(template?.description || '')
      setDomainsText(template?.domains?.join('\n') || '')
      setError('')
      setDomainInput('')
      setSuggestions(null)
      setSelectedSuggestions(new Set())
    }
  }, [template, isOpen])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const domains = domainsText.split('\n').map(d => d.trim()).filter(Boolean)

    try {
      if (template) {
        await api.updateTemplate(template.id, { name, icon, description, domains })
      } else {
        await api.createTemplate({ name, icon, description, domains })
      }
      onSuccess()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAnalyzeDomain = async (e) => {
    e.preventDefault()
    if (!domainInput.trim()) return

    const domain = domainInput.trim()
    setAnalyzing(true)
    setSuggestions(null)

    try {
      const result = await api.analyzeDomain(domain)
      if (result.suggested && result.suggested.length > 0) {
        setSuggestions(result)
        setSelectedSuggestions(new Set(result.suggested))
      } else {
        // No suggestions, just add the domain
        addDomainToList(domain)
        setDomainInput('')
      }
    } catch (err) {
      // On error, just add the domain
      addDomainToList(domain)
      setDomainInput('')
    } finally {
      setAnalyzing(false)
    }
  }

  const addDomainToList = (domain) => {
    const currentDomains = domainsText.split('\n').map(d => d.trim()).filter(Boolean)
    if (!currentDomains.includes(domain)) {
      setDomainsText(prev => prev.trim() ? `${prev.trim()}\n${domain}` : domain)
    }
  }

  const handleAddWithSuggestions = () => {
    const domain = domainInput.trim()
    const domainsToAdd = [domain, ...Array.from(selectedSuggestions)]
    const currentDomains = new Set(domainsText.split('\n').map(d => d.trim()).filter(Boolean))

    domainsToAdd.forEach(d => {
      if (!currentDomains.has(d)) {
        currentDomains.add(d)
      }
    })

    setDomainsText(Array.from(currentDomains).join('\n'))
    setDomainInput('')
    setSuggestions(null)
    setSelectedSuggestions(new Set())
  }

  const handleAddWithoutSuggestions = () => {
    addDomainToList(domainInput.trim())
    setDomainInput('')
    setSuggestions(null)
    setSelectedSuggestions(new Set())
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

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl w-full max-w-lg p-6 m-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {template ? t('templates.editTemplate') : t('templates.newTemplate')}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg">{error}</div>
          )}

          <div className="grid grid-cols-4 gap-4">
            <div>
              <label className="label">{t('templates.icon')}</label>
              <input
                type="text"
                className="input text-center text-2xl"
                value={icon}
                onChange={(e) => setIcon(e.target.value)}
                placeholder="🌐"
                maxLength={2}
              />
            </div>
            <div className="col-span-3">
              <label className="label">{t('templates.templateName')} *</label>
              <input
                type="text"
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          </div>

          <div>
            <label className="label">{t('templates.description')}</label>
            <input
              type="text"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {/* Domain analyzer */}
          <div>
            <label className="label">{t('templates.addDomainWithAnalysis')}</label>
            <div className="flex gap-2">
              <input
                type="text"
                className="input flex-1"
                value={domainInput}
                onChange={(e) => setDomainInput(e.target.value)}
                placeholder="example.com"
                disabled={analyzing}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAnalyzeDomain(e)
                  }
                }}
              />
              <button
                type="button"
                onClick={handleAnalyzeDomain}
                disabled={analyzing || !domainInput.trim()}
                className="btn btn-secondary flex items-center gap-2"
              >
                {analyzing ? (
                  <Loader className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
                {t('templates.analyze')}
              </button>
            </div>
          </div>

          {/* Suggestions */}
          {suggestions && (
            <div className="p-3 border-2 border-blue-200 bg-blue-50/50 rounded-lg">
              <h4 className="font-medium text-gray-900 text-sm mb-2">
                {t('clients.relatedDomainsFound')}
              </h4>

              {/* Redirects */}
              {suggestions.redirects?.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-500 uppercase mb-1">{t('clients.redirectDomains')}</p>
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

              {/* Resources */}
              {suggestions.resources?.length > 0 && (
                <div className="mb-2">
                  <p className="text-xs text-gray-500 uppercase mb-1">{t('clients.resourceDomains')}</p>
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

              {/* Actions */}
              <div className="flex gap-2 mt-3 pt-2 border-t border-blue-200">
                <button
                  type="button"
                  onClick={handleAddWithSuggestions}
                  className="btn btn-primary btn-sm flex-1"
                >
                  <Plus className="w-3 h-3 mr-1" />
                  {t('clients.addWithSelected')} ({1 + selectedSuggestions.size})
                </button>
                <button
                  type="button"
                  onClick={handleAddWithoutSuggestions}
                  className="btn btn-secondary btn-sm"
                >
                  {t('clients.addOnlyOriginal')}
                </button>
              </div>
            </div>
          )}

          <div>
            <label className="label">{t('templates.domainsOnePerLine')} *</label>
            <textarea
              className="input min-h-[200px] font-mono text-sm"
              value={domainsText}
              onChange={(e) => setDomainsText(e.target.value)}
              placeholder="example.com&#10;api.example.com&#10;cdn.example.com"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              {domainsText.split('\n').filter(d => d.trim()).length} {t('clients.domainsCount')}
            </p>
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              {t('common.cancel')}
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">
              {loading ? t('common.saving') : t('common.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Templates() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showModal, setShowModal] = useState(false)
  const [editTemplate, setEditTemplate] = useState(null)

  const { data: templates, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => api.getTemplates(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.deleteTemplate(id),
    onSuccess: () => queryClient.invalidateQueries(['templates']),
  })

  const handleEdit = (template) => {
    setEditTemplate(template)
    setShowModal(true)
  }

  const handleNew = () => {
    setEditTemplate(null)
    setShowModal(true)
  }

  const handleSuccess = () => {
    queryClient.invalidateQueries(['templates'])
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('templates.title')}</h1>
        <button onClick={handleNew} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-5 h-5" />
          {t('templates.newTemplate')}
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">{t('common.loading')}</div>
      ) : templates?.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-gray-500 mb-4">{t('templates.noTemplates')}</p>
          <button onClick={handleNew} className="btn btn-primary">
            {t('templates.createFirst')}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates?.map((template) => (
            <div key={template.id} className="card p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{template.icon}</span>
                  <div>
                    <h3 className="font-semibold text-gray-900">{template.name}</h3>
                    <p className="text-sm text-gray-500">
                      {template.domains.length} {t('clients.domainsCount')}
                    </p>
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => handleEdit(template)}
                    className="p-2 text-gray-400 hover:text-gray-600 rounded"
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(t('templates.deleteConfirm'))) {
                        deleteMutation.mutate(template.id)
                      }
                    }}
                    className="p-2 text-gray-400 hover:text-red-600 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {template.description && (
                <p className="text-sm text-gray-600 mb-3">{template.description}</p>
              )}
              <div className="flex flex-wrap gap-1">
                {template.domains.slice(0, 5).map((domain) => (
                  <span
                    key={domain}
                    className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600"
                  >
                    {domain}
                  </span>
                ))}
                {template.domains.length > 5 && (
                  <span className="px-2 py-1 text-xs text-gray-500">
                    +{template.domains.length - 5} {t('templates.more')}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <TemplateModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        template={editTemplate}
        onSuccess={handleSuccess}
        t={t}
      />
    </div>
  )
}
