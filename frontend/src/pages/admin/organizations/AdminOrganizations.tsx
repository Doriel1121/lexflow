import { useEffect, useState } from 'react';
import { Building2, Search, MoreVertical, Plus, X, Loader2, Zap, ZapOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '../../../services/api';

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  ai_battery_save_mode: boolean;
  member_count: number;
  created_at: string;
}

export default function AdminOrganizations() {
  const { t } = useTranslation();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    organization_name: '',
    admin_name: '',
    admin_email: '',
    password: ''
  });

  useEffect(() => {
    fetchOrganizations();
  }, []);

  const fetchOrganizations = async () => {
    try {
      setLoading(true);
      const res = await api.get('/v1/admin/organizations');
      setOrganizations(res.data);
    } catch (err) {
      console.error('Failed to load organizations', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredOrgs = organizations.filter(org => 
    org.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
    org.slug.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post('/v1/admin/organizations', {
        organization_name: formData.organization_name,
        admin_name: formData.admin_name,
        admin_email: formData.admin_email,
        password: formData.password || undefined // omit if empty so backend auto-generates
      });
      setIsModalOpen(false);
      setFormData({ organization_name: '', admin_name: '', admin_email: '', password: '' });
      fetchOrganizations();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create organization');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleBatterySave = async (orgId: number, currentVal: boolean) => {
    try {
      const nextVal = !currentVal;
      await api.patch(`/v1/organizations/${orgId}/settings`, {
        ai_battery_save_mode: nextVal
      });
      setOrganizations(orgs => orgs.map(o => 
        o.id === orgId ? { ...o, ai_battery_save_mode: nextVal } : o
      ));
    } catch (err: any) {
      alert('Failed to update AI settings');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">{t('adminOrgs.title')}</h1>
          <p className="text-muted-foreground mt-1">{t('adminOrgs.subtitle')}</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t('adminOrgs.addOrg')}
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <div className="relative max-w-sm">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder={t('adminOrgs.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full ps-9 pe-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-start">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">{t('adminOrgs.table.tenantName')}</th>
                <th className="px-6 py-3">{t('adminOrgs.table.slug')}</th>
                <th className="px-6 py-3">AI Mode</th>
                <th className="px-6 py-3">{t('adminOrgs.table.members')}</th>
                <th className="px-6 py-3">{t('adminOrgs.table.status')}</th>
                <th className="px-6 py-3">{t('adminOrgs.table.created')}</th>
                <th className="px-6 py-3 text-end">{t('adminOrgs.table.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin mb-4" />
                      {t('adminOrgs.loading')}
                    </div>
                  </td>
                </tr>
              ) : filteredOrgs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    {t('adminOrgs.noOrgs')}
                  </td>
                </tr>
              ) : (
                filteredOrgs.map((org) => (
                  <tr key={org.id} className="hover:bg-slate-50 transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center text-purple-600 shrink-0">
                          <Building2 className="h-5 w-5" />
                        </div>
                        <div className="font-semibold text-slate-700">{org.name}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-500 font-mono text-xs">{org.slug}</td>
                    <td className="px-6 py-4">
                      <button 
                        onClick={() => handleToggleBatterySave(org.id, org.ai_battery_save_mode)}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors border ${
                          org.ai_battery_save_mode 
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}
                      >
                        {org.ai_battery_save_mode ? <ZapOff className="h-3 w-3" /> : <Zap className="h-3 w-3" />}
                        {org.ai_battery_save_mode ? 'Battery Save' : 'Full Power'}
                      </button>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center justify-center bg-slate-100 text-slate-600 h-6 px-2.5 rounded-full font-medium text-xs">
                        {t('adminOrgs.membersCount', { count: org.member_count })}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {org.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                          {t('status.active')}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
                          {t('status.inactive')}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(org.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-end">
                      <button className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors">
                        <MoreVertical className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h3 className="font-semibold text-lg text-slate-800">{t('adminOrgs.modal.title')}</h3>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:bg-slate-100 hover:text-slate-600 p-1 rounded-md transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreate} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">{t('adminOrgs.modal.nameLabel')}</label>
                <input 
                  type="text" 
                  required
                  value={formData.organization_name}
                  onChange={e => setFormData({...formData, organization_name: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                  placeholder={t('adminOrgs.modal.namePlaceholder')}
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">{t('adminOrgs.modal.adminSection')}</p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">{t('adminOrgs.modal.adminNameLabel')}</label>
                    <input 
                      type="text" 
                      required
                      value={formData.admin_name}
                      onChange={e => setFormData({...formData, admin_name: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder={t('adminOrgs.modal.adminNamePlaceholder')}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">{t('adminOrgs.modal.emailLabel')}</label>
                    <input 
                      type="email" 
                      required
                      value={formData.admin_email}
                      onChange={e => setFormData({...formData, admin_email: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder={t('adminOrgs.modal.emailPlaceholder')}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">{t('adminOrgs.modal.passwordLabel')}</label>
                    <input 
                      type="text" 
                      value={formData.password}
                      onChange={e => setFormData({...formData, password: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder={t('adminOrgs.modal.passwordPlaceholder')}
                    />
                  </div>
                </div>
              </div>

              <div className="pt-4 flex justify-end gap-2">
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                >
                  {t('adminOrgs.modal.cancel')}
                </button>
                <button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                  {isSubmitting ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> {t('adminOrgs.modal.provisioning')}</>
                  ) : t('adminOrgs.modal.provision')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
