import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock3,
  DollarSign,
  RefreshCcw,
  SlidersHorizontal,
  Zap,
} from "lucide-react";

import {
  adminService,
  AIUsageBreakdownRow,
  AIUsageResponse,
} from "../../../services/adminService";
import { cn } from "../../../lib/utils";

const DAY_OPTIONS = [1, 7, 30, 90];

function formatNumber(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString();
}

function formatUsd(value: number | null | undefined): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(Number(value || 0));
}

function formatLatency(value: number | null | undefined): string {
  const ms = Number(value || 0);
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms.toFixed(0)}ms`;
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
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-2 text-2xl font-bold text-slate-900 tabular-nums">
            {value}
          </p>
          {subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}
        </div>
        <div className={cn("h-10 w-10 rounded-lg flex items-center justify-center", toneClass)}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function AdminAIUsage() {
  const { t } = useTranslation();
  const [data, setData] = useState<AIUsageResponse | null>(null);
  const [days, setDays] = useState(7);
  const [provider, setProvider] = useState("");
  const [taskType, setTaskType] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUsage = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await adminService.getAIUsage({
        days,
        ...(provider ? { provider } : {}),
        ...(taskType ? { task_type: taskType } : {}),
        ...(status ? { status } : {}),
      });
      setData(result);
    } catch (err) {
      console.error("Failed to load AI usage", err);
      setError(t("adminAIUsage.loadError", { defaultValue: "Failed to load AI usage telemetry." }));
    } finally {
      setLoading(false);
    }
  }, [days, provider, taskType, status]);

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
  const rows: AIUsageBreakdownRow[] = data?.breakdown || [];
  const successRate = summary?.total_calls
    ? Math.round((summary.success_calls / summary.total_calls) * 100)
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
            {t("adminAIUsage.title", { defaultValue: "AI Usage" })}
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            {t("adminAIUsage.subtitle", {
              defaultValue:
                "Aggregated provider, task, latency, token, and estimated cost telemetry. No prompts or responses are stored.",
            })}
          </p>
        </div>
        <button
          onClick={loadUsage}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary-800 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-900 disabled:opacity-60"
        >
          <RefreshCcw className={cn("h-4 w-4", loading && "animate-spin")} />
          {t("common.refresh", { defaultValue: "Refresh" })}
        </button>
      </div>

      <div className="flex items-center gap-2 px-4 py-2.5 bg-blue-50 border border-blue-200 rounded-lg">
        <Bot className="h-4 w-4 text-blue-700 shrink-0" />
        <p className="text-xs text-blue-800 font-medium">
          {t("adminAIUsage.safetyBanner", {
            defaultValue:
              "This view is safe for system admins: it shows aggregate usage only, not tenant names, user data, document content, prompts, or outputs.",
          })}
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-4">
        <div className="flex items-center gap-2 mb-4 text-sm font-semibold text-slate-700">
          <SlidersHorizontal className="h-4 w-4 text-slate-400" />
          {t("common.filters", { defaultValue: "Filters" })}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <select
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            {DAY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t("adminAIUsage.lastDays", {
                  count: option,
                  defaultValue: `Last ${option} days`,
                })}
              </option>
            ))}
          </select>
          <select
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("adminAIUsage.allProviders", { defaultValue: "All providers" })}</option>
            {providers.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={taskType}
            onChange={(event) => setTaskType(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("adminAIUsage.allTasks", { defaultValue: "All tasks" })}</option>
            {taskTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          >
            <option value="">{t("adminAIUsage.allStatuses", { defaultValue: "All statuses" })}</option>
            <option value="success">{t("adminAIUsage.statusSuccess", { defaultValue: "Success" })}</option>
            <option value="error">{t("adminAIUsage.statusError", { defaultValue: "Error" })}</option>
            <option value="timeout">{t("adminAIUsage.statusTimeout", { defaultValue: "Timeout" })}</option>
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
        <StatCard
          label={t("adminAIUsage.totalCalls", { defaultValue: "Total calls" })}
          value={formatNumber(summary?.total_calls)}
          subtext={t("adminAIUsage.lastDays", {
            count: days,
            defaultValue: `Last ${days} days`,
          })}
          icon={Activity}
          tone="blue"
        />
        <StatCard
          label={t("adminAIUsage.successRate", { defaultValue: "Success rate" })}
          value={`${successRate}%`}
          subtext={t("adminAIUsage.successfulCalls", {
            count: summary?.success_calls || 0,
            defaultValue: `${formatNumber(summary?.success_calls)} successful calls`,
          })}
          icon={CheckCircle2}
          tone="emerald"
        />
        <StatCard
          label={t("adminAIUsage.errors", { defaultValue: "Errors" })}
          value={formatNumber(summary?.error_calls)}
          subtext={t("adminAIUsage.failedAICalls", { defaultValue: "Failed AI calls" })}
          icon={AlertTriangle}
          tone={summary?.error_calls ? "red" : "slate"}
        />
        <StatCard
          label={t("adminAIUsage.avgLatency", { defaultValue: "Avg latency" })}
          value={formatLatency(summary?.avg_latency_ms)}
          subtext={t("adminAIUsage.acrossMatchingCalls", { defaultValue: "Across matching calls" })}
          icon={Clock3}
          tone="violet"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label={t("adminAIUsage.estimatedInputTokens", { defaultValue: "Estimated input tokens" })}
          value={formatNumber(summary?.estimated_input_tokens)}
          icon={Zap}
          tone="slate"
        />
        <StatCard
          label={t("adminAIUsage.estimatedOutputTokens", { defaultValue: "Estimated output tokens" })}
          value={formatNumber(summary?.estimated_output_tokens)}
          icon={Zap}
          tone="slate"
        />
        <StatCard
          label={t("adminAIUsage.estimatedAICost", { defaultValue: "Estimated AI cost" })}
          value={formatUsd(summary?.estimated_total_cost_usd)}
          subtext={
            summary?.pricing_configured
              ? t("adminAIUsage.pricingConfigured", { defaultValue: "Based on configured model pricing" })
              : t("adminAIUsage.pricingNotConfigured", { defaultValue: "Pricing not configured" })
          }
          icon={DollarSign}
          tone={summary?.pricing_configured ? "emerald" : "slate"}
        />
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
              {t("adminAIUsage.breakdown", { defaultValue: "Breakdown" })}
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              {t("adminAIUsage.breakdownDesc", { defaultValue: "Grouped by task, provider, model, and status." })}
            </p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-start">
            <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
              <tr>
                <th className="px-5 py-3 text-start">{t("adminAIUsage.thTask", { defaultValue: "Task" })}</th>
                <th className="px-5 py-3 text-start">{t("adminAIUsage.thProvider", { defaultValue: "Provider" })}</th>
                <th className="px-5 py-3 text-start">{t("adminAIUsage.thModel", { defaultValue: "Model" })}</th>
                <th className="px-5 py-3 text-start">{t("adminAIUsage.thStatus", { defaultValue: "Status" })}</th>
                <th className="px-5 py-3 text-end">{t("adminAIUsage.thCalls", { defaultValue: "Calls" })}</th>
                <th className="px-5 py-3 text-end">{t("adminAIUsage.thAvgLatency", { defaultValue: "Avg latency" })}</th>
                <th className="px-5 py-3 text-end">{t("adminAIUsage.thInputTokens", { defaultValue: "Input tokens" })}</th>
                <th className="px-5 py-3 text-end">{t("adminAIUsage.thOutputTokens", { defaultValue: "Output tokens" })}</th>
                <th className="px-5 py-3 text-end">{t("adminAIUsage.thCost", { defaultValue: "Cost" })}</th>
                <th className="px-5 py-3 text-start">{t("adminAIUsage.thLastSeen", { defaultValue: "Last seen" })}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-slate-500">
                    <div className="flex flex-col items-center gap-3">
                      <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-primary-700 animate-spin" />
                      {t("adminAIUsage.loading", { defaultValue: "Loading AI usage…" })}
                    </div>
                  </td>
                </tr>
              )}
              {!loading && rows.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-6 py-12 text-center text-slate-400">
                    {t("adminAIUsage.noEvents", { defaultValue: "No AI usage events found for the selected filters." })}
                  </td>
                </tr>
              )}
              {!loading && rows.map((row) => (
                <tr key={`${row.task_type}-${row.provider}-${row.model}-${row.status}`} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-slate-700 whitespace-nowrap">{row.task_type}</td>
                  <td className="px-5 py-3">
                    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold", providerClasses(row.provider))}>
                      {row.provider}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-slate-600 max-w-[220px] truncate">{row.model || "—"}</td>
                  <td className="px-5 py-3">
                    <span className={cn("inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold", statusClasses(row.status))}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-end tabular-nums font-semibold text-slate-800">{formatNumber(row.calls)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatLatency(row.avg_latency_ms)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatNumber(row.estimated_input_tokens)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{formatNumber(row.estimated_output_tokens)}</td>
                  <td className="px-5 py-3 text-end tabular-nums text-slate-600">{row.pricing_configured ? formatUsd(row.estimated_total_cost_usd) : "—"}</td>
                  <td className="px-5 py-3 text-slate-500 whitespace-nowrap">
                    {row.last_seen_at ? new Date(row.last_seen_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
