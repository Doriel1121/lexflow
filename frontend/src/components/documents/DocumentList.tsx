import React, { useState, useEffect } from "react";
import {
  Search,
  Filter,
  FileText,
  MoreVertical,
  Tag,
  Calendar,
  Trash2,
  Download,
  Share2,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import api from "../../services/api";
import { useSnackbar } from "../../context/SnackbarContext";

interface Document {
  id: number;
  filename: string;
  case_id: number;
  classification: string;
  created_at: string;
  s3_url: string;
  processing_status?: string | null;
  processing_progress?: number;
  processing_stage?: string;
  content?: string;
  tags?: { id: number; name: string }[];
}

export function DocumentList() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [searchTerm, setSearchTerm] = useState("");
  const [semanticSearchActive, setSemanticSearchActive] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [newDocsToast, setNewDocsToast] = useState(false);
  const [dropdownPos, setDropdownPos] = useState<{
    top: number;
    left?: number;
    right?: number;
  }>({ top: 0, right: 0 });
  const dropdownButtonRef = React.useRef<HTMLButtonElement>(null);
  const docCountRef = React.useRef<number>(0);
  // Always hold a reference to the current documents array (fixes stale closure bug in polling)
  const documentsRef = React.useRef<Document[]>([]);

  // Infinite Scroll State
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [fetchingMore, setFetchingMore] = useState(false);
  const limit = 50;
  const observerTarget = React.useRef<HTMLDivElement>(null);

  // Keep documentsRef in sync
  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  // Close dropdown when clicking outside or scrolling
  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null);
    const handleScroll = () => setOpenDropdownId(null);
    document.addEventListener("click", handleClickOutside);
    document.addEventListener("scroll", handleScroll, true); // Use capture phase for nested scrolls
    return () => {
      document.removeEventListener("click", handleClickOutside);
      document.removeEventListener("scroll", handleScroll, true);
    };
  }, []);

  useEffect(() => {
    fetchDocuments();

    // Smart polling: Only poll when there are documents being processed
    const pollInterval = setInterval(async () => {
      try {
        const currentDocs = documentsRef.current;
        const pendingDocs = currentDocs.filter(
          (d) =>
            getNormalizedStatus(d.processing_status) === "pending" ||
            getNormalizedStatus(d.processing_status) === "processing",
        );

        // Only poll if there are pending documents
        if (pendingDocs.length === 0) {
          return; // Skip polling if nothing is processing
        }

        const statusUpdates: Record<
          number,
          { status: string; progress: number; stage: string }
        > = {};
        await Promise.allSettled(
          pendingDocs.map(async (pDoc) => {
            try {
              const sRes = await api.get(`/v1/documents/${pDoc.id}/status`);
              statusUpdates[pDoc.id] = sRes.data;
            } catch (err) {
              console.error(`Failed to fetch status for doc ${pDoc.id}:`, err);
            }
          }),
        );

        // Functional updater ensures we always operate on fresh state
        setDocuments((prev) => {
          let changed = false;
          const next = prev.map((d) => {
            const update = statusUpdates[d.id];
            if (!update) return d;
            if (
              d.processing_status !== update.status ||
              d.processing_progress !== update.progress ||
              d.processing_stage !== update.stage
            ) {
              changed = true;
              return {
                ...d,
                processing_status: update.status,
                processing_progress: update.progress,
                processing_stage: update.stage,
              };
            }
            return d;
          });
          return changed ? next : prev;
        });
      } catch (err) {
        console.debug("Poll error (non-fatal):", err);
      }
    }, 5000); // Poll every 5 seconds (only when needed)

    // Listen for document processing updates
    // When a document finishes processing, fetch its full updated data
    const handleDocumentProcessed = (event: Event) => {
      const customEvent = event as CustomEvent;
      const { document_id } = customEvent.detail || {};

      console.log(
        `[EVENT] Document processed event received for ID: ${document_id}`,
      );

      if (!document_id) return;

      // Fetch the FULL document data (not just status)
      (async () => {
        try {
          console.log(`[API] Fetching document ${document_id}...`);
          const docRes = await api.get(`/v1/documents/${document_id}`);
          console.log(
            `[UPDATE] Got document data, updating state:`,
            docRes.data,
          );
          // Update just this one document in state with full data
          setDocuments((prev) => {
            const found = prev.find((d) => d.id === document_id);
            if (!found) {
              // Document not in current list, add it to the top
              console.log(`[UPDATE] Document not found in list, adding to top`);
              return [docRes.data, ...prev];
            }
            // Replace document with updated data
            console.log(`[UPDATE] Replacing document in list`);
            return prev.map((d) => (d.id === document_id ? docRes.data : d));
          });
        } catch (err) {
          console.error(
            `[ERROR] Could not fetch document ${document_id}:`,
            err,
          );
          // Polling will catch it in 5 seconds
        }
      })();
    };
    window.addEventListener("document_processed", handleDocumentProcessed);

    return () => {
      clearInterval(pollInterval);
      window.removeEventListener("document_processed", handleDocumentProcessed);
    };
  }, []);

  const fetchDocuments = async (query?: string, targetPage: number = 0) => {
    try {
      const skip = targetPage * limit;
      if (targetPage === 0) {
        setLoading(true);
      } else {
        setFetchingMore(true);
      }

      let response;
      if (query && query.trim().length > 2) {
        setIsSearching(true);
        // Semantic search isn't paginated the same way currently since chunking vectors handles it, but pass it if available
        response = await api.get("/v1/documents/semantic-search", {
          params: { query: query.trim(), skip, limit },
        });
      } else {
        // Normal fetch
        response = await api.get("/v1/documents/", {
          params: { skip, limit },
        });
      }

      const incomingDocs: Document[] = response.data;

      if (targetPage === 0) {
        setDocuments(incomingDocs);
        docCountRef.current = incomingDocs.length > 0 ? incomingDocs[0].id : 0;
      } else {
        setDocuments((prev) => [...prev, ...incomingDocs]);
      }

      setHasMore(incomingDocs.length === limit);
      setPage(targetPage);
    } catch (error) {
      console.error("Failed to fetch documents:", error);
    } finally {
      setLoading(false);
      setIsSearching(false);
      setFetchingMore(false);
    }
  };

  // Intersection Observer for Infinite Scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && !fetchingMore) {
          fetchDocuments(searchTerm, page + 1);
        }
      },
      { threshold: 1.0 },
    );

    if (observerTarget.current) {
      observer.observe(observerTarget.current);
    }

    return () => observer.disconnect();
  }, [hasMore, loading, fetchingMore, page, searchTerm]);

  // Debounced Semantic Search Hook
  useEffect(() => {
    const timer = setTimeout(() => {
      if (semanticSearchActive) {
        fetchDocuments(searchTerm, 0);
      }
    }, 700);
    return () => clearTimeout(timer);
  }, [searchTerm, semanticSearchActive]);

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", files[0]);

    try {
      const response = await api.post("/v1/documents/?case_id=0", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      // Document uploaded successfully - add to list immediately
      const newDoc: Document = response.data;
      setDocuments((prev) => [newDoc, ...prev]);

      // Reset file input
      event.target.value = "";

      // Show success message
      showSnackbar("Document uploaded successfully", { type: "success" });
      console.log("Document uploaded successfully:", newDoc.filename);
    } catch (error: any) {
      console.error("Upload failed:", error);
      const errorMsg =
        error.response?.data?.detail ||
        error.message ||
        "Failed to upload document";
      showSnackbar(`Upload failed: ${errorMsg}`, { type: "error" });
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenDropdownId(null);
    if (!window.confirm("Are you sure you want to delete this document?"))
      return;

    // 🎯 OPTIMISTIC UPDATE: Remove immediately for instant feedback
    const previousDocs = documents;
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
    setDeletingId(docId);

    try {
      await api.delete(`/v1/documents/${docId}`);
      showSnackbar("Document deleted successfully", { type: "success" });
    } catch (error) {
      // ❌ ROLLBACK: Restore previous state on error
      setDocuments(previousDocs);
      console.error("Failed to delete document:", error);
      showSnackbar("Failed to delete document", { type: "error" });
    } finally {
      setDeletingId(null);
    }
  };

  const filteredDocs = React.useMemo(() => {
    if (semanticSearchActive) return documents; // When semantic search is on, the backend does the filtering

    return documents.filter((doc) => {
      const term = searchTerm.toLowerCase();
      const matchFilename = doc.filename.toLowerCase().includes(term);
      const matchContent = doc.content?.toLowerCase().includes(term) ?? false;
      const matchClassification =
        doc.classification?.toLowerCase().includes(term) ?? false;
      return matchFilename || matchContent || matchClassification;
    });
  }, [documents, searchTerm, semanticSearchActive]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "Unknown";
    const utcDateStr = dateStr.endsWith("Z") ? dateStr : `${dateStr}Z`;
    const date = new Date(utcDateStr);
    return date.toISOString().split("T")[0];
  };

  const getNormalizedStatus = (status: string | undefined | null) => {
    if (!status) return "completed"; // Legacy documents default to completed
    return status.toLowerCase();
  };

  const needsAIAnalysis = (doc: Document) => {
    // Check if document is completed but classification indicates AI is pending
    return (
      getNormalizedStatus(doc.processing_status) === "completed" &&
      (doc.classification === "Text Extracted (AI Pending)" ||
        doc.classification === "Pending Analysis" ||
        doc.processing_stage === "completed_without_ai")
    );
  };

  const handleRetryAI = async (docId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Retry AI analysis for this document?")) return;

    // 🎯 OPTIMISTIC UPDATE: Set status to processing immediately
    setDocuments((prev) =>
      prev.map((d) =>
        d.id === docId
          ? { ...d, processing_status: "processing", processing_progress: 0 }
          : d,
      ),
    );

    try {
      await api.post(`/v1/documents/retry-ai-analysis/${docId}`);
      showSnackbar("AI analysis queued successfully", { type: "success" });
      // Document will update via polling status endpoint
    } catch (error: any) {
      // ❌ ROLLBACK: Fetch correct status on error
      console.error("Failed to retry AI analysis:", error);
      showSnackbar(`Failed: ${error.response?.data?.detail || error.message}`, {
        type: "error",
      });

      // Refresh this document's status on error
      try {
        const statusRes = await api.get(`/v1/documents/${docId}/status`);
        setDocuments((prev) =>
          prev.map((d) => (d.id === docId ? { ...d, ...statusRes.data } : d)),
        );
      } catch (statusErr) {
        console.error("Failed to refresh status:", statusErr);
      }
    }
  };

  return (
    <div className="relative">
      {/* New documents toast */}
      {newDocsToast && (
        <div className="fixed top-6 right-6 z-50 flex items-center gap-3 bg-slate-900 text-white text-sm font-medium px-4 py-3 rounded-xl shadow-xl animate-fade-in">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          New documents received via email intake
          <button
            onClick={() => setNewDocsToast(false)}
            className="ml-2 text-slate-400 hover:text-white"
          >
            &times;
          </button>
        </div>
      )}
      <div className="bg-card border border-border-light rounded-lg shadow-legal flex flex-col flex-1 min-h-0">
        <div className="p-4 border-b border-border-light bg-background-secondary flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search
              className={`absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 ${isSearching ? "text-primary-500 animate-pulse" : "text-neutral-400"}`}
            />
            <input
              type="text"
              placeholder={
                semanticSearchActive
                  ? "AI Search: Ask a legal question..."
                  : "Search documents by name or content..."
              }
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
              }}
              className="w-full pl-10 pr-4 py-2.5 bg-white border border-border-light focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 rounded-lg text-sm outline-none transition-all duration-200"
            />
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                setSemanticSearchActive(!semanticSearchActive);
                if (semanticSearchActive && searchTerm.length > 0) {
                  fetchDocuments("", 0);
                }
              }}
              className={`flex items-center space-x-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${semanticSearchActive ? "bg-primary-50 text-primary-700 border border-primary-200 shadow-sm" : "bg-white text-neutral-600 border border-border-light hover:bg-neutral-50"}`}
            >
              <span className="relative flex h-2 w-2 mr-1">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${semanticSearchActive ? "bg-primary-500" : "hidden"}`}
                ></span>
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${semanticSearchActive ? "bg-primary-600" : "bg-neutral-400"}`}
                ></span>
              </span>
              <span>AI Search</span>
            </button>
            <button className="flex items-center space-x-2 px-3 py-2.5 bg-white text-neutral-600 border border-border-light rounded-lg hover:bg-neutral-50 text-sm font-medium transition-all">
              <Filter className="h-4 w-4" />
              <span>Filter</span>
            </button>
            <label className="bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-semibold hover:bg-primary-800 transition-all shadow-sm cursor-pointer">
              {uploading ? "Uploading..." : "Upload"}
              <input
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        <div className="mx-4 mt-3 p-4 border-2 border-dashed border-neutral-200 rounded-lg bg-neutral-50/50 flex items-center justify-center text-center hover:bg-neutral-50 hover:border-primary-300 transition-all cursor-pointer group">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded-lg shadow-sm group-hover:scale-105 transition-transform">
              <FileText className="h-5 w-5 text-primary-600" />
            </div>
            <div className="text-left">
              <p className="text-sm font-semibold text-neutral-800">
                {t("documentList.dropArea")}
              </p>
              <p className="text-xs text-neutral-500 mt-0.5">
                {t("documentList.dropAreaHint")}
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="p-8 text-center text-neutral-500">
              {t("documentList.loading")}
            </div>
          ) : (
            <table className="w-full text-sm text-left">
              <thead className="bg-neutral-50 text-neutral-700 font-semibold border-b border-border-light">
                <tr>
                  <th className="px-6 py-3.5 text-xs uppercase text-start tracking-wider">
                    {t("documentList.table.filename")}
                  </th>
                  <th className="px-6 py-3.5 text-xs uppercase text-start tracking-wider">
                    {t("documentList.table.case")}
                  </th>
                  <th className="px-6 py-3.5 text-xs uppercase text-start tracking-wider">
                    {t("casesPage.notes")}
                  </th>
                  <th className="px-6 py-3.5 text-xs uppercase text-start tracking-wider">
                    {t("casesPage.date")}
                  </th>
                  <th className="px-6 py-3.5 text-xs uppercase text-start tracking-wider">
                    {t("documentList.table.status")}
                  </th>
                  <th className="px-6 py-3.5 text-right text-xs uppercase text-start tracking-wider">
                    {t("adminUsers.table.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-light bg-white">
                {filteredDocs.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-12 text-center text-neutral-500"
                    >
                      <div className="flex flex-col items-center gap-2">
                        <FileText className="h-12 w-12 text-neutral-300" />
                        <p className="font-medium">
                          {t("documentList.noDocuments")}
                        </p>
                        <p className="text-xs text-neutral-400">
                          {t("documentList.uploadFirst")}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredDocs.map((doc) => {
                    const status = getNormalizedStatus(doc.processing_status);
                    const isViewable =
                      status === "completed" ||
                      doc.content ||
                      doc.processing_stage === "ocr_completed" ||
                      doc.processing_stage === "ai_analysis" ||
                      doc.processing_stage === "embedding";

                    return (
                      <tr
                        key={doc.id}
                        className={`transition-all ${isViewable ? "hover:bg-neutral-50 cursor-pointer" : "opacity-75 cursor-not-allowed bg-neutral-25"}`}
                        onClick={() =>
                          isViewable && navigate(`/documents/${doc.id}`)
                        }
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center space-x-3">
                            <div className="p-2 bg-primary-50 rounded-lg text-primary-600">
                              <FileText className="h-4 w-4" />
                            </div>
                            <span className="font-medium text-neutral-800">
                              {doc.filename}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-neutral-600">
                          {doc.case_id
                            ? `Case #${doc.case_id}`
                            : t("documentList.noCase")}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex gap-1.5 flex-wrap">
                            {doc.tags && doc.tags.length > 0 ? (
                              doc.tags.map((tag) => (
                                <span
                                  key={tag.id}
                                  className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-secondary-50 text-secondary-700 border border-secondary-200"
                                >
                                  <Tag className="h-3 w-3 mr-1 opacity-60" />
                                  {tag.name}
                                </span>
                              ))
                            ) : (
                              <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-neutral-100 text-neutral-600 border border-neutral-200">
                                <Tag className="h-3 w-3 mr-1 opacity-60" />
                                {doc.classification || "Unclassified"}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-neutral-500">
                          <div className="flex items-center">
                            <Calendar className="h-3.5 w-3.5 mr-1.5 opacity-70" />
                            {formatDate(doc.created_at)}
                          </div>
                        </td>
                        <td className="px-6 py-4 align-top">
                          {getNormalizedStatus(doc.processing_status) ===
                            "processing" ||
                          getNormalizedStatus(doc.processing_status) ===
                            "pending" ? (
                            <div className="flex flex-col space-y-2 max-w-[160px]">
                              <span className="inline-flex w-fit items-center px-2.5 py-1.5 rounded-md text-xs font-semibold bg-warning-light text-warning-dark shadow-sm border border-warning/20">
                                <svg
                                  className="animate-spin -ml-0.5 mr-2 h-3.5 w-3.5"
                                  xmlns="http://www.w3.org/2000/svg"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                >
                                  <circle
                                    className="opacity-25"
                                    cx="12"
                                    cy="12"
                                    r="10"
                                    stroke="currentColor"
                                    strokeWidth="4"
                                  ></circle>
                                  <path
                                    className="opacity-75"
                                    fill="currentColor"
                                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                  ></path>
                                </svg>
                                {doc.processing_stage
                                  ? doc.processing_stage
                                      .replace(/_/g, " ")
                                      .replace(/\b\w/g, (l) => l.toUpperCase())
                                  : "Analyzing..."}
                              </span>
                              {doc.processing_progress !== undefined &&
                                doc.processing_progress > 0 && (
                                  <div className="w-full bg-neutral-200 rounded-full h-2 overflow-hidden">
                                    <div
                                      className="bg-warning h-2 rounded-full transition-all duration-500 ease-out"
                                      style={{
                                        width: `${Math.min(doc.processing_progress, 100)}%`,
                                      }}
                                    ></div>
                                  </div>
                                )}
                            </div>
                          ) : getNormalizedStatus(doc.processing_status) ===
                            "failed" ? (
                            <div className="flex flex-col space-y-1.5">
                              <span className="inline-flex w-fit items-center px-2.5 py-1.5 rounded-md text-xs font-semibold bg-error-light text-error-dark shadow-sm border border-error/20">
                                {t("documentList.failed")}
                              </span>
                              <button
                                onClick={(e) => handleRetryAI(doc.id, e)}
                                className="text-xs text-primary-600 hover:text-primary-800 font-medium underline text-start"
                              >
                                {t("documentList.retryAI")}
                              </button>
                            </div>
                          ) : needsAIAnalysis(doc) ? (
                            <div className="flex flex-col space-y-1.5">
                              <span className="inline-flex w-fit items-center px-2.5 py-1.5 rounded-md text-xs font-semibold bg-info-light text-info-dark shadow-sm border border-info/20">
                                {t("documentList.textOnly")}
                              </span>
                              <button
                                onClick={(e) => handleRetryAI(doc.id, e)}
                                className="text-xs text-primary-600 hover:text-primary-800 font-medium underline"
                              >
                                {t("documentList.retryAI")}
                              </button>
                            </div>
                          ) : (
                            <span className="inline-flex w-fit items-center px-2.5 py-1.5 rounded-md text-xs font-semibold bg-success-light text-success-dark shadow-sm border border-success/20">
                              {t("status.processed")}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-right relative">
                          <button
                            ref={dropdownButtonRef}
                            className="p-2 hover:bg-neutral-100 rounded-lg text-neutral-400 hover:text-neutral-600 transition-all disabled:opacity-50"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (openDropdownId === doc.id) {
                                setOpenDropdownId(null);
                              } else {
                                // Calculate dropdown position based on button
                                const rect = (e.target as HTMLElement)
                                  .closest("button")
                                  ?.getBoundingClientRect();
                                if (rect) {
                                  const DROPDOWN_WIDTH = 192; // w-48 = 12rem = 192px
                                  const DROPDOWN_HEIGHT = 280; // Approximate height
                                  const GAP = 8;

                                  let top = rect.bottom + GAP;
                                  let left: number | undefined;
                                  let right: number | undefined;

                                  // Check if dropdown would go off right edge
                                  const rightEdge = rect.right + DROPDOWN_WIDTH;
                                  if (rightEdge > window.innerWidth - 16) {
                                    // 16px buffer
                                    // Align to button's left instead
                                    left = rect.left;
                                  } else {
                                    // Align to button's right (original behavior)
                                    right = window.innerWidth - rect.right;
                                  }

                                  // Check if dropdown would go off bottom edge
                                  if (
                                    top + DROPDOWN_HEIGHT >
                                    window.innerHeight - 16
                                  ) {
                                    // Position above button instead
                                    top = rect.top - DROPDOWN_HEIGHT - GAP;
                                  }

                                  setDropdownPos({
                                    top: Math.max(16, top), // Stay within viewport
                                    left,
                                    right,
                                  });
                                }
                                setOpenDropdownId(doc.id);
                              }
                            }}
                          >
                            <MoreVertical className="h-4 w-4" />
                          </button>

                          {/* Dropdown Menu - Fixed Position with Smart Placement */}
                          {openDropdownId === doc.id && (
                            <div
                              className="fixed w-48 bg-white border border-border-light rounded-lg shadow-legal-lg z-50 overflow-hidden"
                              style={{
                                top: `${dropdownPos.top}px`,
                                ...(dropdownPos.left !== undefined && {
                                  left: `${dropdownPos.left}px`,
                                }),
                                ...(dropdownPos.right !== undefined && {
                                  right: `${dropdownPos.right}px`,
                                }),
                              }}
                              onClick={(e) => e.stopPropagation()}
                            >
                              <div className="py-1">
                                {getNormalizedStatus(doc.processing_status) ===
                                  "completed" && (
                                  <button
                                    className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                                    onClick={() =>
                                      navigate(`/documents/${doc.id}`)
                                    }
                                  >
                                    <FileText className="h-4 w-4 text-neutral-400" />
                                    {t("documentList.preview")}
                                  </button>
                                )}
                                {getNormalizedStatus(doc.processing_status) ===
                                  "completed" && (
                                  <>
                                    <button
                                      className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                                      onClick={() => {
                                        setOpenDropdownId(null);
                                        showSnackbar(
                                          t(
                                            "documentList.downloadNotImplemented",
                                          ),
                                          { type: "info" },
                                        );
                                      }}
                                    >
                                      <Download className="h-4 w-4 text-neutral-400" />
                                      {t("documentList.download")}
                                    </button>
                                    <button
                                      className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                                      onClick={() => {
                                        setOpenDropdownId(null);
                                        showSnackbar(
                                          t("documentList.shareNotImplemented"),
                                          { type: "info" },
                                        );
                                      }}
                                    >
                                      <Share2 className="h-4 w-4 text-neutral-400" />
                                      {t("documentList.share")}
                                    </button>
                                    <hr className="my-1 border-neutral-100" />
                                  </>
                                )}
                                <button
                                  className="w-full text-left px-4 py-2.5 text-sm text-error hover:bg-error-light flex items-center gap-3 disabled:opacity-50 transition-colors"
                                  onClick={(e) =>
                                    handleDeleteDocument(doc.id, e)
                                  }
                                  disabled={deletingId === doc.id}
                                >
                                  <Trash2 className="h-4 w-4" />
                                  {deletingId === doc.id
                                    ? t("common.loading")
                                    : t("common.delete")}
                                </button>
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
          {/* Infinite Scroll Sentinel */}
          {!loading && (
            <div ref={observerTarget} className="py-4 text-center">
              {fetchingMore && (
                <span className="text-sm text-slate-500 animate-pulse">
                  {t("documentList.loadingMore")}
                </span>
              )}
              {!hasMore && documents.length > 0 && (
                <span className="text-xs text-slate-400">
                  {t("documentList.endOfRecords")}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
