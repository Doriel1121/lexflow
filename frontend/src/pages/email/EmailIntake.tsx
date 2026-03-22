/**
 * pages/email/EmailIntake.tsx  —  REDESIGNED: AI Intake Center
 * ==============================================================
 * Transforms the old inbox UI into a processing queue.
 * EmailClient.tsx is no longer rendered directly — this page takes over.
 */
import { useEffect, useState, useCallback } from 'react';
import {
  Inbox, RefreshCw, Mail, Link2, AlertTriangle,
  CheckCircle2, Clock, Zap, Settings,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  intakeService, IntakeItem, IntakeSummary, IntakeStatus,
} from '../../services/intakeService';
import { IntakeItemRow } from '../../components/intake/IntakeItemRow';
import { IntakeDetailPanel } from '../../components/intake/IntakeDetailPanel';
import { useSnackbar } from '../../context/SnackbarContext';
import api from '../../services/api';

// ─── Tab config ──────────────────────────────────────────────────────────────

const TABS: { key: IntakeStatus | 'all'; label: string; icon: React.ElementType; summaryKey?: keyof IntakeSummary }[] = [
  { key: 'all',            label: 'All',             icon: Inbox },
  { key: 'needs_review',    label: 'Needs Review',    icon: Clock,         summaryKey: 'needs_review' },
  { key: 'requires_action', label: 'Requires Action', icon: AlertTriangle, summaryKey: 'requires_action' },
  { key: 'auto_processed',  label: 'Auto Processed',  icon: Zap,           summaryKey: 'auto_processed' },
  { key: 'completed',       label: 'Completed',       icon: CheckCircle2,  summaryKey: 'completed' },
];

// ─── Empty state ─────────────────────────────────────────────────────────────

function EmptyState({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
      <div className="h-20 w-20 rounded-2xl bg-indigo-100 flex items-center justify-center mb-6">
        <Zap className="h-10 w-10 text-indigo-500" />
      </div>
      <h3 className="text-xl font-semibold text-slate-800 mb-2">No intake items yet</h3>
      <p className="text-slate-500 text-sm max-w-sm leading-relaxed mb-8">
        Connect your email and AI will automatically convert incoming legal correspondence
        into structured, actionable intake items — with deadlines, case suggestions, and priority scoring.
      </p>
      <div className="flex flex-col gap-3 w-full max-w-xs">
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-xl transition-colors"
        >
          <Link2 className="h-4 w-4" />
          Connect Email
        </button>
        <button
          onClick={onConnect}
          className="flex items-center justify-center gap-2 px-5 py-3 border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium rounded-xl transition-colors text-sm"
        >
          <Settings className="h-4 w-4" />
          Configure Inbound Address
        </button>
      </div>
      <p className="mt-6 text-xs text-slate-400 max-w-xs">
        AI processes each attachment through OCR → classification → deadline extraction → case matching
      </p>
    </div>
  );
}

// ─── Summary bar ─────────────────────────────────────────────────────────────

function SummaryBar({ summary }: { summary: IntakeSummary }) {
  return (
    <div className="flex items-center gap-4 px-5 py-3 bg-white border-b border-slate-200 text-sm shrink-0 flex-wrap">
      <span className="flex items-center gap-1.5 font-medium text-slate-700">
        <Inbox className="h-4 w-4 text-slate-400" />
        <strong className="text-slate-900">{summary.total}</strong> total
      </span>
      {summary.urgent > 0 && (
        <span className="flex items-center gap-1 font-semibold text-red-600">
          🔴 <strong>{summary.urgent}</strong> urgent
        </span>
      )}
      {summary.requires_action > 0 && (
        <span className="flex items-center gap-1 font-semibold text-orange-600">
          🟠 <strong>{summary.requires_action}</strong> require action
        </span>
      )}
      {summary.needs_review > 0 && (
        <span className="text-slate-500">
          📋 <strong>{summary.needs_review}</strong> needs review
        </span>
      )}
      {summary.completed > 0 && (
        <span className="flex items-center gap-1 text-emerald-600">
          🟢 <strong>{summary.completed}</strong> completed
        </span>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function EmailIntake() {
  const { showSnackbar } = useSnackbar();
  const [items, setItems]         = useState<IntakeItem[]>([]);
  const [summary, setSummary]     = useState<IntakeSummary | null>(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<IntakeStatus | 'all'>('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [hasEmailConfig, setHasEmailConfig] = useState(true);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const res = await intakeService.list(
        activeTab === 'all' ? undefined : activeTab,
      );
      setItems(res.items);
      setSummary(res.summary);
      // Check if user has any email config
      if (res.summary.total === 0) {
        const configRes = await api.get('/v1/email/').catch(() => ({ data: [] }));
        setHasEmailConfig(Array.isArray(configRes.data) && configRes.data.length > 0);
      }
    } catch {
      showSnackbar('Failed to load intake items', { type: 'error' });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 30s to pick up newly processed items
  useEffect(() => {
    const interval = setInterval(() => load(true), 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const handleQuickApprove = async (item: IntakeItem) => {
    if (!item.suggested_case) return;
    try {
      await intakeService.confirm(item.id, {
        case_id: item.suggested_case.case_id,
        confirm_deadlines: true,
      });
      showSnackbar(`Linked to: ${item.suggested_case.case_title}`, { type: 'success' });
      load(true);
      if (selectedId === item.id) setSelectedId(null);
    } catch {
      showSnackbar('Failed to approve item', { type: 'error' });
    }
  };

  const handleConfirmed = () => {
    setSelectedId(null);
    load(true);
  };

  const handleConnectEmail = () => {
    // Navigate to email settings — reuse existing email config page
    window.location.href = '/settings';
  };

  const showEmpty = !loading && items.length === 0;

  return (
    <div className="h-full flex flex-col -mx-8 -my-6">
      {/* Page header */}
      <div className="px-8 py-5 border-b border-slate-200 bg-white shrink-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-serif font-bold text-slate-800 tracking-tight flex items-center gap-2">
              <Zap className="h-6 w-6 text-indigo-500" />
              AI Intake Center
            </h1>
            <p className="text-slate-500 text-sm mt-0.5">
              Emails → AI processing → structured actionable items
            </p>
          </div>
          <button
            onClick={() => load(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary bar */}
      {summary && summary.total > 0 && <SummaryBar summary={summary} />}

      {/* Status tabs */}
      <div className="flex gap-1 px-5 py-2 border-b border-slate-200 bg-white shrink-0 overflow-x-auto">
        {TABS.map(tab => {
          const count = tab.summaryKey && summary ? summary[tab.summaryKey] : null;
          const Icon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setSelectedId(null); }}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors',
                activeTab === tab.key
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-slate-500 hover:bg-slate-100 hover:text-slate-700',
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {tab.label}
              {count !== null && count > 0 && (
                <span className={cn(
                  'text-[10px] font-bold px-1.5 py-0.5 rounded-full',
                  activeTab === tab.key ? 'bg-indigo-200 text-indigo-700' : 'bg-slate-200 text-slate-600',
                )}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Main content: list + detail split */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left: Intake item list */}
        <div className={cn(
          'border-r border-slate-200 flex flex-col bg-white overflow-hidden',
          selectedId ? 'w-80 shrink-0' : 'flex-1',
        )}>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center h-48">
                <Loader className="h-8 w-8 text-indigo-400 animate-spin" />
              </div>
            ) : showEmpty ? (
              <EmptyState onConnect={handleConnectEmail} />
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-slate-400">
                <CheckCircle2 className="h-10 w-10 mb-3 text-emerald-400" />
                <p className="text-sm font-medium">All clear in this category</p>
              </div>
            ) : (
              items.map(item => (
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

        {/* Right: Detail panel */}
        {selectedId && (
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            <IntakeDetailPanel
              itemId={selectedId}
              onConfirmed={handleConfirmed}
              onDismissed={() => { setSelectedId(null); load(true); }}
            />
          </div>
        )}

        {/* Placeholder when nothing selected */}
        {!selectedId && !showEmpty && !loading && items.length > 0 && (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-400 bg-slate-50">
            <Mail className="h-12 w-12 mb-4 text-slate-300" />
            <p className="text-sm font-medium text-slate-500">Select an intake item to review</p>
            <p className="text-xs text-slate-400 mt-1">AI analysis and actions will appear here</p>
          </div>
        )}
      </div>
    </div>
  );
}

// tiny inline loader to avoid extra import
function Loader({ className }: { className?: string }) {
  return (
    <svg className={cn('animate-spin', className)} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
