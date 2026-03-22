/**
 * components/intake/IntakeDetailPanel.tsx
 * =========================================
 * Shows ALL data returned by GET /v1/intake/{id}:
 *
 * LEFT COLUMN (7/12)
 *   • AI Summary
 *   • Classification + language chips
 *   • ALL deadlines (not just [0]) — sorted by urgency, with overdue/days badge
 *   • ALL extracted dates
 *   • ALL parties & entities — name, role, id_number, contact, firm
 *   • Financial amounts (if any)
 *   • Case numbers (if any)
 *
 * RIGHT COLUMN (5/12)
 *   • Suggested case card
 *   • Manual routing form (case selector + lawyer selector)
 *
 * FOOTER
 *   • Delete · Save Draft · Confirm & Route Document
 */
import { useState, useEffect } from 'react';
import {
  Loader2, CheckCircle2, AlertTriangle, Paperclip,
  Zap, Tag, Users, Calendar, Link2, ArrowRight, Trash2,
  Clock, DollarSign, Hash, Phone, Building2, BadgeCheck,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  intakeService, IntakeItemDetail, ConfirmIntakeRequest, DeadlineDetail,
} from '../../services/intakeService';
import api from '../../services/api';
import { useSnackbar } from '../../context/SnackbarContext';

interface Props {
  itemId: number;
  onConfirmed: () => void;
  onDismissed: () => void;
}
interface Case { id: number; title: string; status: string; }

// ── helpers ───────────────────────────────────────────────────────────────

function SectionHead({ icon: Icon, label, count }: {
  icon: React.ElementType; label: string; count?: number;
}) {
  return (
    <h3 className="font-bold text-gray-500 text-xs tracking-wider uppercase mb-3 flex items-center gap-1.5">
      <Icon className="w-4 h-4" />
      {label}
      {count !== undefined && count > 0 && (
        <span className="ml-1 bg-gray-100 text-gray-600 text-[10px] font-bold px-1.5 py-0.5 rounded-full">
          {count}
        </span>
      )}
    </h3>
  );
}

function Avatar({ initials, variant = 0 }: { initials: string; variant?: number }) {
  const palettes = [
    'bg-indigo-100 text-indigo-700',
    'bg-emerald-100 text-emerald-700',
    'bg-purple-100 text-purple-700',
    'bg-amber-100 text-amber-700',
  ];
  return (
    <div className={cn(
      'w-8 h-8 rounded-full font-bold text-xs flex items-center justify-center flex-shrink-0',
      palettes[variant % palettes.length],
    )}>
      {initials}
    </div>
  );
}

// ── Deadline row ──────────────────────────────────────────────────────────

function DeadlineRow({ d, first }: { d: DeadlineDetail; first?: boolean }) {
  const overdue  = d.days_until <= 0;
  const critical = d.days_until <= 3;
  const warning  = d.days_until <= 7;

  return (
    <div className={cn(
      'rounded-lg border p-3 relative overflow-hidden',
      overdue   ? 'bg-red-50 border-red-200' :
      critical  ? 'bg-orange-50 border-orange-200' :
      warning   ? 'bg-amber-50 border-amber-100' :
                  'bg-gray-50 border-gray-200',
    )}>
      {first && overdue && (
        <div className="absolute right-0 top-0 w-12 h-12 bg-red-100 rounded-bl-full -z-0" />
      )}
      <div className="relative z-10 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className={cn(
              'text-sm font-bold',
              overdue ? 'text-red-900' : critical ? 'text-orange-900' : 'text-gray-900',
            )}>
              {new Date(d.date).toLocaleDateString()}
            </span>
            {overdue && (
              <span className="bg-red-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider">
                Overdue
              </span>
            )}
          </div>
          <p className={cn(
            'text-xs',
            overdue ? 'text-red-700' : critical ? 'text-orange-700' : 'text-gray-600',
          )}>
            {d.description || d.type || 'Deadline'}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <span className={cn(
            'text-xs font-bold tabular-nums',
            overdue ? 'text-red-600' : critical ? 'text-orange-600' : warning ? 'text-amber-600' : 'text-gray-500',
          )}>
            {overdue ? `−${Math.abs(d.days_until)}d` : `+${d.days_until}d`}
          </span>
          {d.confidence != null && (
            <div className="mt-1 flex items-center gap-1 justify-end">
              <div className="w-12 h-1 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full', overdue ? 'bg-red-400' : 'bg-indigo-400')}
                  style={{ width: `${Math.round(d.confidence * 100)}%` }}
                />
              </div>
              <span className="text-[10px] text-gray-400">{Math.round(d.confidence * 100)}%</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────

export function IntakeDetailPanel({ itemId, onConfirmed, onDismissed }: Props) {
  const { showSnackbar } = useSnackbar();
  const [detail, setDetail]     = useState<IntakeItemDetail | null>(null);
  const [cases,  setCases]      = useState<Case[]>([]);
  const [loading, setLoading]   = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [activeTab, setActiveTab]   = useState<'ai' | 'email'>('ai');
  const [showAllDates, setShowAllDates]   = useState(false);
  const [showAllEntities, setShowAllEntities] = useState(false);

  const [selectedCaseId,   setSelectedCaseId]   = useState<number | ''>('');
  const [selectedLawyerId, setSelectedLawyerId] = useState<number | ''>('');
  const [confirmDeadlines, setConfirmDeadlines] = useState(true);

  useEffect(() => {
    setLoading(true);
    setDetail(null);
    setShowAllDates(false);
    setShowAllEntities(false);
    Promise.all([
      intakeService.getDetail(itemId),
      api.get('/v1/cases').then(r => r.data as Case[]),
    ]).then(([d, c]) => {
      setDetail(d);
      setCases(c);
      if (d.suggested_case) setSelectedCaseId(d.suggested_case.case_id);
    }).catch(() => {
      showSnackbar('Failed to load intake details', { type: 'error' });
    }).finally(() => setLoading(false));
  }, [itemId]);

  const handleConfirm = async () => {
    if (!selectedCaseId) { showSnackbar('Please select a case first', { type: 'warning' }); return; }
    setSubmitting(true);
    try {
      await intakeService.confirm(itemId, {
        case_id: Number(selectedCaseId),
        lawyer_id: selectedLawyerId ? Number(selectedLawyerId) : undefined,
        confirm_deadlines: confirmDeadlines,
      } as ConfirmIntakeRequest);
      showSnackbar('Intake item confirmed and linked to case', { type: 'success' });
      onConfirmed();
    } catch { showSnackbar('Failed to confirm intake item', { type: 'error' }); }
    finally { setSubmitting(false); }
  };

  const handleDismiss = async () => {
    setSubmitting(true);
    try {
      await intakeService.dismiss(itemId);
      showSnackbar('Item dismissed', { type: 'success' });
      onDismissed();
    } catch { showSnackbar('Failed to dismiss item', { type: 'error' }); }
    finally { setSubmitting(false); }
  };

  if (loading) return (
    <div className="flex-1 flex items-center justify-center">
      <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
    </div>
  );
  if (!detail) return null;

  const isCompleted = detail.status === 'completed';
  const ai = detail.ai;

  // sort deadlines: overdue first, then by days_until asc
  const sortedDeadlines = [...(ai.deadlines ?? [])].sort((a, b) => a.days_until - b.days_until);
  const hasOverdue = sortedDeadlines.some(d => d.days_until <= 0);

  // dates — cap at 4 unless expanded
  const allDates = ai.dates ?? [];
  const visibleDates = showAllDates ? allDates : allDates.slice(0, 4);

  // entities
  const allEntities = ai.entities ?? [];
  const visibleEntities = showAllEntities ? allEntities : allEntities.slice(0, 4);

  // financial amounts
  const amounts = ai.amounts ?? [];

  // case numbers
  const caseNumbers = ai.case_numbers ?? [];

  const priorityMap: Record<string, string> = {
    urgent: 'bg-red-100 text-red-700 border-red-200',
    high:   'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-amber-100 text-amber-700 border-amber-200',
    low:    'bg-slate-100 text-slate-500 border-slate-200',
  };

  return (
    <div className="flex flex-col h-full bg-slate-50">

      {/* ── Sticky header ───────────────────────────────────────────── */}
      <div className="bg-white px-8 py-5 border-b border-gray-200 shadow-sm shrink-0 z-10">
        <div className="flex justify-between items-start mb-3">
          <div className="min-w-0 flex-1 pr-4">
            <h2 className="text-xl font-bold text-gray-900 mb-1 leading-tight">
              {detail.subject}
            </h2>
            <div className="flex items-center flex-wrap gap-x-2 gap-y-1 text-sm text-gray-500">
              <span>{detail.from_address}</span>
              <span>·</span>
              <span>{detail.received_at ? new Date(detail.received_at).toLocaleString() : '—'}</span>
              {detail.filename && (
                <>
                  <span>·</span>
                  <span className="flex items-center gap-1">
                    <Paperclip className="w-3.5 h-3.5" />
                    {detail.filename}
                  </span>
                </>
              )}
              {/* deadline summary in header */}
              {sortedDeadlines.length > 0 && (
                <>
                  <span>·</span>
                  <span className={cn(
                    'flex items-center gap-1 font-medium',
                    hasOverdue ? 'text-red-600' : 'text-orange-500',
                  )}>
                    <Clock className="w-3.5 h-3.5" />
                    {sortedDeadlines.length} deadline{sortedDeadlines.length > 1 ? 's' : ''}
                    {hasOverdue && ' — overdue'}
                  </span>
                </>
              )}
            </div>
          </div>
          <span className={cn(
            'inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-bold border shadow-sm shrink-0',
            priorityMap[detail.priority] ?? priorityMap.low,
          )}>
            {detail.priority === 'urgent' && <AlertTriangle className="w-3.5 h-3.5" />}
            {detail.priority.charAt(0).toUpperCase() + detail.priority.slice(1)}
          </span>
        </div>

        <div className="flex gap-2">
          {(['ai', 'email'] as const).map(t => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              className={cn(
                'px-4 py-1.5 rounded-md text-sm font-semibold flex items-center gap-2 transition-colors',
                activeTab === t
                  ? 'bg-indigo-50 border border-indigo-200 text-indigo-700'
                  : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50',
              )}
            >
              {t === 'ai' ? <><Zap className="w-4 h-4" /> AI Analysis</> : <><Paperclip className="w-4 h-4" /> Original Email</>}
            </button>
          ))}
        </div>
      </div>

      {/* ── Scrollable body ─────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-8 py-6 pb-24">

        {activeTab === 'email' ? (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="text-xs text-gray-400 uppercase tracking-wider font-medium mb-4">Original email content</div>
            <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {detail.body_preview || 'No content available'}
            </div>
            {detail.filename && (
              <div className="mt-5 pt-4 border-t border-gray-100">
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200 w-fit">
                  <Paperclip className="w-4 h-4 text-gray-400" />
                  <span className="text-sm text-gray-600 font-medium">{detail.filename}</span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">

            {/* ── LEFT COL (7/12) ─────────────────────────────────── */}
            <div className="xl:col-span-7 space-y-5">

              {/* AI Summary */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="bg-indigo-50/50 px-5 py-3 border-b border-gray-100 flex items-center gap-2">
                  <Zap className="w-5 h-5 text-indigo-500" />
                  <h3 className="font-bold text-gray-800 text-sm tracking-wide uppercase">AI Summary</h3>
                </div>
                <div className="p-5" dir={/[\u0590-\u05FF]/.test(ai.summary || '') ? 'rtl' : 'ltr'}>
                  {ai.summary ? (
                    <p className="text-gray-700 text-[15px] leading-relaxed">{ai.summary}</p>
                  ) : (
                    <p className="text-gray-400 italic text-sm">AI summary not yet available</p>
                  )}
                </div>
              </div>

              {/* Classification + Language */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                <SectionHead icon={Tag} label="Classification" />
                <div className="flex flex-wrap gap-2">
                  {detail.classification && detail.classification !== 'Pending Analysis' ? (
                    <>
                      <span className="px-3 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-full text-sm font-medium">
                        {detail.classification}
                      </span>
                      {detail.language && (
                        <span className="px-3 py-1 bg-gray-100 text-gray-700 border border-gray-200 rounded-full text-sm font-medium uppercase">
                          {detail.language}
                        </span>
                      )}
                      {caseNumbers.length > 0 && caseNumbers.map((cn, i) => (
                        <span key={i} className="px-3 py-1 bg-purple-50 text-purple-700 border border-purple-200 rounded-full text-sm font-medium flex items-center gap-1">
                          <Hash className="w-3 h-3" />{cn}
                        </span>
                      ))}
                    </>
                  ) : (
                    <span className="text-sm text-gray-400 italic">Pending analysis</span>
                  )}
                </div>
              </div>

              {/* ALL Deadlines */}
              {sortedDeadlines.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <div className="flex items-center justify-between mb-3">
                    <SectionHead icon={Calendar} label="Deadlines" count={sortedDeadlines.length} />
                    <label className="flex items-center gap-2 text-xs text-gray-600 font-medium cursor-pointer">
                      <input
                        type="checkbox"
                        checked={confirmDeadlines}
                        onChange={e => setConfirmDeadlines(e.target.checked)}
                        className="w-3.5 h-3.5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                      />
                      Confirm all to case
                    </label>
                  </div>
                  <div className="space-y-2">
                    {sortedDeadlines.map((d, i) => (
                      <DeadlineRow key={d.id} d={d} first={i === 0} />
                    ))}
                  </div>
                </div>
              )}

              {/* ALL Extracted Dates */}
              {allDates.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <SectionHead icon={Clock} label="Extracted Dates" count={allDates.length} />
                  <div className="divide-y divide-gray-50">
                    {visibleDates.map((d: any, i: number) => (
                      <div key={i} className="flex justify-between items-center py-2 text-sm">
                        <span className="text-gray-500 truncate pr-3">{d.description || d.type || 'Date'}</span>
                        <div className="shrink-0 flex items-center gap-2">
                          {d.is_critical_deadline && (
                            <BadgeCheck className="w-3.5 h-3.5 text-red-500" title="Critical deadline" />
                          )}
                          <span className="font-medium text-gray-900">{d.date}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {allDates.length > 4 && (
                    <button
                      onClick={() => setShowAllDates(v => !v)}
                      className="mt-2 text-xs text-indigo-600 font-medium hover:underline"
                    >
                      {showAllDates ? 'Show less' : `+${allDates.length - 4} more dates`}
                    </button>
                  )}
                </div>
              )}

              {/* ALL Parties & Entities */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                <SectionHead icon={Users} label="Parties & Entities" count={allEntities.length} />
                {allEntities.length > 0 ? (
                  <>
                    <div className="space-y-2">
                      {visibleEntities.map((e, i) => {
                        const initials = (e.name || '??').split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2);
                        return (
                          <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50/50 hover:bg-gray-50 transition-colors">
                            <Avatar initials={initials} variant={i} />
                            <div className="flex-1 min-w-0 grid grid-cols-2 gap-x-4 gap-y-0.5">
                              <div className="col-span-2 flex items-center justify-between">
                                <p className="text-sm font-bold text-gray-900 truncate">{e.name}</p>
                                {e.role && (
                                  <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-[10px] font-semibold uppercase tracking-wide shrink-0 ml-2">
                                    {e.role}
                                  </span>
                                )}
                              </div>
                              {e.id_number && (
                                <span className="text-xs text-gray-500 flex items-center gap-1">
                                  <Hash className="w-3 h-3" />{e.id_number}
                                </span>
                              )}
                              {e.contact && (
                                <span className="text-xs text-gray-500 flex items-center gap-1 truncate">
                                  <Phone className="w-3 h-3 shrink-0" />{e.contact}
                                </span>
                              )}
                              {e.firm && (
                                <span className="text-xs text-gray-500 flex items-center gap-1 col-span-2 truncate">
                                  <Building2 className="w-3 h-3 shrink-0" />{e.firm}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {allEntities.length > 4 && (
                      <button
                        onClick={() => setShowAllEntities(v => !v)}
                        className="mt-2 text-xs text-indigo-600 font-medium hover:underline"
                      >
                        {showAllEntities ? 'Show less' : `+${allEntities.length - 4} more parties`}
                      </button>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-gray-400 italic">No entities detected</p>
                )}
              </div>

              {/* Financial Amounts */}
              {amounts.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <SectionHead icon={DollarSign} label="Financial Terms" count={amounts.length} />
                  <div className="divide-y divide-gray-50">
                    {amounts.map((a: any, i: number) => (
                      <div key={i} className="flex items-center justify-between py-2 gap-3">
                        <div className="min-w-0">
                          <p className="text-sm text-gray-700 truncate">{a.description || 'Amount'}</p>
                          {(a.payer || a.payee) && (
                            <p className="text-xs text-gray-400 mt-0.5 truncate">
                              {a.payer && `From: ${a.payer}`}
                              {a.payer && a.payee && ' → '}
                              {a.payee && `To: ${a.payee}`}
                            </p>
                          )}
                        </div>
                        <span className="font-bold text-gray-900 shrink-0 tabular-nums">
                          {a.amount} {a.currency}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            </div>

            {/* ── RIGHT COL (5/12) ────────────────────────────────── */}
            <div className="xl:col-span-5 space-y-5">

              {/* Suggested Case */}
              {detail.suggested_case ? (
                <div className="bg-emerald-50 rounded-xl border border-emerald-200 shadow-sm p-5">
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="font-bold text-emerald-800 text-sm tracking-wide uppercase flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      Suggested Case
                    </h3>
                    <span className="bg-emerald-200 text-emerald-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">
                      {detail.suggested_case.confidence} match
                    </span>
                  </div>
                  <div className="bg-white rounded-lg border border-emerald-100 p-3 mb-3">
                    <h4 className="font-bold text-gray-900">
                      #{detail.suggested_case.case_id} — {detail.suggested_case.case_title}
                    </h4>
                    <p className="text-xs text-gray-500 mt-1">{detail.suggested_case.reason}</p>
                  </div>
                  <button
                    onClick={() => setSelectedCaseId(detail.suggested_case!.case_id)}
                    className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm flex justify-center items-center gap-2"
                  >
                    <Link2 className="w-4 h-4" />
                    Use this suggestion
                  </button>
                </div>
              ) : (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <SectionHead icon={Link2} label="Suggested Case" />
                  <p className="text-sm text-gray-400 italic">No matching case found automatically</p>
                </div>
              )}

              {/* Routing form */}
              {!isCompleted && (
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                  <SectionHead icon={ArrowRight} label="Routing" />
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                        Link to Case <span className="text-red-500">*</span>
                      </label>
                      <select
                        value={selectedCaseId}
                        onChange={e => setSelectedCaseId(e.target.value ? Number(e.target.value) : '')}
                        className="w-full bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 p-2.5"
                      >
                        <option value="">— Select case —</option>
                        {cases.map(c => (
                          <option key={c.id} value={c.id}>#{c.id} — {c.title}</option>
                        ))}
                      </select>
                    </div>
                    {detail.available_lawyers.length > 0 && (
                      <div>
                        <label className="block text-xs font-semibold text-gray-700 mb-1.5">Assign Lawyer</label>
                        <select
                          value={selectedLawyerId}
                          onChange={e => setSelectedLawyerId(e.target.value ? Number(e.target.value) : '')}
                          className="w-full bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-indigo-500 focus:border-indigo-500 p-2.5"
                        >
                          <option value="">— Unassigned —</option>
                          {detail.available_lawyers.map(l => (
                            <option key={l.id} value={l.id}>{l.name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Completed state */}
              {isCompleted && (
                <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-5">
                  <div className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-5 w-5" />
                    <div>
                      <p className="font-semibold">Linked to Case #{detail.case_id}</p>
                      <p className="text-xs text-emerald-600 mt-0.5">This item has been processed</p>
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>
        )}
      </div>

      {/* ── Sticky footer ───────────────────────────────────────────── */}
      {!isCompleted && (
        <div className="absolute bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-8 py-4 flex justify-between items-center shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-20">
          <button
            onClick={handleDismiss}
            disabled={submitting}
            className="text-red-600 hover:bg-red-50 font-medium text-sm px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            <Trash2 className="w-4 h-4" />
            Delete Intake
          </button>
          <div className="flex gap-3">
            <button
              disabled={submitting}
              className="px-5 py-2.5 bg-white border border-gray-300 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors shadow-sm"
            >
              Save as Draft
            </button>
            <button
              onClick={handleConfirm}
              disabled={submitting || !selectedCaseId}
              className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm flex items-center gap-2"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
              Confirm &amp; Route Document
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
