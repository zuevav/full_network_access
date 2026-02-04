import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, XCircle, Clock, X } from 'lucide-react'
import api from '../../api'

function ActionModal({ isOpen, onClose, request, action, onSuccess, t }) {
  const [comment, setComment] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      if (action === 'approve') {
        await api.approveDomainRequest(request.id, comment)
      } else {
        await api.rejectDomainRequest(request.id, comment)
      }
      onSuccess()
      onClose()
    } catch (err) {
      alert(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl w-full max-w-md p-6 m-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">
            {action === 'approve' ? t('domainRequests.approveRequest') : t('domainRequests.rejectRequest')}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-4 p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-500">{t('domainRequests.domain')}</p>
          <p className="font-medium">{request?.domain}</p>
          {request?.reason && (
            <>
              <p className="text-sm text-gray-500 mt-2">{t('domainRequests.reason')}</p>
              <p className="text-gray-700">{request.reason}</p>
            </>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">
              {t('domainRequests.comment')} {action === 'reject' && '*'}
            </label>
            <textarea
              className="input min-h-[100px]"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={action === 'approve' ? t('domainRequests.optionalComment') : t('domainRequests.rejectReason')}
              required={action === 'reject'}
            />
          </div>

          <div className="flex gap-3">
            <button type="button" onClick={onClose} className="btn btn-secondary flex-1">
              {t('common.cancel')}
            </button>
            <button
              type="submit"
              disabled={loading}
              className={`btn flex-1 ${action === 'approve' ? 'btn-primary' : 'btn-danger'}`}
            >
              {loading ? t('domainRequests.processing') : action === 'approve' ? t('domainRequests.approve') : t('domainRequests.reject')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function DomainRequests() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('pending')
  const [showModal, setShowModal] = useState(false)
  const [selectedRequest, setSelectedRequest] = useState(null)
  const [action, setAction] = useState('')

  const { data: requests, isLoading } = useQuery({
    queryKey: ['domain-requests', filter],
    queryFn: () => api.getDomainRequests(filter || undefined),
  })

  const handleAction = (request, actionType) => {
    setSelectedRequest(request)
    setAction(actionType)
    setShowModal(true)
  }

  const handleSuccess = () => {
    queryClient.invalidateQueries(['domain-requests'])
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-4 h-4 text-yellow-500" />
      case 'approved':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'rejected':
        return <XCircle className="w-4 h-4 text-red-500" />
      default:
        return null
    }
  }

  const getStatusLabel = (status) => {
    switch (status) {
      case 'pending':
        return t('domainRequests.pending')
      case 'approved':
        return t('domainRequests.approved')
      case 'rejected':
        return t('domainRequests.rejected')
      default:
        return status
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t('domainRequests.title')}</h1>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {['pending', 'approved', 'rejected', ''].map((status) => (
          <button
            key={status || 'all'}
            onClick={() => setFilter(status)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === status
                ? 'bg-primary-100 text-primary-700'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {status === '' ? t('common.all') : getStatusLabel(status)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-100">
            <tr>
              <th className="text-left p-4 font-medium text-gray-600">{t('domainRequests.clientName')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('domainRequests.domain')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('domainRequests.reason')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('domainRequests.status')}</th>
              <th className="text-left p-4 font-medium text-gray-600">{t('common.date')}</th>
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
            ) : requests?.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-500">
                  {t('domainRequests.noRequests')}
                </td>
              </tr>
            ) : (
              requests?.map((request) => (
                <tr key={request.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="p-4 font-medium">{request.client_name}</td>
                  <td className="p-4">{request.domain}</td>
                  <td className="p-4 text-gray-600 max-w-xs truncate">
                    {request.reason || '-'}
                  </td>
                  <td className="p-4">
                    <span className="inline-flex items-center gap-1">
                      {getStatusIcon(request.status)}
                      {getStatusLabel(request.status)}
                    </span>
                  </td>
                  <td className="p-4 text-gray-500">
                    {new Date(request.created_at).toLocaleDateString()}
                  </td>
                  <td className="p-4">
                    {request.status === 'pending' && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleAction(request, 'approve')}
                          className="p-2 text-green-600 hover:bg-green-50 rounded"
                          title={t('domainRequests.approve')}
                        >
                          <CheckCircle className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleAction(request, 'reject')}
                          className="p-2 text-red-600 hover:bg-red-50 rounded"
                          title={t('domainRequests.reject')}
                        >
                          <XCircle className="w-5 h-5" />
                        </button>
                      </div>
                    )}
                    {request.admin_comment && (
                      <span className="text-sm text-gray-500" title={request.admin_comment}>
                        ...
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <ActionModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        request={selectedRequest}
        action={action}
        onSuccess={handleSuccess}
        t={t}
      />
    </div>
  )
}
