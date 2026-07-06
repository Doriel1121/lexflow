/**
 * WorkflowActivityRail.tsx
 * Chronological audit trail of workflow events.
 */

import { WorkflowEvent } from "../../services/workflows";

const EVENT_ICONS: Record<string, string> = {
  "workflow.created": "🔵",
  "workflow.started": "▶️",
  "workflow.transitioned": "➡️",
  "workflow.cancelled": "🚫",
  "workflow.waiting_for_human": "⏸️",
  "step.started": "⚙️",
  "step.completed": "✅",
  "step.failed": "❌",
  "step.retry_requested": "🔄",
  "step.waiting_for_human": "👤",
  "draft.approved": "✍️",
  "draft.revision_requested": "📝",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatEventLabel(event: WorkflowEvent): string {
  const typeLabel = event.event_type
    .replace(/\./g, " › ")
    .replace(/_/g, " ");

  // Include step_key if present
  if (event.step_key) {
    return `${typeLabel} [${event.step_key}]`;
  }
  return typeLabel;
}

interface Props {
  events: WorkflowEvent[];
}

export function WorkflowActivityRail({ events }: Props) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
            Activity
          </h2>
        </div>
        <div className="px-4 py-8 text-center text-sm text-slate-400">
          No activity yet
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
          Activity ({events.length})
        </h2>
      </div>
      <div className="divide-y divide-slate-100 max-h-72 overflow-y-auto">
        {events.map((event) => (
          <div
            key={event.id}
            className="px-4 py-2.5 flex items-start gap-2.5 hover:bg-slate-50 transition-colors"
          >
            <span className="text-sm mt-0.5 flex-shrink-0">
              {EVENT_ICONS[event.event_type] ?? "◦"}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-700 capitalize">
                {formatEventLabel(event)}
              </p>
              {event.payload &&
                Object.keys(event.payload).length > 0 && (
                  <p className="text-xs text-slate-400 truncate">
                    {JSON.stringify(event.payload).slice(0, 80)}
                  </p>
                )}
            </div>
            <span className="text-xs text-slate-400 flex-shrink-0 mt-0.5">
              {event.created_at ? formatDate(event.created_at) : ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
