import React, { useState, useEffect } from 'react';
import { Search, Filter, FileText, MoreVertical, Tag, Calendar, Trash2, Download, Share2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

interface Document {
  id: number;
  filename: string;
  case_id: number;
  classification: string;
  created_at: string;
  s3_url: string;
  processing_status?: string | null;
  content?: string;
}

export function DocumentList() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [semanticSearchActive, setSemanticSearchActive] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [openDropdownId, setOpenDropdownId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => setOpenDropdownId(null);
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  useEffect(() => {
    fetchDocuments();

    // Listen for WebSocket events indicating a background task finished
    const handleDocumentProcessed = () => {
      fetchDocuments();
    };

    window.addEventListener('document_processed', handleDocumentProcessed);
    
    return () => {
      window.removeEventListener('document_processed', handleDocumentProcessed);
    };
  }, []);

  const fetchDocuments = async (query?: string) => {
    try {
      if (query && query.trim().length > 2) {
        setIsSearching(true);
        // Dispatch to semantic search endpoint
        const response = await api.get('/v1/documents/semantic-search', {
            params: { query: query.trim() }
        });
        setDocuments(response.data);
      } else {
        // Normal fetch
        const response = await api.get('/v1/documents/');
        setDocuments(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  };

  // Debounced Semantic Search Hook
  useEffect(() => {
    const timer = setTimeout(() => {
        if (semanticSearchActive) {
            fetchDocuments(searchTerm);
        }
    }, 700);
    return () => clearTimeout(timer);
  }, [searchTerm, semanticSearchActive]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', files[0]);

    try {
      await api.post('/v1/documents/?case_id=0', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      fetchDocuments();
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (docId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setOpenDropdownId(null);
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    
    setDeletingId(docId);
    try {
      await api.delete(`/v1/documents/${docId}`);
      // Refresh the list after successful deletion
      fetchDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert('Failed to delete document');
      setDeletingId(null);
    }
  };

  const filteredDocs = React.useMemo(() => {
    if (semanticSearchActive) return documents; // When semantic search is on, the backend does the filtering
    
    return documents.filter(doc => {
      const term = searchTerm.toLowerCase();
      const matchFilename = doc.filename.toLowerCase().includes(term);
      const matchContent = doc.content?.toLowerCase().includes(term) ?? false;
      const matchClassification = doc.classification?.toLowerCase().includes(term) ?? false;
      return matchFilename || matchContent || matchClassification;
    });
  }, [documents, searchTerm, semanticSearchActive]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'Unknown';
    return new Date(dateStr).toISOString().split('T')[0];
  };

  const getNormalizedStatus = (status: string | undefined | null) => {
    if (!status) return 'completed'; // Legacy documents default to completed
    return status.toLowerCase();
  };

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className={`absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 ${isSearching ? 'text-blue-500 animate-pulse' : 'text-muted-foreground'}`} />
          <input 
            type="text" 
            placeholder={semanticSearchActive ? "Semantic Search (Ask a legal question...)" : "Search documents purely by text..."}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-muted/50 border border-transparent focus:bg-background focus:border-primary rounded-lg text-sm outline-none transition-all duration-200"
          />
        </div>
        <div className="flex items-center space-x-2">
          <button 
             onClick={() => {
                setSemanticSearchActive(!semanticSearchActive);
                if (semanticSearchActive && searchTerm.length > 0) {
                   // If turning off semantic search, refetch the standard full list
                   fetchDocuments();
                }
             }}
             className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${semanticSearchActive ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' : 'bg-muted text-muted-foreground hover:bg-muted/80'}`}>
            <span className="relative flex h-3 w-3 mr-1">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${semanticSearchActive ? 'bg-blue-400' : 'hidden'}`}></span>
              <span className={`relative inline-flex rounded-full h-3 w-3 ${semanticSearchActive ? 'bg-blue-500' : 'bg-slate-400'}`}></span>
            </span>
            <span>AI Search</span>
          </button>
          <button className="flex items-center space-x-2 px-3 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 text-sm font-medium transition-colors">
            <Filter className="h-4 w-4" />
            <span>Filter</span>
          </button>
          <label className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors shadow-sm cursor-pointer">
            {uploading ? 'Uploading...' : 'Upload'}
            <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
          </label>
        </div>
      </div>

      <div className="mx-4 mt-4 p-8 border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50 flex flex-col items-center justify-center text-center hover:bg-slate-50 hover:border-primary/50 transition-all cursor-pointer group">
        <div className="p-4 bg-white rounded-full shadow-sm mb-3 group-hover:scale-110 transition-transform">
           <FileText className="h-6 w-6 text-primary" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">Drop files here to upload</h3>
        <p className="text-xs text-slate-500 mt-1">Support for PDF, DOCX, JPG (Max 20MB)</p>
      </div>

      <div className="overflow-x-auto flex-1 mt-4">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Loading documents...</div>
        ) : (
        <table className="w-full text-sm text-left">
          <thead className="bg-muted/50 text-muted-foreground font-medium border-b border-border">
            <tr>
              <th className="px-6 py-3">Document Name</th>
              <th className="px-6 py-3">Case</th>
              <th className="px-6 py-3">Tags</th>
              <th className="px-6 py-3">Date</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filteredDocs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                  No documents found
                </td>
              </tr>
            ) : (
              filteredDocs.map((doc) => (
              <tr 
                key={doc.id} 
                className={`transition-colors ${getNormalizedStatus(doc.processing_status) === 'completed' ? 'hover:bg-muted/30 cursor-pointer' : 'opacity-75 cursor-not-allowed bg-slate-50'}`}
                onClick={() => getNormalizedStatus(doc.processing_status) === 'completed' && navigate(`/documents/${doc.id}`)}
              >
                <td className="px-6 py-4">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-slate-100 rounded text-slate-500">
                      <FileText className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-slate-700">{doc.filename}</span>
                  </div>
                </td>
                <td className="px-6 py-4 text-slate-600">Case #{doc.case_id}</td>
                <td className="px-6 py-4">
                  <div className="flex gap-1 flex-wrap">
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                      <Tag className="h-3 w-3 mr-1 opacity-50" />
                      {doc.classification || 'Unclassified'}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-slate-500">
                  <div className="flex items-center">
                    <Calendar className="h-3 w-3 mr-1.5 opacity-70" />
                    {formatDate(doc.created_at)}
                  </div>
                </td>
                <td className="px-6 py-4">
                  {(getNormalizedStatus(doc.processing_status) === 'processing' || getNormalizedStatus(doc.processing_status) === 'pending') ? (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                      <svg className="animate-spin -ml-1 mr-2 h-3 w-3 text-amber-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Analyzing...
                    </span>
                  ) : getNormalizedStatus(doc.processing_status) === 'failed' ? (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                      Failed
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
                      Processed
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-right relative">
                  <button 
                    className="p-1 hover:bg-slate-200 rounded text-slate-400 hover:text-slate-600 transition-colors disabled:opacity-50" 
                    disabled={getNormalizedStatus(doc.processing_status) !== 'completed'}
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenDropdownId(openDropdownId === doc.id ? null : doc.id);
                    }}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </button>

                  {/* Dropdown Menu */}
                  {openDropdownId === doc.id && getNormalizedStatus(doc.processing_status) === 'completed' && (
                    <div 
                      className="absolute right-8 top-10 w-48 bg-white border border-slate-200 rounded-lg shadow-xl z-50 overflow-hidden"
                      onClick={(e) => e.stopPropagation()} // Keep click from navigating to document viewer
                    >
                      <div className="py-1">
                        <button 
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                          onClick={() => navigate(`/documents/${doc.id}`)}
                        >
                          <FileText className="h-4 w-4 text-slate-400" />
                          View Document
                        </button>
                        <button 
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                          onClick={() => {
                            setOpenDropdownId(null);
                            alert("Download functionality not yet implemented in backend.");
                          }}
                        >
                          <Download className="h-4 w-4 text-slate-400" />
                          Download
                        </button>
                        <button 
                          className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                          onClick={() => {
                            setOpenDropdownId(null);
                            alert("Share functionality not yet implemented.");
                          }}
                        >
                          <Share2 className="h-4 w-4 text-slate-400" />
                          Share
                        </button>
                        <hr className="my-1 border-slate-100" />
                        <button 
                          className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 disabled:opacity-50"
                          onClick={(e) => handleDeleteDocument(doc.id, e)}
                          disabled={deletingId === doc.id}
                        >
                          <Trash2 className="h-4 w-4" />
                          {deletingId === doc.id ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            ))
            )}
          </tbody>
        </table>
        )}
      </div>
    </div>
  );
}
