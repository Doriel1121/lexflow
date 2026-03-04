import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Upload, FileText, Calendar, User, Plus, Loader2, X } from 'lucide-react';
import api from '../services/api';
import { Case } from '../types';

const CaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [addingNote, setAddingNote] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetchCase();
  }, [id]);

  const fetchCase = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/v1/cases/${id}`);
      setCaseData(response.data);
      setError(null);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to load case');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !id) return;
    
    setUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post(`/v1/documents/?case_id=${id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      
      e.target.value = ''; // Reset input
      await fetchCase();
    } catch (error: any) {
      console.error('Upload error:', error);
      setError(error.response?.data?.detail || error.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  // Removed unused OCR, Summarize, and Modal viewing functions as they 
  // are fully handled by the rich DocumentViewer route (/documents/:id)

  const handleAddNote = async () => {
    if (!noteContent.trim() || !id) return;
    setAddingNote(true);
    try {
      await api.post(`/v1/cases/${id}/notes`, { content: noteContent });
      setNoteContent('');
      setShowNoteModal(false);
      fetchCase();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add note');
    } finally {
      setAddingNote(false);
    }
  };

  const getStatusColor = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'OPEN') return 'bg-green-100 text-green-700 border-green-200';
    if (s === 'PENDING') return 'bg-amber-100 text-amber-700 border-amber-200';
    if (s === 'CLOSED') return 'bg-slate-100 text-slate-600 border-slate-200';
    return 'bg-slate-100 text-slate-600 border-slate-200';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-slate-400">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span>Loading case details...</span>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-3 text-destructive text-sm max-w-md">
          <span>{error || 'Case not found'}</span>
        </div>
        <button
          onClick={() => navigate('/cases')}
          className="px-4 py-2 border border-slate-200 rounded-lg text-sm hover:bg-slate-50 transition-colors"
        >
          Back to Cases
        </button>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/cases')}
          className="flex items-center gap-2 text-slate-600 hover:text-slate-900 mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="text-sm font-medium">Back to Cases</span>
        </button>
        
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-3xl font-serif font-bold text-slate-800">{caseData.title}</h1>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(caseData.status)}`}>
                  {caseData.status.toUpperCase()}
                </span>
              </div>
              <p className="text-slate-500 text-sm">{caseData.description || 'No description provided'}</p>
            </div>
          </div>
          
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
            <div className="flex items-center gap-2 text-sm">
              <Calendar className="h-4 w-4 text-slate-400" />
              <div>
                <p className="text-slate-500 text-xs">Created</p>
                <p className="font-medium text-slate-700">{new Date(caseData.created_at).toLocaleDateString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <User className="h-4 w-4 text-slate-400" />
              <div>
                <p className="text-slate-500 text-xs">Client</p>
                <p className="font-medium text-slate-700">{caseData.client_id ? `Client #${caseData.client_id}` : 'Not assigned'}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4 text-slate-400" />
              <div>
                <p className="text-slate-500 text-xs">Documents</p>
                <p className="font-medium text-slate-700">{caseData.documents?.length || 0} files</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
        {/* Documents Section - 2 columns */}
        <div className="lg:col-span-2 bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-slate-800">Documents</h2>
            <label className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors cursor-pointer">
              <Upload className="h-4 w-4" />
              <span>{uploading ? 'Uploading...' : 'Upload'}</span>
              <input
                type="file"
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.doc,.docx,image/*"
                disabled={uploading}
              />
            </label>
          </div>

          {uploading && (
            <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
              <span className="text-sm text-blue-700">Processing document with AI...</span>
            </div>
          )}

          {caseData.documents && caseData.documents.length > 0 ? (
            <div className="space-y-3">
              {caseData.documents.map((doc) => (
                <div key={doc.id} className="p-4 bg-slate-50 border border-slate-200 rounded-xl hover:border-primary/30 transition-all">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <FileText className="h-5 w-5 text-primary" />
                      </div>
                      <div className="flex-1">
                        <p className="font-semibold text-slate-800">{doc.filename}</p>
                        <p className="text-xs text-slate-500 mt-1">
                          {doc.classification || 'Unclassified'} • {doc.language || 'Unknown'} • {doc.page_count || 0} pages
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigate(`/documents/${doc.id}`)}
                        className="px-3 py-1.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 text-xs font-medium transition-colors flex items-center gap-1.5"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        Open Viewer
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="p-4 bg-slate-100 rounded-full mb-4">
                <FileText className="h-8 w-8 text-slate-400" />
              </div>
              <p className="font-semibold text-slate-700">No documents yet</p>
              <p className="text-sm text-slate-500 mt-1">Upload documents to get started</p>
            </div>
          )}
        </div>

        {/* Notes Section - 1 column */}
        <div className="bg-card border border-border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-slate-800">Notes</h2>
            <button
              onClick={() => setShowNoteModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </div>

          {caseData.notes && caseData.notes.length > 0 ? (
            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {caseData.notes.map((note) => (
                <div key={note.id} className="p-3 bg-slate-50 border-l-4 border-primary rounded-r-lg">
                  <p className="text-sm text-slate-700">{note.content}</p>
                  <p className="text-xs text-slate-400 mt-2">
                    {new Date(note.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-sm text-slate-500">No notes yet</p>
              <button
                onClick={() => setShowNoteModal(true)}
                className="mt-3 text-sm text-primary hover:underline"
              >
                Add your first note
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Add Note Modal */}
      {showNoteModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-slate-800">Add Note</h2>
              <button onClick={() => setShowNoteModal(false)} className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors">
                <X className="h-5 w-5 text-slate-400" />
              </button>
            </div>
            <textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm resize-none"
              rows={4}
              placeholder="Enter your note here..."
              autoFocus
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowNoteModal(false)}
                className="flex-1 px-4 py-2.5 border border-slate-200 rounded-xl text-sm font-medium hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAddNote}
                disabled={!noteContent.trim() || addingNote}
                className="flex-1 px-4 py-2.5 bg-primary text-primary-foreground rounded-xl text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {addingNote ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {addingNote ? 'Adding...' : 'Add Note'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default CaseDetailPage;
