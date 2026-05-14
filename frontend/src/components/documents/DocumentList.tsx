import React, { useState, useEffect } from "react";
import {
  useFloating,
  autoUpdate,
  offset,
  flip,
  shift,
  useClick,
  useDismiss,
  useRole,
  useInteractions,
} from "@floating-ui/react";
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
import { useConfirm } from "../../context/ConfirmContext";
import { useDocumentWebSocket } from "../../hooks/useDocumentWebSocket";

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
  const { confirm } = useConfirm();
  const [searchTerm, setSearchTerm] = useState("");
  const [semanticSearchActive, setSemanticSearchActive] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [dropdownButtonElement, setDropdownButtonElement] =
    useState<HTMLElement | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [newDocsToast, setNewDocsToast] = useState(false);

  // Floating UI Setup
  const { refs, floatingStyles, context } = useFloating({
    open: openDropdownId !== null,
    onOpenChange: (open) => {
      if (!open) setOpenDropdownId(null);
    },
    elements: { reference: dropdownButtonElement },
    middleware: [offset(8), flip({ padding: 8 }), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  });

  const click = useClick(context);
  const dismiss = useDismiss(context);
  const role = useRole(context);
  const { getFloatingProps } = useInteractions([click, dismiss, role]);

  const dropdownButtonRef = React.useRef<HTMLButtonElement>(null);
  const docCountRef = React.useRef<number>(0);
  // Always hold a reference to the current documents array (fixes stale closure bug in polling)
  const documentsRef = React.useRef<Document[]>([]);

  // Filter State
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>(""); // "completed" | "pending" | "processing" | "failed"
  const [filterClassification, setFilterClassification] = useState<string>("");
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");

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

  // WebSocket for real-time document updates (replaces polling)
  const { isConnected: wsConnected } = useDocumentWebSocket();

  // Listen for WebSocket events
  useEffect(() => {
    const handleDocumentProcessed = () => {
      console.log("[DocumentList] Document processing complete via WebSocket");
      fetchDocuments(); // Refresh full list when any document is done
      setUploading(false);
    };

    const handleStatusUpdate = () => {
      console.log("[DocumentList] Status update via WebSocket");
      if (uploading) {
        fetchDocuments(); // Refresh if we're actively uploading
      }
    };

    window.addEventListener("document_processed", handleDocumentProcessed);
    window.addEventListener("document_status_update", handleStatusUpdate);

    return () => {
      window.removeEventListener("document_processed", handleDocumentProcessed);
      window.removeEventListener("document_status_update", handleStatusUpdate);
    };
  }, [uploading, t]);

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

    // Smart polling: Only poll when there are documents being processed AND WebSocket is disconnected
    const pollInterval = setInterval(async () => {
      try {
        // Skip polling if WebSocket is connected (real-time updates)
        if (wsConnected) {
          return;
        }

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
  }, [wsConnected]);

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
    const ok = await confirm(t("documentList.deleteConfirm"), {
      variant: "danger",
      confirmLabel: t("common.delete"),
    });
    if (!ok) return;

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
      // Search term filter
      const term = searchTerm.toLowerCase();
      const matchFilename = doc.filename.toLowerCase().includes(term);
      const matchContent = doc.content?.toLowerCase().includes(term) ?? false;
      const matchClassification =
        doc.classification?.toLowerCase().includes(term) ?? false;
      const matchesSearch =
        matchFilename || matchContent || matchClassification;

      if (!matchesSearch) return false;

      // Status filter
      if (filterStatus) {
        const normalizedStatus = getNormalizedStatus(doc.processing_status);
        if (normalizedStatus !== filterStatus) return false;
      }

      // Classification filter
      if (filterClassification) {
        if (
          !doc.classification ||
          !doc.classification
            .toLowerCase()
            .includes(filterClassification.toLowerCase())
        ) {
          return false;
        }
      }

      // Date range filter
      if (filterDateFrom || filterDateTo) {
        const docDate = new Date(doc.created_at).getTime();
        if (filterDateFrom) {
          const fromDate = new Date(filterDateFrom).getTime();
          if (docDate < fromDate) return false;
        }
        if (filterDateTo) {
          const toDate = new Date(filterDateTo).getTime();
          if (docDate > toDate) return false;
        }
      }

      return true;
    });
  }, [
    documents,
    searchTerm,
    semanticSearchActive,
    filterStatus,
    filterClassification,
    filterDateFrom,
    filterDateTo,
  ]);

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
    const ok = await confirm(t("documentList.retryAIConfirm"), {
      variant: "warning",
      confirmLabel: t("documentList.retryAI"),
    });
    if (!ok) return;

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
            className="ms-2 text-slate-400 hover:text-white"
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
              className="w-full ps-10 pe-4 py-2.5 bg-white border border-border-light focus:bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 rounded-lg text-sm outline-none transition-all duration-200"
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
              <span className="relative flex h-2 w-2 me-1">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${semanticSearchActive ? "bg-primary-500" : "hidden"}`}
                ></span>
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${semanticSearchActive ? "bg-primary-600" : "bg-neutral-400"}`}
                ></span>
              </span>
              <span>AI Search</span>
            </button>
            <button
              onClick={() => setShowFilterModal(true)}
              className={`flex items-center space-x-2 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                filterStatus ||
                filterClassification ||
                filterDateFrom ||
                filterDateTo
                  ? "bg-primary-50 text-primary-700 border border-primary-200"
                  : "bg-white text-neutral-600 border border-border-light hover:bg-neutral-50"
              }`}
            >
              <Filter className="h-4 w-4" />
              <span>Filter</span>
              {(filterStatus ||
                filterClassification ||
                filterDateFrom ||
                filterDateTo) && (
                <span className="ms-1 inline-flex items-center justify-center h-5 w-5 rounded-full bg-primary-600 text-white text-xs font-bold">
                  {(filterStatus ? 1 : 0) +
                    (filterClassification ? 1 : 0) +
                    (filterDateFrom || filterDateTo ? 1 : 0)}
                </span>
              )}
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

        {/* Applied Filters Display */}
        {(filterStatus ||
          filterClassification ||
          filterDateFrom ||
          filterDateTo) && (
          <div className="mx-4 mt-4 p-3 bg-primary-50 border border-primary-200 rounded-lg">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-primary-700 uppercase">
                {t("documentList.appliedFilters", "Applied Filters")}:
              </span>
              {filterStatus && (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-primary-300 rounded-full text-xs text-neutral-700">
                  <span className="font-medium">
                    {t("documentList.status", "Status")}:
                  </span>
                  <span className="text-primary-600">{filterStatus}</span>
                  <button
                    onClick={() => setFilterStatus("")}
                    className="ms-1 text-neutral-400 hover:text-neutral-600 transition-colors"
                  >
                    ✕
                  </button>
                </div>
              )}
              {filterClassification && (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-primary-300 rounded-full text-xs text-neutral-700">
                  <span className="font-medium">
                    {t("documentList.classification", "Classification")}:
                  </span>
                  <span className="text-primary-600">
                    {filterClassification}
                  </span>
                  <button
                    onClick={() => setFilterClassification("")}
                    className="ms-1 text-neutral-400 hover:text-neutral-600 transition-colors"
                  >
                    ✕
                  </button>
                </div>
              )}
              {(filterDateFrom || filterDateTo) && (
                <div className="inline-flex items-center gap-1 px-2.5 py-1 bg-white border border-primary-300 rounded-full text-xs text-neutral-700">
                  <span className="font-medium">
                    {t("documentList.dateRange", "Date Range")}:
                  </span>
                  <span className="text-primary-600">
                    {filterDateFrom &&
                      new Date(filterDateFrom).toLocaleDateString()}
                    {filterDateFrom && filterDateTo && " - "}
                    {filterDateTo &&
                      new Date(filterDateTo).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => {
                      setFilterDateFrom("");
                      setFilterDateTo("");
                    }}
                    className="ms-1 text-neutral-400 hover:text-neutral-600 transition-colors"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

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
                                  <Tag className="h-3 w-3 me-1 opacity-60" />
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
                            <Calendar className="h-3.5 w-3.5 me-1.5 opacity-70" />
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
                                  className="animate-spin -ms-0.5 me-2 h-3.5 w-3.5"
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
                              setDropdownButtonElement(
                                openDropdownId === doc.id
                                  ? null
                                  : (e.currentTarget as HTMLElement),
                              );
                              setOpenDropdownId(
                                openDropdownId === doc.id ? null : doc.id,
                              );
                            }}
                          >
                            <MoreVertical className="h-4 w-4" />
                          </button>
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

      {/* Dropdown Menu - Rendered at root level to avoid clipping */}
      {openDropdownId !== null && (
        <div
          ref={refs.setFloating}
          style={floatingStyles}
          className="w-48 bg-white border border-border-light rounded-lg shadow-legal-lg z-50 overflow-hidden"
          {...getFloatingProps({
            onClick: (e) => e.stopPropagation(),
          })}
        >
          <div className="py-1">
            {documents.find((d) => d.id === openDropdownId) &&
              getNormalizedStatus(
                documents.find((d) => d.id === openDropdownId)
                  ?.processing_status,
              ) === "completed" && (
                <button
                  className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                  onClick={() => {
                    navigate(`/documents/${openDropdownId}`);
                    setOpenDropdownId(null);
                  }}
                >
                  <FileText className="h-4 w-4 text-neutral-400" />
                  {t("documentList.preview")}
                </button>
              )}
            {documents.find((d) => d.id === openDropdownId) &&
              getNormalizedStatus(
                documents.find((d) => d.id === openDropdownId)
                  ?.processing_status,
              ) === "completed" && (
                <>
                  <button
                    className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                    onClick={() => {
                      setOpenDropdownId(null);
                      showSnackbar(t("documentList.downloadNotImplemented"), {
                        type: "info",
                      });
                    }}
                  >
                    <Download className="h-4 w-4 text-neutral-400" />
                    {t("documentList.download")}
                  </button>
                  <button
                    className="w-full text-left px-4 py-2.5 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-3 transition-colors"
                    onClick={() => {
                      setOpenDropdownId(null);
                      showSnackbar(t("documentList.shareNotImplemented"), {
                        type: "info",
                      });
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
              onClick={(e) => handleDeleteDocument(openDropdownId, e)}
              disabled={deletingId === openDropdownId}
            >
              <Trash2 className="h-4 w-4" />
              {deletingId === openDropdownId
                ? t("common.loading")
                : t("common.delete")}
            </button>
          </div>
        </div>
      )}

      {/* Filter Modal */}
      {showFilterModal && (
        <div className="fixed inset-0 bg-black/50 z-40 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-border-light px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">
                {t("common.filter")}
              </h2>
              <button
                onClick={() => setShowFilterModal(false)}
                className="text-slate-500 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Status Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  {t("documentList.table.status")}
                </label>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full ps-3 pe-10 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                >
                  <option value="">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="processing">Processing</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              {/* Classification Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Classification
                </label>
                <input
                  type="text"
                  value={filterClassification}
                  onChange={(e) => setFilterClassification(e.target.value)}
                  placeholder="e.g., Contract, Invoice..."
                  className="w-full ps-3 pe-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                />
              </div>

              {/* Date Range Filter */}
              <div className="space-y-3">
                <label className="block text-sm font-medium text-slate-700">
                  Date Range
                </label>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    From
                  </label>
                  <input
                    type="date"
                    value={filterDateFrom}
                    onChange={(e) => setFilterDateFrom(e.target.value)}
                    className="w-full ps-3 pe-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">
                    To
                  </label>
                  <input
                    type="date"
                    value={filterDateTo}
                    onChange={(e) => setFilterDateTo(e.target.value)}
                    className="w-full ps-3 pe-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
                  />
                </div>
              </div>
            </div>

            <div className="sticky bottom-0 bg-white border-t border-border-light px-6 py-4 flex gap-3">
              <button
                onClick={() => {
                  setFilterStatus("");
                  setFilterClassification("");
                  setFilterDateFrom("");
                  setFilterDateTo("");
                }}
                className="flex-1 px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={() => setShowFilterModal(false)}
                className="flex-1 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-800 font-medium transition-colors"
              >
                {t("common.filter")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
