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

import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Building2, Plus, X, Loader2, Shield, Save, Search } from "lucide-react";
import { adminService, AdminOrganizationQuotaResponse, TenantStats } from "../../../services/adminService";
import { useSnackbar } from "../../../context/SnackbarContext";

export default function AdminOrganizations() {
  const { showSnackbar } = useSnackbar();
  const { t } = useTranslation();

  const [tenantStats, setTenantStats] = useState<TenantStats | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quotaOrgId, setQuotaOrgId] = useState("");
  const [quotaData, setQuotaData] = useState<AdminOrganizationQuotaResponse | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaSaving, setQuotaSaving] = useState(false);
  const [quotaForm, setQuotaForm] = useState({
    ai_daily_call_limit: "",
    ai_monthly_drafting_limit: "",
    ai_monthly_token_limit: "",
  });
  const [formData, setFormData] = useState({
    organization_name: "",
    admin_name: "",
    admin_email: "",
    password: "",
  });

  const loadStats = useCallback(async () => {
    try {
      const data = await adminService.getDashboard();
      setTenantStats(data.tenant_stats);
    } catch {
      // Non-critical — stats display degrades gracefully
    }
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const hydrateQuotaForm = (data: AdminOrganizationQuotaResponse) => {
    setQuotaForm({
      ai_daily_call_limit: data.ai_quotas.ai_daily_call_limit?.toString() ?? "",
      ai_monthly_drafting_limit: data.ai_quotas.ai_monthly_drafting_limit?.toString() ?? "",
      ai_monthly_token_limit: data.ai_quotas.ai_monthly_token_limit?.toString() ?? "",
    });
  };

  const parseQuotaValue = (value: string): number | null => {
    if (value.trim() === "") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const loadQuotaSettings = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const organizationId = Number(quotaOrgId);
    if (!Number.isInteger(organizationId) || organizationId <= 0) {
      showSnackbar("Enter a valid organization ID", { type: "error" });
      return;
    }

    setQuotaLoading(true);
    try {
      const data = await adminService.getOrganizationAIQuotas(organizationId);
      setQuotaData(data);
      hydrateQuotaForm(data);
    } catch (err: any) {
      setQuotaData(null);
      showSnackbar(err.response?.data?.detail ?? "Failed to load AI quota settings", { type: "error" });
    } finally {
      setQuotaLoading(false);
    }
  };

  const saveQuotaSettings = async () => {
    if (!quotaData) return;
    setQuotaSaving(true);
    try {
      const data = await adminService.updateOrganizationAIQuotas(quotaData.organization.id, {
        ai_daily_call_limit: parseQuotaValue(quotaForm.ai_daily_call_limit),
        ai_monthly_drafting_limit: parseQuotaValue(quotaForm.ai_monthly_drafting_limit),
        ai_monthly_token_limit: parseQuotaValue(quotaForm.ai_monthly_token_limit),
      });
      setQuotaData(data);
      hydrateQuotaForm(data);
      showSnackbar("AI quota settings updated", { type: "success" });
    } catch (err: any) {
      showSnackbar(err.response?.data?.detail ?? "Failed to update AI quota settings", { type: "error" });
    } finally {
      setQuotaSaving(false);
    }
  };

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
      setFormData({
        organization_name: "",
        admin_name: "",
        admin_email: "",
        password: "",
      });
      showSnackbar("Tenant provisioned successfully", { type: "success" });
      loadStats();
    } catch (err: any) {
      showSnackbar(err.response?.data?.detail ?? "Failed to provision tenant", {
        type: "error",
      });
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
            Provision new tenants · Aggregated stats only · No tenant
            identifiers displayed
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 bg-primary hover:bg-primary-800 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          <Plus className="h-4 w-4" />
          Provision Tenant
        </button>
      </div>

      {/* Aggregated stats (no names or IDs) */}
      {tenantStats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Tenants", value: tenantStats.total_tenants },
            { label: "Active Tenants", value: tenantStats.active_tenants },
            { label: "Inactive Tenants", value: tenantStats.inactive_tenants },
            {
              label: "New This Month",
              value: tenantStats.new_tenants_this_month,
            },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm"
            >
              <div className="p-2 bg-primary-50 rounded-lg w-fit mb-3">
                <Building2 className="h-5 w-5 text-primary-700" />
              </div>
              <p className="text-sm text-slate-500 font-medium">{label}</p>
              <h3 className="text-3xl font-bold text-slate-800 mt-1 tabular-nums">
                {value.toLocaleString()}
              </h3>
            </div>
          ))}
        </div>
      )}

      {/* AI quota support workflow */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
        <div className="flex items-start gap-3 mb-5">
          <div className="p-2 bg-blue-50 rounded-lg">
            <Shield className="h-5 w-5 text-blue-700" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-800">AI Quota Management</h2>
            <p className="text-sm text-slate-500 mt-1">
              Support workflow for a known tenant ID. This is intentionally not a tenant directory.
            </p>
          </div>
        </div>

        <form onSubmit={loadQuotaSettings} className="flex flex-col sm:flex-row gap-3 mb-5">
          <input
            type="number"
            min="1"
            value={quotaOrgId}
            onChange={(e) => setQuotaOrgId(e.target.value)}
            placeholder="Organization ID"
            className="w-full sm:max-w-xs px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
          />
          <button
            type="submit"
            disabled={quotaLoading}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-800 disabled:opacity-50 rounded-lg transition-colors"
          >
            {quotaLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Load Quotas
          </button>
        </form>

        {quotaData && (
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <div className="bg-slate-50 px-4 py-3 border-b border-slate-200">
              <p className="text-sm font-semibold text-slate-800">{quotaData.organization.name}</p>
              <p className="text-xs text-slate-500">ID {quotaData.organization.id} · {quotaData.organization.slug} · {quotaData.organization.is_active ? "Active" : "Inactive"}</p>
            </div>
            <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                ["Daily AI calls", "ai_daily_call_limit", "0 disables the limit"],
                ["Monthly drafts", "ai_monthly_drafting_limit", "0 disables the limit"],
                ["Monthly tokens", "ai_monthly_token_limit", "Blank means unlimited"],
              ].map(([label, key, helper]) => (
                <label key={key} className="block">
                  <span className="text-sm font-medium text-slate-700">{label}</span>
                  <input
                    type="number"
                    min="0"
                    value={quotaForm[key as keyof typeof quotaForm]}
                    onChange={(e) => setQuotaForm({ ...quotaForm, [key]: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
                  />
                  <span className="mt-1 block text-xs text-slate-400">{helper}</span>
                </label>
              ))}
            </div>
            <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button
                type="button"
                onClick={saveQuotaSettings}
                disabled={quotaSaving}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-800 disabled:opacity-50 rounded-lg transition-colors"
              >
                {quotaSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save Quotas
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Data boundary notice */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <div className="p-1.5 bg-amber-100 rounded-lg mt-0.5">
            <Building2 className="h-4 w-4 text-amber-600" />
          </div>
          <div>
            <h3 className="font-semibold text-amber-800 text-sm">
              Data Isolation Policy
            </h3>
            <p className="text-amber-700 text-sm mt-1 leading-relaxed">
              Individual tenant records (names, slugs, member lists) are not
              accessible from the system admin panel. This enforces multi-tenant
              data isolation. To manage a specific tenant's settings, use the
              Org Admin role within that organization.
            </p>
          </div>
        </div>
      </div>

      {/* Provision modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <h3 className="font-semibold text-lg text-slate-800">
                Provision New Tenant
              </h3>
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
                  {t("adminOrganizations.organizationName")}
                </label>
                <input
                  type="text"
                  required
                  value={formData.organization_name}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      organization_name: e.target.value,
                    })
                  }
                  placeholder={t(
                    "adminOrganizations.organizationNamePlaceholder",
                  )}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
                />
              </div>

              <div className="pt-2 border-t border-slate-100">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  First Admin User
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Full Name
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.admin_name}
                      onChange={(e) =>
                        setFormData({ ...formData, admin_name: e.target.value })
                      }
                      placeholder={t(
                        "adminOrganizations.primaryContactPlaceholder",
                      )}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      required
                      value={formData.admin_email}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          admin_email: e.target.value,
                        })
                      }
                      placeholder={t("adminOrganizations.emailPlaceholder")}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Password{" "}
                      <span className="text-slate-400 font-normal">
                        (leave blank to auto-generate)
                      </span>
                    </label>
                    <input
                      type="text"
                      value={formData.password}
                      onChange={(e) =>
                        setFormData({ ...formData, password: e.target.value })
                      }
                      placeholder={t("adminOrganizations.apiKeyPlaceholder")}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-700"
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
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-primary-800 disabled:opacity-50 rounded-lg transition-colors"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Provisioning…
                    </>
                  ) : (
                    "Provision Tenant"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
