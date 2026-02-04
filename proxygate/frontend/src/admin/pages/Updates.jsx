import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Download,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  GitBranch,
  Settings,
  Eye,
  EyeOff,
  Loader2,
  Github,
  Clock,
  User
} from 'lucide-react'
import api from '../../api'

function SettingsCard({ onSettingsSaved }) {
  const { t } = useTranslation()
  const [token, setToken] = useState('')
  const [repo, setRepo] = useState('zuevav/full_network_access')
  const [branch, setBranch] = useState('main')
  const [showToken, setShowToken] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  const { data: settings, refetch } = useQuery({
    queryKey: ['updateSettings'],
    queryFn: () => api.getUpdateSettings(),
  })

  useEffect(() => {
    if (settings) {
      setRepo(settings.repo || 'zuevav/full_network_access')
      setBranch(settings.branch || 'main')
    }
  }, [settings])

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)

    try {
      await api.saveUpdateSettings({ token, repo, branch })
      setMessage({ type: 'success', text: t('settings.settingsSaved') })
      setToken('')
      refetch()
      onSettingsSaved?.()
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card p-6">
      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <Github className="w-5 h-5" />
        GitHub {t('settings.title')}
      </h3>

      {settings?.configured && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg flex items-center gap-2">
          <CheckCircle className="w-4 h-4" />
          <span>GitHub API {t('common.active')}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-4">
        {message && (
          <div className={`p-3 rounded-lg flex items-center gap-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>
            {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
            <span>{message.text}</span>
          </div>
        )}

        <div>
          <label className="label">GitHub Personal Access Token</label>
          <div className="relative">
            <input
              type={showToken ? 'text' : 'password'}
              className="input pr-10"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder={settings?.token_set ? '••••••••••••' : 'ghp_xxxxxxxxxxxx'}
            />
            <button
              type="button"
              onClick={() => setShowToken(!showToken)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Token needs 'repo' scope. <a href="https://github.com/settings/tokens" target="_blank" rel="noopener" className="text-primary-600 hover:underline">Create token</a>
          </p>
        </div>

        <div>
          <label className="label">Repository</label>
          <input
            type="text"
            className="input"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/repo"
          />
        </div>

        <div>
          <label className="label">Branch</label>
          <input
            type="text"
            className="input"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder="main"
          />
        </div>

        <button
          type="submit"
          disabled={saving || !token}
          className="btn btn-primary w-full"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
          {t('common.save')}
        </button>
      </form>
    </div>
  )
}

function UpdateStatusCard({ onCheckUpdates }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [updateStarted, setUpdateStarted] = useState(false)

  const { data: status, refetch: refetchStatus, isError: statusError } = useQuery({
    queryKey: ['updateStatus'],
    queryFn: () => api.getUpdateStatus(),
    refetchInterval: (query) => {
      // Poll every 2s when updating or update was just started
      const data = query.state.data
      if (data?.is_updating || updateStarted) return 2000
      return false
    },
    retry: 3,
    retryDelay: 1000,
  })

  // Reset updateStarted when update completes or on error
  useEffect(() => {
    if (status && !status.is_updating && updateStarted && status.update_log?.length > 0) {
      // Update finished
      setUpdateStarted(false)
    }
  }, [status, updateStarted])

  const checkMutation = useMutation({
    mutationFn: () => api.checkForUpdates(),
    onSuccess: (data) => {
      queryClient.setQueryData(['updateCheck'], data)
      refetchStatus()
    }
  })

  const applyMutation = useMutation({
    mutationFn: () => api.applyUpdates(),
    onSuccess: () => {
      // Mark update as started to enable polling
      setUpdateStarted(true)
      // Clear the update check to hide "Updates Available" section
      queryClient.setQueryData(['updateCheck'], null)
      // Refetch status to show the update log
      refetchStatus()
    }
  })

  const { data: updateCheck } = useQuery({
    queryKey: ['updateCheck'],
    enabled: false,
  })

  const handleCheckUpdates = () => {
    checkMutation.mutate()
  }

  const handleApplyUpdates = () => {
    if (confirm('Are you sure you want to update? The system will restart.')) {
      applyMutation.mutate()
    }
  }

  return (
    <div className="space-y-6">
      {/* Current Status */}
      <div className="card p-6">
        <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <GitBranch className="w-5 h-5" />
          System Status
        </h3>

        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-500">Current Version</span>
            <code className="px-2 py-1 bg-gray-100 rounded text-sm">
              {status?.current_commit || 'Unknown'}
            </code>
          </div>

          {status?.last_check && (
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Last Check</span>
              <span className="text-sm text-gray-700">
                {new Date(status.last_check).toLocaleString()}
              </span>
            </div>
          )}

          {status?.last_update && (
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Last Update</span>
              <span className="text-sm text-gray-700">
                {new Date(status.last_update).toLocaleString()}
              </span>
            </div>
          )}
        </div>

        <div className="mt-4 flex gap-2">
          <button
            onClick={handleCheckUpdates}
            disabled={checkMutation.isPending || status?.is_updating}
            className="btn btn-secondary flex-1"
          >
            {checkMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Check for Updates
          </button>
        </div>

        {checkMutation.error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{checkMutation.error.message}</span>
          </div>
        )}
      </div>

      {/* Update Available */}
      {updateCheck && (
        <div className={`card p-6 ${updateCheck.has_updates ? 'border-2 border-primary-500' : ''}`}>
          <h3 className="font-semibold text-gray-900 mb-4">
            {updateCheck.has_updates ? (
              <span className="flex items-center gap-2 text-primary-600">
                <Download className="w-5 h-5" />
                Updates Available
              </span>
            ) : (
              <span className="flex items-center gap-2 text-green-600">
                <CheckCircle className="w-5 h-5" />
                System Up to Date
              </span>
            )}
          </h3>

          {updateCheck.has_updates && (
            <>
              <p className="text-gray-600 mb-4">
                You are <strong>{updateCheck.commits_behind}</strong> commit(s) behind.
              </p>

              {updateCheck.recent_commits?.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Changes:</h4>
                  <ul className="space-y-2">
                    {updateCheck.recent_commits.map((commit) => (
                      <li key={commit.sha} className="text-sm border-l-2 border-gray-200 pl-3">
                        <div className="flex items-center gap-2 text-gray-500">
                          <code className="text-xs bg-gray-100 px-1 rounded">{commit.sha}</code>
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {commit.author}
                          </span>
                        </div>
                        <p className="text-gray-700">{commit.message}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                onClick={handleApplyUpdates}
                disabled={applyMutation.isPending || status?.is_updating}
                className="btn btn-primary w-full"
              >
                {applyMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Download className="w-4 h-4 mr-2" />
                )}
                Apply Updates
              </button>
            </>
          )}
        </div>
      )}

      {/* Update Progress / Log */}
      {(status?.is_updating || status?.update_log?.length > 0 || updateStarted) && (
        <div className={`card p-6 border-2 ${
          status?.is_updating || (statusError && updateStarted)
            ? 'border-yellow-500'
            : status?.update_log?.some(l => l.includes('ERROR'))
              ? 'border-red-500'
              : status?.update_log?.some(l => l.includes('COMPLETE'))
                ? 'border-green-500'
                : 'border-gray-300'
        }`}>
          <h3 className={`font-semibold mb-4 flex items-center gap-2 ${
            status?.is_updating || (statusError && updateStarted)
              ? 'text-yellow-700'
              : status?.update_log?.some(l => l.includes('ERROR'))
                ? 'text-red-700'
                : status?.update_log?.some(l => l.includes('COMPLETE'))
                  ? 'text-green-700'
                  : 'text-gray-700'
          }`}>
            {status?.is_updating ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Update In Progress
              </>
            ) : statusError && updateStarted ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Service Restarting...
              </>
            ) : status?.update_log?.some(l => l.includes('ERROR')) ? (
              <>
                <AlertCircle className="w-5 h-5" />
                Update Failed
              </>
            ) : status?.update_log?.some(l => l.includes('COMPLETE')) ? (
              <>
                <CheckCircle className="w-5 h-5" />
                Update Complete
              </>
            ) : (
              <>
                <Clock className="w-5 h-5" />
                Update Log
              </>
            )}
          </h3>

          <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm text-green-400 max-h-64 overflow-y-auto" ref={(el) => {
            if (el && (status?.is_updating || updateStarted)) el.scrollTop = el.scrollHeight
          }}>
            {status?.update_log?.length > 0 ? (
              status.update_log.map((line, idx) => (
                <div key={idx} className={
                  line.includes('ERROR') ? 'text-red-400' :
                  line.includes('WARNING') ? 'text-yellow-400' :
                  line.includes('COMPLETE') ? 'text-green-300 font-bold' : ''
                }>
                  {line}
                </div>
              ))
            ) : statusError && updateStarted ? (
              <div className="text-yellow-400">Reconnecting to server...</div>
            ) : (
              <div>Starting update...</div>
            )}
          </div>

          {status?.is_updating ? (
            <p className="text-sm text-gray-500 mt-4">
              Please wait. Do not close this page.
            </p>
          ) : statusError && updateStarted ? (
            <p className="text-sm text-yellow-600 mt-4">
              Service is restarting... Please wait.
            </p>
          ) : status?.update_log?.some(l => l.includes('COMPLETE')) ? (
            <p className="text-sm text-green-600 mt-4">
              Update completed successfully. Refresh the page to see the new version.
            </p>
          ) : null}
        </div>
      )}
    </div>
  )
}

export default function Updates() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()

  const handleSettingsSaved = () => {
    queryClient.invalidateQueries(['updateStatus'])
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">System Updates</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <UpdateStatusCard />
        </div>

        <div>
          <SettingsCard onSettingsSaved={handleSettingsSaved} />
        </div>
      </div>
    </div>
  )
}
