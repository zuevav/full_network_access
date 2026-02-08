const API_BASE = '/api'

class ApiClient {
  constructor() {
    this.baseUrl = API_BASE
  }

  // Get token based on type
  getToken(type = 'admin') {
    return localStorage.getItem(`${type}_token`)
  }

  // Set token
  setToken(type, token) {
    localStorage.setItem(`${type}_token`, token)
  }

  // Remove token
  removeToken(type) {
    localStorage.removeItem(`${type}_token`)
  }

  // Make request
  async request(endpoint, options = {}, tokenType = 'admin') {
    const url = `${this.baseUrl}${endpoint}`
    const token = this.getToken(tokenType)

    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
      ...options,
      headers,
    })

    // Handle 401 - unauthorized
    if (response.status === 401) {
      this.removeToken(tokenType)
      if (tokenType === 'admin') {
        window.location.href = '/admin/login'
      } else {
        window.location.href = '/my/login'
      }
      throw new Error('Unauthorized')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    // Handle empty response
    if (response.status === 204) {
      return null
    }

    return response.json()
  }

  // Admin API methods
  async adminLogin(username, password, totpCode) {
    const data = await this.request('/admin/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password, totp_code: totpCode }),
    })
    this.setToken('admin', data.access_token)
    return data
  }

  async getAdminMe() {
    return this.request('/admin/auth/me')
  }

  async getDashboard() {
    return this.request('/admin/dashboard')
  }

  async getClients(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.request(`/admin/clients${query ? `?${query}` : ''}`)
  }

  async getClient(id) {
    return this.request(`/admin/clients/${id}`)
  }

  async createClient(data) {
    return this.request('/admin/clients', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateClient(id, data) {
    return this.request(`/admin/clients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteClient(id) {
    return this.request(`/admin/clients/${id}`, { method: 'DELETE' })
  }

  async activateClient(id) {
    return this.request(`/admin/clients/${id}/activate`, { method: 'POST' })
  }

  async deactivateClient(id) {
    return this.request(`/admin/clients/${id}/deactivate`, { method: 'POST' })
  }

  async getClientDomains(clientId) {
    return this.request(`/admin/clients/${clientId}/domains`)
  }

  async addClientDomains(clientId, domains, includeSubdomains = true) {
    return this.request(`/admin/clients/${clientId}/domains`, {
      method: 'POST',
      body: JSON.stringify({ domains, include_subdomains: includeSubdomains }),
    })
  }

  async deleteClientDomain(clientId, domainId) {
    return this.request(`/admin/clients/${clientId}/domains/${domainId}`, {
      method: 'DELETE',
    })
  }

  async applyTemplate(clientId, templateId) {
    return this.request(`/admin/clients/${clientId}/domains/template`, {
      method: 'POST',
      body: JSON.stringify({ template_id: templateId }),
    })
  }

  async analyzeDomain(domain) {
    return this.request('/admin/clients/analyze', {
      method: 'POST',
      body: JSON.stringify({ domain }),
    })
  }

  async getVpnCredentials(clientId) {
    return this.request(`/admin/clients/${clientId}/vpn/credentials`)
  }

  async resetVpnPassword(clientId) {
    return this.request(`/admin/clients/${clientId}/vpn/reset-password`, {
      method: 'POST',
    })
  }

  async getProxyCredentials(clientId) {
    return this.request(`/admin/clients/${clientId}/proxy/credentials`)
  }

  async resetProxyPassword(clientId) {
    return this.request(`/admin/clients/${clientId}/proxy/reset-password`, {
      method: 'POST',
    })
  }

  async updateProxyAllowedIps(clientId, allowedIps) {
    return this.request(`/admin/clients/${clientId}/proxy/allowed-ips`, {
      method: 'PUT',
      body: JSON.stringify({ allowed_ips: allowedIps }),
    })
  }

  // XRay API methods
  async getXrayStatus() {
    return this.request('/admin/clients/xray/status')
  }

  async setupXrayServer(data) {
    return this.request('/admin/clients/xray/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async startXrayServer() {
    return this.request('/admin/clients/xray/start', { method: 'POST' })
  }

  async stopXrayServer() {
    return this.request('/admin/clients/xray/stop', { method: 'POST' })
  }

  async getClientXray(clientId) {
    return this.request(`/admin/clients/${clientId}/xray`)
  }

  async enableClientXray(clientId) {
    return this.request(`/admin/clients/${clientId}/xray/enable`, { method: 'POST' })
  }

  async disableClientXray(clientId) {
    return this.request(`/admin/clients/${clientId}/xray/disable`, { method: 'POST' })
  }

  async regenerateClientXray(clientId) {
    return this.request(`/admin/clients/${clientId}/xray/regenerate`, { method: 'POST' })
  }

  // WireGuard API methods
  async getWireguardStatus() {
    return this.request('/admin/clients/wireguard/status')
  }

  async setupWireguardServer(data) {
    return this.request('/admin/clients/wireguard/setup', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async startWireguardServer() {
    return this.request('/admin/clients/wireguard/start', { method: 'POST' })
  }

  async stopWireguardServer() {
    return this.request('/admin/clients/wireguard/stop', { method: 'POST' })
  }

  async getClientWireguard(clientId) {
    return this.request(`/admin/clients/${clientId}/wireguard`)
  }

  async enableClientWireguard(clientId) {
    return this.request(`/admin/clients/${clientId}/wireguard/enable`, { method: 'POST' })
  }

  async disableClientWireguard(clientId) {
    return this.request(`/admin/clients/${clientId}/wireguard/disable`, { method: 'POST' })
  }

  async regenerateClientWireguard(clientId) {
    return this.request(`/admin/clients/${clientId}/wireguard/regenerate`, { method: 'POST' })
  }

  async getClientPayments(clientId) {
    return this.request(`/admin/clients/${clientId}/payments`)
  }

  async createPayment(clientId, data) {
    return this.request(`/admin/clients/${clientId}/payments`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async deletePayment(paymentId) {
    return this.request(`/admin/payments/${paymentId}`, { method: 'DELETE' })
  }

  async getTemplates() {
    return this.request('/admin/templates')
  }

  async createTemplate(data) {
    return this.request('/admin/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async updateTemplate(id, data) {
    return this.request(`/admin/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  async deleteTemplate(id) {
    return this.request(`/admin/templates/${id}`, { method: 'DELETE' })
  }

  async getDomainRequests(status) {
    const query = status ? `?status=${status}` : ''
    return this.request(`/admin/domain-requests${query}`)
  }

  async approveDomainRequest(id, comment) {
    return this.request(`/admin/domain-requests/${id}/approve`, {
      method: 'PUT',
      body: JSON.stringify({ admin_comment: comment }),
    })
  }

  async rejectDomainRequest(id, comment) {
    return this.request(`/admin/domain-requests/${id}/reject`, {
      method: 'PUT',
      body: JSON.stringify({ admin_comment: comment }),
    })
  }

  // System Updates API methods
  async getUpdateSettings() {
    return this.request('/admin/updates/settings')
  }

  async saveUpdateSettings(data) {
    return this.request('/admin/updates/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async deleteUpdateSettings() {
    return this.request('/admin/updates/settings', { method: 'DELETE' })
  }

  async getUpdateStatus() {
    return this.request('/admin/updates/status')
  }

  async checkForUpdates() {
    return this.request('/admin/updates/check', { method: 'POST' })
  }

  async applyUpdates() {
    return this.request('/admin/updates/apply', { method: 'POST' })
  }

  async getUpdateLog() {
    return this.request('/admin/updates/log')
  }

  // SSL/Let's Encrypt API methods
  async getSSLSettings() {
    return this.request('/admin/ssl/settings')
  }

  async saveSSLSettings(data) {
    return this.request('/admin/ssl/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async obtainSSLCertificate() {
    return this.request('/admin/ssl/obtain', { method: 'POST' })
  }

  async renewSSLCertificate() {
    return this.request('/admin/ssl/renew', { method: 'POST' })
  }

  async getSSLLog() {
    return this.request('/admin/ssl/log')
  }

  async enableHTTPS() {
    return this.request('/admin/ssl/enable-https', { method: 'POST' })
  }

  // System Settings API methods
  async getVersion() {
    const response = await fetch(`${this.baseUrl}/admin/system/version`)
    return response.json()
  }

  async getSystemSettings() {
    return this.request('/admin/system/settings')
  }

  async saveSystemSettings(data) {
    return this.request('/admin/system/settings', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getServiceStatus() {
    return this.request('/admin/system/status')
  }

  async restartService(serviceName) {
    return this.request(`/admin/system/restart/${serviceName}`, { method: 'POST' })
  }

  async syncVpnConfig() {
    return this.request('/admin/system/vpn/sync', { method: 'POST' })
  }

  // Admin Account API methods
  async changeAdminPassword(currentPassword, newPassword) {
    return this.request('/admin/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    })
  }

  async updateAdminProfile(data) {
    return this.request('/admin/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  }

  // Portal (client) API methods
  async clientLogin(username, password) {
    const data = await this.request('/portal/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }, 'client')
    this.setToken('client', data.access_token)
    return data
  }

  async clientLoginByLink(accessToken) {
    const data = await this.request(`/portal/auth/link/${accessToken}`, {
      method: 'POST',
    }, 'client')
    this.setToken('client', data.access_token)
    return data
  }

  async getPortalMe() {
    return this.request('/portal/me', {}, 'client')
  }

  async getPortalProfiles() {
    return this.request('/portal/profiles/info', {}, 'client')
  }

  async getPortalDomains() {
    return this.request('/portal/domains', {}, 'client')
  }

  async requestDomain(domain, reason) {
    return this.request('/portal/domains/request', {
      method: 'POST',
      body: JSON.stringify({ domain, reason }),
    }, 'client')
  }

  async getPortalDomainRequests() {
    return this.request('/portal/domains/requests', {}, 'client')
  }

  async getPortalPayments() {
    return this.request('/portal/payments', {}, 'client')
  }

  async changePortalPassword(oldPassword, newPassword) {
    return this.request('/portal/account/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }, 'client')
  }

  // Logout
  adminLogout() {
    this.removeToken('admin')
    window.location.href = '/admin/login'
  }

  clientLogout() {
    this.removeToken('client')
    window.location.href = '/my/login'
  }
}

export const api = new ApiClient()
export default api
