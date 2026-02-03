import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Smartphone,
  Globe,
  CreditCard,
  Settings,
  ChevronRight,
  MessageSquare
} from 'lucide-react'
import api from '../../api'

function StatusCard({ subscription }) {
  const getStatusConfig = () => {
    switch (subscription.status) {
      case 'active':
        return {
          icon: CheckCircle,
          color: 'bg-green-50 border-green-200',
          iconColor: 'text-green-500',
          title: 'Подписка активна',
        }
      case 'expiring':
        return {
          icon: AlertTriangle,
          color: 'bg-yellow-50 border-yellow-200',
          iconColor: 'text-yellow-500',
          title: 'Подписка скоро истекает',
        }
      case 'expired':
        return {
          icon: XCircle,
          color: 'bg-red-50 border-red-200',
          iconColor: 'text-red-500',
          title: 'Подписка истекла',
        }
      default:
        return {
          icon: XCircle,
          color: 'bg-gray-50 border-gray-200',
          iconColor: 'text-gray-500',
          title: 'Нет активной подписки',
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  return (
    <div className={`rounded-xl border-2 p-6 ${config.color}`}>
      <div className="flex items-center gap-4">
        <Icon className={`w-10 h-10 ${config.iconColor}`} />
        <div>
          <h2 className="font-semibold text-gray-900">{config.title}</h2>
          {subscription.valid_until && (
            <p className="text-gray-600">
              Действует до: {new Date(subscription.valid_until).toLocaleDateString('ru', {
                day: 'numeric',
                month: 'long',
                year: 'numeric'
              })}
            </p>
          )}
          {subscription.days_left !== null && subscription.days_left >= 0 && (
            <p className="text-sm text-gray-500">
              Осталось: {subscription.days_left} дней
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

const quickActions = [
  {
    path: '/my/devices',
    icon: Smartphone,
    label: 'Настроить устройство',
    description: 'Скачайте профиль для VPN',
  },
  {
    path: '/my/domains',
    icon: Globe,
    label: 'Мои сайты',
    description: 'Доступные домены',
  },
  {
    path: '/my/payments',
    icon: CreditCard,
    label: 'История платежей',
    description: 'Ваши оплаты',
  },
  {
    path: '/my/settings',
    icon: Settings,
    label: 'Сменить пароль',
    description: 'Настройки аккаунта',
  },
]

export default function PortalHome() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['portal-me'],
    queryFn: () => api.getPortalMe(),
  })

  if (isLoading) {
    return <div className="text-center py-12">Загрузка...</div>
  }

  if (error) {
    return <div className="text-center py-12 text-red-600">Ошибка загрузки данных</div>
  }

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Привет, {data.name}!
        </h1>
        <p className="text-gray-500">Добро пожаловать в личный кабинет</p>
      </div>

      {/* Status card */}
      <StatusCard subscription={data.subscription} />

      {/* Quick actions */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Быстрые действия
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {quickActions.map((action) => (
            <Link
              key={action.path}
              to={action.path}
              className="card p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors"
            >
              <div className="p-3 bg-primary-50 rounded-lg">
                <action.icon className="w-5 h-5 text-primary-600" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-gray-900">{action.label}</p>
                <p className="text-sm text-gray-500">{action.description}</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-400" />
            </Link>
          ))}
        </div>
      </div>

      {/* Pending requests */}
      {data.pending_requests > 0 && (
        <Link
          to="/my/domains"
          className="block p-4 bg-yellow-50 border border-yellow-200 rounded-xl"
        >
          <div className="flex items-center gap-3">
            <MessageSquare className="w-5 h-5 text-yellow-600" />
            <span className="text-yellow-800">
              {data.pending_requests} запрос(ов) на рассмотрении
            </span>
            <ChevronRight className="w-5 h-5 text-yellow-600 ml-auto" />
          </div>
        </Link>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="card p-4 text-center">
          <p className="text-3xl font-bold text-primary-600">{data.domains_count}</p>
          <p className="text-sm text-gray-500">Доступных сайтов</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-3xl font-bold text-primary-600">
            {data.service_type === 'both' ? 'VPN + Proxy' : data.service_type.toUpperCase()}
          </p>
          <p className="text-sm text-gray-500">Тип подключения</p>
        </div>
      </div>

      {/* Help */}
      <div className="card p-4">
        <h3 className="font-medium text-gray-900 mb-2">Нужна помощь?</h3>
        <p className="text-sm text-gray-600">
          Обратитесь к администратору для получения помощи с настройкой или продлением подписки.
        </p>
      </div>
    </div>
  )
}
