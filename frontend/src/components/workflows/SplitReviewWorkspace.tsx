/**
 * SplitReviewWorkspace.tsx
 * The split-screen review workspace that places the PDF viewer on the left
 * and the TipTap draft editor on the right.
 */

import { LegalDraft, Workflow } from "../../services/workflows";
import { PdfReviewPane } from "./PdfReviewPane";
import { DraftEditorPane } from "./DraftEditorPane";

interface Props {
  workflow: Workflow;
  draft: LegalDraft | null;
  /** Source document S3/storage URL (fetch separately if needed) */
  documentUrl?: string | null;
  documentOcrText?: string | null;
  documentFilename?: string | null;
  onDraftApproved?: () => void;
  onRevisionRequested?: (instructions: string) => void;
  onDraftSaved?: (draft: LegalDraft) => void;
}

export function SplitReviewWorkspace({
  workflow,
  draft,
  documentUrl,
  documentOcrText,
  documentFilename,
  onDraftApproved,
  onRevisionRequested,
  onDraftSaved,
}: Props) {
  const showReview =
    workflow.status === "PENDING_HUMAN_REVIEW" ||
    workflow.status === "IN_HUMAN_REVIEW" ||
    workflow.status === "REVISION_REQUESTED" ||
    workflow.status === "APPROVED_FOR_ASSEMBLY" ||
    (draft !== null);

  if (!showReview) {
    return null;
  }

  return (
    <div className="rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50">
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
          Split Review Workspace
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Review the source document on the left and edit the AI draft on the right.
        </p>
      </div>
      <div
        className="grid gap-0"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          height: "70vh",
          minHeight: "500px",
        }}
      >
        {/* Left: Source document */}
        <div className="border-r border-slate-200 h-full overflow-hidden">
          <PdfReviewPane
            sourceDocumentId={workflow.source_document_id}
            documentUrl={documentUrl}
            ocrText={documentOcrText}
            filename={documentFilename}
          />
        </div>

        {/* Right: Draft editor */}
        <div className="h-full overflow-hidden">
          <DraftEditorPane
            draft={draft}
            workflowStatus={workflow.status}
            onApprove={onDraftApproved}
            onRequestRevision={onRevisionRequested}
            onSaved={onDraftSaved}
          />
        </div>
      </div>
    </div>
  );
}
