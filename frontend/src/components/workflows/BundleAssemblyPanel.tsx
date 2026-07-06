/**
 * BundleAssemblyPanel.tsx
 * Shows court bundle assembly status, progress checklist,
 * and download links for final bundle and chunks.
 */

import { useCallback, useState } from "react";
import { CourtBundleSummary, Workflow } from "../../services/workflows";
import workflowsApi from "../../services/workflows";

interface Props {
  workflow: Workflow;
  bundle: CourtBundleSummary | null;
  onBundleUpdated?: (bundle: CourtBundleSummary) => void;
}

const ASSEMBLY_STAGES = [
  "Resolving approved draft",
  "Rendering draft to PDF",
  "Collecting attachments",
  "Normalizing PDFs",
  "Applying redactions",
  "Generating table of contents",
  "Merging documents",
  "Adding pagination",
  "Validating size",
  "Splitting into court chunks",
  "Persisting manifest",
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function BundleAssemblyPanel({ workflow, bundle, onBundleUpdated }: Props) {
  const [loading, setLoading] = useState(false);
  const [chunks, setChunks] = useState<any[]>([]);
  const [chunksLoaded, setChunksLoaded] = useState(false);

  const canAssemble =
    workflow.status === "APPROVED_FOR_ASSEMBLY" ||
    workflow.status === "ASSEMBLY_FAILED";

  const handleAssemble = useCallback(async () => {
    if (!workflow.active_draft_id) return;
    setLoading(true);
    try {
      let b = bundle;
      if (!b) {
        b = await workflowsApi.createBundle(workflow.id, {
          approved_draft_id: workflow.active_draft_id,
          max_chunk_bytes: 25 * 1024 * 1024,
        });
        onBundleUpdated?.(b);
      }
      const updated = await workflowsApi.assembleBundle(b.id);
      onBundleUpdated?.(updated);
    } finally {
      setLoading(false);
    }
  }, [workflow, bundle, onBundleUpdated]);

  const handleLoadChunks = useCallback(async () => {
    if (!bundle) return;
    try {
      const c = await workflowsApi.getBundleChunks(bundle.id);
      setChunks(c);
      setChunksLoaded(true);
    } catch {
      // ignore
    }
  }, [bundle]);

  const showPanel =
    canAssemble ||
    workflow.status === "ASSEMBLING_BUNDLE" ||
    workflow.status === "READY_FOR_COURT_SUBMISSION" ||
    !!bundle;

  if (!showPanel) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
            Court Bundle Assembly
          </h2>
          {bundle && (
            <p className="text-xs text-slate-500 mt-0.5">
              Bundle #{bundle.id} ·{" "}
              <span
                className={
                  bundle.status === "READY"
                    ? "text-emerald-600 font-medium"
                    : bundle.status === "FAILED"
                    ? "text-red-600 font-medium"
                    : bundle.status === "ASSEMBLING"
                    ? "text-blue-600 font-medium"
                    : "text-slate-500"
                }
              >
                {bundle.status}
              </span>{" "}
              · Max {formatBytes(bundle.max_chunk_bytes)} per chunk
            </p>
          )}
        </div>
        {canAssemble && (
          <button
            id="bundle-assemble-btn"
            onClick={handleAssemble}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading
              ? "Starting…"
              : bundle?.status === "FAILED"
              ? "Retry Assembly"
              : "Start Assembly"}
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Assembly stages checklist */}
        <div>
          <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
            Assembly Stages
          </p>
          <div className="space-y-1.5">
            {ASSEMBLY_STAGES.map((stage, idx) => {
              const isAssembling =
                bundle?.status === "ASSEMBLING" ||
                workflow.status === "ASSEMBLING_BUNDLE";
              const isReady = bundle?.status === "READY";
              const completed = isReady;
              const active =
                isAssembling &&
                !isReady &&
                idx < Math.floor((Date.now() / 800) % ASSEMBLY_STAGES.length);

              return (
                <div
                  key={stage}
                  className={`flex items-center gap-2 text-sm ${
                    completed
                      ? "text-emerald-700"
                      : active
                      ? "text-blue-600"
                      : "text-slate-400"
                  }`}
                >
                  <span className="text-base leading-none">
                    {completed ? "✅" : active ? "⚙️" : "○"}
                  </span>
                  <span>{stage}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Error display */}
        {bundle?.error && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-3">
            <p className="text-sm font-medium text-red-700 mb-1">
              Assembly Failed
            </p>
            <pre className="text-xs text-red-600 whitespace-pre-wrap">
              {JSON.stringify(bundle.error, null, 2)}
            </pre>
          </div>
        )}

        {/* Manifest summary */}
        {bundle?.manifest && Object.keys(bundle.manifest).length > 0 && (
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3">
            <p className="text-sm font-medium text-slate-700 mb-1">Manifest</p>
            <pre className="text-xs text-slate-600 whitespace-pre-wrap overflow-auto max-h-40">
              {JSON.stringify(bundle.manifest, null, 2)}
            </pre>
          </div>
        )}

        {/* Download final bundle */}
        {bundle?.status === "READY" && bundle.final_artifact_id && (
          <div className="flex flex-wrap gap-2">
            <a
              id="download-bundle-link"
              href={`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/v1/bundles/${bundle.id}/download`}
              download
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 transition-colors"
            >
              ↓ Download Final Bundle
            </a>

            {!chunksLoaded ? (
              <button
                onClick={handleLoadChunks}
                className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-colors"
              >
                Show Chunks
              </button>
            ) : null}
          </div>
        )}

        {/* Chunks list */}
        {chunksLoaded && chunks.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
              Court Chunks ({chunks.length})
            </p>
            <div className="space-y-1">
              {chunks.map((chunk) => (
                <div
                  key={chunk.id}
                  className="flex items-center justify-between text-sm py-1.5 px-2 rounded hover:bg-slate-50"
                >
                  <span className="text-slate-700">{chunk.label}</span>
                  <span className="text-slate-400 text-xs">
                    Pages {chunk.page_start}–{chunk.page_end}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
