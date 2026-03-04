import React, { useState, useEffect } from 'react';
import api from '../../services/api';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { User, Mail, Shield, LogOut, Plus, RefreshCw, Loader2 } from 'lucide-react';

interface EmailConfig {
  id: number;
  email_address: string;
  provider: string;
  is_active: boolean;
  last_synced_at?: string;
}

const SettingsPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [emailConfigs, setEmailConfigs] = useState<EmailConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [syncing, setSyncing] = useState<number | null>(null);
  const [formData, setFormData] = useState({
    provider: 'imap',
    email_address: '',
    imap_server: '',
    imap_port: 993,
    username: '',
    password: '',
  });

  useEffect(() => {
    fetchEmailConfigs();
  }, []);

  const fetchEmailConfigs = async () => {
    try {
      const response = await api.get('/v1/email/');
      setEmailConfigs(response.data);
    } catch (error) {
      console.error('Failed to fetch email configs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/v1/email/', formData);
      setShowAddForm(false);
      setFormData({ provider: 'imap', email_address: '', imap_server: '', imap_port: 993, username: '', password: '' });
      fetchEmailConfigs();
    } catch (error: any) {
      alert(`Failed to add email config: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleSync = async (configId: number) => {
    setSyncing(configId);
    try {
      await api.post(`/v1/email/${configId}/sync`);
      alert('Email sync started! Check the email intake page in a moment.');
      fetchEmailConfigs();
    } catch (error: any) {
      alert(`Sync failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSyncing(null);
    }
  };

  const roleLabel = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1).toLowerCase()
    : 'User';

  const roleColor: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-700',
    ADMIN: 'bg-purple-100 text-purple-700',
    lawyer: 'bg-blue-100 text-blue-700',
    LAWYER: 'bg-blue-100 text-blue-700',
    assistant: 'bg-green-100 text-green-700',
    ASSISTANT: 'bg-green-100 text-green-700',
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and integrations</p>
      </div>

      <div className="max-w-3xl space-y-8">
        {/* User Profile Card */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Profile
          </h2>
          <div className="flex items-center gap-5">
            <div className="h-16 w-16 rounded-full bg-primary/10 border-2 border-primary/20 flex items-center justify-center text-2xl font-bold text-primary">
              {user?.name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) ?? 'U'}
            </div>
            <div className="flex-1">
              <p className="text-xl font-bold text-slate-800">{user?.name ?? '—'}</p>
              <div className="flex items-center gap-2 mt-1">
                <Mail className="h-4 w-4 text-slate-400 shrink-0" />
                <p className="text-sm text-slate-500">{user?.email ?? '—'}</p>
              </div>
              <span className={`inline-block mt-2 text-xs px-2.5 py-1 rounded-full font-semibold ${roleColor[user?.role ?? ''] ?? 'bg-slate-100 text-slate-600'}`}>
                <Shield className="inline h-3 w-3 mr-1" />{roleLabel}
              </span>
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-destructive border border-destructive/20 rounded-xl hover:bg-destructive/5 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Sign Out
            </button>
          </div>
        </div>

        {/* Email Configuration Section */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-center mb-5">
            <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              Email Accounts
            </h2>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              {showAddForm ? 'Cancel' : 'Add Email'}
            </button>
          </div>

          {showAddForm && (
            <form onSubmit={handleSubmit} className="mb-6 p-5 border border-border rounded-xl bg-slate-50 space-y-4">
              <h3 className="font-semibold text-slate-800">New Email Configuration</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Email Address</label>
                  <input type="email" required value={formData.email_address} onChange={e => setFormData({ ...formData, email_address: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="you@example.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Provider</label>
                  <select value={formData.provider} onChange={e => setFormData({ ...formData, provider: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 bg-white">
                    <option value="imap">IMAP</option>
                    <option value="gmail">Gmail</option>
                    <option value="graph">Microsoft Graph</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">IMAP Server</label>
                  <input type="text" value={formData.imap_server} onChange={e => setFormData({ ...formData, imap_server: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" placeholder="imap.gmail.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">IMAP Port</label>
                  <input type="number" value={formData.imap_port} onChange={e => setFormData({ ...formData, imap_port: parseInt(e.target.value) })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Username</label>
                  <input type="text" value={formData.username} onChange={e => setFormData({ ...formData, username: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
                  <input type="password" required value={formData.password} onChange={e => setFormData({ ...formData, password: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50" />
                </div>
              </div>
              <button type="submit" className="px-5 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors">
                Save Configuration
              </button>
            </form>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-slate-400 py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Loading email accounts...</span>
            </div>
          ) : emailConfigs.length > 0 ? (
            <ul className="space-y-3">
              {emailConfigs.map(config => (
                <li key={config.id} className="p-4 border border-border rounded-xl flex items-center justify-between gap-4">
                  <div>
                    <p className="font-semibold text-slate-800">{config.email_address}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      <span className="uppercase font-medium">{config.provider}</span>
                      {' · '}
                      <span className={config.is_active ? 'text-green-600 font-medium' : 'text-slate-400'}>
                        {config.is_active ? '● Active' : '○ Inactive'}
                      </span>
                      {config.last_synced_at && ` · Last synced ${new Date(config.last_synced_at).toLocaleString()}`}
                    </p>
                  </div>
                  <button
                    onClick={() => handleSync(config.id)}
                    disabled={syncing === config.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary/10 text-primary rounded-lg hover:bg-primary/20 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${syncing === config.id ? 'animate-spin' : ''}`} />
                    {syncing === config.id ? 'Syncing...' : 'Sync'}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400 py-4">No email accounts configured yet.</p>
          )}
        </div>

        {/* Email Intake Link */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
          <h3 className="font-semibold text-blue-800 mb-1.5">📧 Email Intake</h3>
          <p className="text-sm text-blue-600 mb-3">View and process incoming emails from your configured accounts.</p>
          <Link to="/email" className="text-sm font-semibold text-blue-700 hover:text-blue-900 transition-colors">
            Go to Email Intake →
          </Link>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
