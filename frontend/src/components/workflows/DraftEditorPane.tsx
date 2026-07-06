/**
 * DraftEditorPane.tsx
 * Right pane of the split-screen review workspace.
 * TipTap rich text editor with debounced autosave, dirty indicator, and approve/revision buttons.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Highlight from "@tiptap/extension-highlight";
import TextAlign from "@tiptap/extension-text-align";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import { LegalDraft } from "../../services/workflows";
import workflowsApi from "../../services/workflows";

const AUTOSAVE_DEBOUNCE_MS = 1500;

interface Props {
  draft: LegalDraft | null;
  workflowStatus: string;
  onApprove?: () => void;
  onRequestRevision?: (instructions: string) => void;
  onSaved?: (draft: LegalDraft) => void;
}

function EditorToolbar({ editor }: { editor: any }) {
  if (!editor) return null;
  return (
    <div className="flex flex-wrap items-center gap-0.5 px-2 py-1.5 border-b border-slate-100">
      {[
        {
          label: "B",
          title: "Bold",
          action: () => editor.chain().focus().toggleBold().run(),
          active: editor.isActive("bold"),
          cls: "font-bold",
        },
        {
          label: "I",
          title: "Italic",
          action: () => editor.chain().focus().toggleItalic().run(),
          active: editor.isActive("italic"),
          cls: "italic",
        },
        {
          label: "U",
          title: "Underline",
          action: () => editor.chain().focus().toggleUnderline().run(),
          active: editor.isActive("underline"),
          cls: "underline",
        },
        {
          label: "H1",
          title: "Heading 1",
          action: () =>
            editor.chain().focus().toggleHeading({ level: 1 }).run(),
          active: editor.isActive("heading", { level: 1 }),
          cls: "",
        },
        {
          label: "H2",
          title: "Heading 2",
          action: () =>
            editor.chain().focus().toggleHeading({ level: 2 }).run(),
          active: editor.isActive("heading", { level: 2 }),
          cls: "",
        },
        {
          label: "¶",
          title: "Paragraph",
          action: () => editor.chain().focus().setParagraph().run(),
          active: editor.isActive("paragraph"),
          cls: "",
        },
        {
          label: "•",
          title: "Bullet list",
          action: () => editor.chain().focus().toggleBulletList().run(),
          active: editor.isActive("bulletList"),
          cls: "",
        },
        {
          label: "1.",
          title: "Ordered list",
          action: () => editor.chain().focus().toggleOrderedList().run(),
          active: editor.isActive("orderedList"),
          cls: "",
        },
        {
          label: "«»",
          title: "Blockquote",
          action: () => editor.chain().focus().toggleBlockquote().run(),
          active: editor.isActive("blockquote"),
          cls: "",
        },
      ].map((btn) => (
        <button
          key={btn.title}
          onClick={btn.action}
          title={btn.title}
          className={`w-7 h-7 rounded text-xs transition-colors ${btn.cls} ${
            btn.active
              ? "bg-slate-700 text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {btn.label}
        </button>
      ))}
    </div>
  );
}

export function DraftEditorPane({
  draft,
  workflowStatus,
  onApprove,
  onRequestRevision,
  onSaved,
}: Props) {
  const [saveStatus, setSaveStatus] = useState<"saved" | "saving" | "unsaved">(
    "saved"
  );
  const [revisionMode, setRevisionMode] = useState(false);
  const [revisionInstructions, setRevisionInstructions] = useState("");
  const [approving, setApproving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftIdRef = useRef<number | null>(null);

  const canEdit = workflowStatus === "IN_HUMAN_REVIEW" || workflowStatus === "PENDING_HUMAN_REVIEW";
  const canApprove = canEdit && draft?.status !== "APPROVED";

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Highlight,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Link.configure({ openOnClick: false }),
      Placeholder.configure({
        placeholder: "Draft content will appear here…",
      }),
    ],
    content: draft?.content_json ?? "",
    editable: canEdit,
    onUpdate: ({ editor }) => {
      setSaveStatus("unsaved");
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        if (!draftIdRef.current) return;
        setSaveStatus("saving");
        try {
          const json = editor.getJSON();
          const text = editor.getText();
          const html = editor.getHTML();
          const updated = await workflowsApi.updateDraft(draftIdRef.current, {
            content_json: json,
            content_text: text,
            html_snapshot: html,
          });
          setSaveStatus("saved");
          onSaved?.(updated);
        } catch {
          setSaveStatus("unsaved");
        }
      }, AUTOSAVE_DEBOUNCE_MS);
    },
  });

  // Sync content when draft changes
  useEffect(() => {
    draftIdRef.current = draft?.id ?? null;
    if (!editor) return;
    if (!draft) {
      editor.commands.setContent("");
      return;
    }
    // Only update if the content actually changed (avoid cursor jump)
    const current = JSON.stringify(editor.getJSON());
    const incoming = JSON.stringify(draft.content_json);
    if (current !== incoming) {
      editor.commands.setContent(draft.content_json);
    }
    editor.setEditable(canEdit);
  }, [draft?.id, draft?.content_json, canEdit, editor]);

  const handleApprove = useCallback(async () => {
    if (!draft) return;
    setApproving(true);
    try {
      await workflowsApi.approveDraft(draft.id);
      onApprove?.();
    } finally {
      setApproving(false);
    }
  }, [draft, onApprove]);

  const handleRequestRevision = useCallback(async () => {
    if (!draft) return;
    await workflowsApi.requestRevision(draft.id, revisionInstructions);
    setRevisionMode(false);
    setRevisionInstructions("");
    onRequestRevision?.(revisionInstructions);
  }, [draft, revisionInstructions, onRequestRevision]);

  if (!draft) {
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
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
        <p className="text-sm font-medium">No draft yet</p>
        <p className="text-xs mt-1">
          Start the workflow to generate an AI draft.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full rounded-xl border border-slate-200 overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 bg-slate-50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700 truncate max-w-xs">
            {draft.title}
          </span>
          <span className="text-xs text-slate-400">v{draft.version}</span>
          <span
            className={`px-1.5 py-0.5 rounded text-xs font-medium ${
              draft.status === "APPROVED"
                ? "bg-emerald-100 text-emerald-700"
                : draft.status === "AI_GENERATED"
                ? "bg-purple-100 text-purple-700"
                : "bg-amber-100 text-amber-700"
            }`}
          >
            {draft.status.replace(/_/g, " ")}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs ${
              saveStatus === "saved"
                ? "text-emerald-600"
                : saveStatus === "saving"
                ? "text-blue-500"
                : "text-amber-500"
            }`}
          >
            {saveStatus === "saved"
              ? "✓ Saved"
              : saveStatus === "saving"
              ? "Saving…"
              : "Unsaved"}
          </span>
        </div>
      </div>

      {/* Editor toolbar */}
      {canEdit && <EditorToolbar editor={editor} />}

      {/* Editor body */}
      <div className="flex-1 overflow-y-auto">
        <EditorContent
          id="draft-editor"
          editor={editor}
          className="prose prose-slate max-w-none p-4 min-h-full focus:outline-none [&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-full"
        />
      </div>

      {/* Approve / Revision actions */}
      {canApprove && (
        <div className="flex-shrink-0 border-t border-slate-100 px-4 py-3 bg-slate-50">
          {revisionMode ? (
            <div className="flex flex-col gap-2">
              <textarea
                id="revision-instructions"
                value={revisionInstructions}
                onChange={(e) => setRevisionInstructions(e.target.value)}
                placeholder="Describe what should be changed in the next draft…"
                rows={3}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setRevisionMode(false)}
                  className="px-3 py-1.5 rounded-lg text-sm text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  id="submit-revision-btn"
                  onClick={handleRequestRevision}
                  className="px-3 py-1.5 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 transition-colors"
                >
                  Request Revision
                </button>
              </div>
            </div>
          ) : (
            <div className="flex justify-between gap-2">
              <button
                id="request-revision-btn"
                onClick={() => setRevisionMode(true)}
                className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-100 transition-colors"
              >
                Request Revision
              </button>
              <button
                id="approve-draft-btn"
                onClick={handleApprove}
                disabled={approving}
                className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {approving ? "Approving…" : "✓ Approve Draft"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
