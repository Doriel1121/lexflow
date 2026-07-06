/**
 * PdfReviewPane.tsx
 * Left pane of the split-screen review workspace.
 * Shows the source document via iframe (PDF) or OCR text fallback.
 */

import { useState } from "react";

interface Props {
  sourceDocumentId: number | null;
  /** S3 / storage URL for the source PDF */
  documentUrl?: string | null;
  /** OCR text fallback */
  ocrText?: string | null;
  filename?: string | null;
}

export function PdfReviewPane({
  sourceDocumentId,
  documentUrl,
  ocrText,
  filename,
}: Props) {
  const [mode, setMode] = useState<"pdf" | "text">(
    documentUrl ? "pdf" : "text"
  );

  if (!sourceDocumentId && !documentUrl && !ocrText) {
    return (
      <div className="flex flex-col h-full items-center justify-center text-slate-400 bg-slate-50 rounded-xl border border-slate-200">
        <svg
          className="w-12 h-12 mb-3 opacity-40"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <p className="text-sm font-medium">No source document</p>
        <p className="text-xs mt-1">
          Attach a document to this workflow to enable review.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full rounded-xl border border-slate-200 overflow-hidden bg-white">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 truncate max-w-xs">
            {filename || "Source Document"}
          </span>
          {sourceDocumentId && (
            <span className="text-xs text-slate-400">#{sourceDocumentId}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {documentUrl && (
            <button
              onClick={() => setMode("pdf")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                mode === "pdf"
                  ? "bg-blue-600 text-white"
                  : "text-slate-500 hover:bg-slate-200"
              }`}
            >
              PDF
            </button>
          )}
          {ocrText && (
            <button
              onClick={() => setMode("text")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                mode === "text"
                  ? "bg-blue-600 text-white"
                  : "text-slate-500 hover:bg-slate-200"
              }`}
            >
              Text
            </button>
          )}
          {documentUrl && (
            <a
              href={documentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-1 px-2 py-1 rounded text-xs text-slate-500 hover:bg-slate-200 transition-colors"
              title="Open in new tab"
            >
              ↗
            </a>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {mode === "pdf" && documentUrl ? (
          <iframe
            id="source-document-iframe"
            src={documentUrl}
            className="w-full h-full border-0"
            title={filename || "Source Document"}
          />
        ) : (
          <div className="h-full overflow-y-auto p-4">
            {ocrText ? (
              <pre className="whitespace-pre-wrap text-sm text-slate-700 font-mono leading-relaxed">
                {ocrText}
              </pre>
            ) : (
              <p className="text-sm text-slate-400 italic">
                OCR text not available for this document.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
