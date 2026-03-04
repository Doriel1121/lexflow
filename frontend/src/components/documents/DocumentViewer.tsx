import { useState, useEffect } from 'react';
import { ArrowLeft, Download, Tag as TagIcon, Bot, AlertTriangle, Loader2, Trash2, FolderGit2, Hash, Building2, Sparkles } from 'lucide-react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import api from '../../services/api';

export function DocumentViewer() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [activeTab, setActiveTab] = useState('summary');
  const [loading, setLoading] = useState(true);
  const [document, setDocument] = useState<any>(null);
  const [intelligence, setIntelligence] = useState<any>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Normalize OCR content: collapse single newlines (OCR line wrapping) into spaces,
  // preserving intentional paragraph breaks (double newlines).
  const normalizeContent = (text: string | null | undefined): string => {
    if (!text) return 'No content available';
    // Split on double newlines to get real paragraphs, then within each paragraph
    // replace all remaining newlines/extra whitespace with a single space.
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

    // Listen for WebSocket events indicating a background task finished
    const handleDocumentProcessed = (event: Event) => {
      const customEvent = event as CustomEvent;
      if (customEvent.detail.document_id === Number(id)) {
        fetchDocumentData();
      }
    };

    window.addEventListener('document_processed', handleDocumentProcessed);
    
    return () => {
      window.removeEventListener('document_processed', handleDocumentProcessed);
    };
  }, [id]);

  const fetchDocumentData = async () => {
    setLoading(true);
    try {
      const [docResponse, intelligenceResponse] = await Promise.all([
        api.get(`/v1/documents/${id}`),
        api.get(`/v1/documents/${id}/intelligence`).catch(() => ({ data: null }))
      ]);
      setDocument(docResponse.data);
      setIntelligence(intelligenceResponse.data);
    } catch (error) {
      console.error('Failed to load document:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await api.delete(`/v1/documents/${id}`);
      navigate('/documents');
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document');
    } finally {
      setDeleting(false);
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

  // --- PROCESSING SKELETON STATE ---
  const normalizedStatus = document.processing_status ? document.processing_status.toLowerCase() : 'completed';
  if (normalizedStatus === 'pending' || normalizedStatus === 'processing') {
    return (
      <div className="h-[calc(100vh-8rem)] flex items-center justify-center bg-slate-50">
        <div className="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-slate-100 flex flex-col items-center text-center">
          <div className="relative mb-6">
            <div className="absolute inset-0 bg-blue-100 rounded-full animate-ping opacity-75"></div>
            <div className="relative bg-gradient-to-br from-blue-500 to-indigo-600 p-4 rounded-full shadow-lg">
              <Sparkles className="h-8 w-8 text-white animate-pulse" />
            </div>
          </div>
          
          <h2 className="text-xl font-bold text-slate-900 mb-2">Analyzing Document</h2>
          <p className="text-slate-500 text-sm mb-8 leading-relaxed">
            LexFlow AI is currently extracting text, identifying entities, and analyzing legal risk factors. This usually takes a few seconds.
          </p>

          <div className="w-full space-y-4">
            <div className="h-2 bg-slate-100 rounded overflow-hidden">
              <div className="h-full bg-blue-500 w-1/3 animate-[slide_2s_ease-in-out_infinite]"></div>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center space-x-3 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                <span>Running Optical Character Recognition (OCR)...</span>
              </div>
              <div className="flex items-center space-x-3 text-sm text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                <span>Generating Vector Embeddings...</span>
              </div>
              <div className="flex items-center space-x-3 text-sm text-slate-400">
                <div className="h-4 w-4 border-2 border-slate-200 rounded-full border-t-slate-400 animate-spin"></div>
                <span>Extracting smart collections...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // --- FAILED PROCESSING STATE ---
  if (normalizedStatus === 'failed') {
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
            LexFlow AI encountered an error while trying to read and analyze this document. The file might be corrupted, password-protected, or in an unsupported format.
          </p>

          <div className="flex space-x-3 w-full">
            <button 
              onClick={() => navigate('/documents')}
              className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
            >
              Back to Documents
            </button>
            <button 
              onClick={() => setShowDeleteConfirm(true)}
              className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
            >
              Delete File
            </button>
          </div>
        </div>

        {/* Delete Confirmation Modal for Failed State */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
              <div className="flex items-start space-x-4">
                <div className="p-3 bg-red-100 rounded-full">
                  <Trash2 className="h-6 w-6 text-red-600" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-slate-900 mb-2">Delete Document</h3>
                  <p className="text-sm text-slate-600 mb-4">
                    Are you sure you want to delete <span className="font-semibold">{document?.filename}</span>? This action cannot be undone.
                  </p>
                  <div className="flex space-x-3">
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      disabled={deleting}
                      className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center"
                    >
                      {deleting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          Deleting...
                        </>
                      ) : (
                        'Delete'
                      )}
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

  // Mock data not used so I will omit the docData object completely
  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-background">
      {/* Viewer Header */}
      <div className="bg-card border-b border-border p-4 flex items-center justify-between shrink-0">
        <div className="flex items-center space-x-4">
          <button 
            onClick={() => navigate('/documents')}
            className="p-2 hover:bg-muted rounded-full text-muted-foreground transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-lg font-bold text-slate-800">{document.filename}</h1>
            <div className="flex items-center space-x-2 text-xs text-muted-foreground">
              <span className="bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded font-medium uppercase tracking-wider text-[10px]">
                {normalizedStatus}
              </span>
              <span>•</span>
              <span>{document.classification} • {document.language?.toUpperCase() || 'UNKNOWN'} • {document.page_count || 0} pages</span>
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

      {/* Main Content - Split View */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pane: Document Text */}
        <div className="w-1/2 bg-slate-50 border-r border-border p-8 overflow-y-auto">
          <div className="bg-white shadow-sm max-w-2xl mx-auto p-8 text-slate-800 text-sm leading-relaxed border border-slate-200 rounded-lg">
            <p className="whitespace-pre-wrap font-sans" dir="auto">{normalizeContent(document.content)}</p>
          </div>
        </div>

        {/* Right Pane: Intelligence */}
        <div className="w-1/2 bg-card flex flex-col">
          <div className="flex border-b border-border">
            <button 
              onClick={() => setActiveTab('summary')}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'summary' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-slate-800'}`}
            >
              Summary
            </button>
            <button 
              onClick={() => setActiveTab('entities')}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'entities' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-slate-800'}`}
            >
              Entities
            </button>
            <button 
              onClick={() => setActiveTab('ocr')}
              className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === 'ocr' ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-slate-800'}`}
            >
              OCR Text
            </button>
          </div>

          <div className="p-6 flex-1 overflow-y-auto">
            {activeTab === 'summary' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {intelligence?.summary?.content ? (
                  <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                    <div className="flex items-start space-x-3">
                      <Bot className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
                      <div className="flex-1">
                        <h3 className="font-bold text-blue-900 text-sm mb-2">AI Analysis</h3>
                        <pre className="text-sm text-blue-800 leading-relaxed whitespace-pre-wrap font-sans">{intelligence.summary.content}</pre>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500 text-sm">No AI analysis available</div>
                )}

                {intelligence?.summary?.parties && intelligence.summary.parties.length > 0 && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Parties Involved</h3>
                    <div className="space-y-2">
                      {intelligence.summary.parties.map((party: string, i: number) => (
                        <div key={i} className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-sm text-slate-700">
                          {party}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {intelligence?.summary?.key_dates && intelligence.summary.key_dates.length > 0 && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Key Dates</h3>
                    <div className="space-y-2">
                      {intelligence.summary.key_dates.map((date: string, i: number) => (
                        <div key={i} className="p-3 bg-blue-50 rounded-lg border border-blue-200 text-sm text-blue-800 font-medium">
                          {date}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {intelligence?.summary?.missing_documents && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-2 text-amber-500" />
                      Missing Documents
                    </h3>
                    <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-sm text-amber-800">
                      <pre className="whitespace-pre-wrap font-sans">{intelligence.summary.missing_documents}</pre>
                    </div>
                  </div>
                )}

                {/* Document Tags / Smart Collections */}
                {document?.tags && document.tags.length > 0 && (
                  <div className="pt-4 border-t border-border">
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider flex items-center">
                      <FolderGit2 className="h-4 w-4 mr-2 text-indigo-500" />
                      Smart Collections
                    </h3>
                    <div className="flex flex-col gap-2">
                      {document.tags.map((tag: any, i: number) => {
                        let Icon = TagIcon;
                        let theme = 'bg-slate-50 text-slate-700 border-slate-200';
                        
                        if (tag.category === 'project') {
                          Icon = FolderGit2;
                          theme = 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100';
                        } else if (tag.category === 'id_number') {
                          Icon = Hash;
                          theme = 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100';
                        } else if (tag.category === 'organization') {
                          Icon = Building2;
                          theme = 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100';
                        }
                        
                        return (
                          <Link 
                            key={i} 
                            to={`/collections/${tag.id}`}
                            className={`flex items-center justify-between p-2.5 rounded-lg border transition-colors ${theme}`}
                          >
                            <div className="flex items-center">
                              <Icon className="h-4 w-4 mr-2 opacity-75" />
                              <span className="font-medium text-sm">{tag.name}</span>
                            </div>
                            <span className="text-xs font-semibold opacity-60 uppercase tracking-wider">
                              {tag.category ? tag.category.replace('_', ' ') : 'General'}
                            </span>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                )}
                
                {/* Legacy simple strings from intelligence block */}
                {intelligence?.tags && intelligence.tags.length > 0 && (
                  <div className="pt-2">
                    <div className="flex flex-wrap gap-2">
                      {intelligence.tags.map((tag: string, i: number) => (
                        <span key={i} className="px-2 py-1 bg-slate-100 text-slate-600 rounded-md text-xs font-medium border border-slate-200">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'entities' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {intelligence?.metadata?.entities && intelligence.metadata.entities.length > 0 ? (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Entities & Organizations</h3>
                    <div className="space-y-3">
                      {intelligence.metadata.entities.map((entity: any, i: number) => {
                        const isObject = typeof entity === 'object';
                        const name = isObject ? entity.name : entity;
                        const role = isObject ? entity.role : null;
                        const idNumber = isObject ? entity.id_number : null;
                        const contact = isObject ? entity.contact : null;
                        const firm = isObject ? entity.firm : null;
                        const barNumber = isObject ? entity.bar_number : null;
                        
                        return (
                          <div key={i} className="p-4 bg-slate-50 rounded-lg border border-slate-200">
                            <div className="flex items-start gap-3">
                              <span className="h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold bg-indigo-100 text-indigo-700 shrink-0">
                                {name?.[0]?.toUpperCase() || '?'}
                              </span>
                              <div className="flex-1 min-w-0">
                                <p className="font-bold text-slate-900">{name}</p>
                                {role && <p className="text-xs text-slate-600 mt-0.5">{role}</p>}
                                {firm && <p className="text-xs text-slate-600 mt-0.5">Firm: {firm}</p>}
                                {idNumber && (
                                  <p className="text-xs text-indigo-600 mt-1 font-mono bg-indigo-50 px-2 py-1 rounded inline-block">
                                    ID: {idNumber}
                                  </p>
                                )}
                                {barNumber && (
                                  <p className="text-xs text-indigo-600 mt-1 font-mono bg-indigo-50 px-2 py-1 rounded inline-block">
                                    Bar #: {barNumber}
                                  </p>
                                )}
                                {contact && <p className="text-xs text-slate-500 mt-1">{contact}</p>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-500 text-sm">No entities extracted</div>
                )}

                {intelligence?.metadata?.dates && intelligence.metadata.dates.length > 0 && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Important Dates</h3>
                    <div className="space-y-2">
                      {intelligence.metadata.dates.map((dateItem: any, i: number) => {
                        const isObject = typeof dateItem === 'object';
                        const date = isObject ? dateItem.date : dateItem;
                        const description = isObject ? dateItem.description : null;
                        const type = isObject ? dateItem.type : null;
                        
                        return (
                          <div key={i} className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                            <p className="text-sm font-bold text-blue-900">{date}</p>
                            {description && <p className="text-xs text-blue-700 mt-1">{description}</p>}
                            {type && <span className="text-xs text-blue-600 bg-blue-100 px-2 py-0.5 rounded mt-1 inline-block">{type}</span>}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {intelligence?.metadata?.amounts && intelligence.metadata.amounts.length > 0 && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Financial Amounts</h3>
                    <div className="space-y-3">
                      {intelligence.metadata.amounts.map((amountItem: any, i: number) => {
                        const isObject = typeof amountItem === 'object';
                        const amount = isObject ? amountItem.amount : amountItem;
                        const currency = isObject ? amountItem.currency : null;
                        const description = isObject ? amountItem.description : null;
                        const payer = isObject ? amountItem.payer : null;
                        const payee = isObject ? amountItem.payee : null;
                        
                        return (
                          <div key={i} className="p-4 bg-green-50 rounded-lg border border-green-200">
                            <div className="flex items-baseline gap-2">
                              <p className="text-2xl font-bold text-green-900">{amount}</p>
                              {currency && <span className="text-sm text-green-700">{currency}</span>}
                            </div>
                            {description && (
                              <p className="text-sm text-green-800 mt-2 font-medium">{description}</p>
                            )}
                            {(payer || payee) && (
                              <div className="mt-2 text-xs text-green-700 space-y-0.5">
                                {payer && <p>From: {payer}</p>}
                                {payee && <p>To: {payee}</p>}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {intelligence?.metadata?.case_numbers && intelligence.metadata.case_numbers.length > 0 && (
                  <div>
                    <h3 className="font-bold text-slate-800 mb-3 text-sm uppercase tracking-wider">Case Numbers</h3>
                    <div className="space-y-2">
                      {intelligence.metadata.case_numbers.map((caseNum: string, i: number) => (
                        <div key={i} className="p-3 bg-purple-50 rounded-lg border border-purple-200 text-sm font-mono text-purple-900">
                          {caseNum}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'ocr' && (
              <div dir="auto" className="prose prose-sm max-w-none text-slate-600 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs whitespace-pre-wrap animate-in fade-in slide-in-from-bottom-2 duration-300 font-sans">
              {normalizeContent(document.content)}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
            <div className="flex items-start space-x-4">
              <div className="p-3 bg-red-100 rounded-full">
                <Trash2 className="h-6 w-6 text-red-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-slate-900 mb-2">Delete Document</h3>
                <p className="text-sm text-slate-600 mb-4">
                  Are you sure you want to delete <span className="font-semibold">{document?.filename}</span>? This action cannot be undone.
                </p>
                <div className="flex space-x-3">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleting}
                    className="flex-1 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center"
                  >
                    {deleting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Deleting...
                      </>
                    ) : (
                      'Delete'
                    )}
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
