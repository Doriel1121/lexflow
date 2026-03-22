/**
 * components/intake/IntakeDetailPanel.tsx
 * =========================================
 * Split-screen right panel: email content (left) + AI panel (right).
 * Includes full action panel: confirm case, assign lawyer, edit deadline.
 */
import { useState, useEffect } from 'react';
import {
  Briefcase, User, Clock, Tag, AlertTriangle, CheckCircle2,
  ChevronDown, Loader2, X, FileText, Zap, CalendarCheck,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { PriorityBadge } from './PriorityBadge';
import {
  intakeService,
  IntakeItemDetail,
  ConfirmIntakeRequest,
  SuggestedCase,
} from '../../services/intakeService';
import api from '../../services/api';
import { useSnackbar } from '../../context/SnackbarContext';

interface Props {
  itemId: number;
  onConfirmed: () => void;
  onDismissed: () => void;
}

interface Case { id: number; title: string; status: string; }

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h4 className="flex items-center gap-1.5 text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </h4>
      {children}
    </div>
  );
}

function ConfidencePill({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-400';
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-500 tabular-nums">{pct}%</span>
    </div>
  );
}

export function IntakeDetailPanel({ itemId, onConfirmed, onDismissed }: Props) {
  const { showSnackbar } = useSnackbar();
  const [detail, setDetail] = useState<IntakeItemDetail | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Action form state
  const [selectedCaseId, setSelectedCaseId] = useState<number | ''>('');
  const [selectedLawyerId, setSelectedLawyerId] = useState<number | ''>('');
  const [confirmDeadlines, setConfirmDeadlines] = useState(true);
  const [activeTab, setActiveTab] = useState<'email' | 'ai'>('ai');

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    Promise.all([
      intakeService.getDetail(itemId),
      api.get('/v1/cases').then(r => r.data as Case[]),
    ]).then(([d, c]) => {
      setDetail(d);
      setCases(c);
      // Pre-fill suggested case
      if (d.suggested_case) setSelectedCaseId(d.suggested_case.case_id);
    }).catch(() => {
      showSnackbar('Failed to load intake details', { type: 'error' });
    }).finally(() => setLoading(false));
  }, [itemId]);

  const handleConfirm = async () => {
    if (!selectedCaseId) {
      showSnackbar('Please select a case first', { type: 'warning' });
      return;
    }
    setSubmitting(true);
    try {
      const body: ConfirmIntakeRequest = {
        case_id: Number(selectedCaseId),
        lawyer_id: selectedLawyerId ? Number(selectedLawyerId) : undefined,
        confirm_deadlines: confirmDeadlines,
      };
      await intakeService.confirm(itemId, body);
      showSnackbar('Intake item confirmed and linked to case', { type: 'success' });
      onConfirmed();
    } catch {
      showSnackbar('Failed to confirm intake item', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDismiss = async () => {
    setSubmitting(true);
    try {
      await intakeService.dismiss(itemId);
      showSnackbar('Item dismissed', { type: 'success' });
      onDismissed();
    } catch {
      showSnackbar('Failed to dismiss item', { type: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
      </div>
    );
  }

  if (!detail) return null;

  const isCompleted = detail.status === 'completed';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-semibold text-slate-800 text-sm leading-tight truncate">{detail.subject}</h3>
            <p className="text-xs text-slate-500 mt-0.5">{detail.from_address} · {detail.received_at ? new Date(detail.received_at).toLocaleString() : '—'}</p>
          </div>
          <PriorityBadge priority={detail.priority} />
        </div>
        {/* Tab switcher */}
        <div className="flex gap-1 mt-3">
          {(['ai', 'email'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors',
                activeTab === tab
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-slate-500 hover:bg-slate-100',
              )}
            >
              {tab === 'ai' ? '🤖 AI Analysis' : '✉️ Original Email'}
            </button>
          ))}
        </div>
      </div>

      {/* Body — scrollable */}
      <div className="flex-1 overflow-y-auto">
        {activeTab === 'email' ? (
          /* ── Email content pane ─────────────────────────────────── */
          <div className="p-5">
            <div className="text-xs text-slate-400 mb-3 font-medium uppercase tracking-wider">Original email content</div>
            <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap text-sm leading-relaxed">
              {detail.body_preview || 'No content available'}
            </div>
            <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg">
              <p className="text-xs text-slate-500">
                <span className="font-medium">Attachment:</span> {detail.filename}
              </p>
            </div>
          </div>
        ) : (
          /* ── AI Analysis pane ───────────────────────────────────── */
          <div className="p-5 space-y-1">

            {/* AI Summary */}
            {detail.ai.summary && (
              <Section title="AI Summary" icon={Zap}>
                <p className="text-sm text-slate-700 leading-relaxed bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                  {detail.ai.summary}
                </p>
              </Section>
            )}

            {/* Classification */}
            <Section title="Classification" icon={Tag}>
              <span className="inline-block px-2.5 py-1 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold">
                {detail.classification || 'Pending Analysis'}
              </span>
            </Section>

            {/* Deadlines */}
            {detail.ai.deadlines.length > 0 && (
              <Section title={`Deadlines (${detail.ai.deadlines.length})`} icon={CalendarCheck}>
                <div className="space-y-2">
                  {detail.ai.deadlines.map(d => (
                    <div key={d.id} className={cn(
                      'flex items-start justify-between p-2.5 rounded-lg border text-xs',
                      d.days_until <= 3 ? 'bg-red-50 border-red-200' :
                      d.days_until <= 7 ? 'bg-orange-50 border-orange-200' :
                      'bg-slate-50 border-slate-200',
                    )}>
                      <div>
                        <p className="font-semibold text-slate-800">{new Date(d.date).toLocaleDateString()}</p>
                        <p className="text-slate-600 mt-0.5">{d.description || d.type}</p>
                      </div>
                      <span className={cn(
                        'font-bold tabular-nums',
                        d.days_until <= 0 ? 'text-red-600' :
                        d.days_until <= 7 ? 'text-orange-600' : 'text-slate-500',
                      )}>
                        {d.days_until <= 0 ? 'OVERDUE' : `${d.days_until}d`}
                      </span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Entities */}
            {detail.ai.entities.length > 0 && (
              <Section title="Parties & Entities" icon={User}>
                <div className="space-y-1.5">
                  {detail.ai.entities.slice(0, 6).map((e, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg px-3 py-2">
                      <span className="font-medium text-slate-800">{e.name}</span>
                      {e.role && <span className="text-slate-500 text-[10px]">{e.role}</span>}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Suggested case */}
            {detail.suggested_case && (
              <Section title="Suggested Case" icon={Briefcase}>
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                  <p className="text-sm font-semibold text-emerald-800">#{detail.suggested_case.case_id} — {detail.suggested_case.case_title}</p>
                  <p className="text-xs text-emerald-600 mt-1">{detail.suggested_case.reason}</p>
                  <div className="mt-2">
                    <ConfidencePill score={detail.suggested_case.confidence === 'high' ? 0.9 : detail.suggested_case.confidence === 'medium' ? 0.6 : 0.35} />
                  </div>
                </div>
              </Section>
            )}

            {/* Financial amounts */}
            {detail.ai.amounts?.length > 0 && (
              <Section title="Financial Terms" icon={FileText}>
                <div className="space-y-1">
                  {detail.ai.amounts.slice(0, 4).map((a: any, i: number) => (
                    <div key={i} className="text-xs flex justify-between bg-slate-50 rounded px-2.5 py-1.5">
                      <span className="text-slate-600">{a.description || 'Amount'}</span>
                      <span className="font-semibold text-slate-800">{a.amount} {a.currency}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}
          </div>
        )}
      </div>

      {/* ── Action Panel ───────────────────────────────────────────── */}
      {!isCompleted && (
        <div className="border-t border-slate-200 p-5 bg-slate-50 space-y-4 shrink-0">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Actions</p>

          {/* Case selector */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
              Link to Case <span className="text-red-500">*</span>
            </label>
            <select
              value={selectedCaseId}
              onChange={e => setSelectedCaseId(e.target.value ? Number(e.target.value) : '')}
              className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400"
            >
              <option value="">— Select case —</option>
              {cases.map(c => (
                <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>
              ))}
            </select>
            {detail.suggested_case && (
              <button
                onClick={() => setSelectedCaseId(detail.suggested_case!.case_id)}
                className="mt-1 text-[11px] text-indigo-600 font-medium hover:underline"
              >
                Use suggested: #{detail.suggested_case.case_id} — {detail.suggested_case.case_title}
              </button>
            )}
          </div>

          {/* Lawyer selector */}
          {detail.available_lawyers.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Assign Lawyer (optional)</label>
              <select
                value={selectedLawyerId}
                onChange={e => setSelectedLawyerId(e.target.value ? Number(e.target.value) : '')}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400"
              >
                <option value="">— Unassigned —</option>
                {detail.available_lawyers.map(l => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Confirm deadlines toggle */}
          {detail.ai.deadlines.length > 0 && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmDeadlines}
                onChange={e => setConfirmDeadlines(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-xs text-slate-700 font-medium">
                Confirm {detail.ai.deadlines.length} extracted deadline(s) into case
              </span>
            </label>
          )}

          {/* Action buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={submitting || !selectedCaseId}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              Confirm & Link
            </button>
            <button
              onClick={handleDismiss}
              disabled={submitting}
              className="px-3 py-2.5 bg-white hover:bg-slate-100 border border-slate-200 text-slate-600 text-sm font-medium rounded-lg transition-colors"
              title="Dismiss item"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Completed state */}
      {isCompleted && (
        <div className="border-t border-slate-200 p-4 bg-emerald-50 shrink-0">
          <div className="flex items-center gap-2 text-emerald-700">
            <CheckCircle2 className="h-5 w-5" />
            <div>
              <p className="text-sm font-semibold">Linked to Case #{detail.case_id}</p>
              <p className="text-xs text-emerald-600 mt-0.5">This intake item has been processed</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
