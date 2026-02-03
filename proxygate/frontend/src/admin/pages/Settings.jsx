import { Globe, Server, MessageSquare } from 'lucide-react'

export default function Settings() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Server Info */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Server className="w-5 h-5" />
            Server Configuration
          </h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">VPN Domain</span>
              <span className="font-mono">vpn.yourdomain.com</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">IKEv2 Port</span>
              <span className="font-mono">500/4500 UDP</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">HTTP Proxy</span>
              <span className="font-mono">3128</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">SOCKS5 Proxy</span>
              <span className="font-mono">1080</span>
            </div>
          </div>
        </div>

        {/* VPN Status */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Globe className="w-5 h-5" />
            VPN Service
          </h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-500">strongSwan</span>
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500">3proxy</span>
              <span className="px-2 py-1 bg-green-100 text-green-700 rounded">Active</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-500">SSL Certificate</span>
              <span className="text-gray-700">Let's Encrypt</span>
            </div>
          </div>
        </div>

        {/* Telegram */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Telegram Notifications
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            Configure Telegram bot token and admin chat ID in the .env file.
          </p>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-gray-500">Bot Status</span>
              <span className="text-gray-700">Not configured</span>
            </div>
          </div>
        </div>

        {/* About */}
        <div className="card p-6">
          <h3 className="font-semibold text-gray-900 mb-4">About ProxyGate</h3>
          <div className="space-y-2 text-sm text-gray-600">
            <p>Version: 2.0.0</p>
            <p>VPN/Proxy Access Management System</p>
            <p className="mt-4">
              Manage IKEv2/IPsec VPN and HTTP/SOCKS5 proxy access for clients.
              Features split tunneling with per-client domain lists.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
