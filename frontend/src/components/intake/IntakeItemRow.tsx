/**
 * components/intake/IntakeItemRow.tsx
 * Single row in the intake list — NOT an email row, an intake item row.
 */
import { Briefcase, FileText, AlertTriangle, Clock, CheckCircle2, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { PriorityBadge, PriorityDot } from './PriorityBadge';
import type { IntakeItem, IntakeStatus } from '../../services/intakeService';

const STATUS_LABEL: Record<IntakeStatus, string> = {
  needs_review:    'Needs Review',
  requires_action: 'Requires Action',
  auto_processed:  'Auto Processed',
  completed:       'Completed',
};

const STATUS_ICON: Record<IntakeStatus, React.ElementType> = {
  needs_review:    Loader2,
  requires_action: AlertTriangle,
  auto_processed:  CheckCircle2,
  completed:       CheckCircle2,
};

const STATUS_COLOR: Record<IntakeStatus, string> = {
  needs_review:    'text-slate-400',
  requires_action: 'text-orange-500',
  auto_processed:  'text-emerald-500',
  completed:       'text-blue-500',
};

function ItemTypeIcon({ classification }: { classification: string | null }) {
  const c = (classification || '').toLowerCase();
  if (c.includes('contract') || c.includes('agreement')) return <FileText className="h-4 w-4 text-blue-600" />;
  if (c.includes('motion') || c.includes('complaint') || c.includes('ruling')) return <Briefcase className="h-4 w-4 text-purple-600" />;
  if (c.includes('deadline') || c.includes('notice')) return <AlertTriangle className="h-4 w-4 text-orange-600" />;
  return <FileText className="h-4 w-4 text-slate-400" />;
}

interface Props {
  item: IntakeItem;
  isSelected: boolean;
  onSelect: (id: number) => void;
  onQuickApprove: (item: IntakeItem) => void;
}

export function IntakeItemRow({ item, isSelected, onSelect, onQuickApprove }: Props) {
  const StatusIcon = STATUS_ICON[item.status];
  const isProcessing = item.processing_status === 'processing' || item.processing_status === 'pending';

  return (
    <div
      onClick={() => onSelect(item.id)}
      className={cn(
        'flex items-start gap-3 p-4 border-b border-slate-100 cursor-pointer transition-all group',
        isSelected
          ? 'bg-indigo-50 border-l-[3px] border-l-indigo-500'
          : 'hover:bg-slate-50 border-l-[3px] border-l-transparent',
        item.priority === 'urgent' && !isSelected && 'border-l-red-400',
        item.priority === 'high'   && !isSelected && 'border-l-orange-400',
      )}
    >
      {/* Priority dot */}
      <PriorityDot priority={item.priority} />

      {/* Type icon */}
      <div className="shrink-0 mt-0.5 p-1.5 bg-slate-100 rounded-lg">
        <ItemTypeIcon classification={item.classification} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold text-slate-800 truncate leading-tight">
            {item.subject}
          </p>
          <div className="shrink-0 flex items-center gap-1.5">
            <PriorityBadge priority={item.priority} size="xs" />
          </div>
        </div>

        <p className="text-xs text-slate-500 mt-0.5 truncate">{item.from_address || '—'}</p>

        {/* AI insight */}
        <p className={cn(
          'text-xs mt-1.5 leading-relaxed truncate font-medium',
          isProcessing ? 'text-slate-400 italic' : 'text-indigo-700',
        )}>
          {isProcessing
            ? <span className="flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Processing…</span>
            : item.ai_insight}
        </p>

        {/* Suggested case pill */}
        {item.suggested_case && (
          <div className="mt-1.5 inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-full text-[10px] font-semibold">
            <Briefcase className="h-2.5 w-2.5" />
            {item.suggested_case.case_title}
            <span className="text-emerald-500">({item.suggested_case.confidence})</span>
          </div>
        )}

        {/* Footer row */}
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Status */}
            <span className={cn('flex items-center gap-1 text-[10px] font-medium', STATUS_COLOR[item.status])}>
              <StatusIcon className="h-2.5 w-2.5" />
              {STATUS_LABEL[item.status]}
            </span>

            {/* Deadline chip */}
            {item.nearest_deadline_days !== null && (
              <span className={cn(
                'flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full',
                item.nearest_deadline_days <= 3
                  ? 'bg-red-100 text-red-700'
                  : item.nearest_deadline_days <= 7
                  ? 'bg-orange-100 text-orange-700'
                  : 'bg-slate-100 text-slate-500',
              )}>
                <Clock className="h-2.5 w-2.5" />
                {item.nearest_deadline_days <= 0
                  ? 'Overdue'
                  : `${item.nearest_deadline_days}d`}
              </span>
            )}
          </div>

          {/* Time */}
          <span className="text-[10px] text-slate-400 tabular-nums">
            {item.received_at ? new Date(item.received_at).toLocaleDateString() : '—'}
          </span>
        </div>
      </div>

      {/* Quick approve on hover */}
      {item.suggested_case && item.status !== 'completed' && (
        <button
          onClick={e => { e.stopPropagation(); onQuickApprove(item); }}
          className="shrink-0 self-center opacity-0 group-hover:opacity-100 transition-opacity px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] font-bold rounded-lg"
          title={`Approve: ${item.suggested_case.case_title}`}
        >
          Approve
        </button>
      )}
    </div>
  );
}
