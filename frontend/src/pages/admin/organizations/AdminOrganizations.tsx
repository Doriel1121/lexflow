import { useEffect, useState } from 'react';
import { Building2, Search, MoreVertical, Plus, X, Loader2 } from 'lucide-react';
import api from '../../../services/api';

interface Organization {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  member_count: number;
  created_at: string;
}

export default function AdminOrganizations() {
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Organizations</h1>
          <p className="text-muted-foreground mt-1">Manage tenant workspaces and subscriptions.</p>
        </div>
        <button 
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add Organization
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search organizations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Tenant Name</th>
                <th className="px-6 py-3">Slug</th>
                <th className="px-6 py-3">Members</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center justify-center">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-purple-600 animate-spin mb-4" />
                      Loading organizations...
                    </div>
                  </td>
                </tr>
              ) : filteredOrgs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    No organizations found matching your search.
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
                      <span className="inline-flex items-center justify-center bg-slate-100 text-slate-600 h-6 px-2.5 rounded-full font-medium text-xs">
                        {org.member_count} users
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {org.is_active ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500">
                      {new Date(org.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
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
              <h3 className="font-semibold text-lg text-slate-800">Manually Provision Organization</h3>
              <button 
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:bg-slate-100 hover:text-slate-600 p-1 rounded-md transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            
            <form onSubmit={handleCreate} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Company / Organization Name</label>
                <input 
                  type="text" 
                  required
                  value={formData.organization_name}
                  onChange={e => setFormData({...formData, organization_name: e.target.value})}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                  placeholder="Acme Legal Corp"
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Initial Admin Account</p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                    <input 
                      type="text" 
                      required
                      value={formData.admin_name}
                      onChange={e => setFormData({...formData, admin_name: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder="Jane Doe"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Email Address</label>
                    <input 
                      type="email" 
                      required
                      value={formData.admin_email}
                      onChange={e => setFormData({...formData, admin_email: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder="jane@acmelegal.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Password (Optional)</label>
                    <input 
                      type="text" 
                      value={formData.password}
                      onChange={e => setFormData({...formData, password: e.target.value})}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                      placeholder="Leave blank to auto-generate"
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
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={isSubmitting}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                  {isSubmitting ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Provisioning</>
                  ) : 'Provision Tenant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
