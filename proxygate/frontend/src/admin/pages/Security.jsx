import { useState, useEffect } from 'react';
import api from '../../api';

export default function Security() {
  const [stats, setStats] = useState(null);
  const [blockedIPs, setBlockedIPs] = useState([]);
  const [failedAttempts, setFailedAttempts] = useState([]);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [activeTab, setActiveTab] = useState('blocked');
  const [loading, setLoading] = useState(true);
  const [showBlockModal, setShowBlockModal] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [blockForm, setBlockForm] = useState({
    ip_address: '',
    reason: '',
    is_permanent: true,
    duration_minutes: 30
  });

  useEffect(() => {
    loadData();
  }, [showHistory]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsRes, blockedRes, attemptsRes, eventsRes] = await Promise.all([
        api.get('/admin/security/stats'),
        api.get(`/admin/security/blocked?active_only=${!showHistory}`),
        api.get('/admin/security/failed-attempts?limit=50'),
        api.get('/admin/security/events?limit=50')
      ]);
      setStats(statsRes.data);
      setBlockedIPs(blockedRes.data.items);
      setFailedAttempts(attemptsRes.data);
      setSecurityEvents(eventsRes.data);
    } catch (err) {
      console.error('Failed to load security data:', err);
    }
    setLoading(false);
  };

  const handleUnblock = async (ip) => {
    if (!confirm(`Разблокировать IP ${ip}?`)) return;
    try {
      await api.post(`/admin/security/blocked/${encodeURIComponent(ip)}/unblock`, {
        notes: 'Разблокирован администратором'
      });
      loadData();
    } catch (err) {
      alert('Ошибка разблокировки: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleBlockIP = async (e) => {
    e.preventDefault();
    try {
      await api.post('/admin/security/blocked', blockForm);
      setShowBlockModal(false);
      setBlockForm({ ip_address: '', reason: '', is_permanent: true, duration_minutes: 30 });
      loadData();
    } catch (err) {
      alert('Ошибка блокировки: ' + (err.response?.data?.detail || err.message));
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ru-RU');
  };

  const getEventTypeBadge = (type) => {
    const badges = {
      'login_failed': 'bg-yellow-100 text-yellow-800',
      'login_success': 'bg-green-100 text-green-800',
      'ip_blocked': 'bg-red-100 text-red-800',
      'ip_unblocked': 'bg-blue-100 text-blue-800',
      'ip_blocked_manual': 'bg-red-100 text-red-800',
      'ip_block_extended': 'bg-orange-100 text-orange-800'
    };
    return badges[type] || 'bg-gray-100 text-gray-800';
  };

  if (loading && !stats) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Безопасность</h1>
        <button
          onClick={() => setShowBlockModal(true)}
          className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
        >
          Заблокировать IP
        </button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-red-50 p-4 rounded-lg border border-red-200">
            <div className="text-3xl font-bold text-red-600">{stats.active_blocks}</div>
            <div className="text-sm text-red-700">Активных блокировок</div>
          </div>
          <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
            <div className="text-3xl font-bold text-orange-600">{stats.failed_attempts_24h}</div>
            <div className="text-sm text-orange-700">Неудачных попыток (24ч)</div>
          </div>
          <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
            <div className="text-3xl font-bold text-yellow-600">{stats.blocked_today}</div>
            <div className="text-sm text-yellow-700">Заблокировано сегодня</div>
          </div>
          <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <div className="text-3xl font-bold text-blue-600">{stats.events_today}</div>
            <div className="text-sm text-blue-700">Событий сегодня</div>
          </div>
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <div className="text-3xl font-bold text-gray-600">{stats.total_blocks}</div>
            <div className="text-sm text-gray-700">Всего блокировок</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'blocked', label: 'Заблокированные IP' },
            { id: 'attempts', label: 'Неудачные попытки' },
            { id: 'events', label: 'Журнал событий' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Blocked IPs Tab */}
      {activeTab === 'blocked' && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b flex justify-between items-center">
            <h2 className="text-lg font-semibold">Заблокированные IP-адреса</h2>
            <label className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={showHistory}
                onChange={(e) => setShowHistory(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm text-gray-600">Показать историю</span>
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Причина</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Попыток</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Заблокирован</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">До</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Статус</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Действия</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {blockedIPs.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-6 py-8 text-center text-gray-500">
                      Нет заблокированных IP-адресов
                    </td>
                  </tr>
                ) : (
                  blockedIPs.map(block => (
                    <tr key={block.id} className={!block.is_active ? 'bg-gray-50' : ''}>
                      <td className="px-6 py-4 whitespace-nowrap font-mono text-sm">{block.ip_address}</td>
                      <td className="px-6 py-4 text-sm">{block.reason}</td>
                      <td className="px-6 py-4 text-sm">{block.failed_attempts}</td>
                      <td className="px-6 py-4 text-sm">{formatDate(block.blocked_at)}</td>
                      <td className="px-6 py-4 text-sm">
                        {block.is_permanent ? (
                          <span className="text-red-600 font-medium">Навсегда</span>
                        ) : (
                          formatDate(block.blocked_until)
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {block.is_active ? (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">
                            Активна
                          </span>
                        ) : (
                          <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-800">
                            Снята
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        {block.is_active && (
                          <button
                            onClick={() => handleUnblock(block.ip_address)}
                            className="text-blue-600 hover:text-blue-800 text-sm"
                          >
                            Разблокировать
                          </button>
                        )}
                        {block.unblocked_by && (
                          <span className="text-xs text-gray-500 block mt-1">
                            Снял: {block.unblocked_by}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Failed Attempts Tab */}
      {activeTab === 'attempts' && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Последние неудачные попытки входа</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Время</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Логин</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Endpoint</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User Agent</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {failedAttempts.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-gray-500">
                      Нет неудачных попыток входа
                    </td>
                  </tr>
                ) : (
                  failedAttempts.map(attempt => (
                    <tr key={attempt.id}>
                      <td className="px-6 py-4 text-sm">{formatDate(attempt.attempt_time)}</td>
                      <td className="px-6 py-4 font-mono text-sm">{attempt.ip_address}</td>
                      <td className="px-6 py-4 text-sm">{attempt.username || '-'}</td>
                      <td className="px-6 py-4 text-sm font-mono">{attempt.endpoint}</td>
                      <td className="px-6 py-4 text-sm truncate max-w-xs" title={attempt.user_agent}>
                        {attempt.user_agent || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Security Events Tab */}
      {activeTab === 'events' && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Журнал событий безопасности</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Время</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">IP</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Пользователь</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Детали</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {securityEvents.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-6 py-8 text-center text-gray-500">
                      Нет событий безопасности
                    </td>
                  </tr>
                ) : (
                  securityEvents.map(event => (
                    <tr key={event.id}>
                      <td className="px-6 py-4 text-sm">{formatDate(event.created_at)}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getEventTypeBadge(event.event_type)}`}>
                          {event.event_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">{event.ip_address || '-'}</td>
                      <td className="px-6 py-4 text-sm">{event.username || '-'}</td>
                      <td className="px-6 py-4 text-sm">{event.details || '-'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Block IP Modal */}
      {showBlockModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Заблокировать IP-адрес</h3>
            <form onSubmit={handleBlockIP} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">IP-адрес</label>
                <input
                  type="text"
                  value={blockForm.ip_address}
                  onChange={(e) => setBlockForm({ ...blockForm, ip_address: e.target.value })}
                  placeholder="192.168.1.1"
                  className="mt-1 block w-full border rounded-md px-3 py-2"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Причина</label>
                <input
                  type="text"
                  value={blockForm.reason}
                  onChange={(e) => setBlockForm({ ...blockForm, reason: e.target.value })}
                  placeholder="Причина блокировки"
                  className="mt-1 block w-full border rounded-md px-3 py-2"
                  required
                />
              </div>
              <div>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={blockForm.is_permanent}
                    onChange={(e) => setBlockForm({ ...blockForm, is_permanent: e.target.checked })}
                    className="rounded"
                  />
                  <span className="text-sm text-gray-700">Постоянная блокировка</span>
                </label>
              </div>
              {!blockForm.is_permanent && (
                <div>
                  <label className="block text-sm font-medium text-gray-700">Длительность (минут)</label>
                  <input
                    type="number"
                    value={blockForm.duration_minutes}
                    onChange={(e) => setBlockForm({ ...blockForm, duration_minutes: parseInt(e.target.value) })}
                    min="1"
                    className="mt-1 block w-full border rounded-md px-3 py-2"
                  />
                </div>
              )}
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowBlockModal(false)}
                  className="px-4 py-2 border rounded hover:bg-gray-50"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                >
                  Заблокировать
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
