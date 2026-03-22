import { FileText, Calendar, UserCheck, AlertCircle, MessageSquare, PlusCircle } from 'lucide-react';
import type { CaseEvent } from '../../types';

const EVENT_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  case_created:        { icon: PlusCircle,    color: 'text-blue-600',    bg: 'bg-blue-100' },
  document_added:      { icon: FileText,      color: 'text-emerald-600', bg: 'bg-emerald-100' },
  deadline_created:    { icon: Calendar,      color: 'text-amber-600',   bg: 'bg-amber-100' },
  deadline_completed:  { icon: Calendar,      color: 'text-emerald-600', bg: 'bg-emerald-100' },
  status_changed:      { icon: AlertCircle,   color: 'text-purple-600',  bg: 'bg-purple-100' },
  lawyer_assigned:     { icon: UserCheck,     color: 'text-indigo-600',  bg: 'bg-indigo-100' },
  note_added:          { icon: MessageSquare, color: 'text-slate-600',   bg: 'bg-slate-100' },
};

interface TimelineViewProps {
  events: CaseEvent[];
}

export function TimelineView({ events }: TimelineViewProps) {
  if (!events || events.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400">
        <Calendar className="h-8 w-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No activity yet</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-100" />

      <div className="space-y-4">
        {events.map((event, i) => {
          const config = EVENT_CONFIG[event.event_type] || EVENT_CONFIG.case_created;
          const Icon = config.icon;

          return (
            <div key={event.id || i} className="relative flex gap-4 pl-1">
              {/* Icon dot */}
              <div className={`relative z-10 flex-shrink-0 w-8 h-8 rounded-full ${config.bg} flex items-center justify-center`}>
                <Icon className={`h-3.5 w-3.5 ${config.color}`} />
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <div className="flex items-baseline justify-between">
                  <p className="text-sm font-medium text-slate-700">
                    {event.description || event.event_type.replace(/_/g, ' ')}
                  </p>
                  <time className="text-xs text-slate-400 whitespace-nowrap ml-2">
                    {new Date(event.created_at).toLocaleDateString(undefined, {
                      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                    })}
                  </time>
                </div>
                {event.metadata_json && Object.keys(event.metadata_json).length > 0 && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    {Object.entries(event.metadata_json)
                      .filter(([_, v]) => v != null)
                      .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
                      .join(' · ')
                    }
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
