/**
 * pages/email/EmailIntake.tsx  —  AI Intake Center
 */
import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  RefreshCw,
  Mail,
  Zap,
  Inbox,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Link2,
  Settings,
  SlidersHorizontal,
  X,
  ArrowRight,
  FileCheck2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { cn } from "../../lib/utils";
import {
  intakeService,
  IntakeItem,
  IntakeSummary,
  IntakeStatus,
} from "../../services/intakeService";
import { IntakeItemRow } from "../../components/intake/IntakeItemRow";
import { IntakeDetailPanel } from "../../components/intake/IntakeDetailPanel";
import { useSnackbar } from "../../context/SnackbarContext";

const TABS: {
  key: IntakeStatus | "all";
  labelKey: string;
  descriptionKey: string;
  icon: React.ElementType;
  summaryKey?: keyof IntakeSummary;
}[] = [
  {
    key: "all",
    labelKey: "all",
    descriptionKey: "allDesc",
    icon: Inbox,
  },
  {
    key: "needs_review",
    labelKey: "needsReview",
    descriptionKey: "needsReviewDesc",
    icon: Clock,
    summaryKey: "needs_review",
  },
  {
    key: "requires_action",
    labelKey: "requiresAction",
    descriptionKey: "requiresActionDesc",
    icon: AlertTriangle,
    summaryKey: "requires_action",
  },
  {
    key: "auto_processed",
    labelKey: "autoProcessed",
    descriptionKey: "autoProcessedDesc",
    icon: Zap,
    summaryKey: "auto_processed",
  },
  {
    key: "completed",
    labelKey: "completed",
    descriptionKey: "completedDesc",
    icon: CheckCircle2,
    summaryKey: "completed",
  },
];

function getTabCount(
  summary: IntakeSummary | null,
  tab: (typeof TABS)[number],
): number {
  if (!summary) return 0;
  if (tab.key === "all") return summary.total;
  return tab.summaryKey ? summary[tab.summaryKey] : 0;
}

function EmptyState({ onConnect }: { onConnect: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
      <div className="h-16 w-16 rounded-2xl bg-primary-50 border border-primary-100 flex items-center justify-center mb-5">
        <Mail className="h-8 w-8 text-primary-700" />
      </div>
      <h3 className="text-lg font-bold text-slate-800 mb-2">
        {t("emailIntake.noItems")}
      </h3>
      <p className="text-slate-500 text-sm max-w-sm leading-relaxed mb-7">
        {t("emailIntake.connectEmail")}
      </p>
      <div className="flex flex-col gap-3 w-full max-w-xs">
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-primary-800 hover:bg-primary-900 text-white font-semibold rounded-lg transition-colors"
        >
          <Link2 className="h-4 w-4" />
          {t("emailIntake.connectEmailBtn")}
        </button>
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium rounded-lg transition-colors text-sm"
        >
          <Settings className="h-4 w-4" />
          {t("emailIntake.configureInbound")}
        </button>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  tone: "blue" | "orange" | "emerald" | "slate";
}) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700 border-blue-100",
    orange: "bg-orange-50 text-orange-700 border-orange-100",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    slate: "bg-slate-50 text-slate-700 border-slate-100",
  }[tone];

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
            {value}
          </p>
        </div>
        <div
          className={cn(
            "h-10 w-10 rounded-lg border flex items-center justify-center",
            toneClass,
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}

export default function EmailIntake() {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [summary, setSummary] = useState<IntakeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<IntakeStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(true);

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      else setRefreshing(true);
      try {
        const res = await intakeService.list(
          activeTab === "all" ? undefined : activeTab,
        );
        setItems(res.items);
        setSummary(res.summary);
      } catch {
        showSnackbar("Failed to load intake items", { type: "error" });
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [activeTab, showSnackbar],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const refreshTimer = setInterval(() => load(true), 30_000);
    return () => clearInterval(refreshTimer);
  }, [load]);

  const handleQuickApprove = async (item: IntakeItem) => {
    if (!item.suggested_case) return;
    try {
      await intakeService.confirm(item.id, {
        case_id: item.suggested_case.case_id,
        confirm_deadlines: true,
      });
      showSnackbar(`Linked to: ${item.suggested_case.case_title}`, {
        type: "success",
      });
      load(true);
      if (selectedId === item.id) {
        setSelectedId(null);
        setShowFilters(true);
      }
    } catch {
      showSnackbar("Failed to approve item", { type: "error" });
    }
  };

  const showEmpty = !loading && items.length === 0;
  const activeTabMeta = TABS.find((tab) => tab.key === activeTab) ?? TABS[0];
  const isReviewing = selectedId !== null;

  return (
    <div className="h-full flex flex-col gap-5">
      <header className="flex flex-col gap-5">
        <div className="flex flex-col xl:flex-row xl:items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-serif font-bold text-slate-800 tracking-tight">
              {t("emailIntake.title")}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {t("emailIntake.subtitle")}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="hidden md:flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-800">
              <Sparkles className="h-4 w-4 shrink-0" />
              {t("emailIntake.workflowHint")}
            </div>
            <button
              onClick={() => load(true)}
              disabled={refreshing}
              className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-sm disabled:opacity-60"
            >
              <RefreshCw
                className={cn("w-4 h-4", refreshing && "animate-spin")}
              />
              {t("emailIntake.refresh")}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          <MetricCard
            label={t("emailIntake.total")}
            value={summary?.total ?? 0}
            icon={Inbox}
            tone="slate"
          />
          <MetricCard
            label={t("emailIntake.needsReview")}
            value={summary?.needs_review ?? 0}
            icon={Clock}
            tone="blue"
          />
          <MetricCard
            label={t("emailIntake.requiresAction")}
            value={summary?.requires_action ?? 0}
            icon={AlertTriangle}
            tone="orange"
          />
          <MetricCard
            label={t("emailIntake.completed")}
            value={summary?.completed ?? 0}
            icon={ShieldCheck}
            tone="emerald"
          />
        </div>
      </header>

      <div
        className={cn(
          "min-h-0 flex-1 grid grid-cols-1 gap-4 transition-all",
          showFilters
            ? "xl:grid-cols-[260px_minmax(320px,380px)_1fr]"
            : isReviewing
              ? "xl:grid-cols-[minmax(280px,340px)_1fr]"
              : "xl:grid-cols-[minmax(340px,420px)_1fr]",
        )}
      >
        {showFilters && (
        <aside className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden xl:min-h-0">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t("emailIntake.queueStatus")}
            </p>
          </div>
          <nav className="p-2 space-y-1">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const count = getTabCount(summary, tab);
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => {
                    setActiveTab(tab.key);
                    setSelectedId(null);
                  }}
                  className={cn(
                    "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                    isActive
                      ? "border-primary-200 bg-primary-50 text-primary-900 shadow-sm"
                      : "border-transparent text-slate-600 hover:bg-slate-50",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <Icon
                        className={cn(
                          "mt-0.5 h-4 w-4 shrink-0",
                          isActive ? "text-primary-700" : "text-slate-400",
                        )}
                      />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">
                          {t(`emailIntake.${tab.labelKey}`)}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {t(`emailIntake.${tab.descriptionKey}`)}
                        </p>
                      </div>
                    </div>
                    <span
                      className={cn(
                        "text-xs font-bold px-2 py-0.5 rounded-full tabular-nums",
                        isActive
                          ? "bg-white text-primary-800"
                          : "bg-slate-100 text-slate-600",
                      )}
                    >
                      {count}
                    </span>
                  </div>
                </button>
              );
            })}
          </nav>
        </aside>
        )}

        <section className={cn(
          "rounded-xl border border-slate-200 bg-white shadow-sm flex flex-col min-h-[520px] xl:min-h-0 overflow-hidden",
          isReviewing && !showFilters && "xl:max-w-[340px]",
        )}>
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {!showFilters && (
                    <button
                      type="button"
                      onClick={() => setShowFilters(true)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <SlidersHorizontal className="h-3.5 w-3.5" />
                      Filters
                    </button>
                  )}
                  <h2 className="text-sm font-bold text-slate-800 truncate">
                    {t(`emailIntake.${activeTabMeta.labelKey}`)}
                  </h2>
                </div>
                <p className="mt-0.5 text-xs text-slate-500">
                  {t(`emailIntake.${activeTabMeta.descriptionKey}`)}
                </p>
              </div>
              {summary?.urgent ? (
                <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {summary.urgent} {t("emailIntake.urgent")}
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto py-3">
            {loading ? (
              <div className="flex items-center justify-center h-48">
                <Spinner className="h-8 w-8 text-primary-500" />
              </div>
            ) : showEmpty ? (
              <EmptyState
                onConnect={() => (window.location.href = "/settings")}
              />
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-slate-400">
                <CheckCircle2 className="h-10 w-10 mb-3 text-emerald-400" />
                <p className="text-sm font-medium">
                  {t("emailIntake.allClear")}
                </p>
              </div>
            ) : (
              items.map((item) => (
                <IntakeItemRow
                  key={item.id}
                  item={item}
                  isSelected={selectedId === item.id}
                  onSelect={(id) => {
                    setSelectedId(id);
                    setShowFilters(false);
                  }}
                  onQuickApprove={handleQuickApprove}
                />
              ))
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white shadow-sm relative overflow-hidden min-h-[620px] xl:min-h-0">
          {selectedId ? (
            <>
              <div className="absolute right-4 top-4 z-30 flex items-center gap-2">
                {!showFilters && (
                  <button
                    type="button"
                    onClick={() => setShowFilters(true)}
                    className="hidden xl:inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5" />
                    Show filters
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(null);
                    setShowFilters(true);
                  }}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                  Close
                </button>
              </div>
              <IntakeDetailPanel
              itemId={selectedId}
              onConfirmed={() => {
                setSelectedId(null);
                setShowFilters(true);
                load(true);
              }}
              onDismissed={() => {
                setSelectedId(null);
                setShowFilters(true);
                load(true);
              }}
              />
            </>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center bg-slate-50 px-8">
              <div className="h-16 w-16 rounded-2xl bg-white border border-slate-200 shadow-sm flex items-center justify-center mb-5">
                <FileCheck2 className="h-8 w-8 text-slate-400" />
              </div>
              <p className="text-base font-bold text-slate-700">
                {t("emailIntake.selectItem")}
              </p>
              <p className="text-sm text-slate-500 mt-2 max-w-sm">
                {t("emailIntake.analysisWillAppear")}
              </p>
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3 max-w-2xl w-full">
                {[
                  ["reviewStepInbox", Inbox],
                  ["reviewStepAi", Sparkles],
                  ["reviewStepRoute", ArrowRight],
                ].map(([key, Icon]) => {
                  const StepIcon = Icon as React.ElementType;
                  return (
                    <div
                      key={key as string}
                      className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-left"
                    >
                      <StepIcon className="h-4 w-4 text-primary-700 mb-2" />
                      <p className="text-xs font-semibold text-slate-700">
                        {t(`emailIntake.${key}`)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
