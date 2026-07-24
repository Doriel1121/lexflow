import { useState, useEffect, useRef } from "react";
import {
  ArrowLeft,
  Download,
  Tag as TagIcon,
  Bot,
  AlertTriangle,
  Loader2,
  Trash2,
  Building2,
  Sparkles,
} from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../../services/api";
import AskAI from "../ai/AskAI";
import { useSnackbar } from "../../context/SnackbarContext";
import { useTranslation } from "react-i18next";

const getDocumentViewerStatus = (document: any) => {
  const status = document?.processing_status ? String(document.processing_status).toLowerCase() : "completed";
  const stage = document?.processing_stage ? String(document.processing_stage).toLowerCase() : "";
  if (status !== "failed" && (document?.processing_progress ?? 0) >= 100) return "completed";
  if (status !== "failed" && stage.startsWith("completed")) return "completed";
  return status;
};

const getDocumentViewerStatusLabel = (
  status: string,
  stage: string | undefined,
  t: (key: string, defaultValue: string) => string,
) => {
  if (status === "completed") return t("documentViewer.status.ready", "Ready");
  if (status === "failed") return t("documentViewer.status.failed", "Failed");

  const normalizedStage = (stage || "").toLowerCase();
  if (normalizedStage.includes("limit") || normalizedStage.includes("quota")) {
    return t("documentViewer.status.aiSearchLimited", "AI search limited");
  }
  return t("documentViewer.status.analyzing", "AI analyzing...");
};

const getTabLabelKey = (tab: string) => `documentViewer.tabs.${tab}`;
type DocumentViewerPayload = {
  document: any;
};

const detailInFlightRequests = new Map<string, Promise<DocumentViewerPayload>>();
const summaryInFlightRequests = new Map<string, Promise<any>>();
const metadataInFlightRequests = new Map<string, Promise<any>>();
const textInFlightRequests = new Map<string, Promise<any>>();
const DETAIL_REFRESH_STAGES = new Set([
  "ocr_completed",
  "fast_metadata_ready",
  "ai_completed",
  "metadata_saved",
  "ai_analysis",
  "embedding_completed",
  "completed",
  "completed_embedding_partial",
  "completed_without_ai",
]);

const loadDocumentViewerPayload = async (
  documentId: string,
  forceRefresh = false,
): Promise<DocumentViewerPayload> => {
  const inFlight = detailInFlightRequests.get(documentId);
  if (!forceRefresh && inFlight) {
    return inFlight;
  }

  const request = api.get(`/v1/documents/${documentId}`)
    .then((docResponse) => {
      const payload = {
        document: docResponse.data,
      };
      return payload;
    })
    .finally(() => {
      detailInFlightRequests.delete(documentId);
    });

  detailInFlightRequests.set(documentId, request);
  return request;
};

const loadDocumentSummary = async (
  documentId: string,
  forceRefresh = false,
): Promise<any> => {
  const inFlight = summaryInFlightRequests.get(documentId);
  if (!forceRefresh && inFlight) {
    return inFlight;
  }

  const request = api
    .get(`/v1/documents/${documentId}/summary`)
    .then((response) => response.data)
    .catch(() => null)
    .finally(() => {
      summaryInFlightRequests.delete(documentId);
    });

  summaryInFlightRequests.set(documentId, request);
  return request;
};

const loadDocumentMetadata = async (
  documentId: string,
  forceRefresh = false,
): Promise<any> => {
  const inFlight = metadataInFlightRequests.get(documentId);
  if (!forceRefresh && inFlight) {
    return inFlight;
  }

  const request = api
    .get(`/v1/documents/${documentId}/metadata`)
    .then((response) => response.data)
    .catch(() => null)
    .finally(() => {
      metadataInFlightRequests.delete(documentId);
    });

  metadataInFlightRequests.set(documentId, request);
  return request;
};

const loadDocumentText = async (
  documentId: string,
  forceRefresh = false,
): Promise<any> => {
  const inFlight = textInFlightRequests.get(documentId);
  if (!forceRefresh && inFlight) {
    return inFlight;
  }

  const request = api
    .get(`/v1/documents/${documentId}/text`)
    .then((response) => response.data)
    .catch(() => null)
    .finally(() => {
      textInFlightRequests.delete(documentId);
    });

  textInFlightRequests.set(documentId, request);
  return request;
};

export function DocumentViewer() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { showSnackbar } = useSnackbar();
  const { i18n, t } = useTranslation();
  const [activeTab, setActiveTab] = useState("summary");
  const [loading, setLoading] = useState(true);
  const [document, setDocument] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [metadata, setMetadata] = useState<any>(null);
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [summaryLoaded, setSummaryLoaded] = useState(false);
  const [metadataLoaded, setMetadataLoaded] = useState(false);
  const [ocrLoaded, setOcrLoaded] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeTabRef = useRef(activeTab);
  const summaryLoadedRef = useRef(false);
  const metadataLoadedRef = useRef(false);
  const ocrLoadedRef = useRef(false);

  // Normalize OCR content: collapse single newlines into spaces, preserving paragraph breaks.
  const normalizeContent = (text: string | null | undefined): string => {
    if (!text) return "No content available";
    const paragraphs = text
      .replace(/\r\n/g, "\n")
      .split(/\n{2,}/)
      .map((para) => para.replace(/\n/g, " ").replace(/  +/g, " ").trim())
      .filter((p) => p.length > 0);
    return paragraphs.join("\n\n");
  };

  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  useEffect(() => {
    summaryLoadedRef.current = summaryLoaded;
  }, [summaryLoaded]);

  useEffect(() => {
    metadataLoadedRef.current = metadataLoaded;
  }, [metadataLoaded]);

  useEffect(() => {
    ocrLoadedRef.current = ocrLoaded;
  }, [ocrLoaded]);

  useEffect(() => {
    setDocument(null);
    setSummary(null);
    setMetadata(null);
    setOcrText(null);
    setSummaryLoaded(false);
    setMetadataLoaded(false);
    setOcrLoaded(false);
    summaryLoadedRef.current = false;
    metadataLoadedRef.current = false;
    ocrLoadedRef.current = false;

    if (id) {
      fetchDocumentData();
    }

    const scheduleRefresh = () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = setTimeout(() => {
        fetchDocumentDataSilent(true);
        const currentTab = activeTabRef.current;
        if (currentTab === "summary" || summaryLoadedRef.current) {
          fetchSummaryData(true);
        }
        if (currentTab === "entities" || metadataLoadedRef.current) {
          fetchMetadataData(true);
        }
        if (currentTab === "ocr" || ocrLoadedRef.current) {
          fetchOcrText(true);
        }
        refreshTimerRef.current = null;
      }, 500);
    };

    const handleDocumentStatus = (event: Event) => {
      const customEvent = event as CustomEvent;
      const detail = customEvent.detail || {};
      if (detail.document_id !== Number(id)) return;

      const stage = detail.stage;
      setDocument((prev: any) =>
        prev
          ? {
              ...prev,
              processing_status: detail.status ?? prev.processing_status,
              processing_stage: stage ?? prev.processing_stage,
              processing_progress: detail.progress ?? prev.processing_progress,
            }
          : prev,
      );

      if (stage && DETAIL_REFRESH_STAGES.has(stage)) {
        scheduleRefresh();
      }
    };

    const handleDocumentProcessed = (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail?.document_id === Number(id)) {
        scheduleRefresh();
      }
    };

    window.addEventListener("document_status_update", handleDocumentStatus);
    window.addEventListener("document_processed", handleDocumentProcessed);

    return () => {
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
      window.removeEventListener(
        "document_status_update",
        handleDocumentStatus,
      );
      window.removeEventListener("document_processed", handleDocumentProcessed);
    };
  }, [id]);

  useEffect(() => {
    if (!id || loading) return;

    if (activeTab === "summary") {
      fetchSummaryData();
    }
    if (activeTab === "entities") {
      fetchMetadataData();
    }
    if (activeTab === "ocr") {
      fetchOcrText();
    }
  }, [id, loading, activeTab]);

  const fetchDocumentData = async () => {
    setLoading(true);
    await fetchDocumentDataSilent();
    setLoading(false);
  };

  const fetchDocumentDataSilent = async (forceRefresh = false) => {
    if (!id) return;

    try {
      const payload = await loadDocumentViewerPayload(id, forceRefresh);
      setDocument(payload.document);
    } catch (error) {
      console.error("Failed to load document:", error);
    }
  };
  const fetchSummaryData = async (forceRefresh = false) => {
    if (!id || (summaryLoaded && !forceRefresh)) return;

    setSummaryLoading(true);
    try {
      const payload = await loadDocumentSummary(id, forceRefresh);
      setSummary(payload);
      setSummaryLoaded(true);
      summaryLoadedRef.current = true;
    } catch (error) {
      console.error("Failed to load document summary:", error);
    } finally {
      setSummaryLoading(false);
    }
  };

  const fetchMetadataData = async (forceRefresh = false) => {
    if (!id || (metadataLoaded && !forceRefresh)) return;

    setMetadataLoading(true);
    try {
      const payload = await loadDocumentMetadata(id, forceRefresh);
      setMetadata(payload);
      setMetadataLoaded(true);
      metadataLoadedRef.current = true;
    } catch (error) {
      console.error("Failed to load document metadata:", error);
    } finally {
      setMetadataLoading(false);
    }
  };

  const fetchOcrText = async (forceRefresh = false) => {
    if (!id || (ocrLoaded && !forceRefresh)) return;

    setOcrLoading(true);
    try {
      const payload = await loadDocumentText(id, forceRefresh);
      setOcrText(payload?.content ?? null);
      setOcrLoaded(true);
      ocrLoadedRef.current = true;
      if (payload) {
        setDocument((prev: any) =>
          prev
            ? {
                ...prev,
                language: payload.language ?? prev.language,
                page_count: payload.page_count ?? prev.page_count,
              }
            : prev,
        );
      }
    } catch (error) {
      console.error("Failed to load OCR text:", error);
    } finally {
      setOcrLoading(false);
    }
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/v1/documents/${id}`);
      navigate("/documents");
    } catch (error) {
      console.error("Failed to delete document:", error);
      showSnackbar("Failed to delete document", { type: "error" });
    } finally {
      setShowDeleteConfirm(false);
    }
  };

  if (loading) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!document) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center">
        <p className="text-slate-500">{t("documentViewer.notFound")}</p>
      </div>
    );
  }

  const normalizedStatus = getDocumentViewerStatus(document);
  const hasOcrMetadata = Boolean(document.page_count || document.language);
  const hasOcrText = Boolean(ocrText && ocrText.length > 0);
  const isSummaryReady = summaryLoaded;
  const isMetadataReady = metadataLoaded;
  const isAIReady = Boolean(summary) || Boolean(metadata);
  const documentTags = Array.isArray(document.tags) ? document.tags : [];
  const isRTL = i18n.language?.toLowerCase().startsWith("he");

  // --- INITIAL OCR LOADING STATE ---
  if (
    !hasOcrMetadata &&
    (normalizedStatus === "pending" || normalizedStatus === "processing")
  ) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center bg-slate-50">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-slate-100 flex flex-col items-center text-center">
          <div className="relative mb-6">
            <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-75"></div>
            <div className="relative bg-gradient-to-br from-blue-500 to-indigo-600 p-4 rounded-full shadow-lg">
              <Sparkles className="h-8 w-8 text-white animate-pulse" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">
            {t("documentViewer.readingTitle")}
          </h2>
          <p className="text-slate-500 text-sm mb-8 leading-relaxed">
            {t("documentViewer.readingDescription")}
          </p>
          <div className="w-full space-y-4">
            <div className="h-2 bg-slate-100 rounded overflow-hidden">
              <div className="h-full bg-blue-500 w-1/3 animate-[slide_2s_ease-in-out_infinite]"></div>
            </div>
            <div className="flex items-center justify-center space-x-3 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span>{t("documentViewer.runningOcr")}</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --- FAILED STATE (ONLY IF NO CONTENT) ---
  if (normalizedStatus === "failed" && !hasOcrMetadata) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center bg-slate-50">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-red-100 flex flex-col items-center text-center">
          <div className="relative mb-6">
            <div className="relative bg-red-100 p-4 rounded-full shadow-inner border border-red-200">
              <AlertTriangle className="h-8 w-8 text-red-600" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">
            {t("documentViewer.processingFailed")}
          </h2>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            {t("documentViewer.processingFailedDescription")}
          </p>
          <div className="flex space-x-3 w-full">
            <button
              onClick={() => navigate("/documents")}
              className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
            >
              {t("documentViewer.backToDocuments")}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
            >
              {t("documentViewer.deleteFile")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleRetryAI = async () => {
    try {
      await api.post(`/v1/documents/retry-ai-analysis/${id}`);
      fetchDocumentData();
      fetchSummaryData(true);
      fetchMetadataData(true);
      showSnackbar("Analysis retry queued.", { type: "success" });
    } catch (e) {
      showSnackbar("Failed to retry analysis.", { type: "error" });
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-background">
      {/* Viewer Header */}
      <div className="bg-card border-b border-border p-4 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate("/documents")}
            className="p-2 hover:bg-muted rounded-full text-muted-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-800">
                {document.filename}
              </h1>
              {normalizedStatus === "failed" && (
                <div className="flex items-center space-x-2 text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-100">
                  <AlertTriangle className="h-3 w-3" />
                  <span className="text-[10px] font-bold uppercase tracking-tight">
                    {t("documentViewer.status.processingError")}
                  </span>
                  <button
                    onClick={handleRetryAI}
                    className="text-[10px] underline hover:text-red-800 transition-colors"
                  >
                    {t("documentViewer.retry")}
                  </button>
                </div>
              )}
            </div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground">
              <span
                className={`px-1.5 py-0.5 rounded font-medium uppercase tracking-wider text-[10px] ${normalizedStatus === "completed" ? "bg-emerald-100 text-emerald-700" : normalizedStatus === "failed" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700 animate-pulse"}`}
              >
                {getDocumentViewerStatusLabel(normalizedStatus, document.processing_stage, t)}
              </span>
              <span>•</span>
              <span>
                {document.classification} •{" "}
                {document.language?.toUpperCase() || t("documentViewer.unknown")} •{" "}
                {t("documentViewer.pageCount", { count: document.page_count || 0 })}
              </span>
              {document.ai_health?.analysis_mode === "chunked" && (
                <>
                  <span>•</span>
                  <span
                    className="px-1.5 py-0.5 rounded bg-violet-100 text-violet-800 text-[10px] font-semibold"
                    title={t("documentViewer.analysisModeChunkedHint")}
                  >
                    {t("documentViewer.analysisModeChunked", {
                      count:
                        document.ai_health?.chunks_analyzed ??
                        "?",
                    })}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button className="p-2 hover:bg-muted rounded-lg text-muted-foreground">
            <Download className="h-5 w-5" />
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="p-2 hover:bg-red-50 rounded-lg text-red-600 transition-colors"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Original Document (PDF/DOCX) */}
        <div className="w-1/2 bg-slate-50 border-r border-border flex flex-col">
          {document.s3_url &&
          document.filename.toLowerCase().endsWith(".pdf") ? (
            <iframe
              src={document.s3_url}
              title={document.filename}
              className="w-full h-full border-0"
            />
          ) : (
            <div className="p-8 overflow-y-auto">
              <div className="bg-white shadow-sm max-w-2xl mx-auto p-8 text-slate-800 text-sm leading-relaxed border border-slate-200 rounded-lg relative">
                {!isAIReady && !summaryLoading && normalizedStatus !== "failed" && (
                  <div className="absolute top-4 end-4 flex items-center gap-2 px-2 py-1 bg-blue-50 text-blue-600 rounded-md text-[10px] font-bold border border-blue-100 animate-pulse">
                    <Sparkles className="h-3 w-3" />
                    {t("documentViewer.aiAnalysisInProgress")}
                  </div>
                )}
                <p
                  className={`whitespace-pre-wrap font-sans ${isRTL ? "font-[var(--font-hebrew)]" : ""}`}
                  dir={isRTL ? "rtl" : "ltr"}
                  lang={i18n.language}
                  style={{
                    fontFamily: isRTL
                      ? "var(--font-hebrew)"
                      : "var(--font-english)",
                  }}
                >
                  {hasOcrText
                    ? normalizeContent(ocrText)
                    : t("documentViewer.openOcrTab")}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Pane: Intelligence */}
        <div className="w-1/2 bg-card flex flex-col">
          <div className="flex border-b border-border">
            {["summary", "entities", "ask", "ocr"].map((tab) => (
              <button
                key={tab}
                onClick={() => handleTabChange(tab)}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors uppercase tracking-wider ${activeTab === tab ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-slate-800"}`}
              >
                {t(getTabLabelKey(tab))}
              </button>
            ))}
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            {activeTab === "ask" && (
              <div className="h-full animate-in fade-in slide-in-from-bottom-2 duration-300">
                <AskAI
                  documentIds={[Number(id)]}
                  title={t("documentViewer.askTitle", { filename: document.filename })}
                />
              </div>
            )}

            {activeTab === "summary" && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {summaryLoading || !isSummaryReady ? (
                  <div className="bg-blue-50/30 border border-blue-100/50 rounded-xl p-8 flex flex-col items-center text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500 mb-4" />
                    <h3 className="font-bold text-blue-900 text-sm mb-2">
                      {t("documentViewer.generatingInsights")}
                    </h3>
                    <p className="text-xs text-blue-700/70 max-w-[250px] leading-relaxed">
                      {t("documentViewer.generatingInsightsDescription")}
                    </p>
                  </div>
                ) : (
                  <>
                    {document.ai_health?.analysis_mode === "chunked" && (
                      <p className="text-xs text-violet-700 bg-violet-50 border border-violet-100 rounded-lg px-3 py-2">
                        {t("documentViewer.analysisModeChunkedBanner")}
                      </p>
                    )}
                    {summary?.content && (
                      <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                        <div className="flex items-start space-x-3">
                          <Bot className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
                          <div className="flex-1">
                            <h3 className="font-bold text-blue-900 text-sm mb-2">
                              {t("documentViewer.aiSummary")}
                            </h3>
                            <pre
                              className={`text-sm text-blue-800 leading-relaxed whitespace-pre-wrap font-sans ${isRTL ? "font-[var(--font-hebrew)]" : ""}`}
                              dir={isRTL ? "rtl" : "ltr"}
                              lang={i18n.language}
                              style={{
                                fontFamily: isRTL
                                  ? "var(--font-hebrew)"
                                  : "var(--font-english)",
                              }}
                            >
                              {summary.content}
                            </pre>
                          </div>
                        </div>
                      </div>
                    )}
                    {summary?.key_dates?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.importantDates")}
                        </h3>
                        <div className="space-y-2">
                          {summary.key_dates.map(
                            (d: any, i: number) => (
                              <div
                                key={i}
                                className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm"
                              >
                                <div className="font-semibold text-slate-800">
                                  {d.date || t("documentViewer.unknownDate")}
                                </div>
                                {d.description && (
                                  <div className="text-xs text-slate-500 mt-1">
                                    {d.description}
                                  </div>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                    {documentTags.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.tags")}
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {documentTags.map((tag: any, i: number) => (
                            <span
                              key={i}
                              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-secondary-50 text-secondary-700 border border-secondary-200"
                            >
                              <TagIcon className="h-3 w-3 mr-1 opacity-60" />
                              {typeof tag === "string" ? tag : tag.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {summary?.parties?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.partiesInvolved")}
                        </h3>
                        <div className="space-y-2">
                          {summary.parties.map(
                            (p: any, i: number) => (
                              <div
                                key={i}
                                className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm font-medium"
                              >
                                {typeof p === "object" ? p.name : p}
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === "entities" && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {metadataLoading || !isMetadataReady ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="p-4 bg-slate-50/50 rounded-lg border border-slate-100 animate-pulse flex gap-3"
                      >
                        <div className="h-10 w-10 rounded-full bg-slate-200" />
                        <div className="flex-1 space-y-2">
                          <div className="h-3 bg-slate-200 rounded w-1/3" />
                          <div className="h-2 bg-slate-200 rounded w-1/2" />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {metadata?.entities?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.entities")}
                        </h3>
                        <div className="space-y-3">
                          {metadata.entities.map(
                            (ent: any, i: number) => (
                              <div
                                key={i}
                                className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-3"
                              >
                                <Building2 className="h-5 w-5 text-indigo-500 mt-1" />
                                <div>
                                  <p className="font-bold text-slate-900">
                                    {ent.name}
                                  </p>
                                  <p className="text-xs text-slate-500">
                                    {ent.role}
                                  </p>
                                  {ent.id_number && (
                                    <p className="text-[11px] text-slate-500">
                                      {t("documentViewer.entityId")}: {ent.id_number}
                                    </p>
                                  )}
                                  {ent.firm && (
                                    <p className="text-[11px] text-slate-500">
                                      {t("documentViewer.entityFirm")}: {ent.firm}
                                    </p>
                                  )}
                                  {ent.bar_number && (
                                    <p className="text-[11px] text-slate-500">
                                      {t("documentViewer.entityBar")}: {ent.bar_number}
                                    </p>
                                  )}
                                </div>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                    {metadata?.dates?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.dates")}
                        </h3>
                        <div className="space-y-2">
                          {metadata.dates.map(
                            (d: any, i: number) => (
                              <div
                                key={i}
                                className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm"
                              >
                                <div className="font-semibold text-slate-800">
                                  {d.date || t("documentViewer.unknownDate")}
                                </div>
                                {d.description && (
                                  <div className="text-xs text-slate-500 mt-1">
                                    {d.description}
                                  </div>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                    {metadata?.amounts?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">
                          {t("documentViewer.amounts")}
                        </h3>
                        <div className="space-y-2">
                          {metadata.amounts.map(
                            (a: any, i: number) => (
                              <div
                                key={i}
                                className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm"
                              >
                                <div className="font-semibold text-slate-800">
                                  {a.amount || t("documentViewer.amount")}
                                  {a.currency ? ` ${a.currency}` : ""}
                                </div>
                                {a.description && (
                                  <div className="text-xs text-slate-500 mt-1">
                                    {a.description}
                                  </div>
                                )}
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === "ocr" && (
              <div
                dir={isRTL ? "rtl" : "ltr"}
                lang={i18n.language}
                className="prose prose-sm max-w-none text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs whitespace-pre-wrap font-sans"
              >
                {ocrLoading ? (
                  <div className="flex items-center gap-2 text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {t("documentViewer.loadingOcrText")}
                  </div>
                ) : hasOcrText ? (
                  ocrText
                ) : (
                  t("documentViewer.ocrNotAvailable")
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
            <div className="flex items-start space-x-4">
              <div className="p-3 bg-red-100 rounded-full">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-slate-900 mb-2">
                  {t("documentViewer.deleteDocument")}
                </h3>
                <p className="text-sm text-slate-600 mb-4">
                  {t("documentViewer.deleteConfirmation")}{" "}
                  <span className="font-semibold">{document?.filename}</span>?
                </p>
                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="flex-1 px-4 py-2 bg-slate-100 rounded-lg font-medium transition-colors"
                  >
                    {t("common.cancel")}
                  </button>
                  <button
                    onClick={handleDelete}
                    className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg font-medium transition-colors"
                  >
                    {t("common.delete")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
