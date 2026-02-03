import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Users,
  UserCheck,
  UserX,
  Globe,
  AlertTriangle,
  MessageSquare,
  ChevronRight
} from 'lucide-react'
import api from '../../api'

function StatCard({ icon: Icon, label, value, color = 'primary' }) {
  const colors = {
    primary: 'bg-primary-50 text-primary-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
  }

  return (
    <div className="card p-6">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-lg ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-semibold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  )
}

function ClientList({ title, clients, emptyText }) {
  return (
    <div className="card">
      <div className="p-4 border-b border-gray-100">
        <h3 className="font-semibold text-gray-900">{title}</h3>
      </div>
      {clients.length === 0 ? (
        <p className="p-4 text-gray-500 text-center">{emptyText}</p>
      ) : (
        <ul>
          {clients.map((client, idx) => (
            <li
              key={client.id}
              className={`p-4 flex items-center justify-between ${
                idx !== clients.length - 1 ? 'border-b border-gray-50' : ''
              }`}
            >
              <div>
                <p className="font-medium text-gray-900">{client.name}</p>
                {client.days_left !== undefined && (
                  <p className={`text-sm ${client.days_left < 0 ? 'text-red-500' : 'text-yellow-600'}`}>
                    {client.days_left < 0
                      ? `Expired ${Math.abs(client.days_left)} days ago`
                      : `${client.days_left} days left`
                    }
                  </p>
                )}
                {client.created_at && (
                  <p className="text-sm text-gray-500">{client.created_at}</p>
                )}
              </div>
              <Link
                to={`/admin/clients/${client.id}`}
                className="text-primary-600 hover:text-primary-700"
              >
                <ChevronRight className="w-5 h-5" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboard(),
  })

  if (isLoading) {
    return <div className="text-center py-12">Loading...</div>
  }

  if (error) {
    return <div className="text-center py-12 text-red-600">Error loading dashboard</div>
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          icon={Users}
          label="Total Clients"
          value={data.total_clients}
          color="primary"
        />
        <StatCard
          icon={UserCheck}
          label="Active"
          value={data.active_clients}
          color="green"
        />
        <StatCard
          icon={UserX}
          label="Inactive"
          value={data.inactive_clients}
          color="red"
        />
        <StatCard
          icon={Globe}
          label="Total Domains"
          value={data.total_domains}
          color="primary"
        />
      </div>

      {/* Pending requests alert */}
      {data.pending_domain_requests > 0 && (
        <Link
          to="/admin/domain-requests"
          className="block mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg hover:bg-yellow-100 transition-colors"
        >
          <div className="flex items-center gap-3">
            <MessageSquare className="w-5 h-5 text-yellow-600" />
            <span className="font-medium text-yellow-800">
              {data.pending_domain_requests} pending domain request(s)
            </span>
            <ChevronRight className="w-5 h-5 text-yellow-600 ml-auto" />
          </div>
        </Link>
      )}

      {/* Client lists */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <ClientList
          title="Expiring Soon"
          clients={data.expiring_soon}
          emptyText="No clients expiring soon"
        />
        <ClientList
          title="Expired"
          clients={data.expired}
          emptyText="No expired clients"
        />
        <ClientList
          title="Recent Clients"
          clients={data.recent_clients}
          emptyText="No clients yet"
        />
      </div>
    </div>
  )
}
