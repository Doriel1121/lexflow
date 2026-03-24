/**
 * AdminOrganizations.tsx  —  REDESIGNED (v2)
 * ============================================
 * Previously: displayed a full table of all organizations with names,
 * slugs, member counts, and AI settings — a direct data isolation violation.
 *
 * Now:
 *   ✅ Provision new tenant (POST /admin/organizations) — legitimate write
 *   ✅ Show aggregated tenant stats (counts, not lists)
 *   ❌ No table of org names, slugs, or IDs
 *   ❌ No per-tenant member counts
 */

import { useEffect, useState, useCallback } from 'react';
import { Building2, Plus, X, Loader2 } from 'lucide-react';
import { adminService, TenantStats } from '../../../services/adminService';
import { useSnackbar } from '../../../context/SnackbarContext';

export default function AdminOrganizations() {
  const { showSnackbar } = useSnackbar();

  const [tenantStats, setTenantStats] = useState<TenantStats | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    organization_name: '',
    admin_name: '',
    admin_email: '',
    password: '',
  });

  const loadStats = useCallback(async () => {
    try {
      const data = await adminService.getDashboard();
      setTenantStats(data.tenant_stats);
    } catch {
      // Non-critical — stats display degrades gracefully
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await adminService.provisionOrganization({
        organization_name: formData.organization_name,
        admin_name: formData.admin_name,
        admin_email: formData.admin_email,
        password: formData.password || undefined,
      });
      setIsModalOpen(false);
      setFormData({ organization_name: '', admin_name: '', admin_email: '', password: '' });
      showSnackbar('Tenant provisioned successfully', { type: 'success' });
      loadStats();
    } catch (err: any) {
      showSnackbar(err.response?.data?.detail ?? 'Failed to provision tenant', { type: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            Tenant Management
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Provision new tenants · Aggregated stats only · No tenant identifiers displayed
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Provision Tenant
        </button>
      </div>

      {/* Aggregated stats (no names or IDs) */}
      {tenantStats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Tenants',      value: tenantStats.total_tenants },
            { label: 'Active Tenants',     value: tenantStats.active_tenants },
            { label: 'Inactive Tenants',   value: tenantStats.inactive_tenants },
            { label: 'New This Month',     value: tenantStats.new_tenants_this_month },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
              <div className="p-2 bg-purple-100 rounded-lg w-fit mb-3">
                <Building2 className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-sm text-slate-500 font-medium">{label}</p>
              <h3 className="text-3xl font-bold text-slate-800 mt-1 tabular-nums">
                {value.toLocaleString()}
              </h3>
            </div>
          ))}
        </div>
      )}

      {/* Data boundary notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <div className="p-1.5 bg-amber-100 rounded-lg mt-0.5">
            <Building2 className="h-4 w-4 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-amber-800 text-sm">Data Isolation Policy</h3>
            <p className="text-amber-700 text-sm mt-1 leading-relaxed">
              Individual tenant records (names, slugs, member lists) are not accessible
              from the system admin panel. This enforces multi-tenant data isolation.
              To manage a specific tenant's settings, use the Org Admin role
              within that organization.
            </p>
          </div>
        </div>
      </div>

      {/* Provision modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h3 className="font-semibold text-lg text-slate-800">Provision New Tenant</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 rounded-md transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Organization Name
                </label>
                <input
                  type="text"
                  required
                  value={formData.organization_name}
                  onChange={e => setFormData({ ...formData, organization_name: e.target.value })}
                  placeholder="e.g. Acme Law Firm"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  First Admin User
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                    <input
                      type="text"
                      required
                      value={formData.admin_name}
                      onChange={e => setFormData({ ...formData, admin_name: e.target.value })}
                      placeholder="e.g. Jane Smith"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                    <input
                      type="email"
                      required
                      value={formData.admin_email}
                      onChange={e => setFormData({ ...formData, admin_email: e.target.value })}
                      placeholder="admin@firm.com"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Password{' '}
                      <span className="text-slate-400 font-normal">(leave blank to auto-generate)</span>
                    </label>
                    <input
                      type="text"
                      value={formData.password}
                      onChange={e => setFormData({ ...formData, password: e.target.value })}
                      placeholder="Auto-generated if empty"
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500"
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
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded-lg transition-colors"
                >
                  {isSubmitting ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Provisioning…</>
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
