/**
 * WorkflowStepper.tsx
 * Visual step-by-step progress indicator for the workflow pipeline.
 */

import { ReactNode } from "react";
import { Workflow, WorkflowStep } from "../../services/workflows";

const STEP_LABELS: Record<string, string> = {
  "intake.capture": "Intake",
  "intake.persist_source_document": "Persist Document",
  "document.ocr": "OCR",
  "document.ai_analysis": "AI Analysis",
  "draft.generate": "Generate Draft",
  "draft.normalize_to_editor_doc": "Normalize Draft",
  "review.human_edit": "Human Review",
  "review.approve": "Approve",
  "bundle.collect_attachments": "Collect Attachments",
  "bundle.redact": "Redact",
  "bundle.paginate": "Paginate",
  "bundle.table_of_contents": "Table of Contents",
  "bundle.validate_size": "Validate Size",
  "bundle.chunk_for_court": "Chunk for Court",
  "bundle.finalize": "Finalize Bundle",
};

const STEP_GROUPS = [
  {
    label: "Intake",
    keys: ["intake.capture", "intake.persist_source_document"],
  },
  {
    label: "Processing",
    keys: ["document.ocr", "document.ai_analysis"],
  },
  {
    label: "Drafting",
    keys: ["draft.generate", "draft.normalize_to_editor_doc"],
  },
  {
    label: "Review",
    keys: ["review.human_edit", "review.approve"],
  },
  {
    label: "Bundle",
    keys: [
      "bundle.collect_attachments",
      "bundle.redact",
      "bundle.paginate",
      "bundle.table_of_contents",
      "bundle.validate_size",
      "bundle.chunk_for_court",
      "bundle.finalize",
    ],
  },
];

function stepIcon(status: string): ReactNode {
  switch (status) {
    case "COMPLETED":
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
          <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
        </svg>
      );
    case "RUNNING":
    case "QUEUED":
      return <span className="w-2 h-2 rounded-full bg-current animate-pulse" />;
    case "FAILED":
      return (
        <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
          <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z" />
        </svg>
      );
    case "WAITING_FOR_HUMAN":
      return <span className="w-2 h-2 rounded-full bg-current" />;
    default:
      return null;
  }
}

function stepColor(status: string, isCurrent: boolean): string {
  if (isCurrent && status === "RUNNING")
    return "border-blue-500 bg-blue-500 text-white";
  switch (status) {
    case "COMPLETED":
      return "border-emerald-500 bg-emerald-500 text-white";
    case "FAILED":
      return "border-red-500 bg-red-500 text-white";
    case "RUNNING":
    case "QUEUED":
      return "border-blue-500 bg-blue-100 text-blue-700";
    case "WAITING_FOR_HUMAN":
      return "border-amber-500 bg-amber-100 text-amber-700";
    case "SKIPPED":
      return "border-slate-300 bg-slate-100 text-slate-400";
    default:
      return "border-slate-200 bg-white text-slate-400";
  }
}

interface Props {
  workflow: Workflow;
  onRetryStep?: (stepKey: string) => void;
}

export function WorkflowStepper({ workflow, onRetryStep }: Props) {
  const stepsByKey = Object.fromEntries(
    (workflow.steps || []).map((s) => [s.step_key, s])
  );

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
          Pipeline Progress
        </h2>
      </div>
      <div className="p-4 space-y-4">
        {STEP_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
              {group.label}
            </p>
            <div className="flex flex-wrap gap-2">
              {group.keys.map((key) => {
                const step: WorkflowStep | undefined = stepsByKey[key];
                if (!step) return null;
                const isCurrent = workflow.current_step_key === key;
                const color = stepColor(step.status, isCurrent);
                const label = STEP_LABELS[key] ?? key;

                return (
                  <div
                    key={key}
                    id={`step-${key.replace(/\./g, "-")}`}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-all ${color} ${isCurrent ? "ring-2 ring-offset-1 ring-blue-400" : ""}`}
                    title={`${label}: ${step.status}${step.attempt_count > 1 ? ` (attempt ${step.attempt_count})` : ""}`}
                  >
                    {stepIcon(step.status)}
                    <span>{label}</span>
                    {step.status === "FAILED" && onRetryStep && (
                      <button
                        onClick={() => onRetryStep(key)}
                        className="ml-1 underline text-current hover:no-underline"
                        title="Retry step"
                      >
                        Retry
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
