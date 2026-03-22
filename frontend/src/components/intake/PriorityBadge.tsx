/**
 * components/intake/PriorityBadge.tsx
 * Reusable priority indicator used in list rows and detail panel.
 */
import { cn } from '../../lib/utils';
import { AlertTriangle, AlertCircle, ArrowRight, Minus } from 'lucide-react';
import type { IntakePriority } from '../../services/intakeService';

const CONFIG: Record<IntakePriority, { label: string; classes: string; dot: string; Icon: React.ElementType }> = {
  urgent: { label: 'Urgent',  classes: 'bg-red-100 text-red-700 border-red-200',    dot: 'bg-red-500',    Icon: AlertCircle },
  high:   { label: 'High',    classes: 'bg-orange-100 text-orange-700 border-orange-200', dot: 'bg-orange-500', Icon: AlertTriangle },
  medium: { label: 'Medium',  classes: 'bg-amber-100 text-amber-700 border-amber-200',   dot: 'bg-amber-500',  Icon: ArrowRight },
  low:    { label: 'Low',     classes: 'bg-slate-100 text-slate-500 border-slate-200',   dot: 'bg-slate-400',  Icon: Minus },
};

export function PriorityBadge({ priority, size = 'sm' }: { priority: IntakePriority; size?: 'xs' | 'sm' }) {
  const cfg = CONFIG[priority] ?? CONFIG.low;
  const Icon = cfg.Icon;
  return (
    <span className={cn(
      'inline-flex items-center gap-1 font-semibold border rounded-full',
      size === 'xs' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-0.5',
      cfg.classes,
    )}>
      <Icon className={size === 'xs' ? 'h-2.5 w-2.5' : 'h-3 w-3'} />
      {cfg.label}
    </span>
  );
}

export function PriorityDot({ priority }: { priority: IntakePriority }) {
  const cfg = CONFIG[priority] ?? CONFIG.low;
  return (
    <span className={cn('h-2 w-2 rounded-full shrink-0 mt-1.5', cfg.dot)} />
  );
}
