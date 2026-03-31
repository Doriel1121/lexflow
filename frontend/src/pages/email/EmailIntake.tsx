/**
 * pages/email/EmailIntake.tsx  —  AI Intake Center
 * ==================================================
 * Layout matches the Angular reference:
 *  - Topbar with title, summary stats, refresh button
 *  - Left list (380px) with tab filters + item cards
 *  - Right detail panel (flex-1) with full AI analysis
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

// ── Tab definitions ───────────────────────────────────────────────────────

const TABS: {
  key: IntakeStatus | "all";
  label: string;
  icon: React.ElementType;
  summaryKey?: keyof IntakeSummary;
}[] = [
  { key: "all", label: "All", icon: Inbox },
  {
    key: "needs_review",
    label: "Needs Review",
    icon: Clock,
    summaryKey: "needs_review",
  },
  {
    key: "requires_action",
    label: "Requires Action",
    icon: AlertTriangle,
    summaryKey: "requires_action",
  },
  {
    key: "auto_processed",
    label: "Auto Processed",
    icon: Zap,
    summaryKey: "auto_processed",
  },
  {
    key: "completed",
    label: "Completed",
    icon: CheckCircle2,
    summaryKey: "completed",
  },
];

// ── Empty state ───────────────────────────────────────────────────────────

function EmptyState({ onConnect }: { onConnect: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
      <div className="h-20 w-20 rounded-2xl bg-indigo-100 flex items-center justify-center mb-6">
        <Zap className="h-10 w-10 text-indigo-500" />
      </div>
      <h3 className="text-lg font-bold text-gray-800 mb-2">
        {t("emailIntake.noItems")}
      </h3>
      <p className="text-gray-500 text-sm max-w-xs leading-relaxed mb-8">
        {t("emailIntake.connectEmail")}
      </p>
      <div className="flex flex-col gap-3 w-full max-w-xs">
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-colors"
        >
          <Link2 className="h-4 w-4" />
          {t("emailIntake.connectEmailBtn")}
        </button>
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 border border-gray-200 hover:bg-gray-50 text-gray-700 font-medium rounded-xl transition-colors text-sm"
        >
          <Settings className="h-4 w-4" />
          {t("emailIntake.configureInbound")}
        </button>
      </div>
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────

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

// ── Main page ─────────────────────────────────────────────────────────────

export default function EmailIntake() {
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [items, setItems] = useState<IntakeItem[]>([]);
  const [summary, setSummary] = useState<IntakeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<IntakeStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);

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
    [activeTab],
  );

  useEffect(() => {
    load();
  }, [load]);

  // auto-refresh every 30 s
  useEffect(() => {
    const t = setInterval(() => load(true), 30_000);
    return () => clearInterval(t);
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
      if (selectedId === item.id) setSelectedId(null);
    } catch {
      showSnackbar("Failed to approve item", { type: "error" });
    }
  };

  const showEmpty = !loading && items.length === 0;

  return (
    /* Stretch to full viewport height, no outer padding */
    <div className="h-full flex flex-col -mx-8 -my-6 bg-white">
      {/* ── Topbar ──────────────────────────────────────────────────── */}
      <header className="h-16 border-b border-gray-200 flex items-center justify-between px-6 shrink-0 bg-white z-10">
        {/* Left: icon + title + stats */}
        <div className="flex items-center gap-4">
          <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-800 leading-tight">
              {t("emailIntake.title")}
            </h1>
            <p className="text-xs text-gray-500">{t("emailIntake.subtitle")}</p>
          </div>
        </div>

        {/* Right: summary counters + refresh */}
        <div className="flex items-center gap-3">
          {summary && (
            <div className="flex items-center gap-4 mr-4 text-sm font-medium">
              <span className="text-gray-600">
                <strong className="text-gray-900">{summary.total}</strong>{" "}
                {t("emailIntake.total")}
              </span>
              {summary.urgent > 0 && (
                <span className="text-red-600 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-600 inline-block" />
                  {summary.urgent} {t("emailIntake.urgent")}
                </span>
              )}
              {summary.requires_action > 0 && (
                <span className="text-orange-500 flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" />
                  {summary.requires_action} {t("emailIntake.requireAction")}
                </span>
              )}
            </div>
          )}
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-sm"
          >
            <RefreshCw
              className={cn("w-4 h-4", refreshing && "animate-spin")}
            />
            {t("emailIntake.refresh")}
          </button>
        </div>
      </header>

      {/* ── Split pane ──────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {/* ── LEFT: Master list (380px fixed) ─────────────────────── */}
        <div className="w-[380px] shrink-0 border-r border-gray-200 bg-white flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
          {/* Tab strip */}
          <div className="px-4 pt-4 border-b border-gray-100 flex gap-1 overflow-x-auto">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const count =
                tab.summaryKey && summary ? summary[tab.summaryKey] : null;
              const isActive = activeTab === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => {
                    setActiveTab(tab.key);
                    setSelectedId(null);
                  }}
                  className={cn(
                    "pb-3 border-b-2 font-medium text-sm flex items-center gap-1.5 whitespace-nowrap px-2 transition-colors",
                    isActive
                      ? "border-indigo-600 text-indigo-600"
                      : "border-transparent text-gray-500 hover:text-gray-700",
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                  {count !== null && count > 0 && (
                    <span
                      className={cn(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded-full",
                        isActive
                          ? "bg-indigo-100 text-indigo-700"
                          : "bg-gray-100 text-gray-600",
                      )}
                    >
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Item list */}
          <div className="flex-1 overflow-y-auto pt-3">
            {loading ? (
              <div className="flex items-center justify-center h-48">
                <Spinner className="h-8 w-8 text-indigo-400" />
              </div>
            ) : showEmpty ? (
              <EmptyState
                onConnect={() => (window.location.href = "/settings")}
              />
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-gray-400">
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
                  onSelect={setSelectedId}
                  onQuickApprove={handleQuickApprove}
                />
              ))
            )}
          </div>
        </div>

        {/* ── RIGHT: Detail view ───────────────────────────────────── */}
        <div className="flex-1 relative overflow-hidden">
          {selectedId ? (
            <IntakeDetailPanel
              itemId={selectedId}
              onConfirmed={() => {
                setSelectedId(null);
                load(true);
              }}
              onDismissed={() => {
                setSelectedId(null);
                load(true);
              }}
            />
          ) : (
            <div className="flex-1 h-full flex flex-col items-center justify-center text-gray-400 bg-slate-50">
              <Mail className="h-12 w-12 mb-4 text-gray-300" />
              <p className="text-sm font-medium text-gray-500">
                {t("emailIntake.selectItem")}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {t("emailIntake.analysisWillAppear")}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
