import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Lock, AlertCircle, CheckCircle } from 'lucide-react'
import api from '../../api'

export default function PortalSettings() {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: () => api.changePortalPassword(oldPassword, newPassword),
    onSuccess: () => {
      setSuccess(true)
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => setSuccess(false), 3000)
    },
    onError: (err) => {
      setError(err.message)
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    setError('')

    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают')
      return
    }

    if (newPassword.length < 6) {
      setError('Пароль должен быть не менее 6 символов')
      return
    }

    mutation.mutate()
  }

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Настройки</h1>
        <p className="text-gray-500 mt-1">Управление аккаунтом</p>
      </div>

      {/* Change password */}
      <div className="card p-4 sm:p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-primary-50 rounded-lg">
            <Lock className="w-5 h-5 text-primary-600" />
          </div>
          <h2 className="font-semibold text-gray-900">Сменить пароль</h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg">
              <AlertCircle className="w-5 h-5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg">
              <CheckCircle className="w-5 h-5" />
              <span>Пароль успешно изменён</span>
            </div>
          )}

          <div>
            <label className="label">Текущий пароль</label>
            <input
              type="password"
              className="input"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="label">Новый пароль</label>
            <input
              type="password"
              className="input"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>

          <div>
            <label className="label">Подтвердите новый пароль</label>
            <input
              type="password"
              className="input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            disabled={mutation.isPending}
            className="btn btn-primary w-full"
          >
            {mutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </button>
        </form>

        <p className="text-sm text-gray-500 mt-4">
          Это пароль для входа в личный кабинет. VPN-пароль настраивается администратором.
        </p>
      </div>

      {/* Info */}
      <div className="card p-4 text-sm text-gray-600">
        <h3 className="font-medium text-gray-900 mb-2">Важно</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li>Пароль должен содержать минимум 6 символов</li>
          <li>Используйте надёжный пароль, который вы не используете на других сайтах</li>
          <li>Если забыли пароль — обратитесь к администратору</li>
        </ul>
      </div>
    </div>
  )
}
