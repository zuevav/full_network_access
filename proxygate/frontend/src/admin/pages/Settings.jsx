import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Globe,
  Server,
  Shield,
  Lock,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  User,
  Mail,
  Key,
  Save,
  Eye,
  EyeOff,
  ExternalLink,
  Wifi
} from 'lucide-react'
import api from '../../api'

export default function Settings() {
  const { t } = useTranslation()

  // System settings state
  const [systemSettings, setSystemSettings] = useState({
    domain: '',
    server_ip: '',
    vpn_subnet: '10.10.10.0/24',
    dns_servers: '8.8.8.8,8.8.4.4',
    http_proxy_port: 3128,
    socks_proxy_port: 1080
  })
  const [systemLoading, setSystemLoading] = useState(true)
  const [systemSaving, setSystemSaving] = useState(false)

  // Service status state
  const [serviceStatus, setServiceStatus] = useState(null)
  const [statusLoading, setStatusLoading] = useState(true)

  // SSL settings state
  const [sslSettings, setSslSettings] = useState({
    domain: '',
    email: '',
    configured: false,
    certificate_exists: false,
    certificate_expiry: null,
    is_processing: false
  })
  const [sslLoading, setSslLoading] = useState(true)
  const [sslSaving, setSslSaving] = useState(false)
  const [sslLog, setSslLog] = useState([])

  // Admin profile state
  const [adminProfile, setAdminProfile] = useState({
    username: '',
    email: ''
  })
  const [passwords, setPasswords] = useState({
    current: '',
    new: '',
    confirm: ''
  })
  const [showPasswords, setShowPasswords] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)
  const [profileSaving, setProfileSaving] = useState(false)
  const [passwordSaving, setPasswordSaving] = useState(false)

  // Messages
  const [message, setMessage] = useState(null)

  // VPN sync state
  const [vpnSyncing, setVpnSyncing] = useState(false)
  const [vpnSyncResult, setVpnSyncResult] = useState(null)

  // XRay state
  const [xrayStatus, setXrayStatus] = useState(null)
  const [xrayLoading, setXrayLoading] = useState(true)
  const [xraySaving, setXraySaving] = useState(false)
  const [xraySettings, setXraySettings] = useState({
    port: 443,
    dest_server: 'www.microsoft.com',
    dest_port: 443,
    server_name: 'www.microsoft.com'
  })

  // WireGuard state
  const [wgStatus, setWgStatus] = useState(null)
  const [wgLoading, setWgLoading] = useState(true)
  const [wgSaving, setWgSaving] = useState(false)
  const [wgSettings, setWgSettings] = useState({
    listen_port: 51820,
    server_ip: '10.10.0.1',
    subnet: '10.10.0.0/24',
    dns: '1.1.1.1,8.8.8.8',
    mtu: 1420
  })

  // App version
  const [appVersion, setAppVersion] = useState('...')

  // Load all data
  useEffect(() => {
    loadSystemSettings()
    loadServiceStatus()
    loadSSLSettings()
    loadAdminProfile()
    loadVersion()
    loadXrayStatus()
    loadWireguardStatus()
  }, [])

  const loadVersion = async () => {
    try {
      const data = await api.getVersion()
      setAppVersion(data.version || 'unknown')
    } catch (error) {
      console.error('Error loading version:', error)
      setAppVersion('unknown')
    }
  }

  // Poll SSL log when processing
  useEffect(() => {
    let interval
    if (sslSettings.is_processing) {
      interval = setInterval(loadSSLLog, 2000)
    }
    return () => clearInterval(interval)
  }, [sslSettings.is_processing])

  const loadSystemSettings = async () => {
    try {
      const data = await api.getSystemSettings()
      setSystemSettings(data)
    } catch (error) {
      console.error('Error loading system settings:', error)
    } finally {
      setSystemLoading(false)
    }
  }

  const loadServiceStatus = async () => {
    try {
      const data = await api.getServiceStatus()
      setServiceStatus(data)
    } catch (error) {
      console.error('Error loading service status:', error)
    } finally {
      setStatusLoading(false)
    }
  }

  const loadSSLSettings = async () => {
    try {
      const data = await api.getSSLSettings()
      setSslSettings(data)
    } catch (error) {
      console.error('Error loading SSL settings:', error)
    } finally {
      setSslLoading(false)
    }
  }

  const loadSSLLog = async () => {
    try {
      const data = await api.getSSLLog()
      setSslLog(data.log || [])
      if (!data.is_processing) {
        setSslSettings(prev => ({ ...prev, is_processing: false }))
        loadSSLSettings()
      }
    } catch (error) {
      console.error('Error loading SSL log:', error)
    }
  }

  const loadAdminProfile = async () => {
    try {
      const data = await api.getAdminMe()
      setAdminProfile({
        username: data.username,
        email: data.email || ''
      })
    } catch (error) {
      console.error('Error loading admin profile:', error)
    } finally {
      setProfileLoading(false)
    }
  }

  const loadXrayStatus = async () => {
    try {
      const data = await api.getXrayStatus()
      setXrayStatus(data)
      if (data.port) {
        setXraySettings(prev => ({
          ...prev,
          port: data.port,
          server_name: data.server_name || prev.server_name
        }))
      }
    } catch (error) {
      console.error('Error loading XRay status:', error)
    } finally {
      setXrayLoading(false)
    }
  }

  const loadWireguardStatus = async () => {
    try {
      const data = await api.getWireguardStatus()
      setWgStatus(data)
      if (data.listen_port) {
        setWgSettings(prev => ({
          ...prev,
          listen_port: data.listen_port,
          server_ip: data.server_ip || prev.server_ip,
          subnet: data.subnet || prev.subnet
        }))
      }
    } catch (error) {
      console.error('Error loading WireGuard status:', error)
    } finally {
      setWgLoading(false)
    }
  }

  const handleSetupXray = async () => {
    setXraySaving(true)
    try {
      await api.setupXrayServer(xraySettings)
      showMessage('XRay сервер настроен и запущен')
      loadXrayStatus()
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setXraySaving(false)
    }
  }

  const handleSetupWireguard = async () => {
    setWgSaving(true)
    try {
      await api.setupWireguardServer(wgSettings)
      showMessage('WireGuard сервер настроен и запущен')
      loadWireguardStatus()
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setWgSaving(false)
    }
  }

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 5000)
  }

  const handleSaveSystemSettings = async () => {
    setSystemSaving(true)
    try {
      await api.saveSystemSettings(systemSettings)
      showMessage(t('settings.settingsSaved'))
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setSystemSaving(false)
    }
  }

  const handleSaveSSLSettings = async () => {
    setSslSaving(true)
    try {
      await api.saveSSLSettings({
        domain: sslSettings.domain,
        email: sslSettings.email
      })
      showMessage(t('settings.settingsSaved'))
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setSslSaving(false)
    }
  }

  const handleObtainCertificate = async () => {
    try {
      await api.obtainSSLCertificate()
      setSslSettings(prev => ({ ...prev, is_processing: true }))
      setSslLog([])
    } catch (error) {
      showMessage(error.message, 'error')
    }
  }

  const handleRenewCertificate = async () => {
    try {
      await api.renewSSLCertificate()
      setSslSettings(prev => ({ ...prev, is_processing: true }))
      setSslLog([])
    } catch (error) {
      showMessage(error.message, 'error')
    }
  }

  const handleEnableHTTPS = async () => {
    try {
      const result = await api.enableHTTPS()
      showMessage(result.message)
      // Redirect to HTTPS after short delay
      if (result.https_url) {
        setTimeout(() => {
          window.location.href = result.https_url + '/admin/settings'
        }, 2000)
      }
    } catch (error) {
      showMessage(error.message, 'error')
    }
  }

  const handleSaveProfile = async () => {
    setProfileSaving(true)
    try {
      await api.updateAdminProfile(adminProfile)
      showMessage(t('settings.profileUpdated'))
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setProfileSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (passwords.new !== passwords.confirm) {
      showMessage(t('settings.passwordMismatch'), 'error')
      return
    }
    if (passwords.new.length < 8) {
      showMessage(t('settings.passwordTooShort'), 'error')
      return
    }

    setPasswordSaving(true)
    try {
      await api.changeAdminPassword(passwords.current, passwords.new)
      showMessage(t('settings.passwordChanged'))
      setPasswords({ current: '', new: '', confirm: '' })
    } catch (error) {
      showMessage(error.message, 'error')
    } finally {
      setPasswordSaving(false)
    }
  }

  const handleRestartService = async (serviceName) => {
    try {
      await api.restartService(serviceName)
      showMessage(t('settings.serviceRestarted', { service: serviceName }))
      loadServiceStatus()
    } catch (error) {
      showMessage(error.message, 'error')
    }
  }

  const handleSyncVpn = async () => {
    setVpnSyncing(true)
    setVpnSyncResult(null)
    try {
      const result = await api.syncVpnConfig()
      setVpnSyncResult(result)
      showMessage(result.message)
      loadServiceStatus()
    } catch (error) {
      showMessage(error.message, 'error')
      setVpnSyncResult({ success: false, message: error.message, details: [] })
    } finally {
      setVpnSyncing(false)
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'stopped':
        return <XCircle className="w-5 h-5 text-red-500" />
      default:
        return <AlertCircle className="w-5 h-5 text-yellow-500" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return 'bg-green-100 text-green-700'
      case 'stopped':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-yellow-100 text-yellow-700'
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('settings.title')}</h1>

      {/* Message */}
      {message && (
        <div className={`mb-6 p-4 rounded-lg ${message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Settings */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Server className="w-5 h-5" />
            {t('settings.systemSettings')}
          </h3>

          {systemLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-10 bg-gray-200 rounded"></div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('settings.domain')}
                </label>
                <input
                  type="text"
                  value={systemSettings.domain}
                  onChange={(e) => setSystemSettings({ ...systemSettings, domain: e.target.value })}
                  className="input"
                  placeholder="vpn.example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('settings.serverIp')}
                </label>
                <input
                  type="text"
                  value={systemSettings.server_ip}
                  onChange={(e) => setSystemSettings({ ...systemSettings, server_ip: e.target.value })}
                  className="input"
                  placeholder="xxx.xxx.xxx.xxx"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('settings.vpnSubnet')}
                </label>
                <input
                  type="text"
                  value={systemSettings.vpn_subnet}
                  onChange={(e) => setSystemSettings({ ...systemSettings, vpn_subnet: e.target.value })}
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('settings.dnsServers')}
                </label>
                <input
                  type="text"
                  value={systemSettings.dns_servers}
                  onChange={(e) => setSystemSettings({ ...systemSettings, dns_servers: e.target.value })}
                  className="input"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('settings.httpProxyPort')}
                  </label>
                  <input
                    type="number"
                    value={systemSettings.http_proxy_port}
                    onChange={(e) => setSystemSettings({ ...systemSettings, http_proxy_port: parseInt(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('settings.socksProxyPort')}
                  </label>
                  <input
                    type="number"
                    value={systemSettings.socks_proxy_port}
                    onChange={(e) => setSystemSettings({ ...systemSettings, socks_proxy_port: parseInt(e.target.value) })}
                    className="input"
                  />
                </div>
              </div>

              <button
                onClick={handleSaveSystemSettings}
                disabled={systemSaving}
                className="btn btn-primary w-full"
              >
                {systemSaving ? t('common.loading') : t('common.save')}
              </button>
            </div>
          )}
        </div>

        {/* Service Status */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Globe className="w-5 h-5" />
              {t('settings.serviceStatus')}
            </h3>
            <button
              onClick={loadServiceStatus}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              <RefreshCw className={`w-4 h-4 ${statusLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {statusLoading ? (
            <div className="animate-pulse space-y-3">
              {[1, 2, 3, 4, 5].map(i => (
                <div key={i} className="h-12 bg-gray-200 rounded"></div>
              ))}
            </div>
          ) : serviceStatus ? (
            <div className="space-y-3">
              {serviceStatus.services.map((service) => (
                <div
                  key={service.name}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    {getStatusIcon(service.status)}
                    <div>
                      <p className="font-medium text-gray-900">{service.display_name}</p>
                      {service.port && (
                        <p className="text-xs text-gray-500">
                          Port: {service.port} {service.port_open ? '✓' : '✗'}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 text-xs rounded ${getStatusColor(service.status)}`}>
                      {service.status}
                    </span>
                    <button
                      onClick={() => handleRestartService(service.name)}
                      className="p-1 text-gray-500 hover:text-gray-700"
                      title={t('settings.restart')}
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}

              {serviceStatus.system_info && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-sm text-gray-500">
                    {t('settings.hostname')}: {serviceStatus.system_info.hostname}
                  </p>
                  <p className="text-sm text-gray-500">
                    {t('settings.uptime')}: {serviceStatus.system_info.uptime}
                  </p>
                  <p className="text-sm text-gray-500">
                    {t('settings.memory')}: {serviceStatus.system_info.memory_usage}
                  </p>
                  <p className="text-sm text-gray-500">
                    {t('settings.disk')}: {serviceStatus.system_info.disk_usage}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">{t('common.error')}</p>
          )}
        </div>

        {/* VPN Configuration Sync */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Wifi className="w-5 h-5" />
            {t('settings.vpnConfig') || 'VPN Configuration'}
          </h3>

          <p className="text-sm text-gray-600 mb-4">
            {t('settings.vpnConfigDescription') || 'Synchronize VPN server configuration with current client credentials. This updates the strongSwan configuration and reloads the VPN service.'}
          </p>

          <button
            onClick={handleSyncVpn}
            disabled={vpnSyncing || !systemSettings.domain}
            className="btn btn-primary w-full mb-4"
          >
            {vpnSyncing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                {t('common.loading') || 'Loading...'}
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('settings.syncVpn') || 'Sync VPN Configuration'}
              </>
            )}
          </button>

          {!systemSettings.domain && (
            <p className="text-sm text-yellow-600 mb-4">
              {t('settings.vpnNeedsDomain') || 'Please configure domain in system settings first.'}
            </p>
          )}

          {vpnSyncResult && (
            <div className={`p-3 rounded-lg ${vpnSyncResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
              <p className={`text-sm font-medium ${vpnSyncResult.success ? 'text-green-700' : 'text-red-700'}`}>
                {vpnSyncResult.message}
              </p>
              {vpnSyncResult.clients_count !== undefined && (
                <p className="text-sm text-gray-600 mt-1">
                  {t('settings.vpnActiveClients', { count: vpnSyncResult.clients_count }) || `Active clients: ${vpnSyncResult.clients_count}`}
                </p>
              )}
              {vpnSyncResult.details && vpnSyncResult.details.length > 0 && (
                <div className="mt-2 p-2 bg-gray-900 rounded max-h-32 overflow-y-auto">
                  {vpnSyncResult.details.map((line, i) => (
                    <p key={i} className="text-xs text-green-400 font-mono">{line}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* XRay VLESS + REALITY */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Server className="w-5 h-5" />
              XRay (VLESS + REALITY)
            </h3>
            {xrayStatus?.is_running && (
              <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-700">
                running
              </span>
            )}
          </div>

          {xrayLoading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-10 bg-gray-200 rounded"></div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
          ) : !xrayStatus?.is_installed ? (
            <p className="text-sm text-gray-500">XRay не установлен на сервере</p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Протокол VLESS + REALITY для обхода DPI. Маскируется под обычный HTTPS-трафик к популярным сайтам.
              </p>

              {xrayStatus?.is_enabled && (
                <div className="p-3 bg-green-50 rounded-lg text-sm">
                  <p><span className="text-gray-500">Public Key:</span> <code className="text-xs break-all">{xrayStatus.public_key}</code></p>
                  {xrayStatus.short_id && <p><span className="text-gray-500">Short ID:</span> {xrayStatus.short_id}</p>}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Порт</label>
                <input
                  type="number"
                  value={xraySettings.port}
                  onChange={(e) => setXraySettings({ ...xraySettings, port: parseInt(e.target.value) })}
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Маскировка под сайт (SNI)</label>
                <input
                  type="text"
                  value={xraySettings.server_name}
                  onChange={(e) => setXraySettings({ ...xraySettings, server_name: e.target.value, dest_server: e.target.value })}
                  className="input"
                  placeholder="www.microsoft.com"
                />
                <p className="text-xs text-gray-500 mt-1">Рекомендуется использовать популярные сайты: microsoft.com, apple.com, cloudflare.com</p>
              </div>

              <button
                onClick={handleSetupXray}
                disabled={xraySaving}
                className="btn btn-primary w-full"
              >
                {xraySaving ? 'Настройка...' : xrayStatus?.is_enabled ? 'Обновить настройки' : 'Настроить и запустить'}
              </button>
            </div>
          )}
        </div>

        {/* WireGuard VPN */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 flex items-center gap-2">
              <Shield className="w-5 h-5" />
              WireGuard VPN
            </h3>
            {wgStatus?.is_running && (
              <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-700">
                running
              </span>
            )}
          </div>

          {wgLoading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-10 bg-gray-200 rounded"></div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
          ) : !wgStatus?.is_installed ? (
            <p className="text-sm text-gray-500">WireGuard не установлен на сервере</p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Быстрый и современный VPN протокол. Полный туннель для всего трафика.
              </p>

              {wgStatus?.is_enabled && wgStatus?.public_key && (
                <div className="p-3 bg-green-50 rounded-lg text-sm">
                  <p><span className="text-gray-500">Public Key:</span> <code className="text-xs break-all">{wgStatus.public_key}</code></p>
                  <p><span className="text-gray-500">Подсеть:</span> {wgStatus.subnet}</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Порт</label>
                  <input
                    type="number"
                    value={wgSettings.listen_port}
                    onChange={(e) => setWgSettings({ ...wgSettings, listen_port: parseInt(e.target.value) })}
                    className="input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">IP сервера</label>
                  <input
                    type="text"
                    value={wgSettings.server_ip}
                    onChange={(e) => setWgSettings({ ...wgSettings, server_ip: e.target.value })}
                    className="input"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Подсеть</label>
                <input
                  type="text"
                  value={wgSettings.subnet}
                  onChange={(e) => setWgSettings({ ...wgSettings, subnet: e.target.value })}
                  className="input"
                  placeholder="10.10.0.0/24"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">DNS серверы</label>
                <input
                  type="text"
                  value={wgSettings.dns}
                  onChange={(e) => setWgSettings({ ...wgSettings, dns: e.target.value })}
                  className="input"
                  placeholder="1.1.1.1,8.8.8.8"
                />
              </div>

              <button
                onClick={handleSetupWireguard}
                disabled={wgSaving}
                className="btn btn-primary w-full"
              >
                {wgSaving ? 'Настройка...' : wgStatus?.is_enabled ? 'Обновить настройки' : 'Настроить и запустить'}
              </button>
            </div>
          )}
        </div>

        {/* SSL / Let's Encrypt */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5" />
            {t('ssl.title')}
          </h3>

          {sslLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-10 bg-gray-200 rounded"></div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('ssl.domain')}
                </label>
                <input
                  type="text"
                  value={sslSettings.domain || ''}
                  onChange={(e) => setSslSettings({ ...sslSettings, domain: e.target.value })}
                  className="input"
                  placeholder="vpn.example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('ssl.email')}
                </label>
                <input
                  type="email"
                  value={sslSettings.email || ''}
                  onChange={(e) => setSslSettings({ ...sslSettings, email: e.target.value })}
                  className="input"
                  placeholder="admin@example.com"
                />
              </div>

              {sslSettings.certificate_exists && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-700 flex items-center gap-2">
                    <CheckCircle className="w-4 h-4" />
                    {t('ssl.certificateActive')}
                  </p>
                  {sslSettings.certificate_expiry && (
                    <p className="text-xs text-green-600 mt-1">
                      {t('ssl.expiresOn')}: {sslSettings.certificate_expiry}
                    </p>
                  )}
                  {window.location.protocol === 'http:' && sslSettings.domain && (
                    <button
                      onClick={handleEnableHTTPS}
                      className="mt-2 inline-flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700 font-medium"
                    >
                      <ExternalLink className="w-4 h-4" />
                      {t('ssl.goToHttps')}
                    </button>
                  )}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={handleSaveSSLSettings}
                  disabled={sslSaving}
                  className="btn btn-secondary flex-1"
                >
                  {sslSaving ? t('common.loading') : t('common.save')}
                </button>

                {sslSettings.certificate_exists ? (
                  <button
                    onClick={handleRenewCertificate}
                    disabled={sslSettings.is_processing}
                    className="btn btn-primary flex-1"
                  >
                    {t('ssl.renewCertificate')}
                  </button>
                ) : (
                  <button
                    onClick={handleObtainCertificate}
                    disabled={sslSettings.is_processing || !sslSettings.domain || !sslSettings.email}
                    className="btn btn-primary flex-1"
                  >
                    {sslSettings.is_processing ? t('common.loading') : t('ssl.obtainCertificate')}
                  </button>
                )}
              </div>

              {/* SSL Log */}
              {sslLog.length > 0 && (
                <div className="mt-4 p-3 bg-gray-900 rounded-lg max-h-40 overflow-y-auto">
                  {sslLog.map((line, i) => (
                    <p key={i} className="text-xs text-green-400 font-mono">{line}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Admin Profile */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <User className="w-5 h-5" />
            {t('settings.adminProfile')}
          </h3>

          {profileLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-10 bg-gray-200 rounded"></div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <User className="w-4 h-4 inline mr-1" />
                  {t('auth.username')}
                </label>
                <input
                  type="text"
                  value={adminProfile.username}
                  onChange={(e) => setAdminProfile({ ...adminProfile, username: e.target.value })}
                  className="input"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  <Mail className="w-4 h-4 inline mr-1" />
                  Email
                </label>
                <input
                  type="email"
                  value={adminProfile.email}
                  onChange={(e) => setAdminProfile({ ...adminProfile, email: e.target.value })}
                  className="input"
                  placeholder="admin@example.com"
                />
              </div>

              <button
                onClick={handleSaveProfile}
                disabled={profileSaving}
                className="btn btn-primary w-full"
              >
                {profileSaving ? t('common.loading') : t('settings.saveProfile')}
              </button>

              {/* Change Password */}
              <div className="pt-4 border-t border-gray-200">
                <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  {t('settings.changePassword')}
                </h4>

                <div className="space-y-3">
                  <div className="relative">
                    <input
                      type={showPasswords ? 'text' : 'password'}
                      value={passwords.current}
                      onChange={(e) => setPasswords({ ...passwords, current: e.target.value })}
                      className="input pr-10"
                      placeholder={t('settings.currentPassword')}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPasswords(!showPasswords)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500"
                    >
                      {showPasswords ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>

                  <input
                    type={showPasswords ? 'text' : 'password'}
                    value={passwords.new}
                    onChange={(e) => setPasswords({ ...passwords, new: e.target.value })}
                    className="input"
                    placeholder={t('settings.newPassword')}
                  />

                  <input
                    type={showPasswords ? 'text' : 'password'}
                    value={passwords.confirm}
                    onChange={(e) => setPasswords({ ...passwords, confirm: e.target.value })}
                    className="input"
                    placeholder={t('settings.confirmPassword')}
                  />

                  <button
                    onClick={handleChangePassword}
                    disabled={passwordSaving || !passwords.current || !passwords.new || !passwords.confirm}
                    className="btn btn-secondary w-full"
                  >
                    {passwordSaving ? t('common.loading') : t('settings.changePassword')}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* About */}
        <div className="card p-6 lg:col-span-2">
          <h3 className="font-semibold text-gray-900 mb-4">{t('settings.about')}</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm text-gray-600">
            <div>
              <p className="font-medium text-gray-900">{t('settings.version')}</p>
              <p>{appVersion}</p>
            </div>
            <div>
              <p className="font-medium text-gray-900">{t('settings.system')}</p>
              <p>VPN/Proxy Access Management System</p>
            </div>
            <div>
              <p className="font-medium text-gray-900">{t('settings.features')}</p>
              <p>IKEv2/IPsec VPN, HTTP/SOCKS5 Proxy, Split Tunneling</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
