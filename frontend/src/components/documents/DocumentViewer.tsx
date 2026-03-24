import { useState, useEffect } from 'react';
import { ArrowLeft, Download, Tag as TagIcon, Bot, AlertTriangle, Loader2, Trash2, Building2, Sparkles } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import AskAI from '../ai/AskAI';
import { useSnackbar } from '../../context/SnackbarContext';
import { useTranslation } from 'react-i18next';

export function DocumentViewer() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { showSnackbar } = useSnackbar();
  const { i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState('summary');
  const [loading, setLoading] = useState(true);
  const [document, setDocument] = useState<any>(null);
  const [intelligence, setIntelligence] = useState<any>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Normalize OCR content: collapse single newlines into spaces, preserving paragraph breaks.
  const normalizeContent = (text: string | null | undefined): string => {
    if (!text) return 'No content available';
    const paragraphs = text
      .replace(/\r\n/g, '\n')
      .split(/\n{2,}/)
      .map(para => para.replace(/\n/g, ' ').replace(/  +/g, ' ').trim())
      .filter(p => p.length > 0);
    return paragraphs.join('\n\n');
  };

  useEffect(() => {
    if (id) {
      fetchDocumentData();
    }

    // Listen for WebSocket events
    const handleDocumentStatus = (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail.document_id === Number(id)) {
        // Silent refresh to pick up new stages (OCR ready, AI ready)
        fetchDocumentDataSilent();
      }
    };

    window.addEventListener('document_status_update', handleDocumentStatus);
    window.addEventListener('document_processed', handleDocumentStatus);
    
    return () => {
      window.removeEventListener('document_status_update', handleDocumentStatus);
      window.removeEventListener('document_processed', handleDocumentStatus);
    };
  }, [id]);

  const fetchDocumentData = async () => {
    setLoading(true);
    await fetchDocumentDataSilent();
    setLoading(false);
  };

  const fetchDocumentDataSilent = async () => {
    try {
      const [docResponse, intelligenceResponse] = await Promise.all([
        api.get(`/v1/documents/${id}`),
        api.get(`/v1/documents/${id}/intelligence`).catch(() => ({ data: null }))
      ]);
      setDocument(docResponse.data);
      setIntelligence(intelligenceResponse.data);
    } catch (error) {
      console.error('Failed to load document:', error);
    }
  };

  const handleDelete = async () => {
    try {
      await api.delete(`/v1/documents/${id}`);
      navigate('/documents');
    } catch (error) {
      console.error('Failed to delete document:', error);
      showSnackbar('Failed to delete document', { type: 'error' });
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
        <p className="text-slate-500">Document not found</p>
      </div>
    );
  }

  const normalizedStatus = document.processing_status ? document.processing_status.toLowerCase() : 'completed';
  const isOCRReady = document.content && document.content.length > 0;
  const isAIReady = !!intelligence && (intelligence.summary || intelligence.metadata);
  const isRTL = i18n.language?.toLowerCase().startsWith('he');

  // --- INITIAL OCR LOADING STATE ---
  if (!isOCRReady && (normalizedStatus === 'pending' || normalizedStatus === 'processing')) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center bg-slate-50">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-slate-100 flex flex-col items-center text-center">
          <div className="relative mb-6">
            <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-75"></div>
            <div className="relative bg-gradient-to-br from-blue-500 to-indigo-600 p-4 rounded-full shadow-lg">
              <Sparkles className="h-8 w-8 text-white animate-pulse" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Reading Document</h2>
          <p className="text-slate-500 text-sm mb-8 leading-relaxed">
            LegalOS AI is extracting text from your document. You will be able to view the text in a few moments.
          </p>
          <div className="w-full space-y-4">
            <div className="h-2 bg-slate-100 rounded overflow-hidden">
              <div className="h-full bg-blue-500 w-1/3 animate-[slide_2s_ease-in-out_infinite]"></div>
            </div>
            <div className="flex items-center justify-center space-x-3 text-sm text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span>Running OCR...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --- FAILED STATE (ONLY IF NO CONTENT) ---
  if (normalizedStatus === 'failed' && !isOCRReady) {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center bg-slate-50">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-red-100 flex flex-col items-center text-center">
          <div className="relative mb-6">
            <div className="relative bg-red-100 p-4 rounded-full shadow-inner border border-red-200">
              <AlertTriangle className="h-8 w-8 text-red-600" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-slate-900 mb-2">Processing Failed</h2>
          <p className="text-slate-500 text-sm mb-6 leading-relaxed">
            LegalOS AI encountered an error while trying to read and analyze this document.
          </p>
          <div className="flex space-x-3 w-full">
            <button onClick={() => navigate('/documents')} className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors">Back to Documents</button>
            <button onClick={() => setShowDeleteConfirm(true)} className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors">Delete File</button>
          </div>
        </div>
      </div>
    );
  }

  const handleRetryAI = async () => {
    try {
      await api.post(`/v1/documents/retry-ai-analysis/${id}`);
      fetchDocumentData();
      showSnackbar('Analysis retry queued.', { type: 'success' });
    } catch (e) {
      showSnackbar('Failed to retry analysis.', { type: 'error' });
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-background">
      {/* Viewer Header */}
      <div className="bg-card border-b border-border p-4 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-4">
          <button onClick={() => navigate('/documents')} className="p-2 hover:bg-muted rounded-full text-muted-foreground transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-800">{document.filename}</h1>
              {normalizedStatus === 'failed' && (
                <div className="flex items-center space-x-2 text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-100">
                  <AlertTriangle className="h-3 w-3" />
                  <span className="text-[10px] font-bold uppercase tracking-tight">Processing Error</span>
                  <button onClick={handleRetryAI} className="text-[10px] underline hover:text-red-800 transition-colors">Retry</button>
                </div>
              )}
            </div>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground">
              <span className={`px-1.5 py-0.5 rounded font-medium uppercase tracking-wider text-[10px] ${normalizedStatus === 'completed' ? 'bg-emerald-100 text-emerald-700' : normalizedStatus === 'failed' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700 animate-pulse'}`}>
                {normalizedStatus === 'completed' ? 'Ready' : normalizedStatus === 'failed' ? 'Failed' : 'AI Analyzing...'}
              </span>
              <span>•</span>
              <span>{document.classification} • {document.language?.toUpperCase() || 'UNKNOWN'} • {document.page_count || 0} pages</span>
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <button className="p-2 hover:bg-muted rounded-lg text-muted-foreground"><Download className="h-5 w-5" /></button>
          <button onClick={() => setShowDeleteConfirm(true)} className="p-2 hover:bg-red-50 rounded-lg text-red-600 transition-colors"><Trash2 className="h-5 w-5" /></button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Original Document (PDF) */}
        <div className="w-1/2 bg-slate-50 border-r border-border flex flex-col">
          {document.s3_url ? (
            <iframe
              src={document.s3_url}
              title={document.filename}
              className="w-full h-full border-0"
            />
          ) : (
            <div className="p-8 overflow-y-auto">
              <div className="bg-white shadow-sm max-w-2xl mx-auto p-8 text-slate-800 text-sm leading-relaxed border border-slate-200 rounded-lg relative">
                {!isAIReady && normalizedStatus !== 'failed' && (
                  <div className="absolute top-4 end-4 flex items-center gap-2 px-2 py-1 bg-blue-50 text-blue-600 rounded-md text-[10px] font-bold border border-blue-100 animate-pulse">
                    <Sparkles className="h-3 w-3" />
                    AI ANALYSIS IN PROGRESS
                  </div>
                )}
                <p
                  className="whitespace-pre-wrap font-sans"
                  dir={isRTL ? 'rtl' : 'ltr'}
                  lang={i18n.language}
                >
                  {normalizeContent(document.content)}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right Pane: Intelligence */}
        <div className="w-1/2 bg-card flex flex-col">
          <div className="flex border-b border-border">
            {['summary', 'entities', 'ask', 'ocr'].map(tab => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors uppercase tracking-wider ${activeTab === tab ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-slate-800'}`}
              >
                {tab === 'ask' ? 'Ask AI' : tab}
              </button>
            ))}
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            {activeTab === 'ask' && (
              <div className="h-full animate-in fade-in slide-in-from-bottom-2 duration-300">
                <AskAI 
                  documentIds={[Number(id)]} 
                  title={`Ask about ${document.filename}`}
                />
              </div>
            )}

            {activeTab === 'summary' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {!isAIReady ? (
                  <div className="bg-blue-50/30 border border-blue-100/50 rounded-xl p-8 flex flex-col items-center text-center">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-500 mb-4" />
                    <h3 className="font-bold text-blue-900 text-sm mb-2">Generating AI Insights...</h3>
                    <p className="text-xs text-blue-700/70 max-w-[250px] leading-relaxed">
                      We're currently analyzing the text to extract parties, dates, and a professional summary. This will update automatically.
                    </p>
                  </div>
                ) : (
                  <>
                    {intelligence?.summary?.content && (
                      <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                        <div className="flex items-start space-x-3">
                          <Bot className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
                          <div className="flex-1">
                            <h3 className="font-bold text-blue-900 text-sm mb-2">AI Summary</h3>
                            <pre className="text-sm text-blue-800 leading-relaxed whitespace-pre-wrap font-sans" dir={isRTL ? 'rtl' : 'ltr'} lang={i18n.language}>{intelligence.summary.content}</pre>
                          </div>
                        </div>
                      </div>
                    )}
                    {intelligence?.summary?.key_dates?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Important Dates</h3>
                        <div className="space-y-2">
                          {intelligence.summary.key_dates.map((d: any, i: number) => (
                            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm">
                              <div className="font-semibold text-slate-800">{d.date || 'Unknown date'}</div>
                              {d.description && <div className="text-xs text-slate-500 mt-1">{d.description}</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {intelligence?.tags?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Tags</h3>
                        <div className="flex flex-wrap gap-2">
                          {intelligence.tags.map((t: string, i: number) => (
                            <span key={i} className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-secondary-50 text-secondary-700 border border-secondary-200">
                              <TagIcon className="h-3 w-3 mr-1 opacity-60" />
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {intelligence?.summary?.parties?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Parties Involved</h3>
                        <div className="space-y-2">
                          {intelligence.summary.parties.map((p: any, i: number) => (
                            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm font-medium">{typeof p === 'object' ? p.name : p}</div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            {activeTab === 'entities' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {!isAIReady ? (
                  <div className="space-y-4">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="p-4 bg-slate-50/50 rounded-lg border border-slate-100 animate-pulse flex gap-3">
                        <div className="h-10 w-10 rounded-full bg-slate-200" />
                        <div className="flex-1 space-y-2"><div className="h-3 bg-slate-200 rounded w-1/3" /><div className="h-2 bg-slate-200 rounded w-1/2" /></div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-6">
                    {intelligence?.metadata?.entities?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Entities</h3>
                        <div className="space-y-3">
                          {intelligence.metadata.entities.map((ent: any, i: number) => (
                            <div key={i} className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex items-start gap-3">
                              <Building2 className="h-5 w-5 text-indigo-500 mt-1" />
                              <div>
                                <p className="font-bold text-slate-900">{ent.name}</p>
                                <p className="text-xs text-slate-500">{ent.role}</p>
                                {ent.id_number && <p className="text-[11px] text-slate-500">ID: {ent.id_number}</p>}
                                {ent.firm && <p className="text-[11px] text-slate-500">Firm: {ent.firm}</p>}
                                {ent.bar_number && <p className="text-[11px] text-slate-500">Bar: {ent.bar_number}</p>}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {intelligence?.metadata?.dates?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Dates</h3>
                        <div className="space-y-2">
                          {intelligence.metadata.dates.map((d: any, i: number) => (
                            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm">
                              <div className="font-semibold text-slate-800">{d.date || 'Unknown date'}</div>
                              {d.description && <div className="text-xs text-slate-500 mt-1">{d.description}</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {intelligence?.metadata?.amounts?.length > 0 && (
                      <div>
                        <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Amounts</h3>
                        <div className="space-y-2">
                          {intelligence.metadata.amounts.map((a: any, i: number) => (
                            <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm">
                              <div className="font-semibold text-slate-800">
                                {a.amount || 'Amount'}{a.currency ? ` ${a.currency}` : ''}
                              </div>
                              {a.description && <div className="text-xs text-slate-500 mt-1">{a.description}</div>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'ocr' && (
              <div dir={isRTL ? 'rtl' : 'ltr'} lang={i18n.language} className="prose prose-sm max-w-none text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs whitespace-pre-wrap font-sans">
                {document.content}
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
              <div className="p-3 bg-red-100 rounded-full"><Trash2 className="h-6 w-6 text-red-600" /></div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-slate-900 mb-2">Delete Document</h3>
                <p className="text-sm text-slate-600 mb-4">Are you sure you want to delete <span className="font-semibold">{document?.filename}</span>?</p>
                <div className="flex space-x-3">
                  <button onClick={() => setShowDeleteConfirm(false)} className="flex-1 px-4 py-2 bg-slate-100 rounded-lg font-medium transition-colors">Cancel</button>
                  <button onClick={handleDelete} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg font-medium transition-colors">Delete</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
