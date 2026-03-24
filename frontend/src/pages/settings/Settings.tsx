import React, { useState, useEffect } from 'react';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from '../../context/SnackbarContext';
import { User, Mail, Shield, LogOut, Plus, Copy, CheckCheck, Trash2, ToggleLeft, ToggleRight, Inbox, Clock, FileCheck, Zap, ZapOff } from 'lucide-react';

interface EmailConfig {
  id: number;
  email_address: string;
  provider: string;
  is_active: boolean;
  ingestion_enabled: boolean;
  inbound_slug: string | null;
  total_ingested: number;
  last_received_at: string | null;
}

const INBOUND_DOMAIN = 'inbound.lexflow.app';

const SettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const { showSnackbar } = useSnackbar();
  const [emailConfigs, setEmailConfigs] = useState<EmailConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [batterySave, setBatterySave] = useState(false);
  const [updatingBattery, setUpdatingBattery] = useState(false);

  useEffect(() => { 
    fetchEmailConfigs();
    if (user?.organization?.id) {
      fetchOrgSettings();
    }
  }, [user]);

  const fetchOrgSettings = async () => {
    try {
      const response = await api.get(`/v1/organizations/${user?.organization?.id}`);
      setBatterySave(response.data.ai_battery_save_mode);
    } catch (error) {
      console.error('Failed to fetch org settings:', error);
    }
  };

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

  const toggleBatterySave = async () => {
    if (!user?.organization?.id) return;
    setUpdatingBattery(true);
    try {
      const nextValue = !batterySave;
      await api.patch(`/v1/organizations/${user.organization.id}/settings`, {
        ai_battery_save_mode: nextValue
      });
      setBatterySave(nextValue);
    } catch (error: any) {
      showSnackbar(`Failed to update AI settings: ${error.response?.data?.detail || error.message}`, { type: 'error' });
    } finally {
      setUpdatingBattery(false);
    }
  };

  const handleAddEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail.trim()) return;
    setAdding(true);
    try {
      await api.post('/v1/email/', { email_address: newEmail.trim() });
      setNewEmail('');
      setShowAddForm(false);
      await fetchEmailConfigs();
    } catch (error: any) {
      showSnackbar(`Failed to add email: ${error.response?.data?.detail || error.message}`, { type: 'error' });
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Remove this email intake address?')) return;
    try {
      await api.delete(`/v1/email/${id}`);
      setEmailConfigs(c => c.filter(cfg => cfg.id !== id));
    } catch (error: any) {
      showSnackbar(`Failed to remove: ${error.response?.data?.detail || error.message}`, { type: 'error' });
    }
  };

  const handleToggle = async (id: number) => {
    try {
      const res = await api.patch(`/v1/email/${id}/toggle`);
      setEmailConfigs(c => c.map(cfg =>
        cfg.id === id ? { ...cfg, ingestion_enabled: res.data.ingestion_enabled } : cfg
      ));
    } catch (error: any) {
      showSnackbar(`Toggle failed: ${error.response?.data?.detail || error.message}`, { type: 'error' });
    }
  };

  const copyToClipboard = (id: number, slug: string) => {
    navigator.clipboard.writeText(`${slug}@${INBOUND_DOMAIN}`);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const roleLabel = user?.role === 'org_admin' ? t('roles.orgAdmin')
    : user?.role ? t(`roles.${user.role}`)
    : t('roles.user');

  const roleColor: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-700',
    org_admin: 'bg-indigo-100 text-indigo-700',
    lawyer: 'bg-blue-100 text-blue-700',
    assistant: 'bg-green-100 text-green-700',
    viewer: 'bg-slate-100 text-slate-700',
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">{t('settingsPage.title')}</h1>
        <p className="text-sm text-slate-400 mt-1">{t('settingsPage.subtitle')}</p>
      </div>

      {/* Profile Card */}
      <div className="bg-white rounded-2xl p-6">
        <div className="flex items-center gap-4 mb-5">
          <User className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold text-slate-700">{t('settingsPage.profile')}</h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center text-white text-xl font-bold">
            {user?.name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <div>
            <p className="text-lg font-semibold text-slate-800">{user?.name}</p>
            <p className="text-sm text-slate-500">{user?.email}</p>
            <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-semibold ${roleColor[user?.role ?? ''] ?? 'bg-slate-100 text-slate-700'}`}>
              {roleLabel}
            </span>
          </div>
          <button
            onClick={logout}
            className="ms-auto flex items-center gap-2 text-sm text-red-500 hover:text-red-600 font-medium transition-colors"
          >
            <LogOut className="h-4 w-4" />
            {t('settingsPage.signOut')}
          </button>
        </div>
      </div>

      {/* AI Settings - Only for System Super Admins (ADMIN) */}
      {user?.role === 'admin' && (
        <div className="bg-white rounded-2xl p-6 border-2 border-emerald-50">
          <div className="flex items-center justify-between">
            <div className="flex items-start gap-4">
              <div className={`p-3 rounded-xl ${batterySave ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'}`}>
                {batterySave ? <ZapOff className="h-6 w-6" /> : <Zap className="h-6 w-6" />}
              </div>
              <div>
                <h2 className="font-semibold text-slate-700 flex items-center gap-2">
                  AI Battery Save Mode
                  {batterySave && <span className="text-[10px] bg-emerald-500 text-white px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider">Active</span>}
                </h2>
                <p className="text-xs text-slate-400 mt-1 max-w-md">
                  When enabled, AI will only analyze a sample of document pages to save API tokens and reduce costs. 
                  Best for large documents and restricted quotas.
                </p>
              </div>
            </div>
            <button
              onClick={toggleBatterySave}
              disabled={updatingBattery}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${batterySave ? 'bg-emerald-500' : 'bg-slate-200'}`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${batterySave ? 'translate-x-6' : 'translate-x-1'}`}
              />
            </button>
          </div>
        </div>
      )}

      {/* Email Intake */}
      <div className="bg-white rounded-2xl p-6">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Inbox className="h-5 w-5 text-slate-400" />
            <h2 className="font-semibold text-slate-700">{t('settingsPage.emailIntake')}</h2>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-slate-900 border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            {t('settingsPage.addEmail')}
          </button>
        </div>

        <p className="text-sm text-slate-400 mb-5">
          {t('settingsPage.emailIntakeDesc')}
        </p>

        {/* Add form */}
        {showAddForm && (
          <form onSubmit={handleAddEmail} className="mb-5 p-4 bg-slate-50 rounded-xl border border-slate-100">
            <label className="block text-sm font-medium text-slate-600 mb-1.5">
              {t('settingsPage.addForm.label')}
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder={t('settingsPage.addForm.placeholder')}
                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm outline-none focus:border-slate-400 bg-white"
                required
              />
              <button
                type="submit"
                disabled={adding}
                className="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 disabled:opacity-50 transition"
              >
                {adding ? t('settingsPage.addForm.adding') : t('settingsPage.addForm.add')}
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-2 text-sm text-slate-500 hover:text-slate-700 transition"
              >
                {t('settingsPage.addForm.cancel')}
              </button>
            </div>
          </form>
        )}

        {/* Email config cards */}
        {loading ? (
          <div className="text-center py-8 text-slate-400 text-sm">{t('settingsPage.loading')}</div>
        ) : emailConfigs.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">
            {t('settingsPage.noEmails')}
          </div>
        ) : (
          <div className="space-y-3">
            {emailConfigs.map(cfg => {
              const inboundAddress = cfg.inbound_slug ? `${cfg.inbound_slug}@${INBOUND_DOMAIN}` : null;
              const copied = copiedId === cfg.id;

              return (
                <div key={cfg.id} className={`rounded-xl border p-4 transition-all ${cfg.ingestion_enabled ? 'border-slate-100 bg-slate-50/50' : 'border-dashed border-slate-200 opacity-60'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Mail className="h-4 w-4 text-slate-400 shrink-0" />
                        <span className="text-sm font-semibold text-slate-700 truncate">{cfg.email_address}</span>
                        {cfg.ingestion_enabled
                          ? <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full">{t('status.active')}</span>
                          : <span className="text-xs font-semibold text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{t('status.paused')}</span>
                        }
                      </div>

                      {/* Inbound address with copy button */}
                      {inboundAddress && (
                        <div className="flex items-center gap-2 mt-2">
                          <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-1.5 flex-1 min-w-0">
                            <span className="text-xs text-slate-500 font-mono truncate">{inboundAddress}</span>
                          </div>
                          <button
                            onClick={() => copyToClipboard(cfg.id, cfg.inbound_slug!)}
                            className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-slate-700 transition shrink-0"
                            title={t('settingsPage.copy')}
                          >
                            {copied ? <CheckCheck className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                            {copied ? t('settingsPage.copied') : t('settingsPage.copy')}
                          </button>
                        </div>
                      )}

                      {/* Stats row */}
                      <div className="flex items-center gap-4 mt-2.5 text-xs text-slate-400">
                        <span className="flex items-center gap-1">
                          <FileCheck className="h-3 w-3" />
                          {t('settingsPage.docsIngested', { count: cfg.total_ingested ?? 0 })}
                        </span>
                        {cfg.last_received_at && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {t('settingsPage.last', { date: new Date(cfg.last_received_at).toLocaleString() })}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleToggle(cfg.id)}
                        title={cfg.ingestion_enabled ? 'Pause ingestion' : 'Enable ingestion'}
                        className="p-2 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition"
                      >
                        {cfg.ingestion_enabled
                          ? <ToggleRight className="h-5 w-5 text-emerald-500" />
                          : <ToggleLeft className="h-5 w-5" />
                        }
                      </button>
                      <button
                        onClick={() => handleDelete(cfg.id)}
                        title="Remove"
                        className="p-2 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {/* Setup instructions (shown only when email was just added) */}
                  {inboundAddress && cfg.total_ingested === 0 && (
                    <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-100">
                      <p className="text-xs font-semibold text-blue-700 mb-1">{t('settingsPage.setup')}</p>
                      <ol className="text-xs text-blue-600 space-y-0.5 list-decimal list-inside">
                        <li>{t('settingsPage.setup1')}</li>
                        <li>{t('settingsPage.setup2')}</li>
                        <li>{t('settingsPage.setup3')}</li>
                      </ol>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Security */}
      <div className="bg-white rounded-2xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="h-5 w-5 text-slate-400" />
          <h2 className="font-semibold text-slate-700">{t('settingsPage.security')}</h2>
        </div>
        <p className="text-sm text-slate-500">
          {t('settingsPage.securityDesc')}
        </p>
      </div>
    </div>
  );
};

export default SettingsPage;
