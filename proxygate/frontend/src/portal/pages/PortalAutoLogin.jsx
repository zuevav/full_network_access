import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Globe, AlertCircle, Loader2 } from 'lucide-react'
import api from '../../api'

export default function PortalAutoLogin() {
  const { token } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [error, setError] = useState('')

  useEffect(() => {
    const login = async () => {
      try {
        await api.clientLoginByLink(token)
        navigate('/my', { replace: true })
      } catch (err) {
        setError(err.message || t('auth.loginFailed'))
      }
    }

    if (token) {
      login()
    }
  }, [token, navigate, t])

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-primary-600 to-purple-700 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
              <AlertCircle className="w-8 h-8 text-red-600" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">{t('auth.error')}</h1>
          </div>
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-center mb-4">
            {error}
          </div>
          <a href="/my/login" className="btn btn-primary w-full block text-center">
            {t('auth.goToLogin')}
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-600 to-purple-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-100 rounded-full mb-4">
            <Globe className="w-8 h-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">ZETIT FNA</h1>
          <p className="text-xs text-gray-400 mb-4">Full Network Access</p>
          <div className="flex items-center justify-center gap-2 text-gray-500">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>{t('auth.signingIn')}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
