import { useQuery } from '@tanstack/react-query'
import { CheckCircle, AlertTriangle, XCircle, CreditCard } from 'lucide-react'
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
              до {new Date(subscription.valid_until).toLocaleDateString('ru', {
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

export default function PortalPayments() {
  const { data, isLoading } = useQuery({
    queryKey: ['portal-payments'],
    queryFn: () => api.getPortalPayments(),
  })

  if (isLoading) {
    return <div className="text-center py-12">Загрузка...</div>
  }

  return (
    <div className="space-y-6 pb-20 md:pb-0">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Мои платежи</h1>
        <p className="text-gray-500 mt-1">История оплат и статус подписки</p>
      </div>

      {/* Status card */}
      <StatusCard subscription={data.current_subscription} />

      {/* History */}
      <div>
        <h2 className="font-semibold text-gray-900 mb-3">История</h2>
        {data.history.length === 0 ? (
          <div className="card p-8 text-center text-gray-500">
            Нет истории платежей
          </div>
        ) : (
          <div className="card divide-y divide-gray-100">
            {data.history.map((payment, idx) => (
              <div key={idx} className="p-4 flex items-center gap-4">
                <div className="p-2 bg-green-50 rounded-lg">
                  <CreditCard className="w-5 h-5 text-green-600" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">
                    {payment.amount} {payment.currency}
                  </p>
                  <p className="text-sm text-gray-500">{payment.period}</p>
                </div>
                <p className="text-sm text-gray-500">
                  {new Date(payment.paid_at).toLocaleDateString('ru')}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Contact */}
      <div className="card p-4 text-center text-sm text-gray-600">
        По вопросам оплаты обратитесь к администратору
      </div>
    </div>
  )
}
