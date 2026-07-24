import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  FileText,
  Gauge,
  RefreshCcw,
  SlidersHorizontal,
  Sparkles,
  Zap,
} from "lucide-react";

import type { AIQuotaBucket, AIUsageBreakdownRow, AIUsageResponse } from "../../../services/adminService";
import { orgAIUsageService } from "../../../services/orgAIUsageService";
import { useTranslation } from "react-i18next";
import { cn } from "../../../lib/utils";
import { formatDate } from "../../../lib/formatters";

const DAY_OPTIONS = [1, 7, 30, 90];

function formatNumber(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString();
}

function formatLatency(value: number | null | undefined): string {
  const ms = Number(value || 0);
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms.toFixed(0)}ms`;
}

function formatLimit(value: number | null | undefined, unlimitedLabel: string): string {
  if (value === null || value === undefined) return unlimitedLabel;
  return formatNumber(value);
}

function formatResetDate(value: string | null | undefined, noResetLabel: string): string {
  if (!value) return noResetLabel;
  return formatDate(value, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function quotaPercent(quota: AIQuotaBucket | undefined): number {
  if (!quota?.limit || quota.limit <= 0) return 0;
  return Math.min(100, Math.round((quota.used / quota.limit) * 100));
}

function quotaTone(percent: number): "slate" | "amber" | "red" | "emerald" {
  if (percent >= 100) return "red";
  if (percent >= 80) return "amber";
  if (percent > 0) return "emerald";
  return "slate";
}

function statusClasses(status: string): string {
  switch (status) {
    case "success":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "error":
      return "bg-red-50 text-red-700 border-red-200";
    case "timeout":
      return "bg-amber-50 text-amber-700 border-amber-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

function providerClasses(provider: string): string {
  switch (provider.toLowerCase()) {
    case "cohere":
      return "bg-violet-50 text-violet-700 border-violet-200";
    case "gemini":
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "openrouter":
      return "bg-cyan-50 text-cyan-700 border-cyan-200";
    case "ollama":
      return "bg-slate-900 text-white border-slate-900";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

function QuotaCard({
  title,
  description,
  quota,
  icon: Icon,
}: {
  title: string;
  description: string;
  quota?: AIQuotaBucket;
  icon: React.ElementType;
}) {
  const { t } = useTranslation();
  const percent = quotaPercent(quota);
  const tone = quotaTone(percent);
  const barClass = {
    slate: "bg-slate-300",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
  }[tone];
  const iconClass = {
    slate: "bg-slate-100 text-slate-600",
    emerald: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  }[tone];

  return (
    <div className={cn(
      "bg-white border rounded-xl p-5 shadow-sm",
      tone === "red" ? "border-red-200" : tone === "amber" ? "border-amber-200" : "border-slate-200",
    )}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-slate-800">{title}</p>
          <p className="mt-1 text-xs text-slate-500">{description}</p>
        </div>
        <div className={cn("h-10 w-10 rounded-lg flex items-center justify-center shrink-0", iconClass)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>

      <div className="mt-5 flex items-end justify-between gap-3">
        <div>
          <p className="text-2xl font-bold text-slate-900 tabular-nums">{formatNumber(quota?.used)}</p>
          <p className="text-xs text-slate-500">{t("orgAIUsage.usedOf", { limit: formatLimit(quota?.limit, t("orgAIUsage.unlimited")) })}</p>
        </div>
        <div className="text-end">
          <p className={cn("text-sm font-bold tabular-nums", tone === "red" ? "text-red-700" : tone === "amber" ? "text-amber-700" : "text-slate-700")}>
            {quota?.remaining === null || quota?.remaining === undefined ? t("orgAIUsage.unlimited") : t("orgAIUsage.remaining", { value: formatNumber(quota.remaining) })}
          </p>
          <p className="text-xs text-slate-500">{t("orgAIUsage.resets", { date: formatResetDate(quota?.reset_at, t("orgAIUsage.noResetDate")) })}</p>
        </div>
      </div>

      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={cn("h-full rounded-full transition-all", barClass)} style={{ width: `${percent}%` }} />
      </div>
      {quota?.limit ? <p className="mt-2 text-xs text-slate-500">{t("orgAIUsage.percentOfLimit", { percent })}</p> : <p className="mt-2 text-xs text-slate-500">{t("orgAIUsage.noLimitConfigured")}</p>}
    </div>
  );
}

function StatCard({
  label,
  value,
  subtext,
  icon: Icon,
  tone = "slate",
}: {
  label: string;
  value: string;
  subtext?: string;
  icon: React.ElementType;
  tone?: "slate" | "emerald" | "red" | "blue" | "violet";
}) {
  const toneClass = {
    slate: "bg-slate-100 text-slate-700",
    emerald: "bg-emerald-100 text-emerald-700",
    red: "bg-red-100 text-red-700",
    blue: "bg-blue-100 text-blue-700",
    violet: "bg-violet-100 text-violet-700",
  }[tone];

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
          {subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}
        </div>
        <div className={cn("h-10 w-10 rounded-lg flex items-center justify-center", toneClass)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function OrgAIUsage() {
  const { t } = useTranslation();
  const [data, setData] = useState<AIUsageResponse | null>(null);
  const [days, setDays] = useState(30);
  const [provider, setProvider] = useState("");
  const [taskType, setTaskType] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUsage = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await orgAIUsageService.getAIUsage({
        days,
        ...(provider ? { provider } : {}),
        ...(taskType ? { task_type: taskType } : {}),
        ...(status ? { status } : {}),
      });
      setData(result);
    } catch (err) {
      console.error("Failed to load organization AI usage", err);
      setError(t("orgAIUsage.loadError"));
    } finally {
      setLoading(false);
    }
  }, [days, provider, taskType, status, t]);

  useEffect(() => {
    loadUsage();
  }, [loadUsage]);

  const providers = useMemo(
    () => Array.from(new Set((data?.breakdown || []).map((row) => row.provider))).sort(),
    [data],
  );
  const taskTypes = useMemo(
    () => Array.from(new Set((data?.breakdown || []).map((row) => row.task_type))).sort(),
    [data],
  );

  const summary = data?.summary;
  const quota = data?.quota;
  const quotaWarnings = [
    { label: t("orgAIUsage.dailyCallsQuota"), quota: quota?.daily_ai_calls },
    { label: t("orgAIUsage.monthlyDraftsQuota"), quota: quota?.monthly_drafting_calls },
    { label: t("orgAIUsage.monthlyTokensQuota"), quota: quota?.monthly_ai_tokens },
  ].filter((item) => quotaPercent(item.quota) >= 80);
  const rows: AIUsageBreakdownRow[] = data?.breakdown || [];
  const successRate = summary?.total_calls
    ? Math.round((summary.success_calls / summary.total_calls) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">{t("orgAIUsage.title")}</h1>
          <p className="text-slate-500 mt-1 text-sm">
            {t("orgAIUsage.subtitle")}
          </p>
        </div>
        <button
          onClick={loadUsage}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-900 disabled:opacity-60"
        >
          <RefreshCcw className={cn("h-4 w-4", loading && "animate-spin")} />
          {t("orgAIUsage.refresh")}
        </button>
      </div>

      <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg">
        <Bot className="h-4 w-4 text-blue-700 shrink-0" />
        <p className="text-xs text-blue-800 font-medium">
          {t("orgAIUsage.privacyNotice")}
        </p>
      </div>

      {quotaWarnings.length > 0 && (
        <div className={cn(
          "flex items-start gap-3 px-4 py-3 border rounded-lg",
          quotaWarnings.some((item) => quotaPercent(item.quota) >= 100)
            ? "bg-red-50 border-red-200 text-red-800"
            : "bg-amber-50 border-amber-200 text-amber-800",
        )}>
          <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-bold">{t("orgAIUsage.quotaAttention")}</p>
            <p className="mt-1 text-xs">
              {quotaWarnings.map((item) => t("orgAIUsage.quotaWarningItem", { label: item.label, percent: quotaPercent(item.quota) })).join(" • ")}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <QuotaCard
          title={t("orgAIUsage.dailyCallsQuota")}
          description={t("orgAIUsage.dailyCallsDesc")}
          quota={quota?.daily_ai_calls}
          icon={Gauge}
        />
        <QuotaCard
          title={t("orgAIUsage.monthlyDraftsQuota")}
          description={t("orgAIUsage.monthlyDraftsDesc")}
          quota={quota?.monthly_drafting_calls}
          icon={FileText}
        />
        <QuotaCard
          title={t("orgAIUsage.monthlyTokensQuota")}
          description={t("orgAIUsage.monthlyTokensDesc")}
          quota={quota?.monthly_ai_tokens}
          icon={Sparkles}
        />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
        <div className="flex items-center gap-2 mb-4 text-sm font-semibold text-slate-700">
          <SlidersHorizontal className="h-4 w-4 text-slate-400" />
          {t("orgAIUsage.filters")}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <select
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            {DAY_OPTIONS.map((option) => (
              <option key={option} value={option}>{t("orgAIUsage.lastDays", { count: option })}</option>
            ))}
          </select>
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("orgAIUsage.allProviders")}</option>
            {providers.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select
            value={taskType}
            onChange={(event) => setTaskType(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("orgAIUsage.allTasks")}</option>
            {taskTypes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("orgAIUsage.allStatuses")}</option>
            <option value="success">{t("orgAIUsage.statusSuccess")}</option>
            <option value="error">{t("orgAIUsage.statusError")}</option>
            <option value="timeout">{t("orgAIUsage.statusTimeout")}</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label={t("orgAIUsage.totalCalls")} value={formatNumber(summary?.total_calls)} subtext={t("orgAIUsage.lastDays", { count: days })} icon={Activity} tone="blue" />
        <StatCard label={t("orgAIUsage.successRate")} value={`${successRate}%`} subtext={t("orgAIUsage.successfulCalls", { value: formatNumber(summary?.success_calls) })} icon={CheckCircle2} tone="emerald" />
        <StatCard label={t("orgAIUsage.errors")} value={formatNumber(summary?.error_calls)} subtext={t("orgAIUsage.failedAICalls")} icon={AlertTriangle} tone={summary?.error_calls ? "red" : "slate"} />
        <StatCard label={t("orgAIUsage.avgLatency")} value={formatLatency(summary?.avg_latency_ms)} subtext={t("orgAIUsage.acrossMatchingCalls")} icon={Clock3} tone="violet" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <StatCard label={t("orgAIUsage.estimatedInputTokens")} value={formatNumber(summary?.estimated_input_tokens)} icon={Zap} tone="slate" />
        <StatCard label={t("orgAIUsage.estimatedOutputTokens")} value={formatNumber(summary?.estimated_output_tokens)} icon={Zap} tone="slate" />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200">
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">{t("orgAIUsage.breakdown")}</h2>
          <p className="text-xs text-slate-500 mt-1">{t("orgAIUsage.breakdownDesc")}</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-start">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-5 py-3 text-start">{t("orgAIUsage.thTask")}</th>
                <th className="px-5 py-3 text-start">{t("orgAIUsage.thProvider")}</th>
                <th className="px-5 py-3 text-start">{t("orgAIUsage.thModel")}</th>
                <th className="px-5 py-3 text-start">{t("orgAIUsage.thStatus")}</th>
                <th className="px-5 py-3 text-end">{t("orgAIUsage.thCalls")}</th>
                <th className="px-5 py-3 text-end">{t("orgAIUsage.thAvgLatency")}</th>
                <th className="px-5 py-3 text-end">{t("orgAIUsage.thInputTokens")}</th>
                <th className="px-5 py-3 text-end">{t("orgAIUsage.thOutputTokens")}</th>
                <th className="px-5 py-3 text-start">{t("orgAIUsage.thLastSeen")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={9} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center gap-3">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-primary-700 animate-spin" />
                      {t("orgAIUsage.loading")}
                    </div>
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-6 py-12 text-center text-slate-400">
                    {t("orgAIUsage.noEvents")}
                  </td>
                </tr>
              )}
              {!loading && rows.map((row) => (
                <tr key={`${row.task_type}-${row.provider}-${row.model}-${row.status}`} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-slate-700 whitespace-nowrap">{row.task_type}</td>
                  <td className="px-5 py-3">
                    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold", providerClasses(row.provider))}>{row.provider}</span>
                  </td>
                  <td className="px-5 py-3 text-slate-600 max-w-[220px] truncate">{row.model || "—"}</td>
                  <td className="px-5 py-3">
                    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold", statusClasses(row.status))}>{t(`orgAIUsage.statuses.${row.status}`, { defaultValue: row.status })}</span>
                  </td>
                  <td className="px-5 py-3 text-end tabular-nums font-semibold text-slate-800">{formatNumber(row.calls)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatLatency(row.avg_latency_ms)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatNumber(row.estimated_input_tokens)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatNumber(row.estimated_output_tokens)}</td>
                  <td className="px-5 py-3 text-slate-500 whitespace-nowrap">{row.last_seen_at ? formatDate(row.last_seen_at, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
