/**
 * components/intake/IntakeItemRow.tsx
 * Styled after the Angular reference design — card with left accent bar,
 * status chips, AI insight line, deadline badge, and hover quick-approve.
 */
import { FileText, AlertTriangle, Clock, CheckCircle2, Loader2, Paperclip } from 'lucide-react';
import { cn } from '../../lib/utils';
import type { IntakeItem, IntakeStatus } from '../../services/intakeService';

// ── Priority accent colours (left border + dot) ───────────────────────────
const PRIORITY_BORDER: Record<string, string> = {
  urgent: 'border-l-red-500',
  high:   'border-l-orange-400',
  medium: 'border-l-amber-400',
  low:    'border-l-slate-300',
};

const PRIORITY_DOT: Record<string, string> = {
  urgent: 'bg-red-500',
  high:   'bg-orange-400',
  medium: 'bg-amber-400',
  low:    'bg-slate-300',
};

// ── Priority badge ────────────────────────────────────────────────────────
function PriorityBadge({ priority }: { priority: string }) {
  const map: Record<string, string> = {
    urgent: 'bg-red-100 text-red-700 border-red-200',
    high:   'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-amber-100 text-amber-700 border-amber-200',
    low:    'bg-slate-100 text-slate-500 border-slate-200',
  };
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wide',
      map[priority] ?? map.low,
    )}>
      {priority === 'urgent' && (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )}
      {priority}
    </span>
  );
}

// ── Classification chip ───────────────────────────────────────────────────
function ClassChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
      {label}
    </span>
  );
}

// ── Deadline chip ─────────────────────────────────────────────────────────
function DeadlineChip({ days }: { days: number }) {
  const overdue = days <= 0;
  const urgent  = days > 0 && days <= 3;
  return (
    <span className={cn(
      'inline-flex items-center gap-1 text-xs font-semibold',
      overdue ? 'text-red-600' : urgent ? 'text-red-500' : 'text-orange-500',
    )}>
      <Clock className="w-3.5 h-3.5" />
      {overdue ? `Overdue ${Math.abs(days)} day(s)` : `Due in ${days}d`}
    </span>
  );
}

interface Props {
  item: IntakeItem;
  isSelected: boolean;
  onSelect: (id: number) => void;
  onQuickApprove: (item: IntakeItem) => void;
}

export function IntakeItemRow({ item, isSelected, onSelect, onQuickApprove }: Props) {
  const isProcessing = item.processing_status === 'processing' || item.processing_status === 'pending';

  return (
    <div
      onClick={() => onSelect(item.id)}
      className={cn(
        'relative group cursor-pointer mx-3 mb-2 rounded-xl border transition-all duration-150',
        'border-l-4',
        PRIORITY_BORDER[item.priority] ?? 'border-l-slate-300',
        isSelected
          ? 'bg-indigo-50/50 border-indigo-100 shadow-sm'
          : 'bg-white border-gray-200 hover:border-gray-300 hover:shadow-sm',
      )}
    >
      <div className="p-4">
        {/* Row 1 — title + priority badge */}
        <div className="flex items-start justify-between gap-2 mb-1.5 pl-1">
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="w-4 h-4 text-gray-400 shrink-0" />
            <h3 className="text-sm font-bold text-gray-900 leading-tight truncate">
              {item.subject}
            </h3>
          </div>
          <PriorityBadge priority={item.priority} />
        </div>

        {/* Row 2 — sender */}
        <p className="text-xs text-gray-500 mb-2 pl-1 truncate">{item.from_address || '—'}</p>

        {/* Row 3 — chips */}
        <div className="flex flex-wrap gap-1.5 mb-2 pl-1">
          {item.nearest_deadline_days !== null && (
            <span className={cn(
              'inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded border',
              item.nearest_deadline_days <= 0
                ? 'bg-amber-50 text-amber-700 border-amber-200'
                : 'bg-orange-50 text-orange-700 border-orange-200',
            )}>
              <AlertTriangle className="w-3 h-3 mr-1" />
              Requires Action
            </span>
          )}
          {item.classification && item.classification !== 'Pending Analysis' && (
            <ClassChip label={item.classification} />
          )}
        </div>

        {/* Row 4 — AI insight */}
        {!isProcessing && item.ai_insight && (
          <p className="text-xs text-indigo-600 font-medium pl-1 truncate mb-2">
            {item.ai_insight}
          </p>
        )}
        {isProcessing && (
          <p className="text-xs text-slate-400 italic pl-1 flex items-center gap-1 mb-2">
            <Loader2 className="w-3 h-3 animate-spin" /> Processing…
          </p>
        )}

        {/* Row 5 — deadline + date */}
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-indigo-100/50 pl-1">
          {item.nearest_deadline_days !== null ? (
            <DeadlineChip days={item.nearest_deadline_days} />
          ) : (
            <span className="text-[10px] text-gray-400">
              {item.status === 'completed' ? (
                <span className="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 className="w-3 h-3" /> Completed
                </span>
              ) : 'No deadline'}
            </span>
          )}
          <span className="text-[10px] text-gray-400 tabular-nums">
            {item.received_at ? new Date(item.received_at).toLocaleDateString() : '—'}
          </span>
        </div>
      </div>

      {/* Quick approve button — hover only */}
      {item.suggested_case && item.status !== 'completed' && (
        <div className="absolute right-3 top-3 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={e => { e.stopPropagation(); onQuickApprove(item); }}
            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold rounded-lg shadow-sm"
          >
            Approve
          </button>
        </div>
      )}
    </div>
  );
}
