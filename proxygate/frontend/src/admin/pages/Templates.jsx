import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Edit, Trash2, X } from 'lucide-react'
import api from '../../api'

function TemplateModal({ isOpen, onClose, template, onSuccess }) {
  const [name, setName] = useState(template?.name || '')
  const [icon, setIcon] = useState(template?.icon || '')
  const [description, setDescription] = useState(template?.description || '')
  const [domainsText, setDomainsText] = useState(template?.domains?.join('\n') || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl w-full max-w-lg p-6 m-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {template ? 'Edit Template' : 'New Template'}
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
              <label className="label">Icon</label>
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
              <label className="label">Name *</label>
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
            <label className="label">Description</label>
            <input
              type="text"
              className="input"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <label className="label">Domains (one per line) *</label>
            <textarea
              className="input min-h-[200px] font-mono text-sm"
              value={domainsText}
              onChange={(e) => setDomainsText(e.target.value)}
              placeholder="example.com&#10;api.example.com&#10;cdn.example.com"
              required
            />
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary flex-1">
              {loading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Templates() {
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
        <h1 className="text-2xl font-bold text-gray-900">Domain Templates</h1>
        <button onClick={handleNew} className="btn btn-primary flex items-center gap-2">
          <Plus className="w-5 h-5" />
          New Template
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12">Loading...</div>
      ) : templates?.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-gray-500 mb-4">No templates yet</p>
          <button onClick={handleNew} className="btn btn-primary">
            Create First Template
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
                      {template.domains.length} domains
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
                      if (confirm('Delete this template?')) {
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
                    +{template.domains.length - 5} more
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
      />
    </div>
  )
}
